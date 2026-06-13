from dataclasses import dataclass, field

from .bands import FrequencyBandConfig, get_default_eeg_bands


@dataclass(slots=True)
class FilterConfig:
    enabled: bool
    low_cut: float
    high_cut: float
    filter_type: str = "fir"
    fir_order: int = 1001
    fir_window: str = "hamming"
    iir_order: int = 4
    iir_design: str = "butterworth"


@dataclass(slots=True)
class NotchFilterConfig(FilterConfig):
    enabled: bool = False
    low_cut: float = 49.0
    high_cut: float = 51.0


@dataclass(slots=True)
class BandpassFilterConfig(FilterConfig):
    enabled: bool = True
    low_cut: float = 0.5
    high_cut: float = 60.0


@dataclass(slots=True)
class PreprocessingConfig:
    apply_car: bool = False
    notch: NotchFilterConfig = field(default_factory=NotchFilterConfig)
    bandpass: BandpassFilterConfig = field(default_factory=BandpassFilterConfig)
    frequency_bands: list[FrequencyBandConfig] = field(default_factory=get_default_eeg_bands)
