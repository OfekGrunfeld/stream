import sys
from typing import Any


def stdout(value: Any) -> None:
    print(value, flush=True, file=sys.stdout)
