from dataclasses import dataclass

from .features import FeatureSelectionConfig
from .filters import PreprocessingConfig


@dataclass(slots=True)
class EEGAnalysisConfig:
    files: list[str]
    metadata: object
    preprocessing: PreprocessingConfig
    features: FeatureSelectionConfig
