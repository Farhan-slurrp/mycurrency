import os
import sys
from datetime import date, timedelta
from decimal import Decimal

# Add parent directory to path for Django setup
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.currencies.models import Currency, CurrencyExchangeRate
from adapters.mock import MockAdapter


def generate_mock_data(
    days: int = 365,
    currencies: list[str] = None
):
    """Generate mock historical exchange rate data."""
    if currencies is None:
        currencies = ['EUR', 'USD', 'GBP', 'CHF']
    
    currency_objects = {}
    currency_info = {
        'EUR': ('Euro', '€'),
        'USD': ('US Dollar', '$'),
        'GBP': ('British Pound', '£'),
        'CHF': ('Swiss Franc', 'CHF'),
    }
    
    for code in currencies:
        name, symbol = currency_info.get(code, (f'Currency {code}', code))
        currency, created = Currency.objects.get_or_create(
            code=code,
            defaults={'name': name, 'symbol': symbol}
        )
        currency_objects[code] = currency
        if created:
            print(f"Created currency: {currency}")
    
    adapter = MockAdapter(config={'volatility': 0.03, 'seed': 42})
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    created_count = 0
    updated_count = 0
    
    for source_code in currencies:
        for target_code in currencies:
            if source_code == target_code:
                continue
            
            print(f"Generating rates: {source_code} -> {target_code}")
            
            results = adapter.get_historical_rates(
                source_code, target_code, start_date, end_date
            )
            
            for result in results:
                rate, created = CurrencyExchangeRate.objects.update_or_create(
                    source_currency=currency_objects[source_code],
                    exchanged_currency=currency_objects[target_code],
                    valuation_date=result.valuation_date,
                    defaults={'rate_value': result.rate_value}
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
    
    print(f"\nData generation complete!")
    print(f"Created: {created_count} rates")
    print(f"Updated: {updated_count} rates")
    print(f"Total: {created_count + updated_count} rates")


def generate_sample_rates():
    """Generate a small sample of rates for quick testing."""
    generate_mock_data(days=30)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Generate mock exchange rate data'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=365,
        help='Number of days of historical data (default: 365)'
    )
    parser.add_argument(
        '--sample',
        action='store_true',
        help='Generate only 30 days of sample data'
    )
    
    args = parser.parse_args()
    
    if args.sample:
        generate_sample_rates()
    else:
        generate_mock_data(days=args.days)
