import logging
import time
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

import httpx
from django.conf import settings
from django.core.cache import cache

from .base import (
    BaseExchangeRateAdapter,
    ExchangeRateResult,
    ProviderUnavailableError,
    RateNotFoundError,
)


logger = logging.getLogger(__name__)


class CurrencyBeaconAdapter(BaseExchangeRateAdapter):
    """Adapter for CurrencyBeacon exchange rate API."""

    DEFAULT_BASE_URL = 'https://api.currencybeacon.com/v1'
    DEFAULT_TIMEOUT = 30
    DEFAULT_RATE_LIMIT_DELAY = 0.1
    DEFAULT_CACHE_TTL = 3600  # 1 hour

    @property
    def name(self) -> str:
        return "CurrencyBeacon"

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self.api_key = self.config.get(
            'api_key',
            getattr(settings, 'CURRENCY_BEACON_API_KEY', '')
        )
        self.base_url = self.config.get('base_url', self.DEFAULT_BASE_URL)
        self.timeout = self.config.get('timeout', self.DEFAULT_TIMEOUT)
        self.rate_limit_delay = self.config.get('rate_limit_delay', self.DEFAULT_RATE_LIMIT_DELAY)
        self.cache_ttl = self.config.get('cache_ttl', self.DEFAULT_CACHE_TTL)

        if not self.api_key:
            logger.warning(
                "CurrencyBeacon API key not configured. "
                "Set CURRENCY_BEACON_API_KEY in settings or provider config."
            )

    def _get_cache_key(self, source: str, target: str, valuation_date: date) -> str:
        """Generate cache key for exchange rate."""
        return f"currencybeacon:{source}:{target}:{valuation_date.isoformat()}"

    def _make_request(
        self,
        endpoint: str,
        params: Optional[dict] = None
    ) -> dict:
        """
        Make a request to the CurrencyBeacon API.
        
        Args:
            endpoint: API endpoint (e.g., '/latest', '/historical')
            params: Query parameters
            
        Returns:
            JSON response as dictionary
            
        Raises:
            ProviderUnavailableError: If the request fails
        """
        url = f"{self.base_url}{endpoint}"
        request_params = {'api_key': self.api_key}
        if params:
            request_params.update(params)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=request_params)
                response.raise_for_status()
                data = response.json()
                
                # Check for API-level errors
                if 'error' in data:
                    raise ProviderUnavailableError(
                        f"CurrencyBeacon API error: {data['error']}"
                    )
                
                return data

        except httpx.TimeoutException as e:
            logger.error(f"CurrencyBeacon request timeout: {e}")
            raise ProviderUnavailableError(
                f"CurrencyBeacon request timed out: {e}"
            )
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            logger.error(f"CurrencyBeacon HTTP error {status_code}: {e}")
            
            if status_code == 401:
                raise ProviderUnavailableError(
                    "CurrencyBeacon authentication failed: Invalid API key"
                )
            elif status_code == 403:
                raise ProviderUnavailableError(
                    "CurrencyBeacon access forbidden: Your plan does not support this endpoint. "
                    "The /timeseries endpoint requires a Startup or Pro plan."
                )
            elif status_code == 429:
                raise ProviderUnavailableError(
                    "CurrencyBeacon rate limit exceeded. Please upgrade your plan or reduce request frequency."
                )
            else:
                raise ProviderUnavailableError(
                    f"CurrencyBeacon HTTP error {status_code}"
                )
        except httpx.RequestError as e:
            logger.error(f"CurrencyBeacon request error: {e}")
            raise ProviderUnavailableError(
                f"CurrencyBeacon request failed: {e}"
            )

    def get_exchange_rate(
        self,
        source_currency: str,
        exchanged_currency: str,
        valuation_date: date
    ) -> ExchangeRateResult:
        """Get exchange rate from CurrencyBeacon for a specific date."""
        source = source_currency.upper()
        target = exchanged_currency.upper()

        if source == target:
            return ExchangeRateResult(
                source_currency=source,
                exchanged_currency=target,
                valuation_date=valuation_date,
                rate_value=Decimal('1.000000'),
                provider_name=self.name
            )

        cache_key = self._get_cache_key(source, target, valuation_date)
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.debug(f"Cache hit for {cache_key}")
            return cached_result

        today = date.today()
        
        if valuation_date > today:
            logger.warning(
                f"Requested future date {valuation_date}, using today's rate instead"
            )
            valuation_date = today
        
        try:
            if valuation_date >= today:
                data = self._make_request('/latest', {'base': source})
                actual_date = today
            else:
                data = self._make_request('/historical', {
                    'base': source,
                    'date': valuation_date.isoformat()
                })
                actual_date = valuation_date

            rates = data.get('rates', {})
            if not rates:
                response = data.get('response', {})
                if isinstance(response, dict):
                    rates = response.get('rates', {})
            
            if target not in rates:
                raise RateNotFoundError(
                    f"Rate not found for {source} -> {target} on {valuation_date}"
                )

            rate_value = Decimal(str(rates[target]))

            result = ExchangeRateResult(
                source_currency=source,
                exchanged_currency=target,
                valuation_date=actual_date,
                rate_value=rate_value,
                provider_name=self.name
            )

            cache.set(cache_key, result, self.cache_ttl)
            
            return result
            
        except (ProviderUnavailableError, RateNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching exchange rate: {e}")
            raise ProviderUnavailableError(f"Unexpected error: {e}")

    def get_exchange_rates_for_date(
        self,
        source_currency: str,
        valuation_date: date,
        target_currencies: Optional[list[str]] = None
    ) -> list[ExchangeRateResult]:
        """Get exchange rates for multiple currencies on a specific date."""
        source = source_currency.upper()
        today = date.today()
        
        if valuation_date > today:
            logger.warning(
                f"Requested future date {valuation_date}, using today's rates instead"
            )
            valuation_date = today

        try:
            if valuation_date >= today:
                data = self._make_request('/latest', {'base': source})
                actual_date = today
            else:
                data = self._make_request('/historical', {
                    'base': source,
                    'date': valuation_date.isoformat()
                })
                actual_date = valuation_date

            if not rates:
                response = data.get('response', {})
                if isinstance(response, dict):
                    rates = response.get('rates', {})
            
            if target_currencies:
                target_set = {c.upper() for c in target_currencies}
                rates = {k: v for k, v in rates.items() if k in target_set}

            results = []
            for currency, rate in rates.items():
                if currency != source:
                    result = ExchangeRateResult(
                        source_currency=source,
                        exchanged_currency=currency,
                        valuation_date=actual_date,
                        rate_value=Decimal(str(rate)),
                        provider_name=self.name
                    )
                    results.append(result)
                    
                    cache_key = self._get_cache_key(source, currency, actual_date)
                    cache.set(cache_key, result, self.cache_ttl)

            return results
            
        except Exception as e:
            logger.error(f"Failed to get rates for date {valuation_date}: {e}")
            raise ProviderUnavailableError(f"Failed to get rates: {e}")

    def _fallback_historical_rates(
        self,
        source: str,
        target: str,
        start_date: date,
        end_date: date
    ) -> list[ExchangeRateResult]:
        """
        Fallback method using individual /historical requests per date.
        
        This is used when the timeseries endpoint is not available (free tier)
        or when it fails. Includes rate limiting to avoid hitting API limits.
        """
        logger.info(
            f"Fetching {source}->{target} rates individually "
            f"from {start_date} to {end_date} "
            f"with {self.rate_limit_delay}s delay between requests"
        )
        
        results = []
        current_date = start_date
        today = date.today()
        error_count = 0
        max_errors = 5 
        
        while current_date <= end_date and current_date <= today:
            try:
                cache_key = self._get_cache_key(source, target, current_date)
                cached_result = cache.get(cache_key)
                
                if cached_result:
                    results.append(cached_result)
                else:
                    result = self.get_exchange_rate(source, target, current_date)
                    results.append(result)
                    
                error_count = 0 
                
            except RateNotFoundError:
                logger.debug(
                    f"Rate not found for {source} -> {target} on {current_date}"
                )
                error_count = 0
            except Exception as e:
                error_count += 1
                logger.warning(
                    f"Error fetching rate for {current_date} ({error_count}/{max_errors}): {e}"
                )
                
                if error_count >= max_errors:
                    logger.error(
                        f"Too many consecutive errors ({max_errors}), stopping fallback requests"
                    )
                    break
            
            time.sleep(self.rate_limit_delay)
            current_date += timedelta(days=1)
        
        logger.info(f"Fallback completed: fetched {len(results)} rates")
        return sorted(results, key=lambda r: r.valuation_date)


    def get_historical_rates(
        self,
        source_currency: str,
        exchanged_currency: str,
        start_date: date,
        end_date: date
    ) -> list[ExchangeRateResult]:
        """
        Get historical rates for a date range.
        """
        source = source_currency.upper()
        target = exchanged_currency.upper()

        if start_date > end_date:
            raise ValueError("start_date must be before end_date")
        
        today = date.today()
        
        if start_date > today:
            logger.warning(f"Start date {start_date} is in the future, no data available")
            return []
        
        if end_date > today:
            logger.warning(f"End date {end_date} is in the future, limiting to today")
            end_date = today

        try:
            logger.info(
                f"Attempting timeseries request for {source}->{target} "
                f"from {start_date} to {end_date}"
            )
            
            data = self._make_request('/timeseries', {
                'base': source,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'symbols': target
            })
            
            results = []
            
            response = data.get('response', data.get('rates', {}))
            
            if isinstance(response, list):
                logger.info(
                    "Timeseries endpoint not available on current plan (empty list response), "
                    "falling back to individual requests"
                )
                return self._fallback_historical_rates(source, target, start_date, end_date)
            
            elif isinstance(response, dict):
                logger.info(f"Processing timeseries data with {len(response)} entries")
                
                for date_str, rates in response.items():
                    try:
                        if 'T' in date_str:
                            rate_date = date.fromisoformat(date_str.split('T')[0])
                        else:
                            rate_date = date.fromisoformat(date_str)
                        
                        if isinstance(rates, dict) and target in rates:
                            rate_value = Decimal(str(rates[target]))
                        elif isinstance(rates, (int, float, str)):
                            rate_value = Decimal(str(rates))
                        else:
                            logger.warning(f"Skipping unexpected rate format for {date_str}: {type(rates)}")
                            continue
                        
                        result = ExchangeRateResult(
                            source_currency=source,
                            exchanged_currency=target,
                            valuation_date=rate_date,
                            rate_value=rate_value,
                            provider_name=self.name
                        )
                        results.append(result)
                        
                        cache_key = self._get_cache_key(source, target, rate_date)
                        cache.set(cache_key, result, self.cache_ttl)
                        
                    except (ValueError, KeyError, TypeError, ArithmeticError) as e:
                        logger.warning(f"Skipping invalid date/rate format for {date_str}: {e}")
                        continue
                
                if results:
                    sorted_results = sorted(results, key=lambda r: r.valuation_date)
                    logger.info(f"Timeseries returned {len(sorted_results)} rates")
                    return sorted_results
                else:
                    logger.warning("Timeseries returned no valid rates, falling back to individual requests")
                    return self._fallback_historical_rates(source, target, start_date, end_date)
            
            else:
                logger.warning(
                    f"Unexpected response format from timeseries endpoint: {type(response)}"
                )
                return self._fallback_historical_rates(source, target, start_date, end_date)

        except ProviderUnavailableError as e:
            error_str = str(e)
            
            if "403" in error_str or "forbidden" in error_str.lower():
                logger.info(
                    "Timeseries endpoint restricted (403 - requires paid plan), "
                    "falling back to individual requests"
                )
            else:
                logger.warning(f"Timeseries endpoint unavailable: {e}")
            
            return self._fallback_historical_rates(source, target, start_date, end_date)
        
        except Exception as e:
            logger.error(f"Unexpected error in timeseries request: {e}")
            return self._fallback_historical_rates(source, target, start_date, end_date)

    def get_latest_rate(
        self,
        source_currency: str,
        exchanged_currency: str
    ) -> ExchangeRateResult:
        """Get the latest exchange rate using the /latest endpoint."""
        source = source_currency.upper()
        target = exchanged_currency.upper()

        if source == target:
            return ExchangeRateResult(
                source_currency=source,
                exchanged_currency=target,
                valuation_date=date.today(),
                rate_value=Decimal('1.000000'),
                provider_name=self.name
            )

        today = date.today()
        cache_key = self._get_cache_key(source, target, today)
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.debug(f"Cache hit for latest rate {cache_key}")
            return cached_result

        try:
            data = self._make_request('/latest', {'base': source})
            
            rates = data.get('rates', {})
            if not rates:
                response = data.get('response', {})
                if isinstance(response, dict):
                    rates = response.get('rates', {})
            
            if target not in rates:
                raise RateNotFoundError(
                    f"Latest rate not found for {source} -> {target}"
                )

            result = ExchangeRateResult(
                source_currency=source,
                exchanged_currency=target,
                valuation_date=today,
                rate_value=Decimal(str(rates[target])),
                provider_name=self.name
            )

            cache.set(cache_key, result, self.cache_ttl)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get latest rate: {e}")
            raise ProviderUnavailableError(f"Failed to get latest rate: {e}")