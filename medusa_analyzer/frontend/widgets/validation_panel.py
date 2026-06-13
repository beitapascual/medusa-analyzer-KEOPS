from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from medusa_analyzer.backend.validation.models import ValidationReport


class ValidationPanel(QFrame):
    def __init__(self):
        super().__init__()
        self.setProperty("role", "validation-panel")
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(18, 14, 18, 14)
        self.title = QLabel("Configuration valid")
        self.title.setObjectName("validationTitle")
        self.detail = QLabel("All enabled preprocessing settings are within range.")
        self.detail.setWordWrap(True)
        self.detail.setObjectName("muted")
        self.layout_.addWidget(self.title)
        self.layout_.addWidget(self.detail)

    def set_report(self, report: ValidationReport) -> None:
        self.setProperty("status", "error" if report.errors else "valid")
        self.style().unpolish(self)
        self.style().polish(self)
        if report.errors:
            self.title.setText(f"{len(report.errors)} issue(s) require attention")
            self.detail.setText("\n".join(f"• {item.message}" for item in report.errors))
        elif report.warnings:
            self.title.setText("Configuration valid with warnings")
            self.detail.setText("\n".join(f"• {item.message}" for item in report.warnings))
        else:
            self.title.setText("Configuration valid")
            self.detail.setText("All enabled preprocessing settings are within range.")
