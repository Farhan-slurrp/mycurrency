from decimal import Decimal
from django import forms
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse

from services.exchange_rate_service import get_exchange_rate_service
from .models import Currency, CurrencyExchangeRate


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "symbol", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["code", "name"]
    ordering = ["code"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = (
        (None, {"fields": ("code", "name", "symbol", "is_active")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(CurrencyExchangeRate)
class CurrencyExchangeRateAdmin(admin.ModelAdmin):
    list_display = [
        "source_currency",
        "exchanged_currency",
        "valuation_date",
        "rate_value",
        "created_at",
    ]
    list_filter = ["source_currency", "exchanged_currency", "valuation_date"]
    search_fields = ["source_currency__code", "exchanged_currency__code"]
    ordering = ["-valuation_date", "source_currency__code"]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "valuation_date"
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "source_currency",
                    "exchanged_currency",
                    "valuation_date",
                    "rate_value",
                )
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


class CurrencyConverterForm(forms.Form):
    """Form for the currency converter view."""

    source_currency = forms.ModelChoiceField(
        queryset=Currency.objects.filter(is_active=True),
        label="Source Currency",
        empty_label="Select source currency",
    )
    amount = forms.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("0.01"),
        label="Amount",
        initial=Decimal("100.00"),
    )
    target_currencies = forms.ModelMultipleChoiceField(
        queryset=Currency.objects.filter(is_active=True),
        label="Target Currencies",
        widget=forms.CheckboxSelectMultiple,
        help_text="Select one or more target currencies",
    )


def converter_view(request):
    """Custom view for currency conversion in admin."""
    context = dict(
        admin.site.each_context(request),
        title="Currency Converter",
    )

    if request.method == "POST":
        form = CurrencyConverterForm(request.POST)
        if form.is_valid():
            source_currency = form.cleaned_data["source_currency"]
            amount = form.cleaned_data["amount"]
            target_currencies = form.cleaned_data["target_currencies"]

            service = get_exchange_rate_service()
            results = []

            for target in target_currencies:
                if target.code != source_currency.code:
                    try:
                        conversion = service.convert_amount(
                            source_currency.code, target.code, amount
                        )
                        results.append(
                            {
                                "target_currency": target,
                                "converted_amount": conversion["converted_amount"],
                                "rate_value": conversion["rate_value"],
                                "valuation_date": conversion["valuation_date"],
                                "success": True,
                            }
                        )
                    except Exception as e:
                        results.append(
                            {
                                "target_currency": target,
                                "error": str(e),
                                "success": False,
                            }
                        )

            context["results"] = results
            context["source_currency"] = source_currency
            context["amount"] = amount
    else:
        form = CurrencyConverterForm()

    context["form"] = form
    return render(request, "admin/currencies/converter.html", context)


def get_admin_urls(urls):
    """Add custom converter URL to admin."""
    custom_urls = [
        path(
            "currencies/converter/",
            admin.site.admin_view(converter_view),
            name="currencies_converter",
        ),
    ]
    return custom_urls + urls


# Override admin site get_urls to include custom URL
_original_get_urls = admin.site.get_urls
admin.site.get_urls = lambda: get_admin_urls(_original_get_urls())


_original_get_app_list = admin.site.get_app_list


def get_app_list_with_converter(request, app_label=None):
    """Add Currency Converter to the currencies app in sidebar."""
    app_list = _original_get_app_list(request, app_label)

    for app in app_list:
        if app["app_label"] == "currencies":
            app["models"].append(
                {
                    "name": "Currency Converter",
                    "object_name": "CurrencyConverter",
                    "admin_url": reverse("admin:currencies_converter"),
                    "view_only": True,
                }
            )
            break

    return app_list


admin.site.get_app_list = get_app_list_with_converter
