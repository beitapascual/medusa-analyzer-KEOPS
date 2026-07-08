import unittest

from PySide6.QtWidgets import QApplication

from medusa_analyzer.frontend.widgets.load_data import LoadDataAction, LoadDataWidget, WorkerCall, load_files


def _fake_result(path: str, sampling_frequency: float = 1000.0) -> dict:
    return {"name": path, "sampling_frequency": sampling_frequency}


def _metadata(results, selection):
    del selection
    first = results[0] if isinstance(results, list) and results else {}
    return {"recordings": len(results), "sampling_frequency": first.get("sampling_frequency")}


class LoadDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_load_files_runs_loader_for_first_selection(self):
        progress = []

        def loader(path, progress_callback):
            progress_callback(25)
            return _fake_result(path)

        results = load_files(loader, ["first.edf", "second.edf"], progress_callback=progress.append)

        self.assertEqual(results, [_fake_result("first.edf")])
        self.assertEqual(progress, [25, 100])

    def test_loaded_batch_is_stored_as_current_state(self):
        state = {}
        widget = LoadDataWidget(
            config={"allowed_extensions": [".edf"]},
            state=state,
            actions=[LoadDataAction(
                id="test",
                label="Load",
                select=lambda _: ["first.edf", "second.edf"],
                build_call=lambda paths: WorkerCall(function=lambda: []),
                display_names=lambda paths: paths,
                status_text="Loading",
            )],
            title="Load data",
            description="Test",
            metadata_labels={"recordings": "Recordings", "sampling_frequency": "Sampling frequency"},
            metadata_builder=_metadata,
        )
        widget._selected_source = ["first.edf", "second.edf"]

        widget._loaded([_fake_result("first.edf"), _fake_result("second.edf")])

        self.assertEqual(state["input_data"], ["first.edf", "second.edf"])
        self.assertEqual(len(state["loader_results"]), 2)
        self.assertEqual(state["metadata"], {"recordings": 2, "sampling_frequency": 1000.0})
        self.assertTrue(widget.can_continue())

    def test_clear_loaded_state_disables_continue(self):
        state = {
            "input_data": ["first.edf"],
            "loader_results": [_fake_result("first.edf")],
            "metadata": {"recordings": 1, "sampling_frequency": 1000.0},
            "broadband": {"id": "broadband"},
        }
        widget = LoadDataWidget(
            config={},
            state=state,
            actions=[LoadDataAction(
                id="test",
                label="Load",
                select=lambda _: ["first.edf"],
                build_call=lambda paths: WorkerCall(function=lambda: []),
                display_names=lambda paths: paths,
                status_text="Loading",
            )],
            title="Load data",
            description="Test",
            metadata_labels={"recordings": "Recordings", "sampling_frequency": "Sampling frequency"},
            metadata_builder=_metadata,
        )

        widget._clear_loaded_state()

        self.assertFalse(widget.can_continue())
        self.assertEqual(state["input_data"], [])
        self.assertEqual(state["loader_results"], [])
        self.assertNotIn("metadata", state)
        self.assertNotIn("broadband", state)


if __name__ == "__main__":
    unittest.main()
