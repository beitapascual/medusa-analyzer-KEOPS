import unittest

from PySide6.QtWidgets import QApplication

from medusa_analyzer.frontend.widgets.step_progress_bar import StepProgressBar


class StepProgressBarStyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_qss_can_override_step_progress_colors(self):
        original_stylesheet = self.app.styleSheet()
        self.addCleanup(self.app.setStyleSheet, original_stylesheet)
        self.app.setStyleSheet(
            """
            QWidget[role="step-progress"] {
                qproperty-lineColor: #123456;
                qproperty-activeStepColor: #654321;
                qproperty-activeLabelColor: #ABCDEF;
                qproperty-lockedLabelColor: #FEDCBA;
            }
            """
        )

        widget = StepProgressBar(["Load", "Pre-process"])
        widget.ensurePolished()
        self.app.processEvents()

        self.assertEqual(widget.property("lineColor").name(), "#123456")
        self.assertEqual(widget.property("activeStepColor").name(), "#654321")
        self.assertEqual(widget.property("activeLabelColor").name(), "#abcdef")
        self.assertEqual(widget.property("lockedLabelColor").name(), "#fedcba")


if __name__ == "__main__":
    unittest.main()
