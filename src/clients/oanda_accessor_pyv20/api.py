import os
from typing import Any, Dict, List, Optional, Tuple, Union

from aws_lambda_powertools import Logger

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

LOGGER = Logger()


# granularity list
# http://developer.oanda.com/rest-live-v20/instrument-df/#CandlestickGranularity
class OandaClient:
    REQUESTABLE_COUNT = 5000

    def __init__(self, instrument: str, environment: str = "practice", test: bool = False):
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

        self.__api_client = API(
            access_token=os.environ["OANDA_ACCESS_TOKEN"],
            environment=environment,
        )
        self.__accessable: bool = True
        self.__instrument: str = instrument
        self.__units: str = os.environ.get("UNITS") or "1"
        self.__trade_ids: List[Optional[str]] = []
        self.__test: bool = test

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
            accountID=os.environ["OANDA_ACCOUNT_ID"], params=params
        )
        response = self.__api_client.request(request_obj)
        tradeable = response["prices"][0]["tradeable"]
        return {"instrument": self.__instrument, "tradeable": tradeable}

    def request_open_trades(self) -> Dict[str, Union[List[dict], str]]:
        """
        request open position on the OANDA platform
        """
        request_obj: APIRequest = trades.OpenTrades(accountID=os.environ["OANDA_ACCOUNT_ID"])
        response = self.__api_client.request(request_obj)
        LOGGER.info({"[Client] OpenTrades": response})

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
        self.__trade_ids = [trade["id"] for trade in extracted_trades]

        print("[Client] There is open position: {}".format(extracted_trades != []))
        return {
            "positions": extracted_trades,
            "last_transaction_id": response["lastTransactionID"],
        }

    def request_market_ordering(
        self, posi_nega_sign: str = "", stoploss_price: Optional[float] = None
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
                "units": "{sign}{units}".format(sign=posi_nega_sign, units=self.__units),
                "type": "MARKET",
                "positionFill": "DEFAULT",
            }
        }

        if self.__test:
            print("[Test] market_order: {}".format(data))
            return data

        request_obj: APIRequest = orders.OrderCreate(
            accountID=os.environ["OANDA_ACCOUNT_ID"], data=data
        )
        res: Dict[str, Any] = self.__api_client.request(request_obj)
        LOGGER.info({"[Client] market-order": res})

        response: Dict[str, Any] = res["orderCreateTransaction"]
        if response == {}:
            return {"messsage": "Market order is failed.", "result": res}

        response_for_display = {
            "instrument": response.get("instrument"),
            # 'price': response.get('price'),  # There isn't 'price' in result of market order
            "units": response.get("units"),
            "time": response.get("time"),
            "stopLossOnFill": response.get("stopLossOnFill"),
        }

        return {"messsage": "Market order is done !", "order": response_for_display}

    def request_closing(self, reason: str = "") -> Dict[str, Any]:
        """close position"""
        if self.__trade_ids == []:
            return {"error": "[Client] The position to be closed was missing."}
        if self.__test:
            print("[Test] close_order")
            return {}

        target_trade_id = self.__trade_ids[0]
        # data = {'units': self.__units}
        request_obj: APIRequest = trades.TradeClose(
            accountID=os.environ["OANDA_ACCOUNT_ID"],
            tradeID=target_trade_id,  # , data=data
        )
        response: Dict[str, Any] = self.__api_client.request(request_obj)
        LOGGER.info({"[Client] TradeClose": response})
        if (
            response.get("orderFillTransaction") is None
            and response.get("orderCancelTransaction") is not None
        ):
            reason = response.get("orderCancelTransaction").get("reason")  # type: ignore
            LOGGER.warn({"message": "The exit order was canceled because of {}".format(reason)})
            return {"[Client] message": "Close order is failed", "reason": reason}

        dict_close_notification: Dict[str, Any] = {
            "[Client] message": "Position is closed",
            "reason": reason,
            "result": response,
        }
        return dict_close_notification

    def request_trailing_stoploss(self, stoploss_price: float) -> Dict[str, Any]:
        """change stoploss price toward the direction helping us get revenue"""
        if self.__trade_ids == []:
            return {"error": "[Client] There is no position"}

        data = {
            # 'takeProfit': {'timeInForce': 'GTC', 'price': '1.3'},
            "stopLoss": {"timeInForce": "GTC", "price": str(stoploss_price)[:7]}
        }

        request_obj: APIRequest = trades.TradeCRCDO(
            accountID=os.environ["OANDA_ACCOUNT_ID"],
            tradeID=self.__trade_ids[0],
            data=data,
        )
        response: Dict[str, Any] = self.__api_client.request(request_obj)
        LOGGER.info({"[Client] trail": response})
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
            accountID=os.environ["OANDA_ACCOUNT_ID"], params=params
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
            accountID=os.environ["OANDA_ACCOUNT_ID"], params=params
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
    ) -> Dict[str, Any]:
        """request price data against OandaAPI"""
        params = {
            "alignmentTimezone": "Etc/GMT",
            "dailyAlignment": 0,
            "granularity": granularity,
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
