from collections.abc import Callable
from typing import Any

from .models import ValidationContext, ValidationError

Rule = Callable[[dict[str, Any], ValidationContext], list[ValidationError]]


def _error(field: str, message: str, severity: str = "error") -> list[ValidationError]:
    return [ValidationError(field, message, severity)]


def required(data: dict, context: ValidationContext) -> list[ValidationError]:
    return _error("value", "A value is required.") if data is None else []


def non_negative(data: dict, context: ValidationContext) -> list[ValidationError]:
    for field in ("low_cut", "high_cut"):
        if float(data.get(field, 0)) < 0:
            return _error(field, "Frequency values cannot be negative.")
    return []


def lower_less_than_upper(data: dict, context: ValidationContext) -> list[ValidationError]:
    if float(data["low_cut"]) >= float(data["high_cut"]):
        return _error("high_cut", "Upper frequency must be greater than lower frequency.")
    return []


def upper_below_nyquist(data: dict, context: ValidationContext) -> list[ValidationError]:
    if float(data["high_cut"]) >= context.nyquist:
        return _error("high_cut", f"Upper frequency must be below Nyquist ({context.nyquist:g} Hz).")
    return []


def valid_filter_type(data: dict, context: ValidationContext) -> list[ValidationError]:
    return [] if data.get("filter_type") in {"fir", "iir"} else _error("filter_type", "Use FIR or IIR.")


def valid_fir_order(data: dict, context: ValidationContext) -> list[ValidationError]:
    if data.get("filter_type") != "fir":
        return []
    order = int(data.get("fir_order", 0))
    return [] if order >= 3 and order % 2 == 1 else _error("fir_order", "FIR order must be an odd integer of at least 3.")


def valid_iir_order(data: dict, context: ValidationContext) -> list[ValidationError]:
    if data.get("filter_type") != "iir":
        return []
    order = int(data.get("iir_order", 0))
    return [] if 1 <= order <= 20 else _error("iir_order", "IIR order must be between 1 and 20.")


def valid_window(data: dict, context: ValidationContext) -> list[ValidationError]:
    if data.get("filter_type") != "fir":
        return []
    return [] if data.get("fir_window") in {"hamming", "hann", "blackman"} else _error("fir_window", "Unsupported FIR window.")


def valid_iir_design(data: dict, context: ValidationContext) -> list[ValidationError]:
    if data.get("filter_type") != "iir":
        return []
    return [] if data.get("iir_design") in {"butterworth"} else _error("iir_design", "Unsupported IIR design.")


def band_inside_bandpass_range(data: dict, context: ValidationContext) -> list[ValidationError]:
    if float(data["low_cut"]) < context.global_low_cut or float(data["high_cut"]) > context.global_high_cut:
        return _error("frequency_band", "Enabled band must stay inside the active bandpass range.")
    return []


RULES: dict[str, Rule] = {
    name: rule for name, rule in {
        "required": required, "non_negative": non_negative,
        "lower_less_than_upper": lower_less_than_upper,
        "upper_below_nyquist": upper_below_nyquist,
        "valid_filter_type": valid_filter_type, "valid_fir_order": valid_fir_order,
        "valid_iir_order": valid_iir_order, "valid_window": valid_window,
        "valid_iir_design": valid_iir_design,
        "band_inside_bandpass_range": band_inside_bandpass_range,
    }.items()
}
