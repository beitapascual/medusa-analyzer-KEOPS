from __future__ import annotations

import math
from copy import deepcopy
from collections.abc import MutableSequence

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from medusa_analyzer.frontend.widgets.table import EditableTable, TableColumn


def validate_eeg_frequency_bands(
    rows: MutableSequence[dict],
    minimum_frequency: float = 0.1,
    maximum_frequency: float = 10000.0,
) -> list[str]:
    errors: list[str] = []
    for index, row in enumerate(rows, start=1):
        title = str(row.get("title", "")).strip()
        if not title:
            errors.append(f"Row {index}: band name is required.")
        elif any(character.isspace() for character in title):
            errors.append(f"Row {index}: band name must not contain spaces.")

        try:
            low_cut = float(row.get("low_cut", 0.0))
            high_cut = float(row.get("high_cut", 0.0))
        except (TypeError, ValueError):
            errors.append(f"Row {index}: cut values must be numeric.")
            continue

        if not math.isfinite(low_cut) or not math.isfinite(high_cut):
            errors.append(f"Row {index}: cut values must be finite.")
            continue
        if low_cut < minimum_frequency:
            errors.append(
                f"Row {index}: low cut must be greater than or equal to {minimum_frequency:g} Hz."
            )
        if high_cut < minimum_frequency:
            errors.append(
                f"Row {index}: high cut must be greater than or equal to {minimum_frequency:g} Hz."
            )
        if high_cut <= low_cut:
            errors.append(f"Row {index}: high cut must be greater than low cut.")
        if low_cut > maximum_frequency or high_cut > maximum_frequency:
            errors.append(
                f"Row {index}: cut values must be lower than or equal to {maximum_frequency:g} Hz."
            )
    return errors


class EEGFrequencyBandsTable(EditableTable):
    def __init__(
        self,
        rows: MutableSequence[dict],
        default_rows: MutableSequence[dict] | None = None,
        minimum_frequency: float = 0.1,
        maximum_frequency: float = 10000.0,
    ):
        self.minimum_frequency = minimum_frequency
        self.maximum_frequency = maximum_frequency
        default_high_cut = max(self.minimum_frequency + 0.1, 1.0)
        for row in rows:
            self._normalize_row(row)
        self.default_rows = [
            self._normalized_row_copy(row)
            for row in (default_rows if default_rows is not None else rows)
        ]

        columns = [
            TableColumn("enabled", "Enabled", "checkbox", default=True, width=72),
            TableColumn("title", "Band", "text", default="Band"),
            TableColumn(
                "low_cut",
                "From",
                "float",
                default=minimum_frequency,
                minimum=minimum_frequency,
                maximum=maximum_frequency,
                decimals=1,
                suffix=" Hz",
                width=112,
            ),
            TableColumn(
                "high_cut",
                "To",
                "float",
                default=default_high_cut,
                minimum=minimum_frequency,
                maximum=maximum_frequency,
                decimals=1,
                suffix=" Hz",
                width=112,
            ),
        ]

        super().__init__(
            rows,
            columns,
            validator=self._validate_rows,
            row_role="band-chip",
            reorderable=True,
        )
        self.actions = QWidget()
        actions_layout = QHBoxLayout(self.actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        self.add_row_button = QPushButton("Add new row")
        self.add_row_button.setProperty("variant", "secondary")
        self.add_row_button.clicked.connect(self._add_new_row)
        self.reset_button = QPushButton("Reset table")
        self.reset_button.setProperty("variant", "secondary")
        self.reset_button.clicked.connect(self.reset_to_defaults)
        actions_layout.addWidget(self.add_row_button)
        actions_layout.addWidget(self.reset_button)
        actions_layout.addStretch(1)
        self.layout().insertWidget(2, self.actions)
        self.set_frequency_bounds(
            minimum_frequency=self.minimum_frequency,
            maximum_frequency=self.maximum_frequency,
            emit_changed=False,
        )

    def _validate_rows(self, current_rows: MutableSequence[dict]) -> list[str]:
        return validate_eeg_frequency_bands(
            current_rows,
            minimum_frequency=self.minimum_frequency,
            maximum_frequency=self.maximum_frequency,
        )

    def set_frequency_bounds(
        self,
        minimum_frequency: float = 0.1,
        maximum_frequency: float | None = None,
        emit_changed: bool = True,
    ) -> None:
        self.minimum_frequency = float(minimum_frequency)
        if maximum_frequency is not None:
            self.maximum_frequency = max(self.minimum_frequency, float(maximum_frequency))
        else:
            self.maximum_frequency = max(self.minimum_frequency, self.maximum_frequency)

        for widgets_by_key in self.row_widgets:
            for key in ("low_cut", "high_cut"):
                spin = widgets_by_key[key]
                spin.blockSignals(True)
                spin.setMinimum(self.minimum_frequency)
                spin.blockSignals(False)

        self._sync(emit_changed=emit_changed)

    def _add_new_row(self) -> None:
        default_high_cut = min(
            self.maximum_frequency,
            max(self.minimum_frequency + 0.1, 1.0),
        )
        widgets = self.append_row(
            {
                "enabled": True,
                "id": "",
                "title": "",
                "low_cut": self.minimum_frequency,
                "high_cut": default_high_cut,
            }
        )
        widgets["title"].setFocus()

    def reset_to_defaults(self) -> None:
        self.replace_rows(
            [self._normalized_row_copy(row) for row in self.default_rows],
            emit_changed=False,
        )
        self.set_frequency_bounds(
            minimum_frequency=self.minimum_frequency,
            maximum_frequency=self.maximum_frequency,
            emit_changed=True,
        )
        if self.row_widgets:
            self.row_widgets[0]["title"].setFocus()

    def _normalized_row_copy(self, row: dict) -> dict:
        return self._normalize_row(deepcopy(row))

    def _normalize_row(self, row: dict) -> dict:
        default_high_cut = max(self.minimum_frequency + 0.1, 1.0)
        row["enabled"] = bool(row.get("enabled", True))
        row["title"] = str(row.get("title") or row.get("id") or "Band")
        row["low_cut"] = float(
            row.get("low_cut", self.minimum_frequency)
        )
        row["high_cut"] = float(
            row.get("high_cut", default_high_cut)
        )
        return row


__all__ = ["EEGFrequencyBandsTable", "validate_eeg_frequency_bands"]
