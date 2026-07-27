import unittest

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QSpinBox,
)

from medusa_analyzer.frontend.widgets.table import EditableTable, TableColumn


class EditableTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_table_updates_rows_in_place_for_supported_column_kinds(self):
        rows = [{}]
        columns = [
            TableColumn("enabled", "Enabled", "checkbox", default=True),
            TableColumn("name", "Name", "text", default="alpha"),
            TableColumn("gain", "Gain", "float", default=1.5, minimum=0.0, maximum=10.0),
            TableColumn("count", "Count", "int", default=2, minimum=0, maximum=10),
            TableColumn(
                "mode",
                "Mode",
                "choice",
                default="auto",
                options=[("auto", "Auto"), ("manual", "Manual")],
            ),
            TableColumn("summary", "Summary", "label", default="ready"),
        ]

        table = EditableTable(rows, columns)
        widgets = table.row_widgets[0]

        self.assertIsInstance(widgets["enabled"], QCheckBox)
        self.assertIsInstance(widgets["name"], QLineEdit)
        self.assertIsInstance(widgets["gain"], QDoubleSpinBox)
        self.assertIsInstance(widgets["count"], QSpinBox)
        self.assertIsInstance(widgets["mode"], QComboBox)
        self.assertIsInstance(widgets["summary"], QLabel)
        self.assertEqual(rows[0]["name"], "alpha")

        widgets["enabled"].setChecked(False)
        widgets["name"].setText("beta")
        widgets["gain"].setValue(2.5)
        widgets["count"].setValue(4)
        widgets["mode"].setCurrentIndex(1)
        self.app.processEvents()

        self.assertFalse(rows[0]["enabled"])
        self.assertEqual(rows[0]["name"], "beta")
        self.assertEqual(rows[0]["gain"], 2.5)
        self.assertEqual(rows[0]["count"], 4)
        self.assertEqual(rows[0]["mode"], "manual")
        self.assertEqual(rows[0]["summary"], "ready")

    def test_table_runs_validator_and_exposes_errors(self):
        rows = [{"name": "alpha"}]
        columns = [TableColumn("name", "Name", "text", default="alpha")]
        states: list[bool] = []

        def validator(current_rows):
            return [] if current_rows[0]["name"] else ["Name is required."]

        table = EditableTable(rows, columns, validator=validator)
        table.validation_changed.connect(states.append)

        self.assertTrue(table.is_valid())
        table.row_widgets[0]["name"].setText("")
        self.app.processEvents()

        self.assertFalse(table.is_valid())
        self.assertEqual(table.validation_errors(), ["Name is required."])
        self.assertIn("Name is required.", table.error_label.text())
        self.assertEqual(states[-1], False)

    def test_append_row_adds_widgets_and_updates_rows(self):
        rows = [{"name": "alpha"}]
        table = EditableTable(rows, [TableColumn("name", "Name", "text", default="")])

        widgets = table.append_row({"name": "beta"})
        self.app.processEvents()

        self.assertEqual(len(rows), 2)
        self.assertEqual(len(table.row_widgets), 2)
        self.assertEqual(rows[1]["name"], "beta")
        self.assertIs(widgets, table.row_widgets[1])

    def test_move_row_reorders_rows_and_widgets(self):
        rows = [{"name": "alpha"}, {"name": "beta"}, {"name": "gamma"}]
        table = EditableTable(
            rows,
            [TableColumn("name", "Name", "text", default="")],
            reorderable=True,
        )

        table.move_row(0, 3)
        self.app.processEvents()

        self.assertEqual([row["name"] for row in rows], ["beta", "gamma", "alpha"])
        self.assertEqual(table.row_widgets[0]["name"].text(), "beta")
        self.assertEqual(table.row_widgets[2]["name"].text(), "alpha")

    def test_reorderable_table_encodes_drag_payload_for_own_rows(self):
        rows = [{"name": "alpha"}, {"name": "beta"}]
        table = EditableTable(
            rows,
            [TableColumn("name", "Name", "text", default="")],
            reorderable=True,
        )

        mime_data = table._build_row_mime_data(1)

        self.assertEqual(table._decode_row_mime_data(mime_data), 1)

        other_table = EditableTable(
            [{"name": "gamma"}],
            [TableColumn("name", "Name", "text", default="")],
            reorderable=True,
        )
        self.assertIsNone(other_table._decode_row_mime_data(mime_data))


if __name__ == "__main__":
    unittest.main()
