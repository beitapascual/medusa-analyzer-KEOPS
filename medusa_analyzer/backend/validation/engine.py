from dataclasses import asdict, is_dataclass
from typing import Any

from .models import ValidationContext, ValidationReport
from .rules import RULES
from .schemas import VALIDATION_SCHEMAS


class ValidationEngine:

    def validate(self, target: str, data: Any, context: ValidationContext) -> ValidationReport:
        # 1. Comprueba que target exista.
        # 2. Convierte dataclass a dict con asdict().
        # 3. Si enabled es False, devuelve informe válido.
        # 4. Lee la lista de reglas del schema.
        # 5. Busca cada función en RULES.
        # 6. Ejecuta la regla.
        # 7. Separa errors y warnings.
        # 8. Devuelve ValidationReport.

        if target not in VALIDATION_SCHEMAS:
            raise ValueError(f"Unknown validation target: {target}")
        values = asdict(data) if is_dataclass(data) else dict(data)
        report = ValidationReport()
        if values.get("enabled") is False:
            return report
        for rule_name in VALIDATION_SCHEMAS[target]:
            for issue in RULES[rule_name](values, context):
                (report.warnings if issue.severity == "warning" else report.errors).append(issue)
        return report
