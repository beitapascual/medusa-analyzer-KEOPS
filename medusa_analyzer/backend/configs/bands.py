from dataclasses import dataclass


@dataclass(slots=True)
class FrequencyBandConfig:
    name: str
    low_cut: float
    high_cut: float
    enabled: bool = True


def get_default_eeg_bands() -> list[FrequencyBandConfig]:
    return [
        FrequencyBandConfig("Delta", 1.0, 4.0),
        FrequencyBandConfig("Theta", 4.0, 8.0),
        FrequencyBandConfig("Alpha", 8.0, 13.0),
        FrequencyBandConfig("Beta", 13.0, 30.0),
        FrequencyBandConfig("Gamma", 30.0, 60.0),
    ]
