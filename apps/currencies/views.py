from collections import defaultdict
from datetime import date

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter

from .models import Currency, CurrencyExchangeRate
from .serializers import (
    CurrencySerializer,
    CurrencyExchangeRateSerializer,
    RatesQuerySerializer,
    ConvertQuerySerializer,
    ConvertResponseSerializer,
    TimeSeriesResponseSerializer,
    HistoricalLoadRequestSerializer,
)
from services.exchange_rate_service import get_exchange_rate_service


class CurrencyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Currency CRUD operations.
    
    - GET /currencies/ - List all currencies
    - POST /currencies/ - Create a new currency
    - GET /currencies/{code}/ - Retrieve a currency
    - PUT /currencies/{code}/ - Update a currency
    - DELETE /currencies/{code}/ - Delete a currency
    """
    
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer
    lookup_field = 'code'

    def get_queryset(self):
        queryset = super().get_queryset()
        # Optional filter for active currencies only
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset


class ExchangeRateListView(APIView):
    """
    API endpoint to retrieve exchange rates for a time period.
    
    GET /rates/?source_currency=EUR&date_from=2024-01-01&date_to=2024-01-31
    """

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='source_currency',
                description='Source currency code (e.g., EUR)',
                required=True,
                type=str
            ),
            OpenApiParameter(
                name='date_from',
                description='Start date (YYYY-MM-DD)',
                required=True,
                type=str
            ),
            OpenApiParameter(
                name='date_to',
                description='End date (YYYY-MM-DD)',
                required=True,
                type=str
            ),
        ],
        responses={200: TimeSeriesResponseSerializer}
    )
    def get(self, request):
        """Get exchange rates for a time period."""
        serializer = RatesQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        source_currency = serializer.validated_data['source_currency'].upper()
        date_from = serializer.validated_data['date_from']
        date_to = serializer.validated_data['date_to']
        
        if not Currency.objects.filter(code=source_currency).exists():
            return Response(
                {'error': f"Currency '{source_currency}' not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        service = get_exchange_rate_service()
        rates = service.get_rates_for_period(
            source_currency, date_from, date_to
        )
        
        rates_by_currency = defaultdict(list)
        for rate in rates:
            rates_by_currency[rate.exchanged_currency.code].append({
                'date': rate.valuation_date,
                'rate': rate.rate_value
            })
        
        response_data = {
            'source_currency': source_currency,
            'date_from': date_from,
            'date_to': date_to,
            'rates': dict(rates_by_currency)
        }
        
        return Response(response_data)


class ConvertView(APIView):
    """
    API endpoint to convert an amount between currencies.
    
    GET /convert/?source_currency=EUR&exchanged_currency=USD&amount=100
    """

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='source_currency',
                description='Source currency code',
                required=True,
                type=str
            ),
            OpenApiParameter(
                name='exchanged_currency',
                description='Target currency code',
                required=True,
                type=str
            ),
            OpenApiParameter(
                name='amount',
                description='Amount to convert',
                required=True,
                type=float
            ),
        ],
        responses={200: ConvertResponseSerializer}
    )
    def get(self, request):
        """Convert an amount from one currency to another."""
        serializer = ConvertQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        source = serializer.validated_data['source_currency'].upper()
        target = serializer.validated_data['exchanged_currency'].upper()
        amount = serializer.validated_data['amount']
        
        # Verify currencies exist
        for code in [source, target]:
            if not Currency.objects.filter(code=code).exists():
                return Response(
                    {'error': f"Currency '{code}' not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        service = get_exchange_rate_service()
        
        try:
            result = service.convert_amount(source, target, amount)
            return Response(result)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )


class HistoricalLoadView(APIView):
    """
    API endpoint to trigger historical data loading.
    
    POST /rates/load-historical/
    {
        "source_currency": "EUR",
        "exchanged_currency": "USD",
        "start_date": "YYYY-MM-DD",
        "end_date": "YYYY-MM-DD"
    }
    """

    @extend_schema(
        request=HistoricalLoadRequestSerializer,
        responses={202: dict}
    )
    def post(self, request):
        """Trigger async loading of historical exchange rates."""
        serializer = HistoricalLoadRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        from tasks.historical_data import load_historical_rates_task
        
        # Queue the async task
        task = load_historical_rates_task.delay(
            source_currency=data['source_currency'],
            exchanged_currency=data['exchanged_currency'],
            start_date=data['start_date'].isoformat(),
            end_date=data['end_date'].isoformat(),
            provider=data.get('provider')
        )
        
        return Response(
            {
                'message': 'Historical data loading started',
                'task_id': str(task.id),
                'status': 'queued'
            },
            status=status.HTTP_202_ACCEPTED
        )
