import factory
from datetime import date
from decimal import Decimal

from apps.currencies.models import Currency, CurrencyExchangeRate
from apps.providers.models import Provider


class CurrencyFactory(factory.django.DjangoModelFactory):
    """Factory for creating Currency instances."""
    
    class Meta:
        model = Currency
        django_get_or_create = ('code',)
    
    code = factory.Sequence(lambda n: f'C{n:02d}')
    name = factory.LazyAttribute(lambda obj: f'Currency {obj.code}')
    symbol = factory.LazyAttribute(lambda obj: obj.code[0])
    is_active = True


class CurrencyExchangeRateFactory(factory.django.DjangoModelFactory):
    """Factory for creating CurrencyExchangeRate instances."""
    
    class Meta:
        model = CurrencyExchangeRate
    
    source_currency = factory.SubFactory(CurrencyFactory)
    exchanged_currency = factory.SubFactory(CurrencyFactory)
    valuation_date = factory.LazyFunction(date.today)
    rate_value = factory.LazyFunction(lambda: Decimal('1.234567'))


class ProviderFactory(factory.django.DjangoModelFactory):
    """Factory for creating Provider instances."""
    
    class Meta:
        model = Provider
        django_get_or_create = ('name',)
    
    name = factory.Sequence(lambda n: f'Provider {n}')
    adapter_path = 'adapters.mock.MockAdapter'
    priority = factory.Sequence(lambda n: n * 10)
    is_active = True
    config = factory.LazyFunction(dict)


# Predefined currencies
class EURCurrencyFactory(CurrencyFactory):
    code = 'EUR'
    name = 'Euro'
    symbol = '€'


class USDCurrencyFactory(CurrencyFactory):
    code = 'USD'
    name = 'US Dollar'
    symbol = '$'


class GBPCurrencyFactory(CurrencyFactory):
    code = 'GBP'
    name = 'British Pound'
    symbol = '£'


class CHFCurrencyFactory(CurrencyFactory):
    code = 'CHF'
    name = 'Swiss Franc'
    symbol = 'CHF'
