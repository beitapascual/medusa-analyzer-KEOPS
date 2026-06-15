from dataclasses import dataclass

import numpy as np
from scipy import signal

from medusa_analyzer.backend.configs.filters import FilterConfig


@dataclass(frozen=True, slots=True)
class FilterResponse:
    frequencies: list[float]
    magnitude_db: list[float]


def compute_filter_response(config: FilterConfig, fs: float) -> FilterResponse:
    if not config.enabled:
        return FilterResponse([0.0, fs / 2], [0.0, 0.0])

    is_notch = config.low_cut > 20 and config.high_cut - config.low_cut < 10
    if config.filter_type == "fir":
        coefficients = signal.firwin(
            config.fir_order,
            [config.low_cut, config.high_cut],
            pass_zero="bandstop" if is_notch else False,
            fs=fs,
            window=config.fir_window,
        )
        frequencies, response = signal.freqz(coefficients, worN=1024, fs=fs)
    else:
        iir_kwargs = {}
        if config.iir_design in {"cheby1", "ellip"}:
            iir_kwargs["rp"] = config.iir_rp_db
        if config.iir_design in {"cheby2", "ellip"}:
            iir_kwargs["rs"] = config.iir_rs_db

        coefficients = signal.iirfilter(
            config.iir_order,
            [config.low_cut, config.high_cut],
            btype="bandstop" if is_notch else "bandpass",
            fs=fs,
            ftype=config.iir_design,
            output="sos",
            **iir_kwargs,
        )
        frequencies, response = signal.sosfreqz(coefficients, worN=1024, fs=fs)

    magnitude = 20 * np.log10(np.maximum(np.abs(response), 1e-8))
    return FilterResponse(frequencies.tolist(), magnitude.tolist())
