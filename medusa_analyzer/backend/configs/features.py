from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class FeatureDescriptor:
    id: str
    name: str
    category: str
    description: str
    enabled_by_default: bool = False
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FeatureSelectionConfig:
    selected_feature_ids: list[str] = field(default_factory=list)
