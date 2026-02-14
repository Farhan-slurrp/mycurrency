from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass
class ExchangeRateResult:
    """
    Data class representing an exchange rate result from a provider.
    """
    source_currency: str
    exchanged_currency: str
    valuation_date: date
    rate_value: Decimal
    provider_name: str

    def __post_init__(self):
        """Ensure rate_value is a Decimal."""
        if not isinstance(self.rate_value, Decimal):
            self.rate_value = Decimal(str(self.rate_value))


class ExchangeRateAdapterError(Exception):
    """Base exception for adapter errors."""
    pass


class ProviderUnavailableError(ExchangeRateAdapterError):
    """Raised when a provider is temporarily unavailable."""
    pass


class RateNotFoundError(ExchangeRateAdapterError):
    """Raised when a requested rate is not found."""
    pass


class BaseExchangeRateAdapter(ABC):
    """Abstract base class for exchange rate adapters."""

    def __init__(self, config: Optional[dict] = None):
        """Initialize the adapter with optional configuration."""
        self.config = config or {}

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this provider."""
        pass

    @abstractmethod
    def get_exchange_rate(
        self,
        source_currency: str,
        exchanged_currency: str,
        valuation_date: date
    ) -> ExchangeRateResult:
        """Get the exchange rate for a specific currency pair and date."""
        pass

    @abstractmethod
    def get_exchange_rates_for_date(
        self,
        source_currency: str,
        valuation_date: date,
        target_currencies: Optional[list[str]] = None
    ) -> list[ExchangeRateResult]:
        """ Get exchange rates for a source currency to multiple target currencies."""
        pass

    @abstractmethod
    def get_historical_rates(
        self,
        source_currency: str,
        exchanged_currency: str,
        start_date: date,
        end_date: date
    ) -> list[ExchangeRateResult]:
        """Get historical exchange rates for a date range."""
        pass

    def get_latest_rate(
        self,
        source_currency: str,
        exchanged_currency: str
    ) -> ExchangeRateResult:
        """Get the latest available exchange rate."""
        return self.get_exchange_rate(
            source_currency,
            exchanged_currency,
            date.today()
        )
