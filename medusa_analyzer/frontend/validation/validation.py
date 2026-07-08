from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


# Esta clase concentra validaciones reutilizables para los widgets del frontend.
# La idea es que el codigo de cada experimento describa "que" quiere validar
# (numero finito, mayor que cero, menor que otro valor, etc.) y no tenga que
# reimplementar cada regla una y otra vez.

ValidationOutcome = "ValidationResult | str | Sequence[str] | None"
ValidationCallable = Callable[..., ValidationOutcome]
RuleSpec = str | tuple[str, dict[str, Any]]


@dataclass(frozen=True, slots=True)
class ValidationResult:
    # Si ok es True la validacion ha pasado. Si no, error contiene el mensaje
    # que se puede enseguida mostrar en la UI.
    ok: bool
    error: str | None = None


class Validation:
    def __init__(self, custom_validators: Mapping[str, ValidationCallable] | None = None):
        self._validators: dict[str, ValidationCallable] = {
            "required_text": self._validate_required_text,
            "no_whitespace": self._validate_no_whitespace,
            "numeric": self._validate_numeric,
            "finite_number": self._validate_finite_number,
            "integer": self._validate_integer,
            "boolean": self._validate_boolean,
            "one_of": self._validate_one_of,
            "greater_than": self._validate_greater_than,
            "greater_or_equal": self._validate_greater_or_equal,
            "less_than": self._validate_less_than,
            "less_or_equal": self._validate_less_or_equal,
            "pattern": self._validate_pattern,
            "minimum_length": self._validate_minimum_length,
            "custom": self._validate_custom,
        }
        for key, validator in (custom_validators or {}).items():
            self.register(key, validator)

    def register(self, key: str, validator: ValidationCallable) -> None:
        # Permite extender el validador desde un workflow concreto sin tocar la
        # lista de reglas genericas.
        self._validators[str(key)] = validator

    def validate(self, value: Any, rule_key: str, *, label: str, **options: Any) -> ValidationResult:
        errors = self.validate_errors(value, rule_key, label=label, **options)
        if not errors:
            return ValidationResult(ok=True)
        return ValidationResult(ok=False, error=errors[0])

    def validate_errors(self, value: Any, rule_key: str, *, label: str, **options: Any) -> list[str]:
        # Variante orientada a coleccionar errores. Es especialmente util para
        # validaciones personalizadas que generan mas de un mensaje.
        validator = self._validators.get(rule_key)
        if validator is None:
            raise KeyError(f"Unknown validation rule: {rule_key}")
        return self._normalize_errors(validator(value, label=label, **options), label)

    def validate_many(self, value: Any, rules: Iterable[RuleSpec], *, label: str,
        stop_on_first_error: bool = True) -> list[str]:
        errors: list[str] = []
        for rule in rules:
            rule_key, options = self._normalize_rule(rule)
            rule_errors = self.validate_errors(value, rule_key, label=label, **options)
            if not rule_errors:
                continue
            errors.extend(rule_errors)
            if stop_on_first_error:
                break
        return errors

    @staticmethod
    def coerce_float(value: Any) -> float:
        if isinstance(value, bool):
            raise ValueError("Boolean values are not numeric.")
        if isinstance(value, (int, float)):
            numeric_value = float(value)
        elif isinstance(value, str):
            text = value.strip()
            if not text:
                raise ValueError("Empty string is not numeric.")
            numeric_value = float(text)
        else:
            raise ValueError("Value is not numeric.")
        if not math.isfinite(numeric_value):
            raise ValueError("Value is not finite.")
        return numeric_value

    @staticmethod
    def coerce_int(value: Any) -> int:
        if isinstance(value, bool):
            raise ValueError("Boolean values are not integers.")
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            if not math.isfinite(value) or not value.is_integer():
                raise ValueError("Value is not an integer.")
            return int(value)
        if isinstance(value, str):
            text = value.strip()
            if not re.fullmatch(r"[+-]?\d+", text):
                raise ValueError("Value is not an integer.")
            return int(text)
        raise ValueError("Value is not an integer.")

    @staticmethod
    def _normalize_rule(rule: RuleSpec) -> tuple[str, dict[str, Any]]:
        if isinstance(rule, str):
            return rule, {}
        rule_key, options = rule
        return rule_key, dict(options)

    @staticmethod
    def _normalize_errors(result: ValidationOutcome, label: str) -> list[str]:
        if isinstance(result, ValidationResult):
            if result.ok:
                return []
            return [result.error or f"{label} is invalid."]
        if result is None:
            return []
        if isinstance(result, str):
            return [result]
        return [str(error) for error in result if error]

    @staticmethod
    def _format_bound(bound: Any, suffix: str = "") -> str:
        if isinstance(bound, (int, float)) and not isinstance(bound, bool):
            text = f"{float(bound):g}"
        else:
            text = str(bound)
        if suffix and not text.endswith(suffix):
            return f"{text}{suffix}"
        return text

    def _validate_required_text(self, value: Any, *, label: str, **_: Any) -> str | None:
        if isinstance(value, str) and value.strip():
            return None
        return f"{label} is required."

    def _validate_no_whitespace(self, value: Any, *, label: str, **_: Any) -> str | None:
        text = str(value or "")
        if any(character.isspace() for character in text):
            return f"{label} must not contain spaces."
        return None

    def _validate_numeric(self, value: Any, *, label: str, **_: Any) -> str | None:
        try:
            self.coerce_float(value)
        except ValueError:
            return f"{label} must be numeric."
        return None

    def _validate_finite_number(self, value: Any, *, label: str, **_: Any) -> str | None:
        try:
            self.coerce_float(value)
        except ValueError as exc:
            if "finite" in str(exc).lower():
                return f"{label} must be a finite number."
            return f"{label} must be numeric."
        return None

    def _validate_integer(self, value: Any, *, label: str, **_: Any) -> str | None:
        try:
            self.coerce_int(value)
        except ValueError:
            return f"{label} must be an integer."
        return None

    def _validate_boolean(self, value: Any, *, label: str, **_: Any) -> str | None:
        if isinstance(value, bool):
            return None
        return f"{label} must be boolean."

    def _validate_one_of(self, value: Any, *, label: str, options: Sequence[Any], **_: Any) -> str | None:
        if value in set(options):
            return None
        return f"{label} has an invalid option."

    def _validate_greater_than(self, value: Any, *, label: str, minimum: Any, suffix: str = "",
        **_: Any) -> str | None:
        try:
            numeric_value = self.coerce_float(value)
            minimum_value = self.coerce_float(minimum)
        except ValueError:
            return f"{label} must be numeric."
        if numeric_value > minimum_value:
            return None
        return f"{label} must be greater than {self._format_bound(minimum_value, suffix)}."

    def _validate_greater_or_equal(self, value: Any, *, label: str, minimum: Any, suffix: str = "",
        **_: Any) -> str | None:
        try:
            numeric_value = self.coerce_float(value)
            minimum_value = self.coerce_float(minimum)
        except ValueError:
            return f"{label} must be numeric."
        if numeric_value >= minimum_value:
            return None
        return f"{label} must be greater than or equal to {self._format_bound(minimum_value, suffix)}."

    def _validate_less_than(self, value: Any, *, label: str, maximum: Any, suffix: str = "",
        **_: Any) -> str | None:
        try:
            numeric_value = self.coerce_float(value)
            maximum_value = self.coerce_float(maximum)
        except ValueError:
            return f"{label} must be numeric."
        if numeric_value < maximum_value:
            return None
        return f"{label} must be lower than {self._format_bound(maximum_value, suffix)}."

    def _validate_less_or_equal(self, value: Any, *, label: str, maximum: Any, suffix: str = "",
        **_: Any) -> str | None:
        try:
            numeric_value = self.coerce_float(value)
            maximum_value = self.coerce_float(maximum)
        except ValueError:
            return f"{label} must be numeric."
        if numeric_value <= maximum_value:
            return None
        return f"{label} must be lower than or equal to {self._format_bound(maximum_value, suffix)}."

    def _validate_pattern(self, value: Any, *, label: str, pattern: str | re.Pattern[str],
        message: str | None = None, **_: Any) -> str | None:
        text = value if isinstance(value, str) else str(value)
        compiled = re.compile(pattern) if isinstance(pattern, str) else pattern
        if compiled.fullmatch(text):
            return None
        return message or f"{label} must match the expected format."

    def _validate_minimum_length(self, value: Any, *, label: str, minimum: int, item_name: str = "item",
        action: str = "contain", **_: Any) -> str | None:
        try:
            current_length = len(value)
        except TypeError:
            current_length = 0
        if current_length >= int(minimum):
            return None

        if action == "select":
            if int(minimum) == 1:
                return f"{label}: select at least one {item_name}."
            return f"{label}: select at least {int(minimum)} {item_name}s."
        return f"{label} must contain at least {int(minimum)} {item_name}(s)."

    def _validate_custom(self, value: Any, *, label: str, validator: ValidationCallable,
        **options: Any) -> ValidationResult | str | None:
        return validator(value, label=label, **options)


__all__ = ["Validation", "ValidationResult", "ValidationCallable", "RuleSpec"]
