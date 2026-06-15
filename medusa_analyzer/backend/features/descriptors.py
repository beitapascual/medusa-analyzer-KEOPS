from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class FeatureDescriptor:
    id: str
    name: str
    category: str
    description: str
    compatible_experiments: tuple[str, ...]
    enabled_by_default_for: tuple[str, ...] = ()
    parameters: dict[str, Any] = field(default_factory=dict)


FEATURES = [
    FeatureDescriptor(
        id="mean",
        name="Mean",
        category="Temporal",
        description="Average signal amplitude.",
        compatible_experiments=("eeg",),
        enabled_by_default_for=("eeg",),
    ),
    FeatureDescriptor(
        id="median",
        name="Median",
        category="Temporal",
        description="Robust central tendency.",
        compatible_experiments=("eeg",),
    ),
    FeatureDescriptor(
        id="variance",
        name="Variance",
        category="Temporal",
        description="Signal amplitude dispersion.",
        compatible_experiments=("eeg",),
        enabled_by_default_for=("eeg",),
    ),
    FeatureDescriptor(
        id="skewness",
        name="Skewness",
        category="Temporal",
        description="Distribution asymmetry.",
        compatible_experiments=("eeg",),
    ),
    FeatureDescriptor(
        id="kurtosis",
        name="Kurtosis",
        category="Temporal",
        description="Distribution tail weight.",
        compatible_experiments=("eeg",),
    ),
    FeatureDescriptor(
        id="power_spectral_density",
        name="PSD",
        category="Spectral",
        description="Power spectral density.",
        compatible_experiments=("eeg",),
        enabled_by_default_for=("eeg",),
    ),
    FeatureDescriptor(
        id="absolute_power",
        name="Absolute power",
        category="Spectral",
        description="Power in each enabled band.",
        compatible_experiments=("eeg",),
        enabled_by_default_for=("eeg",),
    ),
    FeatureDescriptor(
        id="relative_power",
        name="Relative power",
        category="Spectral",
        description="Band power normalized by total power.",
        compatible_experiments=("eeg",),
        enabled_by_default_for=("eeg",),
    ),
    FeatureDescriptor(
        id="median_frequency",
        name="Median frequency",
        category="Spectral",
        description="Frequency dividing spectral power.",
        compatible_experiments=("eeg",),
    ),
    FeatureDescriptor(
        id="spectral_entropy",
        name="Spectral entropy",
        category="Spectral",
        description="Spectral complexity estimate.",
        compatible_experiments=("eeg",),
    ),
    FeatureDescriptor(
        id="lempel_ziv_complexity",
        name="Lempel-Ziv complexity",
        category="Non linear",
        description="Sequence complexity estimate.",
        compatible_experiments=("eeg",),
    ),
    FeatureDescriptor(
        id="ctm",
        name="Central tendency measure",
        category="Non linear",
        description="Variability in phase space.",
        compatible_experiments=("eeg",),
    ),
    FeatureDescriptor(
        id="aec",
        name="AEC",
        category="Connectivity",
        description="Amplitude envelope correlation.",
        compatible_experiments=("eeg",),
    ),
    FeatureDescriptor(
        id="orthogonalized_aec",
        name="Orthogonalized AEC",
        category="Connectivity",
        description="Leakage-reduced AEC.",
        compatible_experiments=("eeg",),
    ),
    FeatureDescriptor(
        id="pli",
        name="PLI",
        category="Connectivity",
        description="Phase lag index.",
        compatible_experiments=("eeg",),
    ),
    FeatureDescriptor(
        id="wpli",
        name="wPLI",
        category="Connectivity",
        description="Weighted phase lag index.",
        compatible_experiments=("eeg",),
    ),
    FeatureDescriptor(
        id="plv",
        name="PLV",
        category="Connectivity",
        description="Phase locking value.",
        compatible_experiments=("eeg",),
    ),
]
