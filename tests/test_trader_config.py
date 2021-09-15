from typing import Dict, List, Union
from unittest.mock import patch
import pytest
from _pytest.fixtures import SubRequest

from models.trader_config import EntryRulesDict, FILTER_ELEMENTS, TraderConfig


@pytest.fixture(name='days', scope='module')
def fixture_days():
    return 120


@pytest.fixture(name='set_stub', scope='module')
def fixture_set_stub():
    with patch('models.tools.interface.ask_true_or_false', return_value=True):
        with patch('models.client_manager.ClientManager.select_instrument', return_value=['', 0.004]):
            yield


@pytest.fixture(name='config', scope='function')
def fixture_config(set_envs) -> TraderConfig:
    set_envs
    yield TraderConfig(operation='unittest')


@pytest.fixture(name='selected_entry_rules', scope='module')
def fixture_selected_entry_rules(days, stoploss_buffer) -> Dict[str, Union[int, float]]:
    return {
        'static_spread': 0.0,
        'stoploss_buffer_pips': stoploss_buffer,
        'days': days
    }


@pytest.mark.usefixtures('set_stub')
class TestSelectConfigs:
    def test_basic(self, config, instrument, selected_entry_rules, days):
        expected_inst: str = instrument
        expected_rules: Dict[str, Union[int, float]] = selected_entry_rules

        result_inst: str
        result_rules: Dict[str, Union[int, float]]
        result_inst, result_rules = config._TraderConfig__select_configs(days=days)

        assert result_inst == expected_inst
        assert result_rules == expected_rules


@pytest.fixture(name='additional_entry_rules', scope='module')
def fixture_additional_entry_rules() -> Dict[str, Union[str, List[str]]]:
    return {
        'granularity': 'M5',
        'entry_filters': []
    }


class TestInitEntryRules:
    def test_basic(
        self, config: TraderConfig,
        selected_entry_rules: Dict[str, Union[int, float]],
        additional_entry_rules: Dict[str, Union[str, List[str]]]
    ):
        expected: Dict[str, Union[str, List[str]]] = additional_entry_rules
        expected.update(selected_entry_rules)

        result: EntryRulesDict = config._TraderConfig__init_entry_rules(selected_entry_rules)
        assert result == expected


class TestGetInstrument:
    def test_basic(self, config, instrument):
        assert config.get_instrument() == instrument


@pytest.fixture
def get_fixture_values(request):
    def _get_fixture(fixture):
        return request.getfixturevalue(fixture)
    return _get_fixture


class TestGetEntryRules:

    @pytest.fixture(params=[
        'static_spread', 'stoploss_buffer_pips', 'days', 'granularity', 'entry_filters'
    ])
    def entry_rule_items(
        self, request: SubRequest, selected_entry_rules, additional_entry_rules
    ) -> List[Union[str, int, float, List[str]]]:
        rules = selected_entry_rules
        rules.update(additional_entry_rules)
        return (request.param, rules[request.param])

    def test_basic(self, entry_rule_items, config: TraderConfig):
        target_rule, expected = entry_rule_items
        config.set_entry_rules('days', 120)
        assert config.get_entry_rules(target_rule) == expected


class TestSetEntryRules:

    def test_basic(self, config: TraderConfig):
        config.set_entry_rules('entry_filters', FILTER_ELEMENTS)
        assert config.get_entry_rules('entry_filters') == FILTER_ELEMENTS
