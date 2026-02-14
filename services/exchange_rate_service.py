import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.db.models import Q

from adapters.base import (
    BaseExchangeRateAdapter,
    ExchangeRateAdapterError,
    ExchangeRateResult,
)
from apps.currencies.models import Currency, CurrencyExchangeRate
from .provider_manager import get_provider_manager


logger = logging.getLogger(__name__)


class ExchangeRateService:
    """Service for exchange rate"""

    def __init__(self):
        self.provider_manager = get_provider_manager()

    def get_exchange_rate_data(
        self,
        source_currency: str,
        exchanged_currency: str,
        valuation_date: date,
        provider: Optional[str] = None
    ) -> CurrencyExchangeRate:
        """Get exchange rate data"""
        source_currency = source_currency.upper()
        exchanged_currency = exchanged_currency.upper()

        existing_rate = self._get_rate_from_db(
            source_currency, exchanged_currency, valuation_date
        )
        if existing_rate:
            logger.debug(
                f"Found rate in DB: {source_currency} -> "
                f"{exchanged_currency} on {valuation_date}"
            )
            return existing_rate

        logger.info(
            f"Rate not in DB, fetching from provider: "
            f"{source_currency} -> {exchanged_currency} on {valuation_date}"
        )
        result = self._fetch_from_provider(
            source_currency, exchanged_currency, valuation_date, provider
        )

        return self._save_rate_to_db(result)

    def _get_rate_from_db(
        self,
        source_currency: str,
        exchanged_currency: str,
        valuation_date: date
    ) -> Optional[CurrencyExchangeRate]:
        """Try to get an exchange rate from the database."""
        try:
            return CurrencyExchangeRate.objects.select_related(
                'source_currency', 'exchanged_currency'
            ).get(
                source_currency__code=source_currency,
                exchanged_currency__code=exchanged_currency,
                valuation_date=valuation_date
            )
        except CurrencyExchangeRate.DoesNotExist:
            return None

    def _fetch_from_provider(
        self,
        source_currency: str,
        exchanged_currency: str,
        valuation_date: date,
        provider_name: Optional[str] = None
    ) -> ExchangeRateResult:
        """Fetch exchange rate from provider(s) with failover."""
        
        def fetch_operation(adapter: BaseExchangeRateAdapter):
            return adapter.get_exchange_rate(
                source_currency, exchanged_currency, valuation_date
            )

        if provider_name:
            from apps.providers.models import Provider
            try:
                provider = Provider.objects.get(
                    name__iexact=provider_name, is_active=True
                )
                adapter = self.provider_manager.get_adapter_for_provider(
                    provider
                )
                return fetch_operation(adapter)
            except Provider.DoesNotExist:
                raise ExchangeRateAdapterError(
                    f"Provider '{provider_name}' not found or inactive"
                )
        else:
            return self.provider_manager.execute_with_failover(fetch_operation)

    def _save_rate_to_db(
        self,
        result: ExchangeRateResult
    ) -> CurrencyExchangeRate:
        """Save an exchange rate result to the database."""
        source = Currency.objects.get(code=result.source_currency)
        target = Currency.objects.get(code=result.exchanged_currency)

        rate, created = CurrencyExchangeRate.objects.update_or_create(
            source_currency=source,
            exchanged_currency=target,
            valuation_date=result.valuation_date,
            defaults={'rate_value': result.rate_value}
        )

        if created:
            logger.info(f"Created new rate: {rate}")
        else:
            logger.info(f"Updated existing rate: {rate}")

        return rate

    def get_rates_for_period(
        self,
        source_currency: str,
        date_from: date,
        date_to: date,
        target_currencies: Optional[list[str]] = None
    ) -> list[CurrencyExchangeRate]:
        """Get exchange rates for a time period."""
        source_currency = source_currency.upper()
        
        queryset = CurrencyExchangeRate.objects.select_related(
            'source_currency', 'exchanged_currency'
        ).filter(
            source_currency__code=source_currency,
            valuation_date__gte=date_from,
            valuation_date__lte=date_to
        )

        if target_currencies:
            target_currencies = [c.upper() for c in target_currencies]
            queryset = queryset.filter(
                exchanged_currency__code__in=target_currencies
            )

        return list(queryset.order_by('valuation_date', 'exchanged_currency'))

    def convert_amount(
        self,
        source_currency: str,
        exchanged_currency: str,
        amount: Decimal,
        valuation_date: Optional[date] = None
    ) -> dict:
        """Convert an amount from one currency to another."""
        if valuation_date is None:
            valuation_date = date.today()

        source_currency = source_currency.upper()
        exchanged_currency = exchanged_currency.upper()

        if source_currency == exchanged_currency:
            return {
                'source_currency': source_currency,
                'exchanged_currency': exchanged_currency,
                'original_amount': amount,
                'converted_amount': amount,
                'rate_value': Decimal('1.000000'),
                'valuation_date': valuation_date
            }

        rate = self.get_exchange_rate_data(
            source_currency, exchanged_currency, valuation_date
        )

        converted_amount = amount * rate.rate_value

        return {
            'source_currency': source_currency,
            'exchanged_currency': exchanged_currency,
            'original_amount': amount,
            'converted_amount': round(converted_amount, 2),
            'rate_value': rate.rate_value,
            'valuation_date': valuation_date
        }

    def load_historical_rates(
        self,
        source_currency: str,
        exchanged_currency: str,
        start_date: date,
        end_date: date,
        provider_name: Optional[str] = None
    ) -> list[CurrencyExchangeRate]:
        """Load historical rates for a date range."""
        source_currency = source_currency.upper()
        exchanged_currency = exchanged_currency.upper()

        def fetch_historical(adapter: BaseExchangeRateAdapter):
            return adapter.get_historical_rates(
                source_currency, exchanged_currency, start_date, end_date
            )

        if provider_name:
            from apps.providers.models import Provider
            provider = Provider.objects.get(
                name__iexact=provider_name, is_active=True
            )
            adapter = self.provider_manager.get_adapter_for_provider(provider)
            results = fetch_historical(adapter)
        else:
            results = self.provider_manager.execute_with_failover(
                fetch_historical
            )

        return self._bulk_save_rates(results)

    def _bulk_save_rates(
        self,
        results: list[ExchangeRateResult]
    ) -> list[CurrencyExchangeRate]:
        """Bulk save exchange rate results to the database."""
        saved_rates = []
        
        currency_codes = set()
        for r in results:
            currency_codes.add(r.source_currency)
            currency_codes.add(r.exchanged_currency)
        
        currencies = {
            c.code: c for c in Currency.objects.filter(code__in=currency_codes)
        }

        with transaction.atomic():
            for result in results:
                source = currencies.get(result.source_currency)
                target = currencies.get(result.exchanged_currency)
                
                if not source or not target:
                    logger.warning(
                        f"Skipping rate - currency not found: "
                        f"{result.source_currency} -> {result.exchanged_currency}"
                    )
                    continue

                rate, _ = CurrencyExchangeRate.objects.update_or_create(
                    source_currency=source,
                    exchanged_currency=target,
                    valuation_date=result.valuation_date,
                    defaults={'rate_value': result.rate_value}
                )
                saved_rates.append(rate)

        logger.info(f"Saved {len(saved_rates)} exchange rates")
        return saved_rates


_exchange_rate_service: Optional[ExchangeRateService] = None


def get_exchange_rate_service() -> ExchangeRateService:
    """Get the singleton ExchangeRateService instance."""
    global _exchange_rate_service
    if _exchange_rate_service is None:
        _exchange_rate_service = ExchangeRateService()
    return _exchange_rate_service
