import importlib
import logging
from typing import Optional, Type

from adapters.base import BaseExchangeRateAdapter, ExchangeRateAdapterError


logger = logging.getLogger(__name__)


class ProviderManager:
    """Manages exchange rate providers with priority and failover support."""

    def __init__(self):
        self._adapters_cache: dict[str, BaseExchangeRateAdapter] = {}

    def _import_adapter_class(
        self,
        adapter_path: str
    ) -> Type[BaseExchangeRateAdapter]:
        """Dynamically import an adapter class from its path."""
        try:
            module_path, class_name = adapter_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            return getattr(module, class_name)
        except (ValueError, ImportError, AttributeError) as e:
            logger.error(f"Failed to import adapter '{adapter_path}': {e}")
            raise ImportError(
                f"Cannot import adapter class '{adapter_path}': {e}"
            )

    def get_adapter(
        self,
        adapter_path: str,
        config: Optional[dict] = None
    ) -> BaseExchangeRateAdapter:
        """Get an adapter instance, using cache if available."""
        cache_key = f"{adapter_path}:{hash(str(config))}"
        
        if cache_key not in self._adapters_cache:
            adapter_class = self._import_adapter_class(adapter_path)
            self._adapters_cache[cache_key] = adapter_class(config)
        
        return self._adapters_cache[cache_key]

    def get_active_providers(self) -> list:
        """Get all active providers ordered by priority."""
        from apps.providers.models import Provider
        return list(
            Provider.objects.filter(is_active=True).order_by('priority', 'name')
        )

    def get_adapter_for_provider(self, provider) -> BaseExchangeRateAdapter:
        """Get the adapter instance for a provider model."""
        return self.get_adapter(provider.adapter_path, provider.config)

    def execute_with_failover(self, operation: callable, *args, **kwargs):
        """Execute an operation with automatic failover through providers."""
        providers = self.get_active_providers()
        
        if not providers:
            raise ExchangeRateAdapterError(
                "No active exchange rate providers configured"
            )
        
        last_error = None
        
        for provider in providers:
            try:
                adapter = self.get_adapter_for_provider(provider)
                logger.info(
                    f"Trying provider '{provider.name}' "
                    f"(priority: {provider.priority})"
                )
                result = operation(adapter, *args, **kwargs)
                logger.info(f"Successfully got data from '{provider.name}'")
                return result
            
            except ExchangeRateAdapterError as e:
                logger.warning(
                    f"Provider '{provider.name}' failed: {e}. "
                    f"Trying next provider..."
                )
                last_error = e
                continue
        
        error_msg = (
            f"All providers failed. Last error: {last_error}"
            if last_error else "All providers failed"
        )
        logger.error(error_msg)
        raise ExchangeRateAdapterError(error_msg)

    def clear_cache(self):
        """Clear the adapter cache."""
        self._adapters_cache.clear()


_provider_manager: Optional[ProviderManager] = None


def get_provider_manager() -> ProviderManager:
    """Get the singleton ProviderManager instance."""
    global _provider_manager
    if _provider_manager is None:
        _provider_manager = ProviderManager()
    return _provider_manager
