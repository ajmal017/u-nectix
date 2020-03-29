#!/usr/bin/env python
# -*- coding: utf-8 -*-
from src.asset_selector import AssetSelector, AssetValidationException
from src.broker import BrokerException
from util import time_from_datetime
from algos import BaseAlgo
from datetime import datetime, timedelta
from pytz import timezone
import time


class Algorithm(AssetSelector, BaseAlgo):

    def __init__(self, broker, cli_args):
        super().__init__(broker=broker, cli_args=cli_args, edgar_token=None)

    def bullish_overnight_momentum(self):
        """
        Given a list of assets, evaluate which ones are bullish and return a sample of each.

        These method names should correspond with files in the algos/ directory.
        """
        if not self.poolsize or self.poolsize is None or self.poolsize is 0:
            raise AssetValidationException("[!] Invalid pool size.")

        self.portfolio = []

        for ass in self.tradeable_assets:
            """ The extraneous stuff that currently happens before the main part of evaluate_candlestick """
            limit = 1000
            df = self.broker.get_barset_df(ass.symbol, self.period, limit=limit)

            # guard clauses to make sure we have enough data to work with
            if df is None or len(df) != limit:
                continue

            # throw it away if the price is out of our min-max range
            close = df["close"].iloc[-1]
            if close > self.max_stock_price or close < self.min_stock_price:
                continue

            # throw it away if the candlestick pattern is not bullish
            pattern = self.candle_pattern_direction(df)
            if pattern in ["bear", None]:
                continue

            # assume the current symbol pattern is bullish and add to the portfolio
            self.portfolio.append(ass.symbol)
            if len(self.portfolio) >= self.poolsize:
                # exit the filter process
                break

    def portfolio_allocation(self, data, total_risk):
        """Calculate portfolio allocation size given a ratings dataframe and a cash amount.

        :param data:
        :param total_risk:
        :return:
        """
        total_rating = data["rating"].sum()
        shares = {}
        risk_amt = total_risk
        for _, row in data.iterrows():
            numshares = int(float(row["rating"]) / float(total_rating) * float(risk_amt) / float(row["price"]))
            if numshares > 10:
                multiplier = int(numshares / 10)
                numshares = multiplier * 10
            shares[row["symbol"]] = numshares

            risk_amt -= numshares * row["price"]
        # debug
        # for k, v in shares.items():
        #     print("[*] Ticker: {}, Shares: {}".format(k, v))
        return shares

    def total_asset_value(self, positions, date):
        """ does what it says

        TODO: Move this to Broker

        :param positions:
        :param date:
        :return:
        """
        if len(positions.keys()) == 0:
            return positions, 0,

        total_value = 0
        formatted_date = time_from_datetime(date)

        barset = self.broker.api.get_barset(symbols=positions.keys(), timeframe='day', limit=2, end=formatted_date)
        for symbol in positions:
            close = barset[symbol][0].c
            open = barset[symbol][-1].o
            change = float(open - close)
            positions[symbol] = {"shares": positions[symbol], "value": positions[symbol] * open, "change": change}
            total_value += positions[symbol]["value"]
        return positions, total_value,


def run(broker, args):

    if not broker or broker is None:
        raise BrokerException("[!] A broker instance is required.")
    else:
        broker = broker

    if args.algorithm is None:
        args.algorithm = "bullish_overnight_momentum"
    if args.testperiods is None:
        args.testperiods = 30

    if args.cash is not None and type(args.cash) == float:
        cash = args.cash
    else:
        cash = float(broker.cash)

    if args.risk_pct is not None and type(args.risk_pct) in [int, float]:
        risk_pct = args.risk_pct
    else:
        risk_pct = .10

    # initial trade state
    starting_amount = cash
    risk_amount = broker.calculate_tolerable_risk(cash, risk_pct)
    algorithm = Algorithm(broker, args)

    symbols = algorithm.portfolio
    print("[*] Trading assets: {}".format(",".join(symbols)))

    if args.backtest:
        # TODO: Make all time usages consistent
        now = datetime.now(timezone("EST"))
        beginning = now - timedelta(days=args.testperiods)
        calendars = broker.get_calendar(start_date=beginning.strftime("%Y-%m-%d"), end_date=now.strftime("%Y-%m-%d"))
        portfolio = {}
        cal_index = 0

        for calendar in calendars:
            # see how much we got back by holding the last day's picks overnight
            positions, asset_value = algorithm.total_asset_value(portfolio, calendar.date)
            cash += asset_value
            print("[*] Cash account value on {}: ${}".format(calendar.date.strftime("%Y-%m-%d"), round(cash, 2)),
                "Risk amount: ${}".format(round(risk_amount, 2)))

            if cash <= 0:
                print("[!] Account has gone to $0.")
                break

            if cal_index == len(calendars) - 1:
                print("[*] End of the backtesting window.")
                print("[*] Starting account value: {}".format(starting_amount))
                print("[*] Holdings: ")
                for k, v in portfolio.items():
                    print(" - Symbol: {}, Shares: {}, Value: {}".format(k, v["shares"], v["value"]))
                print("[*] Account value: {}".format(round(cash, 2)))
                print("[*] Change from starting value: ${}". format(round(float(cash) - float(starting_amount), 2)))
                break

            # calculate position size based on volume/momentum rating
            ratings = algorithm.calculate_volume_ratings(symbols, timezone("EST").localize(calendar.date), window_size=10)
            portfolio = algorithm.portfolio_allocation(ratings, risk_amount)

            for _, row in ratings.iterrows():
                shares_to_buy = int(portfolio[row["symbol"]])
                cost = (row["price"] + .01) * shares_to_buy     # Try to be a maker
                cash -= cost

                # calculate the amount we want to risk on the next trade
                risk_amount = broker.calculate_tolerable_risk(cash, risk_pct)
            cal_index += 1
    else:
        cash = float(broker.cash)
        starting_amount = cash
        cycle = 0
        bought_today = False
        sold_today = False
        try:
            orders = broker.get_orders(after=time_from_datetime(datetime.today() - timedelta(days=1)), limit=400, status="all")
        except BrokerException:
            # We don't have any orders, so we've obviously not done anything today.
            pass
        else:
            for order in orders:
                if order.side == "buy":
                    bought_today = True
                    # This handles an edge case where the script is restarted right before the market closes.
                    sold_today = True
                    break
                else:
                    sold_today = True

        while True:
            # wait until the market's open to do anything.
            clock = broker.get_clock()
            if clock.is_open and not bought_today:
                if sold_today:
                    time_until_close = clock.next_close - clock.timestamp
                    if time_until_close.seconds <= 120:
                        print("[+] Buying position(s).")
                        cash = float(broker.api.get_account().cash)
                        ratings = algorithm.get_ratings(window_size=10)
                        portfolio = algorithm.portfolio_allocation(ratings, risk_amount)
                        for symbol in portfolio:
                            broker.api.submit_order(symbol=symbol, qty=portfolio[symbol], side="buy", type="market",
                                time_in_force="day")
                        print("[*] Position(s) bought.")
                        bought_today = True
                else:
                    # sell our old positions before buying new ones.
                    time_after_open = clock.next_open - clock.timestamp
                    if time_after_open.seconds >= 60:
                        print("[-] Liquidating positions.")
                        broker.api.close_all_positions()
                    sold_today = True
            else:
                bought_today = False
                sold_today = False
                if cycle % 10 == 0:
                    print("[*] Waiting for next market day...")
                    print("[-] Cash: {}".format(cash))
            time.sleep(30)
            cycle += 1