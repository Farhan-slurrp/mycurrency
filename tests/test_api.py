import pytest
from datetime import date, timedelta
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.currencies.models import Currency, CurrencyExchangeRate
from apps.providers.models import Provider


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def currencies(db):
    """Create test currencies."""
    Currency.objects.all().delete()
    return [
        Currency.objects.create(code='EUR', name='Euro', symbol='€'),
        Currency.objects.create(code='USD', name='US Dollar', symbol='$'),
        Currency.objects.create(code='GBP', name='British Pound', symbol='£'),
        Currency.objects.create(code='CHF', name='Swiss Franc', symbol='CHF'),
    ]


@pytest.fixture
def mock_provider(db):
    """Create mock provider."""
    return Provider.objects.create(
        name='Mock Provider',
        adapter_path='adapters.mock.MockAdapter',
        priority=1,
        is_active=True
    )


@pytest.fixture
def exchange_rates(currencies, db):
    """Create test exchange rates."""
    eur = currencies[0]
    usd = currencies[1]
    rates = []
    
    for i in range(5):
        rate_date = date.today() - timedelta(days=i)
        rates.append(
            CurrencyExchangeRate.objects.create(
                source_currency=eur,
                exchanged_currency=usd,
                valuation_date=rate_date,
                rate_value=Decimal('1.08') + Decimal(str(i * 0.001))
            )
        )
    return rates


@pytest.mark.django_db
class TestCurrencyAPI:
    """Tests for Currency CRUD endpoints."""
    
    def test_list_currencies(self, api_client, currencies):
        url = '/api/v1/currencies/'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 4
    
    def test_create_currency(self, api_client, db):
        url = '/api/v1/currencies/'
        data = {
            'code': 'JPY',
            'name': 'Japanese Yen',
            'symbol': '¥'
        }
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert Currency.objects.filter(code='JPY').exists()
    
    def test_retrieve_currency(self, api_client, currencies):
        url = '/api/v1/currencies/EUR/'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['code'] == 'EUR'
        assert response.data['name'] == 'Euro'
    
    def test_update_currency(self, api_client, currencies):
        url = '/api/v1/currencies/EUR/'
        data = {
            'code': 'EUR',
            'name': 'European Euro',
            'symbol': '€'
        }
        response = api_client.put(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'European Euro'
    
    def test_delete_currency(self, api_client, currencies):
        url = '/api/v1/currencies/EUR/'
        response = api_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Currency.objects.filter(code='EUR').exists()
    
    def test_filter_active_currencies(self, api_client, currencies):
        # Deactivate one currency
        Currency.objects.filter(code='CHF').update(is_active=False)
        
        url = '/api/v1/currencies/?is_active=true'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 3


@pytest.mark.django_db
class TestExchangeRatesAPI:
    """Tests for exchange rates endpoints."""
    
    def test_get_rates_for_period(
        self, api_client, currencies, exchange_rates
    ):
        url = '/api/v1/rates/'
        params = {
            'source_currency': 'EUR',
            'date_from': (date.today() - timedelta(days=4)).isoformat(),
            'date_to': date.today().isoformat()
        }
        response = api_client.get(url, params)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['source_currency'] == 'EUR'
        assert 'rates' in response.data
    
    def test_get_rates_invalid_currency(self, api_client, currencies):
        url = '/api/v1/rates/'
        params = {
            'source_currency': 'XYZ',
            'date_from': date.today().isoformat(),
            'date_to': date.today().isoformat()
        }
        response = api_client.get(url, params)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_get_rates_invalid_date_range(self, api_client, currencies):
        url = '/api/v1/rates/'
        params = {
            'source_currency': 'EUR',
            'date_from': date.today().isoformat(),
            'date_to': (date.today() - timedelta(days=5)).isoformat()
        }
        response = api_client.get(url, params)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestConvertAPI:
    """Tests for currency conversion endpoint."""
    
    def test_convert_amount(
        self, api_client, currencies, exchange_rates, mock_provider
    ):
        url = '/api/v1/convert/'
        params = {
            'source_currency': 'EUR',
            'exchanged_currency': 'USD',
            'amount': '100.00'
        }
        response = api_client.get(url, params)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'converted_amount' in response.data
        assert 'rate_value' in response.data
    
    def test_convert_same_currency(
        self, api_client, currencies, mock_provider
    ):
        url = '/api/v1/convert/'
        params = {
            'source_currency': 'EUR',
            'exchanged_currency': 'EUR',
            'amount': '100.00'
        }
        response = api_client.get(url, params)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['converted_amount'] == '100.00'
        assert response.data['rate_value'] == '1.000000'
    
    def test_convert_invalid_currency(self, api_client, currencies):
        url = '/api/v1/convert/'
        params = {
            'source_currency': 'XYZ',
            'exchanged_currency': 'USD',
            'amount': '100.00'
        }
        response = api_client.get(url, params)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_convert_missing_params(self, api_client, currencies):
        url = '/api/v1/convert/'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
