from collections.abc import Callable
from typing import Any

from pydantic import BaseModel


class Program(BaseModel):
    season: str | None
    drift: str | None
    gyges: dict[str, Callable[[Any], Any]]
    spring_pipeline: tuple[str, str]
