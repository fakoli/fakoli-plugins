"""Provider registry for fakoli-speak.

Providers are registered by name and resolved at call-time using:
  1. An explicit *name* argument passed to :func:`get_provider`.
  2. The ``FAKOLI_SPEAK_PROVIDER`` environment variable.
  3. The built-in default (``"openai"``).

Auto-discovery imports every module found inside the ``providers/`` sub-package
so that providers only need to call :func:`register` at import time to become
visible — no manual wiring required.
"""

from __future__ import annotations

import importlib
import logging
import os
import pkgutil

from .protocol import TTSProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_registry: dict[str, TTSProvider] = {}
_DEFAULT_PROVIDER = "openai"
_ENV_VAR = "FAKOLI_SPEAK_PROVIDER"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def register(provider: TTSProvider) -> None:
    """Add *provider* to the registry under its :attr:`~TTSProvider.name`.

    Calling :func:`register` with a provider whose name is already present
    will silently overwrite the previous entry, allowing providers to be
    replaced at runtime (e.g., in tests).

    Usage::

        from fakoli_speak.registry import register
        from fakoli_speak.providers.myprovider import MyProvider

        register(MyProvider())

    Args:
        provider: An object that satisfies the :class:`~fakoli_speak.protocol.TTSProvider`
                  protocol.
    """
    _registry[provider.name] = provider
    logger.debug("Registered TTS provider: %s", provider.name)


def get_provider(name: str | None = None) -> TTSProvider:
    """Resolve and return a registered provider.

    Resolution order:
    1. *name* argument (if given and non-empty).
    2. ``FAKOLI_SPEAK_PROVIDER`` environment variable.
    3. Built-in default (``"openai"``).

    Args:
        name: Optional explicit provider name to look up.

    Returns:
        The matching :class:`~fakoli_speak.protocol.TTSProvider` instance.

    Raises:
        KeyError: If the resolved name is not present in the registry.
    """
    resolved = name or os.environ.get(_ENV_VAR) or _DEFAULT_PROVIDER

    if resolved not in _registry:
        available = ", ".join(sorted(_registry)) or "<none>"
        raise KeyError(
            f"TTS provider {resolved!r} is not registered. "
            f"Available providers: {available}"
        )

    return _registry[resolved]


def get_provider_names() -> list[str]:
    """Return a sorted list of all currently registered provider names."""
    return sorted(_registry)


# ---------------------------------------------------------------------------
# Auto-discovery
# ---------------------------------------------------------------------------


def discover_providers() -> None:
    """Import every module inside the ``fakoli_speak.providers`` sub-package.

    Each module is expected to call :func:`register` at import time.
    Import errors are caught and logged as warnings so that a provider that
    requires a platform-specific dependency (e.g., macOS-only ``afplay``)
    does not break the entire import chain on other platforms.
    """
    import fakoli_speak.providers as _providers_pkg  # noqa: PLC0415

    pkg_path = _providers_pkg.__path__
    pkg_name = _providers_pkg.__name__

    for module_info in pkgutil.iter_modules(pkg_path):
        full_name = f"{pkg_name}.{module_info.name}"
        try:
            importlib.import_module(full_name)
            logger.debug("Discovered provider module: %s", full_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Skipping provider module %s — import failed: %s",
                full_name,
                exc,
            )


# ---------------------------------------------------------------------------
# Module initialisation — run discovery automatically on first import
# ---------------------------------------------------------------------------

discover_providers()
