#!/usr/bin/env python
# -*- coding: utf-8 -*-
# from algos import bullish_overnight_hold, bullish_overnight_crypto_hold, bullish_overnight_forex_hold
from src.broker import Broker, BrokerException, BrokerValidationException
from src.krak_dealer import KrakDealer
from src.forex_broker import ForexBroker
from util import parse_configs, parse_args
from pykrakenapi.pykrakenapi import KrakenAPI, KrakenAPIError
from alpaca_trade_api.rest import REST, APIError
from oandapy import API, OandaError
import krakenex
import os

from importlib import import_module


def main(config, args):

    if args.forex:
        print("[-] do stuff with Oanda.")
        try:
            oanda = API()
        except OandaError as error:
            raise error

        try:
            broker = ForexBroker(oanda)
        except BrokerException as error:
            raise error

        # how much money can we use to open new positions?
        # print("[?] ${} is available in cash.".format(broker.trade_balance["tb"]))

        """Run the algorithm."""
        if args.mode is None:
            args.mode = 'long'
        if args.period is None:
            args.period = "1D"
        if args.testperiods is None:
            args.testperiods = 30

        # bullish_overnight_forex_hold.run(broker, args)

    # are we trading crypto?
    if args.crypto:
        print("[-] do stuff with Kraken.")
        try:
            api = krakenex.API()
            kraken = KrakenAPI(api)
        except KrakenAPIError as error:
            raise error

        try:
            broker = KrakDealer(kraken)
        except BrokerException as error:
            raise error
        else:
            # is our account restricted from trading?
            if broker.trading_blocked:
                raise BrokerException("[!] Insufficient balances across coins or account is currently restricted from trading.")

        # how much money can we use to open new positions?
        print("[?] ${} is available in cash.".format(broker.trade_balance["tb"]))

        """Run the algorithm."""
        if args.pair is None:
            args.pair = "XBTUSD"
        if args.mode is None:
            args.mode = 'long'
        if args.period is None:
            args.period = "1D"
        if args.algorithm is None:
            args.algorithm = "bullish_overnight_crypto_hold"
        if args.testperiods is None:
            args.testperiods = 30

        # bullish_overnight_crypto_hold.run(broker, args)

    else:
        # we must be trading stocks
        try:
            alpaca = REST(base_url=config["alpaca"]["APCA_API_BASE_URL"], key_id=config["alpaca"]["APCA_API_KEY_ID"],
                secret_key=config["alpaca"]["APCA_API_SECRET_KEY"], api_version=config["alpaca"]["VERSION"])
        except APIError as error:
            raise error

        try:
            broker = Broker(alpaca)
        except (BrokerException, BrokerValidationException, Exception) as error:
            raise error
        else:
            # is our account restricted from trading?
            if broker.trading_blocked:
                raise BrokerException("[!] Account is currently restricted from trading.")

        # how much money can we use to open new positions?
        print("[?] ${} is available in cash.".format(broker.cash))

        """Run the algorithm."""
        if args.mode is None:
            args.mode = 'long'
        if args.period is None:
            args.period = "1D"
        if args.algorithm is None:
            args.algorithm = "bullish_overnight_hold"
        if args.testperiods is None:
            args.testperiods = 30
        if args.max is None:
            args.max = 26
        if args.min is None:
            args.min = 6

        # algo_name = args.selection_method
        # algo_file = os.path.join("algos", f"{args.algorithm}.py")
        # if not os.path.exists(algo_file):
        #     raise FileExistsError
        # if not os.path.isfile(algo_file):
        #     raise FileNotFoundError
        #
        # bullish_overnight_hold.run(broker, args)

    trade(broker, args)


def trade(broker, args):
    try:
        algorithm = import_module("algos", package=args.algorithm)
    except ImportError as error:
        raise error
    else:

        # algo_file = os.path.join("algos", f"{args.algorithm}.py")
        # if not os.path.exists(algo_file):
        #     raise FileExistsError
        # if not os.path.isfile(algo_file):
        #     raise FileNotFoundError

        algorithm.run(broker, args)


if __name__ == "__main__":
    configuration = parse_configs()
    arguments = parse_args()
    main(configuration, arguments)
