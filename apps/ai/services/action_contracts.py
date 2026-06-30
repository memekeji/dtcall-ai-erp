from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AIActionRequest:
    resource: str
    operation: str
    object_ids: list[Any] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    changes: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AIActionResult:
    success: bool
    message: str = ''
    data: dict[str, Any] = field(default_factory=dict)
