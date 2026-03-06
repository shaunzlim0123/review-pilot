"""@specialist decorator and registry — the Python replacement for TS switch-case dispatch."""

from __future__ import annotations

from collections.abc import Callable

from ...models import Finding

# Specialist function signature: (SpecialistInput) -> list[Finding]
# We use Any here to avoid circular imports with common.py
SpecialistFn = Callable[..., list[Finding]]

_REGISTRY: dict[str, SpecialistFn] = {}


def specialist(name: str) -> Callable[[SpecialistFn], SpecialistFn]:
    """Register a specialist function under the given name."""

    def decorator(fn: SpecialistFn) -> SpecialistFn:
        _REGISTRY[name] = fn
        return fn

    return decorator


def get_specialist(name: str) -> SpecialistFn | None:
    return _REGISTRY.get(name)


def get_all_specialists() -> dict[str, SpecialistFn]:
    return dict(_REGISTRY)
