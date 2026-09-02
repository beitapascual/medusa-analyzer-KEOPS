from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any

import numpy as np
from matplotlib.axes import Axes


class BasePlot(ABC):
    """
    Abstract base class for plot types.
    Provides a standard interface for plotting and shared utilities.
    """

    subject_pattern = r"sub-([^\\/]+)"

    def __init__(self, ax: Axes, plot_params: dict[str, Any] | None = None, tabs_widget: Any = None):
        self.ax = ax
        self.plot_params = plot_params or {}
        self.last_limits = {} # save info from the last draw
        self.tabs_widget = tabs_widget

    @abstractmethod
    def load_data(self, *args, **kwargs) -> None:
        """Load and preprocess data specific to the plot type."""

    @abstractmethod
    def draw(self, colors: dict[str, str] | None = None) -> None:
        """Render the plot on the assigned Axes."""

    def clear(self) -> None:
        """Clear the current axis."""
        self.ax.clear()
        self.apply_labels()
        self.apply_title()

    def apply_labels(self) -> None:
        font_size = self.plot_params.get("font_size", 10)
        font_weight = self.plot_params.get("font_weight", "normal")
        self.ax.set_xlabel(self.plot_params.get("x_label", ""), fontsize=font_size, fontweight=font_weight)
        self.ax.set_ylabel(self.plot_params.get("y_label", ""), fontsize=font_size, fontweight=font_weight)

    def apply_title(self) -> None:
        title = self.plot_params.get("title", "")
        if not title:
            return
        self.ax.set_title(title, fontsize=self.plot_params.get("title_size", 12),
            fontweight=self.plot_params.get("title_weight", "bold"))

    def apply_grid_and_spines(self, axis: str = "both") -> None:
        self.ax.grid(True, axis=axis, linestyle="--", alpha=0.4)
        self.ax.spines["top"].set_visible(False)
        self.ax.spines["right"].set_visible(False)

    def safe_set_lim(self, method: str, lim) -> None:
        if not isinstance(lim, (list, tuple)) or len(lim) != 2:
            return

        lo, hi = lim
        if lo is None and hi is None:
            return

        try:
            ax_method = getattr(self.ax, method)
            cur_lo, cur_hi = ax_method()
            ax_method([lo if lo is not None else cur_lo, hi if hi is not None else cur_hi])
        except Exception as error:
            print(f"[WARN] Could not apply {method}: {error}")

    def save_limits(self) -> None:
        self.last_limits = {"xlim": list(map(float, self.ax.get_xlim())), "ylim": list(map(float, self.ax.get_ylim()))}

    def get_last_limits(self) -> dict[str, list[float]]:
        return self.last_limits

    def normalize_data(self, data) -> np.ndarray | None:
        """
        Normalize data to shape (channels,) or (times, channels).
        Accepted shapes:
        - (channels,)
        - (1, channels)
        - (epochs, channels)
        - (epochs, times, channels)
        """

        if data is None:
            return None

        data = np.asarray(data)
        if data.ndim == 1:
            return data
        if data.ndim == 2:
            if data.shape[0] == 1:
                return data.squeeze()
            return np.mean(data, axis=0) # shape: epochs x channels
        if data.ndim == 3:
            return np.mean(data, axis=0) # shape: times x channels

        raise ValueError(f"[BasePlot] Unsupported data shape: {data.shape}")

    def normalize_data_psd(self, values) -> np.ndarray:
        """
        Normalize PSD data to shape (freqs, channels).
        Accepted shapes:
        - (freqs, channels)
        - (channels, freqs)
        - (epochs, freqs, channels)
        """

        values = np.asarray(values)
        if values.ndim == 2:
            return values
        if values.ndim == 3:
            return np.mean(values, axis=0)

        raise ValueError(f"[PSDPlot] Unsupported PSD shape: {values.shape}")

    def aggregate_subject_data(self, subject_data) -> np.ndarray:
        """
        Receives a list of tuples:
            [(subject_id, value), (subject_id, value), ...]

        where value can be:
        - a scalar
        - a 1D array / signal
        """

        grouped = defaultdict(list)
        for subject_id, value in subject_data:
            if value is None:
                continue

            arr = np.asarray(value).squeeze()
            if arr.ndim > 1 or arr.size == 0:
                continue

            grouped[subject_id].append(arr)

        if not grouped:
            return np.array([])

        first_subject_values = next(iter(grouped.values()))
        first_value = np.asarray(first_subject_values[0]).squeeze()
        if first_value.ndim == 0:
            return np.array([np.mean([float(value) for value in values]) for values in grouped.values()],
                dtype=float)

        per_subject = []
        for values in grouped.values():
            min_len = min(np.asarray(value).shape[0] for value in values)
            aligned = np.array([np.asarray(value)[:min_len] for value in values])
            mean_subject_signal = np.mean(aligned, axis=0)
            per_subject.append(mean_subject_signal)

        min_len = min(signal.shape[0] for signal in per_subject)
        return np.array([signal[:min_len] for signal in per_subject])

    def extract_subject_id(self, filepath: str) -> str:
        match = re.search(self.subject_pattern, filepath)
        if match:
            return match.group(1)
        return os.path.basename(filepath)

    def current_tab(self):
        if self.tabs_widget is None or not hasattr(self.tabs_widget, "tab_widgets"):
            return None
        return next((tab for tab in self.tabs_widget.tab_widgets if getattr(tab, "_plot", None) is self), None)
