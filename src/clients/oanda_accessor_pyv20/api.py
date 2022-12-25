import os
from typing import Any, Dict, List, Optional, Tuple, Union

# For trading
from oandapyV20 import API
from oandapyV20.endpoints.apirequest import APIRequest
import oandapyV20.endpoints.instruments as module_inst
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.pricing as pricing
import oandapyV20.endpoints.trades as trades
import oandapyV20.endpoints.transactions as transactions

import src.clients.oanda_accessor_pyv20.preprocessor as prepro

from .definitions import ISO_DATETIME_STR

# from aws_lambda_powertools import Logger


# LOGGER = Logger()


# granularity list
# http://developer.oanda.com/rest-live-v20/instrument-df/#CandlestickGranularity
class OandaClient:
    REQUESTABLE_COUNT = 5000

    def __init__(
        self,
        instrument: str,
        environment: str = "practice",
        test: bool = False,
        account_id: Optional[str] = None,
        access_token: Optional[str] = None,
    ):
        """

        Args:
            instrument (str): The pare of currencies you want to treat.
                Example: "USD_JPY"
            environment (str, optional): Account type of Oanda.
                Example: "live"
                Defaults to None.
            test (bool, optional): Whether you want make order really.
                If you set True, then your order is going to be ignored.
                Defaults to False.
        """
        if environment is None:
            environment = os.environ.get("OANDA_ENVIRONMENT")
        if environment not in ["live", "practice"]:
            raise ValueError(f"The args environment is invalid. : {environment}")

        auth_variables: Dict[str, str] = self.__validate_auth_variables(account_id, access_token)

        self.__api_client = API(
            access_token=auth_variables["access_token"],
            environment=environment,
        )
        self.__oanda_account_id: str = auth_variables["account_id"]
        self.__accessable: bool = True
        self.__instrument: str = instrument
        self.__units: str = os.environ.get("UNITS") or "1"
        self.__test: bool = test

    def __validate_auth_variables(
        self,
        account_id: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> Dict[str, str]:
        account_id = account_id or os.environ.get("OANDA_ACCOUNT_ID")
        access_token = access_token or os.environ.get("OANDA_ACCESS_TOKEN")

        blank_variables: List[str] = []
        if account_id and access_token:
            return {"account_id": account_id, "access_token": access_token}
        if account_id is None:
            blank_variables.append("account_id")
        if access_token is None:
            blank_variables.append("access_token")

        raise ValueError(
            f"The following variables are blank: {blank_variables}. "
            "You have to set them by environment variables or passing arguments."
        )

    @property
    def accessable(self) -> bool:
        return self.__accessable

    def __stop_request(self) -> None:
        self.__accessable = False

    #
    # Public
    #
    # INFO: request-something (excluding candles)
    def request_is_tradeable(self) -> Dict[str, Union[str, bool]]:
        params = {"instruments": self.__instrument}  # 'USD_JPY,EUR_USD,EUR_JPY'
        request_obj: APIRequest = pricing.PricingInfo(
            accountID=self.__oanda_account_id, params=params
        )
        response = self.__api_client.request(request_obj)
        tradeable = response["prices"][0]["tradeable"]
        return {"instrument": self.__instrument, "tradeable": tradeable}

    def request_open_trades(self) -> Dict[str, Union[List[dict], str]]:
        """
        request open position on the OANDA platform
        """
        request_obj: APIRequest = trades.OpenTrades(accountID=self.__oanda_account_id)
        response = self.__api_client.request(request_obj)
        # LOGGER.info({"[Client] OpenTrades": response})

        open_trades = response["trades"]

        extracted_trades: List[dict] = [
            trade
            for trade in open_trades
            if (
                # 'clientExtensions' not in trade.keys() and
                trade["instrument"]
                == self.__instrument
            )
        ]

        print("[Client] There is open position: {}".format(extracted_trades != []))
        return {
            "positions": extracted_trades,
            "last_transaction_id": response["lastTransactionID"],
            "response": response,
        }

    def request_market_ordering(
        self,
        posi_nega_sign: str = "",
        stoploss_price: Optional[float] = None,
        units: int = None,
    ) -> Dict[str, Any]:
        """market order"""
        if stoploss_price is None:
            return {
                "error": "[Client] It is restricted to execute market order without StopLoss order."
            }

        data = {
            "order": {
                "stopLossOnFill": {
                    "timeInForce": "GTC",
                    # TODO: consider currrency pairs whose digits are too small
                    "price": str(stoploss_price)[:7],
                },
                "instrument": self.__instrument,
                "units": "{sign}{units}".format(sign=posi_nega_sign, units=(units or self.__units)),
                "type": "MARKET",
                "positionFill": "DEFAULT",
            }
        }

        if self.__test:
            print("[Test] market_order: {}".format(data))
            return data

        request_obj: APIRequest = orders.OrderCreate(accountID=self.__oanda_account_id, data=data)
        response: Dict[str, Any] = self.__api_client.request(request_obj)
        # LOGGER.info({"[Client] market-order": response})

        order_transaction: Dict[str, Any] = response["orderCreateTransaction"]
        if order_transaction == {}:
            return {"messsage": "Market order is failed.", "result": response}

        response_for_display = {
            "instrument": order_transaction.get("instrument"),
            # 'price': order_transaction.get('price'),  # There isn't 'price' in result of market order
            "units": order_transaction.get("units"),
            "time": order_transaction.get("time"),
            "stopLossOnFill": order_transaction.get("stopLossOnFill"),
        }

        return {
            "messsage": "Market order is done !",
            "order": response_for_display,
            "response": response,
        }

    def request_closing(self, trade_id: str, reason: str = "") -> Dict[str, Any]:
        """close position"""
        if self.__test:
            print("[Test] close_order")
            return {}

        # data = {'units': self.__units}
        request_obj: APIRequest = trades.TradeClose(
            accountID=self.__oanda_account_id,
            tradeID=trade_id,  # , data=data
        )
        response: Dict[str, Any] = self.__api_client.request(request_obj)
        # LOGGER.info({"[Client] TradeClose": response})
        if (
            response.get("orderFillTransaction") is None
            and response.get("orderCancelTransaction") is not None
        ):
            reason = response.get("orderCancelTransaction").get("reason")  # type: ignore
            # LOGGER.warn({"message": "The exit order was canceled because of {}".format(reason)})
            return {
                "message": "[Client] Close order is canceled",
                "reason": reason,
                "response": response,
            }

        return {
            "message": "[Client] Position is closed",
            "reason": reason,
            "response": response,
        }

    def request_trailing_stoploss(self, trade_id: str, stoploss_price: float) -> Dict[str, Any]:
        """change stoploss price toward the direction helping us get revenue"""
        if (trade_id is None) or (trade_id == ""):
            return {"error": "[Client] There is no position"}

        data = {
            # 'takeProfit': {'timeInForce': 'GTC', 'price': '1.3'},
            "stopLoss": {"timeInForce": "GTC", "price": str(stoploss_price)[:7]}
        }

        request_obj: APIRequest = trades.TradeCRCDO(
            accountID=self.__oanda_account_id,
            tradeID=trade_id,
            data=data,
        )
        response: Dict[str, Any] = self.__api_client.request(request_obj)
        # LOGGER.info({"[Client] trail": response})
        return response

    def request_transactions_once(self, from_id: str, to_id: str) -> Dict[str, Any]:
        params = {
            # len(from ... to) < 500 くらいっぽい
            "from": from_id,
            "to": to_id,
            "type": ["ORDER"],
            # 消えるtype => TRADE_CLIENT_EXTENSIONS_MODIFY, DAILY_FINANCING
        }
        request_obj: APIRequest = transactions.TransactionIDRange(
            accountID=self.__oanda_account_id, params=params
        )
        response: Dict[str, Any] = self.__api_client.request(request_obj)

        return response

    # TODO: from_str の扱いを決める必要あり
    def request_transaction_ids(self, from_str: str, to_str: str) -> Tuple[str, str]:
        params: Dict[str, Union[str, int]] = {
            "from": from_str,
            "pageSize": 1000,
            "to": to_str,
        }
        request_obj: APIRequest = transactions.TransactionList(
            accountID=self.__oanda_account_id, params=params
        )
        response: Dict[str, Any] = self.__api_client.request(request_obj)
        if "error" in response:
            self.__stop_request()
            return None, None  # type: ignore

        ids: Dict[str, str] = prepro.extract_transaction_ids(response)
        return ids["old_id"], ids["last_id"]

    def query_instruments(
        self,
        start: Optional[ISO_DATETIME_STR] = None,
        end: Optional[ISO_DATETIME_STR] = None,
        candles_count: Optional[int] = None,
        granularity: str = "M5",
        price_type: str = "M",
    ) -> Dict[str, Any]:
        """
        request price data against OandaAPI

        Parameters
        ----------
        price_type : str
            Available: "M", "B", "A" or combination of those
            Example: "M", "BA", "MA" or so on...
        """
        params = {
            "alignmentTimezone": "Etc/GMT",
            "dailyAlignment": 0,
            "granularity": granularity,
            "price": price_type,
        }
        if start is None and end is None:
            params.update({"count": candles_count})
        elif candles_count is not None:
            params.update({"from": start, "count": candles_count})
        else:
            params.update({"from": start, "to": end})

        request_obj: APIRequest = module_inst.InstrumentsCandles(
            instrument=self.__instrument, params=params
        )
        # HACK: 現在値を取得する際、誤差で将来の時間と扱われてエラーになることがある
        response: Dict[str, Any] = self.__api_client.request(request_obj)
        if "error" in response:
            return {"candles": [], "error": response["error"]}

        return response
