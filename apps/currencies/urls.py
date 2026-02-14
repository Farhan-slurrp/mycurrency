from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CurrencyViewSet,
    ExchangeRateListView,
    ConvertView,
    HistoricalLoadView,
)


app_name = 'currencies'

router = DefaultRouter()
router.register(r'currencies', CurrencyViewSet, basename='currency')

urlpatterns = [
    # Router URLs
    path('', include(router.urls)),
    
    # Exchange rates endpoints
    path('rates/', ExchangeRateListView.as_view(), name='rates-list'),
    path('convert/', ConvertView.as_view(), name='convert'),
    path(
        'rates/load-historical/',
        HistoricalLoadView.as_view(),
        name='historical-load'
    ),
]
