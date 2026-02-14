"""
Mock adapter for generating random exchange rate data.

This adapter is useful for testing and development purposes.
"""
import random
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from .base import (
    BaseExchangeRateAdapter,
    ExchangeRateResult,
    RateNotFoundError,
)


class MockAdapter(BaseExchangeRateAdapter):
    """Mock exchange rate adapter that generates random rates."""

    # Default base rates (trying to make it real but sti random)
    DEFAULT_BASE_RATES = {
        ('EUR', 'USD'): Decimal('1.08'),
        ('EUR', 'GBP'): Decimal('0.86'),
        ('EUR', 'CHF'): Decimal('0.94'),
        ('USD', 'EUR'): Decimal('0.93'),
        ('USD', 'GBP'): Decimal('0.79'),
        ('USD', 'CHF'): Decimal('0.87'),
        ('GBP', 'EUR'): Decimal('1.16'),
        ('GBP', 'USD'): Decimal('1.27'),
        ('GBP', 'CHF'): Decimal('1.10'),
        ('CHF', 'EUR'): Decimal('1.06'),
        ('CHF', 'USD'): Decimal('1.15'),
        ('CHF', 'GBP'): Decimal('0.91'),
    }

    @property
    def name(self) -> str:
        return "Mock Provider"

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self.base_rates = self.config.get('base_rates', self.DEFAULT_BASE_RATES)
        self.volatility = self.config.get('volatility', 0.05)
        
        # Set random seed if provided for reproducibility
        seed = self.config.get('seed')
        if seed is not None:
            random.seed(seed)

    def _get_base_rate(
        self,
        source_currency: str,
        exchanged_currency: str
    ) -> Decimal:
        """Get the base rate for a currency pair."""
        key = (source_currency.upper(), exchanged_currency.upper())
        
        if key in self.base_rates:
            return self.base_rates[key]
        
        # If direct rate not found, try to calculate via EUR
        if source_currency.upper() != 'EUR':
            source_to_eur = self.base_rates.get(
                (source_currency.upper(), 'EUR')
            )
            eur_to_target = self.base_rates.get(
                ('EUR', exchanged_currency.upper())
            )
            if source_to_eur and eur_to_target:
                return source_to_eur * eur_to_target
        
        # Generate a random base rate if not found
        return Decimal(str(round(random.uniform(0.5, 2.0), 6)))

    def _apply_variation(
        self,
        base_rate: Decimal,
        valuation_date: date
    ) -> Decimal:
        """
        Apply date-based variation to a base rate.
        
        Uses the date as part of the variation to ensure consistent
        rates for the same date.
        """
        # Use date components to create deterministic but varying rates
        date_factor = (
            valuation_date.year * 10000 +
            valuation_date.month * 100 +
            valuation_date.day
        )
        random.seed(date_factor)
        
        variation = Decimal(str(
            random.uniform(-self.volatility, self.volatility)
        ))
        varied_rate = base_rate * (1 + variation)
        
        # Reset random seed
        random.seed()
        
        return round(varied_rate, 6)

    def get_exchange_rate(
        self,
        source_currency: str,
        exchanged_currency: str,
        valuation_date: date
    ) -> ExchangeRateResult:
        """Generate a mock exchange rate for the given parameters."""
        if source_currency.upper() == exchanged_currency.upper():
            rate_value = Decimal('1.000000')
        else:
            base_rate = self._get_base_rate(source_currency, exchanged_currency)
            rate_value = self._apply_variation(base_rate, valuation_date)

        return ExchangeRateResult(
            source_currency=source_currency.upper(),
            exchanged_currency=exchanged_currency.upper(),
            valuation_date=valuation_date,
            rate_value=rate_value,
            provider_name=self.name
        )

    def get_exchange_rates_for_date(
        self,
        source_currency: str,
        valuation_date: date,
        target_currencies: Optional[list[str]] = None
    ) -> list[ExchangeRateResult]:
        """Get mock exchange rates for multiple currencies on a date."""
        if target_currencies is None:
            target_currencies = ['EUR', 'USD', 'GBP', 'CHF']
        
        results = []
        for target in target_currencies:
            if target.upper() != source_currency.upper():
                results.append(
                    self.get_exchange_rate(
                        source_currency,
                        target,
                        valuation_date
                    )
                )
        return results

    def get_historical_rates(
        self,
        source_currency: str,
        exchanged_currency: str,
        start_date: date,
        end_date: date
    ) -> list[ExchangeRateResult]:
        """Generate mock historical rates for a date range."""
        results = []
        current_date = start_date
        
        while current_date <= end_date:
            results.append(
                self.get_exchange_rate(
                    source_currency,
                    exchanged_currency,
                    current_date
                )
            )
            current_date += timedelta(days=1)
        
        return results
