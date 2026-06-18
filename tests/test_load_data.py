import unittest

from PySide6.QtWidgets import QApplication

from medusa_analyzer.frontend.models import MetadataSummary
from medusa_analyzer.frontend.widgets.load_data import LoadDataWidget, _load_files


def _fake_result(path: str, sampling_rate: float = 1000.0) -> dict:
    return {
        "name": path,
        "path": path,
        "channels": ["C3", "C4"],
        "sampling_rate": sampling_rate,
        "duration_seconds": 2.0,
        "n_samples": 2000,
    }


class LoadDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_load_files_preserves_order_and_aggregates_progress(self):
        progress = []

        def loader(path, progress_callback):
            progress_callback(0)
            progress_callback(100)
            return _fake_result(path)

        results = _load_files(
            loader,
            ["first.edf", "second.edf"],
            progress.append,
        )

        self.assertEqual(
            [result["name"] for result in results],
            ["first.edf", "second.edf"],
        )
        self.assertEqual(progress, [0, 50, 50, 100])

    def test_loaded_batch_is_stored_only_as_collections(self):
        state = {}
        widget = LoadDataWidget(
            config={"allowed_extensions": [".edf"]},
            state=state,
            loader=lambda path, progress_callback: _fake_result(path),
            title="Load data",
            description="Test",
        )
        results = [_fake_result("first.edf"), _fake_result("second.edf")]

        widget._loaded(results)

        self.assertEqual(state["loaded_file_paths"], ["first.edf", "second.edf"])
        self.assertEqual(len(state["loader_results"]), 2)
        self.assertEqual(
            [metadata.file_name for metadata in state["metadata_list"]],
            ["first.edf", "second.edf"],
        )
        self.assertNotIn("loaded_file_path", state)
        self.assertNotIn("loader_result", state)
        self.assertNotIn("metadata", state)
        self.assertTrue(widget.can_continue())

    def test_clear_loaded_state_disables_continue(self):
        state = {
            "loaded_file_paths": ["first.edf"],
            "loader_results": [_fake_result("first.edf")],
            "metadata_list": [MetadataSummary.from_loader_result(_fake_result("first.edf"))],
            "loaded_file_path": "first.edf",
            "loader_result": _fake_result("first.edf"),
            "metadata": MetadataSummary.from_loader_result(_fake_result("first.edf")),
        }
        widget = LoadDataWidget(
            config={},
            state=state,
            loader=lambda path, progress_callback: _fake_result(path),
            title="Load data",
            description="Test",
        )

        widget._clear_loaded_state()

        self.assertFalse(widget.can_continue())
        self.assertEqual(state["loaded_file_paths"], [])
        self.assertEqual(state["loader_results"], [])
        self.assertEqual(state["metadata_list"], [])
        self.assertNotIn("loaded_file_path", state)
        self.assertNotIn("loader_result", state)
        self.assertNotIn("metadata", state)

    def test_widget_scrolls_when_loaded_content_exceeds_available_height(self):
        state = {}
        widget = LoadDataWidget(
            config={"allowed_extensions": [".edf"]},
            state=state,
            loader=lambda path, progress_callback: _fake_result(path),
            title="Load data",
            description="Test",
        )
        widget._loaded([_fake_result("first.edf"), _fake_result("second.edf")])
        widget.resize(700, 220)
        widget.show()
        self.app.processEvents()

        self.assertTrue(widget.status_label.wordWrap())
        self.assertGreater(widget.verticalScrollBar().maximum(), 0)


if __name__ == "__main__":
    unittest.main()
