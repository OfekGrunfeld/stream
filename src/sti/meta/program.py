from typing import Any, Callable, Dict, Tuple

from pydantic import BaseModel


class Program(BaseModel):
    season: str | None
    drift: str | None
    gyges: Dict[str, Callable[[Any], Any]]
    spring_pipeline: Tuple[str, str]
