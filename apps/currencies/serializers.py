from rest_framework import serializers
from .models import Currency, CurrencyExchangeRate


class CurrencySerializer(serializers.ModelSerializer):
    """Serializer for Currency model."""
    
    class Meta:
        model = Currency
        fields = [
            'id', 'code', 'name', 'symbol', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CurrencyListSerializer(serializers.ModelSerializer):
    """Simplified serializer for currency lists."""
    
    class Meta:
        model = Currency
        fields = ['code', 'name', 'symbol']


class CurrencyExchangeRateSerializer(serializers.ModelSerializer):
    """Serializer for CurrencyExchangeRate model."""
    
    source_currency = CurrencyListSerializer(read_only=True)
    exchanged_currency = CurrencyListSerializer(read_only=True)
    
    class Meta:
        model = CurrencyExchangeRate
        fields = [
            'id', 'source_currency', 'exchanged_currency',
            'valuation_date', 'rate_value', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ExchangeRateListSerializer(serializers.Serializer):
    """Serializer for exchange rate list in time series format."""
    
    source_currency = serializers.CharField(max_length=3)
    exchanged_currency = serializers.CharField(max_length=3)
    valuation_date = serializers.DateField()
    rate_value = serializers.DecimalField(max_digits=18, decimal_places=6)


class RatesQuerySerializer(serializers.Serializer):
    """Serializer for validating rate query parameters."""
    
    source_currency = serializers.CharField(
        max_length=3,
        help_text="Source currency code (e.g., EUR)"
    )
    date_from = serializers.DateField(
        help_text="Start date (YYYY-MM-DD)"
    )
    date_to = serializers.DateField(
        help_text="End date (YYYY-MM-DD)"
    )
    
    def validate(self, data):
        if data['date_from'] > data['date_to']:
            raise serializers.ValidationError(
                "date_from must be before or equal to date_to"
            )
        return data


class ConvertQuerySerializer(serializers.Serializer):
    """Serializer for validating conversion query parameters."""
    
    source_currency = serializers.CharField(
        max_length=3,
        help_text="Source currency code (e.g., EUR)"
    )
    exchanged_currency = serializers.CharField(
        max_length=3,
        help_text="Target currency code (e.g., USD)"
    )
    amount = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        help_text="Amount to convert"
    )


class ConvertResponseSerializer(serializers.Serializer):
    """Serializer for conversion response."""
    
    source_currency = serializers.CharField()
    exchanged_currency = serializers.CharField()
    original_amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    converted_amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    rate_value = serializers.DecimalField(max_digits=18, decimal_places=6)
    valuation_date = serializers.DateField()


class TimeSeriesRateSerializer(serializers.Serializer):
    """Serializer for time series rate data."""
    
    date = serializers.DateField(source='valuation_date')
    rate = serializers.DecimalField(
        source='rate_value', max_digits=18, decimal_places=6
    )


class TimeSeriesResponseSerializer(serializers.Serializer):
    """Serializer for time series response grouped by currency."""
    
    source_currency = serializers.CharField()
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    rates = serializers.DictField(
        child=serializers.ListSerializer(child=TimeSeriesRateSerializer()),
        help_text="Rates grouped by target currency"
    )


class HistoricalLoadRequestSerializer(serializers.Serializer):
    """Serializer for historical data loading request."""
    
    source_currency = serializers.CharField(max_length=3)
    exchanged_currency = serializers.CharField(max_length=3)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    provider = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError(
                "start_date must be before or equal to end_date"
            )
        return data
