import asyncio
import logging
from datetime import date, timedelta
from typing import Optional

from celery import shared_task

from config.celery import app


logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
)
def load_historical_rates_task(
    self,
    source_currency: str,
    exchanged_currency: str,
    start_date: str,
    end_date: str,
    provider: Optional[str] = None,
    batch_size: int = 30
):
    """Async task to load historical exchange rate data."""
    from services.exchange_rate_service import get_exchange_rate_service
    
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    
    logger.info(
        f"Starting historical data load: {source_currency} -> "
        f"{exchanged_currency} from {start} to {end}"
    )
    
    service = get_exchange_rate_service()
    total_days = (end - start).days + 1
    processed = 0
    errors = []
    
    # Process in batches
    current_start = start
    while current_start <= end:
        current_end = min(current_start + timedelta(days=batch_size - 1), end)
        
        try:
            rates = service.load_historical_rates(
                source_currency=source_currency,
                exchanged_currency=exchanged_currency,
                start_date=current_start,
                end_date=current_end,
                provider_name=provider
            )
            processed += len(rates)
            
            logger.info(
                f"Batch complete: {current_start} to {current_end}, "
                f"loaded {len(rates)} rates"
            )
            
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': processed,
                    'total': total_days,
                    'percent': int((processed / total_days) * 100)
                }
            )
            
        except Exception as e:
            error_msg = (
                f"Batch failed: {current_start} to {current_end}: {str(e)}"
            )
            logger.error(error_msg)
            errors.append(error_msg)
        
        current_start = current_end + timedelta(days=1)
    
    result = {
        'source_currency': source_currency,
        'exchanged_currency': exchanged_currency,
        'start_date': start_date,
        'end_date': end_date,
        'total_days': total_days,
        'rates_loaded': processed,
        'errors': errors
    }
    
    if errors:
        logger.warning(
            f"Historical load completed with {len(errors)} errors"
        )
    else:
        logger.info(
            f"Historical load completed successfully: {processed} rates"
        )
    
    return result


@shared_task(bind=True)
def load_all_currency_pairs_task(
    self,
    start_date: str,
    end_date: str,
    currencies: Optional[list[str]] = None,
    provider: Optional[str] = None
):
    """Load historical rates for all currency pairs."""
    from apps.currencies.models import Currency
    
    if currencies is None:
        currencies = list(
            Currency.objects.filter(is_active=True)
            .values_list('code', flat=True)
        )
    
    logger.info(
        f"Loading historical rates for currencies: {currencies}"
    )
    
    # Create subtasks for each currency pair
    tasks = []
    for source in currencies:
        for target in currencies:
            if source != target:
                task = load_historical_rates_task.delay(
                    source_currency=source,
                    exchanged_currency=target,
                    start_date=start_date,
                    end_date=end_date,
                    provider=provider
                )
                tasks.append({
                    'pair': f"{source}/{target}",
                    'task_id': str(task.id)
                })
    
    return {
        'message': f"Started {len(tasks)} historical load tasks",
        'tasks': tasks
    }


@shared_task
def daily_rate_update_task(currencies: Optional[list[str]] = None):
    """Daily task to fetch and store current exchange rates."""
    from apps.currencies.models import Currency
    from services.exchange_rate_service import get_exchange_rate_service
    
    if currencies is None:
        currencies = list(
            Currency.objects.filter(is_active=True)
            .values_list('code', flat=True)
        )
    
    service = get_exchange_rate_service()
    today = date.today()
    updated = 0
    errors = []
    
    for source in currencies:
        for target in currencies:
            if source != target:
                try:
                    service.get_exchange_rate_data(
                        source_currency=source,
                        exchanged_currency=target,
                        valuation_date=today
                    )
                    updated += 1
                except Exception as e:
                    errors.append(f"{source}/{target}: {str(e)}")
    
    logger.info(f"Daily rate update complete: {updated} rates updated")
    
    return {
        'date': today.isoformat(),
        'rates_updated': updated,
        'errors': errors
    }
