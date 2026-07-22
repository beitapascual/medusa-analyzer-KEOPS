from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QComboBox

from medusa_analyzer.frontend.widgets import LoadDataAction, LoadDataWidget, WorkerCall

from .experiment_bids_validation import load_eeg_bids_dataset


def _metadata_from_group(group: dict[str, Any]) -> dict[str, Any]:
    return {
        "n_recordings": group["n_recordings"],
        "subjects": group["subjects"],
        "sessions": group["sessions"] or ["No session"],
        "datatype": group["datatype"],
        "task": group["task"],
        "sampling_frequency": group["sampling_frequency"],
        "n_channels": group["n_channels"],
        "channel_set": group["channel_set"],
    }


class EEGLoadDataWidget(LoadDataWidget):
    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        del experiment_info
        config = defaults.get("load_data", {})
        self._configuration_groups: list[dict[str, Any]] = []
        super().__init__(
            config=config,
            state=state,
            actions=[LoadDataAction(
                id="bids_dataset",
                label="Select BIDS folder",
                select=lambda widget: widget.select_directory("Select BIDS dataset"),
                build_call=lambda path: WorkerCall(function=load_eeg_bids_dataset, args=(path, config)),
                display_names=lambda path: [Path(path).name or str(path)],
                status_text=lambda path: f"Reading BIDS dataset: {Path(path).name or path}...",
                overlay_text="Validating BIDS dataset...",
            )],
            title="Load EEG BIDS data",
            description="Select a BIDS dataset folder. The loader will use the compatible EEG recording group.",
            metadata_labels={
                "n_recordings": "Recordings",
                "subjects": "Subjects",
                "sessions": "Sessions",
                "datatype": "Datatype",
                "task": "Task",
                "sampling_frequency": "Sampling frequency",
                "n_channels": "Channels",
                "channel_set": "Channel set",
            },
        )

        self.group_combo = QComboBox()
        self.group_combo.currentIndexChanged.connect(self._configuration_selected)
        self.files.parentWidget().layout().insertWidget(1, self.group_combo)
        self.group_combo.hide()

        if self.state.get("selected_recordings"):
            self._show_recordings(self.state["selected_recordings"])

    def _loaded(self, results: dict[str, Any]) -> None:
        if isinstance(self._selected_source, (list, tuple)):
            selected_paths = [str(path) for path in self._selected_source]
        elif self._selected_source is None:
            selected_paths = []
        else:
            selected_paths = [str(self._selected_source)]

        groups = list(results.get("groups") or [])
        self.state["input_data"] = selected_paths
        self.state["loader_results"] = []
        self.state["bids_root"] = results.get("root")
        self.state["bids_groups"] = groups
        self.state.pop("metadata", None)
        self.state.pop("selected_bids_group", None)
        self.state.pop("selected_recordings", None)
        self.state.pop("broadband", None)
        self.metadata_panel.hide()
        self.files.clear()

        self._configuration_groups = groups
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        self.group_combo.addItem("Select recording configuration", None)
        for group in groups:
            self.group_combo.addItem(self._group_label(group), group["id"])
        self.group_combo.blockSignals(False)

        if len(groups) == 1:
            self.group_combo.hide()
            self._apply_group(groups[0])
        elif groups:
            self.group_combo.show()
            self.status_label.setText(f"{len(groups)} recording configuration(s) found. Select one to continue.")
            self.status_label.setProperty("status", "idle")
            self._refresh_status_style()
            self.changed.emit()

    def _configuration_selected(self, _: int) -> None:
        group_id = self.group_combo.currentData()
        if not group_id:
            self.state.pop("metadata", None)
            self.state.pop("selected_bids_group", None)
            self.state.pop("selected_recordings", None)
            self.state.pop("broadband", None)
            self.files.clear()
            self.metadata_panel.hide()
            self.status_label.setText(f"{len(self._configuration_groups)} recording configuration(s) found. Select one to continue.")
            self.status_label.setProperty("status", "idle")
            self._refresh_status_style()
            self.changed.emit()
            return

        group = next((item for item in self._configuration_groups if item.get("id") == group_id), None)
        if group is not None:
            self._apply_group(group)

    def _apply_group(self, group: dict[str, Any]) -> None:
        metadata = _metadata_from_group(group)
        self.state["metadata"] = metadata
        self.state["selected_bids_group"] = group["id"]
        self.state["selected_recordings"] = group["recordings"]

        nyquist = float(metadata["sampling_frequency"]) / 2
        self.state["broadband"] = {"id": "broadband", "title": "Broadband", "enabled": True,
            "low_cut": 0.1, "high_cut": nyquist}
        self.status_label.setText(f"{metadata['n_recordings']} recording(s) selected.")
        self.status_label.setProperty("status", "ready")
        self._refresh_status_style()
        self._show_recordings(group["recordings"])
        self._show_metadata(metadata)
        self.changed.emit()

    def _show_recordings(self, recordings: list[dict[str, Any]]) -> None:
        self.files.clear()
        self.files.addItems([str(recording.get("relative_path") or recording.get("path") or "")
            for recording in recordings])

    @staticmethod
    def _group_label(group: dict[str, Any]) -> str:
        sessions = ",".join(group["sessions"]) if group["sessions"] else "no-session"
        return (f"{group['id']} | {group['n_recordings']} rec | {group['sampling_frequency']:g} Hz | "
            f"{group['reference']} | task {group['task']} | ses {sessions}")

    def _clear_loaded_state(self) -> None:
        super()._clear_loaded_state()
        for key in ("bids_root", "bids_groups", "selected_bids_group", "selected_recordings"):
            self.state.pop(key, None)
        self._configuration_groups = []
        if hasattr(self, "group_combo"):
            self.group_combo.clear()
            self.group_combo.hide()
