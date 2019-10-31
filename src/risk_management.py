#!/usr/bin/env python
# -*- coding: utf-8 -*-
from empyrical import *

class RiskManagement:

    def __init__(self, dataframe):

        self.dataframe = dataframe

    def get_max_drawdown(self, data):
        if data is None or len(data.keys()) < 1:
            raise RMDataframeException

        result = max_drawdown(data)
        return result if result is not None else None

    def risk_management(self):
        raise NotImplementedError


class RiskManagementException(Exception):
    pass

class RMDataframeException(RiskManagementException):
    pass
