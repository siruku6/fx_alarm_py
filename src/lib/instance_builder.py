from typing import Any, Dict, Optional

from src.candle_loader import CandleLoader
from src.clients.oanda_accessor_pyv20.interface import OandaInterface
from src.result_processor import ResultProcessor
from src.trader_config import TraderConfig


class InstanceBuilder:
    @classmethod
    def build(cls, operation: str, days: int, instrument: Optional[str] = None) -> Dict[str, Any]:
        config: "TraderConfig" = TraderConfig(operation, instrument)
        o_interface: "OandaInterface" = OandaInterface(
            instrument=config.get_instrument(),
            test=operation in ("backtest", "forward_test"),
        )
        candle_loader: "CandleLoader" = CandleLoader(config, o_interface, days)
        result_processor: "ResultProcessor" = ResultProcessor(operation, config)
        return {
            "config": config,
            "o_interface": o_interface,
            "candle_loader": candle_loader,
            "result_processor": result_processor,
        }
