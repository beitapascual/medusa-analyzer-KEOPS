VALIDATION_SCHEMAS = {
    "notch_filter": [
        "non_negative", "lower_less_than_upper", "upper_below_nyquist",
        "valid_filter_type", "valid_fir_order", "valid_iir_order",
        "valid_window", "valid_iir_design",
    ],
    "bandpass_filter": [
        "non_negative", "lower_less_than_upper", "upper_below_nyquist",
        "valid_filter_type", "valid_fir_order", "valid_iir_order",
        "valid_window", "valid_iir_design",
    ],
    "frequency_band": [
        "non_negative", "lower_less_than_upper", "upper_below_nyquist",
        "band_inside_bandpass_range",
    ],
}
