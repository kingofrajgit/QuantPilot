"""Thread-safe indicator registry for discovery, factory instantiation, and reflection."""

import threading
from typing import Any

from quantpilot.quant.base import BaseIndicator


class IndicatorRegistry:
    """Thread-safe catalog for indicator discovery, factory instantiation, and reflection."""

    def __init__(self) -> None:
        self._registry: dict[str, type[BaseIndicator]] = {}
        self._lock = threading.Lock()

    def register(self, indicator_cls: type[BaseIndicator]) -> None:
        """Register an indicator class by canonical name, rejecting duplicates fail-closed."""
        # Instantiate with default parameters to verify name and contract
        instance = indicator_cls()
        name = instance.name.lower()
        with self._lock:
            if name in self._registry:
                raise ValueError(f"Indicator '{name}' is already registered in registry")
            self._registry[name] = indicator_cls

    def get(self, name: str, **kwargs: Any) -> BaseIndicator:
        """Instantiate a registered indicator with optional customized parameters."""
        canonical_name = name.lower()
        with self._lock:
            if canonical_name not in self._registry:
                raise KeyError(f"Indicator '{canonical_name}' not found in registry")
            cls = self._registry[canonical_name]
        return cls(**kwargs)

    def list_available(self) -> list[dict[str, Any]]:
        """Reflect all registered indicators, metadata, and default parameters."""
        with self._lock:
            items = list(self._registry.items())

        catalog = []
        for name, cls in sorted(items):
            instance = cls()
            catalog.append(
                {
                    "name": name,
                    "class_name": cls.__name__,
                    "version": instance.version,
                    "required_fields": instance.required_fields,
                    "minimum_observations": instance.minimum_observations,
                    "default_parameters": instance.parameters,
                }
            )
        return catalog

    def __contains__(self, name: str) -> bool:
        canonical_name = name.lower()
        with self._lock:
            return canonical_name in self._registry

    def __len__(self) -> int:
        with self._lock:
            return len(self._registry)


default_registry = IndicatorRegistry()
