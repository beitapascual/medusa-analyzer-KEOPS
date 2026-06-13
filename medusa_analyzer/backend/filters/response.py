from dataclasses import dataclass
import math

from medusa_analyzer.backend.configs.filters import FilterConfig


@dataclass(frozen=True, slots=True)
class FilterResponse:
    frequencies: list[float]
    magnitude_db: list[float]


def _mock_response(config: FilterConfig, fs: float) -> FilterResponse:
    frequencies = [fs * 0.5 * index / 255 for index in range(256)]
    transition = max((config.high_cut - config.low_cut) * 0.12, fs / 1000, 0.1)
    values: list[float] = []
    is_notch = config.low_cut > 20 and (config.high_cut - config.low_cut) < 10
    for frequency in frequencies:
        if is_notch:
            distance = min(abs(frequency - config.low_cut), abs(frequency - config.high_cut))
            inside = config.low_cut <= frequency <= config.high_cut
            value = -55.0 if inside else -30.0 * math.exp(-distance / transition)
        else:
            low_gain = 1 / (1 + math.exp(-(frequency - config.low_cut) / transition))
            high_gain = 1 / (1 + math.exp((frequency - config.high_cut) / transition))
            value = 20 * math.log10(max(low_gain * high_gain, 1e-4))
        values.append(max(-80.0, value))
    return FilterResponse(frequencies, values)


def compute_filter_response(config: FilterConfig, fs: float) -> FilterResponse:
    if not config.enabled:
        return FilterResponse([0.0, fs / 2], [0.0, 0.0])
    try:
        import numpy as np
        from scipy import signal
        if config.filter_type == "fir":
            pass_zero = "bandstop" if config.low_cut > 20 and config.high_cut - config.low_cut < 10 else False
            coefficients = signal.firwin(
                config.fir_order, [config.low_cut, config.high_cut],
                pass_zero=pass_zero, fs=fs, window=config.fir_window,
            )
            frequencies, response = signal.freqz(coefficients, worN=1024, fs=fs)
        else:
            kind = "bandstop" if config.low_cut > 20 and config.high_cut - config.low_cut < 10 else "bandpass"
            coefficients = signal.butter(
                config.iir_order, [config.low_cut, config.high_cut],
                btype=kind, fs=fs, output="sos",
            )
            frequencies, response = signal.sosfreqz(coefficients, worN=1024, fs=fs)
        magnitude = 20 * np.log10(np.maximum(np.abs(response), 1e-8))
        return FilterResponse(frequencies.tolist(), magnitude.tolist())
    except (ImportError, ValueError):
        return _mock_response(config, fs)
