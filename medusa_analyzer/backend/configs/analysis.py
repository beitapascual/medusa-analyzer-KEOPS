from dataclasses import dataclass

from .features import FeatureSelectionConfig
from .filters import PreprocessingConfig


# Final object that contain all necessary data for future 'run pipeline'
# Build when 'process' is pushed
# It's a DTO: data transfer object
@dataclass(slots=True)
class EEGAnalysisConfig:
    files: list[str]
    metadata: object
    preprocessing: PreprocessingConfig
    features: FeatureSelectionConfig
