#!/usr/bin/env python
# -*- coding: utf-8 -*-
from src.asset_selector import AssetSelector
from src.indicators import Indicators
from src.edgar_interface import EdgarInterface
from src.twitter_interface import TwitterInterface
from src.sentiment_analysis import SentimentAnalysis as Sent
from src.predictor import Predictor
from util import submit_buy_order


def run(alpaca_api, twitter_api, edgar_token):

    # initial trade state
    trading         = False
    trading_symbol  = None
    assets          = AssetSelector(alpaca_api, edgar_token=edgar_token).get_assets_with_8k_filings()
    indicators      = Indicators(alpaca_api, assets).get_indicators()
    edgar           = EdgarInterface(edgar_token, indicators).get_edgar_signals()

    # TODO: SEC form sentiment analysis
    # tweets          = TwitterInterface(twitter_api, indicators).get_ticker_tweets()
    # sentiments      = Sent(indicators, tweets).get_sentiments()
    # predictions     = Predictor(indicators).get_securities_predictions()

    # trade decision here
    for e in edgar.keys():

        instrument = indicators[e]
        # check the most recent moving average convergence-divergence
        # has the MACD crossed over its signal and is the MACD percentage change is positive?
        if instrument["macd"].iloc[-1] > instrument["signal"].iloc[-1] and instrument["macd_ptc"].iloc[-1] > 0:
            # if the MACD checks out, check the directional movement indicator
            # has the DMI positive value crossed over the negative value?
            if instrument["DMp"].iloc[-1] > instrument["DMm"].iloc[-1]:
                # if the DMI checks out, what is the EDGAR signal?
                if e["signal"] in ["BULL", "STRONGBULL"]:
                    trading = True
                    trading_symbol = str(e)
            else:
                # if DMI has not crossed over, check for a stronger EDGAR signal
                if e["signal"] is "STRONGBULL":
                    trading = True
                    trading_symbol = str(e)

        if trading_symbol is not None:
            break

    if trading is True:
        # decide how much to buy # TODO

        # then submit
        submit_buy_order(trading_symbol, "buy", "market", "ioc")
