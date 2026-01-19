import re
from typing import Any

from stream.modules import MODULES


def resolve_import(spec: str) -> Any:
    """
    Resolve <o>::fd::stdout style imports.
    """
    spec = spec.strip()
    m = re.fullmatch(r"<([A-Za-z_]\w*)>(?:::([A-Za-z_]\w*))*", spec)
    if not m:
        raise ValueError(f"Bad import syntax: {spec!r}")

    # Split manually to keep it simple and predictable
    # "<o>::fd::stdout" -> module "o", parts ["fd", "stdout"]
    if not spec.startswith("<") or ">" not in spec:
        raise ValueError(f"Bad import syntax: {spec!r}")

    mod_name = spec[1 : spec.index(">")]
    rest = spec[spec.index(">") + 1 :]
    parts = [p for p in rest.split("::") if p]  # drop empty

    obj = MODULES.get(mod_name)
    if obj is None:
        raise ValueError(f"Unknown module <{mod_name}> in import {spec!r}")

    obj = resolve_parts(obj, parts, spec)
    return obj


def _step(obj: Any, key: str, spec: str) -> Any:
    # 1) If module/object provides an explicit export map, prefer it
    export = getattr(obj, "STREAM_EXPORT", None)
    if isinstance(export, dict) and key in export:
        return export[key]

    # 2) Dict-like traversal
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        raise ValueError(f"Cannot resolve '{key}' in import {spec!r} (missing dict key)")

    # 3) Attribute traversal (modules, namespaces, objects)
    if hasattr(obj, key):
        return getattr(obj, key)

    # 4) Last-resort: mapping protocol (for custom containers)
    try:
        return obj[key]
    except Exception:
        pass

    obj_type = type(obj).__name__
    raise ValueError(f"Cannot resolve '{key}' in import {spec!r} (got {obj_type})")


def resolve_parts(obj: Any, parts: list[str], spec: str) -> Any:
    for p in parts:
        obj = _step(obj, p, spec)
    return obj
