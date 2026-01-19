import pkgutil
from importlib import import_module
from typing import Any

# Map Python module names -> language module keys
ALIASES: dict[str, str] = {"self": "o"}


def _discover_modules() -> dict[str, Any]:
    modules: dict[str, Any] = {}

    # Iterate over stream.modules.* submodules
    for m in pkgutil.iter_modules(__path__):
        name = m.name
        if name.startswith("_"):
            continue

        mod = import_module(f"{__name__}.{name}")

        # What do we expose?
        # - If module defines STREAM_EXPORT, use that (e.g., STREAM_EXPORT = fd)
        # - Else expose the module object itself
        exported = getattr(mod, "___export___", mod)

        key = ALIASES.get(name, name)
        modules[key] = exported

    return modules


MODULES: dict[str, Any] = _discover_modules()

__all__ = ["MODULES", "ALIASES"]
