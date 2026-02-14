from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class Currency(models.Model):
    """
    Model representing a currency.
    """
    code = models.CharField(
        max_length=3,
        unique=True,
        help_text="ISO 4217 currency code (e.g., USD, EUR)"
    )
    name = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Full name of the currency"
    )
    symbol = models.CharField(
        max_length=10,
        help_text="Currency symbol (e.g., $, €)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this currency is active in the platform"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Currency"
        verbose_name_plural = "Currencies"
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class CurrencyExchangeRate(models.Model):
    """
    Model representing exchange rate between two currencies for a specific date.
    """
    source_currency = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
        related_name='exchange_rates_as_source',
        help_text="The base currency"
    )
    exchanged_currency = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
        related_name='exchange_rates_as_target',
        help_text="The target currency"
    )
    valuation_date = models.DateField(
        db_index=True,
        help_text="The date for this exchange rate"
    )
    rate_value = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        db_index=True,
        validators=[MinValueValidator(Decimal('0.000001'))],
        help_text="The exchange rate value"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Currency Exchange Rate"
        verbose_name_plural = "Currency Exchange Rates"
        ordering = ['-valuation_date', 'source_currency__code']
        unique_together = [
            ['source_currency', 'exchanged_currency', 'valuation_date']
        ]
        indexes = [
            models.Index(
                fields=['source_currency', 'exchanged_currency', 'valuation_date'],
                name='rate_lookup_idx'
            ),
            models.Index(
                fields=['valuation_date', 'source_currency'],
                name='date_source_idx'
            ),
        ]

    def __str__(self):
        return (
            f"{self.source_currency.code} -> {self.exchanged_currency.code}: "
            f"{self.rate_value} ({self.valuation_date})"
        )
