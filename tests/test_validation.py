import unittest

from medusa_analyzer.frontend.validation import Validation


class ValidationTests(unittest.TestCase):
    def test_reusable_numeric_rules_validate_bounds(self):
        validation = Validation()

        ok_result = validation.validate(12.5, "less_than", label="High cut", maximum=20, suffix=" Hz")
        error_result = validation.validate(25.0, "less_or_equal", label="High cut", maximum=20, suffix=" Hz")

        self.assertTrue(ok_result.ok)
        self.assertFalse(error_result.ok)
        self.assertEqual(error_result.error, "High cut must be lower than or equal to 20 Hz.")

    def test_minimum_length_select_message_is_generic(self):
        validation = Validation()

        result = validation.validate([], "minimum_length", label="Relative band power", minimum=1,
            item_name="frequency band", action="select")

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "Relative band power: select at least one frequency band.")

    def test_custom_validation_can_be_passed_per_call(self):
        validation = Validation()

        def odd_integer_only(value, *, label, **_):
            if int(value) % 2 == 1:
                return None
            return f"{label} must be odd."

        ok_result = validation.validate(5, "custom", label="FIR order", validator=odd_integer_only)
        error_result = validation.validate(6, "custom", label="FIR order", validator=odd_integer_only)

        self.assertTrue(ok_result.ok)
        self.assertFalse(error_result.ok)
        self.assertEqual(error_result.error, "FIR order must be odd.")

    def test_custom_validation_can_return_multiple_errors(self):
        validation = Validation()

        def validator(_value, *, label, **_):
            return [f"{label} first error.", f"{label} second error."]

        errors = validation.validate_errors("value", "custom", label="Field", validator=validator)
        result = validation.validate("value", "custom", label="Field", validator=validator)

        self.assertEqual(errors, ["Field first error.", "Field second error."])
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "Field first error.")


if __name__ == "__main__":
    unittest.main()
