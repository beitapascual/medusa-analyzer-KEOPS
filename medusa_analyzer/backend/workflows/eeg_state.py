from dataclasses import dataclass, field

from medusa_analyzer.backend.configs.features import FeatureSelectionConfig
from medusa_analyzer.backend.configs.filters import PreprocessingConfig
from medusa_analyzer.backend.validation.models import ValidationReport


@dataclass(frozen=True, slots=True)
class RecordingMetadata:
    n_files: int
    fs: float
    nyquist: float
    n_channels: int
    duration_seconds: float
    frequency_range: tuple[float, float]


@dataclass(slots=True)
class EEGWorkflowState:
    selected_files: list[str] = field(default_factory=list)
    metadata: RecordingMetadata | None = None
    preprocessing_config: PreprocessingConfig = field(default_factory=PreprocessingConfig)
    feature_config: FeatureSelectionConfig = field(default_factory=FeatureSelectionConfig)
    validation_report: ValidationReport = field(default_factory=ValidationReport)
    current_step: str = "load"
