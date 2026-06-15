from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ValidationContext:
    fs: float
    nyquist: float
    global_low_cut: float = 0.0
    global_high_cut: float = float("inf")


@dataclass(frozen=True, slots=True)
class ValidationError:
    field: str
    message: str
    severity: str = "error" # for warnings -- severity="warning"


@dataclass(slots=True)
class ValidationReport:
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def extend(self, other: "ValidationReport") -> None:
        # To combine reports
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
