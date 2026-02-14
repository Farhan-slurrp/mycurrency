import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from adapters.base import (
    BaseExchangeRateAdapter,
    ExchangeRateResult,
    ExchangeRateAdapterError,
    ProviderUnavailableError,
    RateNotFoundError,
)
from adapters.mock import MockAdapter
from adapters.currencybeacon import CurrencyBeaconAdapter


class TestExchangeRateResult:
    """Tests for ExchangeRateResult dataclass."""
    
    def test_creates_result_with_decimal(self):
        result = ExchangeRateResult(
            source_currency='EUR',
            exchanged_currency='USD',
            valuation_date=date.today(),
            rate_value=Decimal('1.08'),
            provider_name='Test'
        )
        assert result.rate_value == Decimal('1.08')
    
    def test_converts_float_to_decimal(self):
        result = ExchangeRateResult(
            source_currency='EUR',
            exchanged_currency='USD',
            valuation_date=date.today(),
            rate_value=1.08,
            provider_name='Test'
        )
        assert isinstance(result.rate_value, Decimal)


class TestMockAdapter:
    """Tests for MockAdapter."""
    
    def setup_method(self):
        self.adapter = MockAdapter()
    
    def test_name_property(self):
        assert self.adapter.name == 'Mock Provider'
    
    def test_get_exchange_rate_same_currency(self):
        result = self.adapter.get_exchange_rate('EUR', 'EUR', date.today())
        assert result.rate_value == Decimal('1.000000')
    
    def test_get_exchange_rate_different_currency(self):
        result = self.adapter.get_exchange_rate('EUR', 'USD', date.today())
        assert result.source_currency == 'EUR'
        assert result.exchanged_currency == 'USD'
        assert result.rate_value > 0
    
    def test_get_exchange_rate_consistent_for_same_date(self):
        test_date = date(2024, 1, 15)
        result1 = self.adapter.get_exchange_rate('EUR', 'USD', test_date)
        result2 = self.adapter.get_exchange_rate('EUR', 'USD', test_date)
        assert result1.rate_value == result2.rate_value
    
    def test_get_exchange_rates_for_date(self):
        results = self.adapter.get_exchange_rates_for_date(
            'EUR', date.today(), ['USD', 'GBP']
        )
        assert len(results) == 2
        currencies = {r.exchanged_currency for r in results}
        assert currencies == {'USD', 'GBP'}
    
    def test_get_historical_rates(self):
        start = date.today() - timedelta(days=5)
        end = date.today()
        results = self.adapter.get_historical_rates(
            'EUR', 'USD', start, end
        )
        assert len(results) == 6  # 5 days + 1
        dates = [r.valuation_date for r in results]
        assert dates[0] == start
        assert dates[-1] == end
    
    def test_custom_volatility(self):
        adapter = MockAdapter(config={'volatility': 0.1})
        assert adapter.volatility == 0.1
    
    def test_seed_for_reproducibility(self):
        adapter1 = MockAdapter(config={'seed': 42})
        adapter2 = MockAdapter(config={'seed': 42})
        # Both should produce same results
        r1 = adapter1.get_exchange_rate('EUR', 'USD', date.today())
        r2 = adapter2.get_exchange_rate('EUR', 'USD', date.today())
        # Note: Due to date-based seeding, these should be equal
        assert r1.rate_value == r2.rate_value


class TestCurrencyBeaconAdapter:
    """Tests for CurrencyBeaconAdapter."""
    
    def setup_method(self):
        self.adapter = CurrencyBeaconAdapter(config={'api_key': 'test-key'})
    
    def test_name_property(self):
        assert self.adapter.name == 'CurrencyBeacon'
    
    def test_get_exchange_rate_same_currency(self):
        result = self.adapter.get_exchange_rate('EUR', 'EUR', date.today())
        assert result.rate_value == Decimal('1.000000')
    
    @patch('adapters.currencybeacon.httpx.Client')
    def test_get_exchange_rate_api_call(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'rates': {'USD': 1.08}
        }
        mock_response.raise_for_status = MagicMock()
        
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client
        
        result = self.adapter.get_exchange_rate('EUR', 'USD', date.today())
        
        assert result.source_currency == 'EUR'
        assert result.exchanged_currency == 'USD'
        assert result.rate_value == Decimal('1.08')
    
    @patch('adapters.currencybeacon.httpx.Client')
    def test_handles_api_error(self, mock_client_class):
        import httpx
        
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.TimeoutException('Timeout')
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client
        
        with pytest.raises(ProviderUnavailableError):
            self.adapter.get_exchange_rate('EUR', 'USD', date.today())
    
    @patch('adapters.currencybeacon.httpx.Client')
    def test_rate_not_found(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.json.return_value = {'rates': {}}
        mock_response.raise_for_status = MagicMock()
        
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client
        
        with pytest.raises(RateNotFoundError):
            self.adapter.get_exchange_rate('EUR', 'XYZ', date.today())
