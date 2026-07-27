import unittest

from medusa_analyzer.frontend.widgets.filtering import (
    build_filter_defaults,
    compute_filter_response,
    filter_defaults,
    filter_validation_errors,
    filter_response_error,
)


class FilteringTests(unittest.TestCase):
    def test_build_filter_defaults_preserves_active_fir_parameters(self):
        config = {
            "enabled": True,
            "low_cut": 49.0,
            "high_cut": 51.0,
            "filter_type": "bandstop",
            "filter_design": "fir",
            "order": 1000,
            "window": "hamming",
        }

        defaults = build_filter_defaults(config)

        self.assertEqual(defaults["filter_type"], "bandstop")
        self.assertEqual(defaults["filter_design"], "fir")
        self.assertEqual(defaults["order"], 1000)
        self.assertEqual(defaults["window"], "hamming")
        self.assertEqual(
            set(defaults),
            {
                "enabled",
                "low_cut",
                "high_cut",
                "filter_type",
                "filter_design",
                "order",
                "window",
            },
        )

    def test_iir_defaults_do_not_expose_rp_rs_design_parameters(self):
        iir_defaults = filter_defaults["iir"]

        self.assertEqual(
            set(iir_defaults),
            {"default_design", "default_order", "minimum_order", "maximum_order", "designs"},
        )
        for design in iir_defaults["designs"]:
            self.assertEqual(set(design), {"id", "title"})

    def test_compute_filter_response_returns_flat_line_when_disabled(self):
        response = compute_filter_response(
            {
                "enabled": False,
                "low_cut": 49.0,
                "high_cut": 51.0,
                "filter_type": "bandstop",
                "filter_design": "fir",
                "order": 101,
                "window": "hamming",
            },
            fs=512.0,
            mode="bandstop",
        )

        self.assertIsNotNone(response)
        self.assertEqual(response.frequencies, [0.0, 256.0])
        self.assertEqual(response.magnitude_db, [0.0, 0.0])

    def test_invalid_cutoffs_return_none_and_nyquist_error(self):
        config = {
            "enabled": True,
            "low_cut": 10.0,
            "high_cut": 300.0,
            "filter_type": "bandpass",
            "filter_design": "fir",
            "order": 101,
            "window": "hamming",
        }

        response = compute_filter_response(config, fs=500.0, mode="bandpass")

        self.assertIsNone(response)
        self.assertIn("250 Hz", filter_response_error(config, 500.0))

    def test_invalid_iir_window_is_reported_by_validation_layer(self):
        config = {
            "enabled": True,
            "low_cut": 10.0,
            "high_cut": 40.0,
            "filter_type": "bandpass",
            "filter_design": "iir",
            "order": 4,
            "window": "invalid_design",
        }

        errors = filter_validation_errors(config, fs=256.0)

        self.assertEqual(errors, ["Window has an invalid option."])

    def test_frequency_bounds_can_come_from_the_caller(self):
        config = {
            "enabled": True,
            "low_cut": 0.05,
            "high_cut": 40.0,
            "filter_type": "bandpass",
            "filter_design": "fir",
            "order": 101,
            "window": "hamming",
        }

        errors = filter_validation_errors(
            config,
            fs=256.0,
            minimum_frequency=0.1,
            maximum_frequency=45.0,
        )

        self.assertEqual(errors, ["Low cut must be greater than or equal to 0.1 Hz."])


if __name__ == "__main__":
    unittest.main()
