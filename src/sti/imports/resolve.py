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

    mod_name = spec[1:spec.index(">")]
    rest = spec[spec.index(">") + 1:]
    parts = [p for p in rest.split("::") if p]  # drop empty

    obj = MODULES.get(mod_name)
    if obj is None:
        raise ValueError(f"Unknown module <{mod_name}> in import {spec!r}")

    for p in parts:
        if isinstance(obj, dict) and p in obj:
            obj = obj[p]
        else:
            raise ValueError(f"Cannot resolve '{p}' in import {spec!r}")

    return obj
