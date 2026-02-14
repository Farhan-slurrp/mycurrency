from django.db import models


class Provider(models.Model):
    """Model for exchange rate data provider."""
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique name for the provider"
    )
    adapter_path = models.CharField(
        max_length=255,
        help_text="Python import path to the adapter class "
                  "(e.g., 'adapters.currencybeacon.CurrencyBeaconAdapter')"
    )
    priority = models.PositiveIntegerField(
        default=100,
        db_index=True,
        help_text="Priority order (lower number = higher priority)"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this provider is currently active"
    )
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Provider-specific configuration (API keys, endpoints, etc.)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Exchange Rate Provider"
        verbose_name_plural = "Exchange Rate Providers"
        ordering = ['priority', 'name']

    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"{self.name} (Priority: {self.priority}, {status})"
