import unittest

from PySide6.QtWidgets import QApplication

from medusa_analyzer.frontend.widgets.filtering import FilterPreviewPlot
from medusa_analyzer.frontend.widgets.plots import LinePlot


class FilterPreviewPlotStyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_qss_can_override_generic_plot_colors(self):
        original_stylesheet = self.app.styleSheet()
        self.addCleanup(self.app.setStyleSheet, original_stylesheet)
        self.app.setStyleSheet(
            """
            QFrame[role="plot"] {
                qproperty-plotBackgroundColor: #112233;
                qproperty-gridColor: #223344;
                qproperty-axisLineColor: #334455;
                qproperty-axisTextColor: #445566;
                qproperty-responseLineColor: #556677;
                qproperty-emptyMessageColor: #667788;
            }
            """
        )

        widget = LinePlot()
        widget.ensurePolished()
        self.app.processEvents()

        self.assertEqual(widget.property("plotBackgroundColor").name(), "#112233")
        self.assertEqual(widget.property("gridColor").name(), "#223344")
        self.assertEqual(widget.property("axisLineColor").name(), "#334455")
        self.assertEqual(widget.property("axisTextColor").name(), "#445566")
        self.assertEqual(widget.property("responseLineColor").name(), "#556677")
        self.assertEqual(widget.property("emptyMessageColor").name(), "#667788")

    def test_filter_plot_keeps_default_frequency_axis_label(self):
        widget = FilterPreviewPlot()

        self.assertEqual(widget.x_axis_label, "Frequency (Hz)")

    def test_generic_plot_can_hide_x_axis_label(self):
        widget = LinePlot(x_axis_label=None)

        self.assertIsNone(widget.x_axis_label)


if __name__ == "__main__":
    unittest.main()
