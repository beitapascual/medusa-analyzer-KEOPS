from dataclasses import dataclass, field


@dataclass(slots=True)
class FeatureSelectionConfig:
    selected_feature_ids: list[str] = field(default_factory=list)
