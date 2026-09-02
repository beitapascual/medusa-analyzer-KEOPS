from __future__ import annotations

import os
import re

import numpy as np
import scipy.io
from .base_plot import BasePlot

class ScatterPlot(BasePlot):
    """
    Scatter plot:
    X = selected secondary parameter
    Y = tab parameter
    One point per subject, colored by group
    """

    def __init__(self, ax, plot_params=None, tabs_widget=None):
        super().__init__(ax, plot_params, tabs_widget)
        self._points = {}  # group -> (x_vals, y_vals)

    def load_data(self, filtered_files_y: dict[str, list[str]], filtered_files_x: dict[str, list[str]],
        selected_channels: list[int]) -> None:

        self._points.clear()
        for group, files_y in filtered_files_y.items():
            files_x = filtered_files_x.get(group, [])
            if not files_x:
                continue

            subject_points = {}
            files_x_map = {self._base_name(filepath): filepath for filepath in files_x}

            for filepath_y in files_y:
                key = self._base_name(filepath_y)
                filepath_x = files_x_map.get(key)
                if filepath_x is None:
                    continue

                y_value = self._load_scalar(filepath_y, selected_channels)
                x_value = self._load_scalar(filepath_x, selected_channels)
                if x_value is None or y_value is None:
                    continue

                subject_id = self.extract_subject_id(filepath_y)
                subject_points.setdefault(subject_id, []).append((x_value, y_value))

            if not subject_points:
                continue

            x_vals = []
            y_vals = []
            for points in subject_points.values():
                points_arr = np.asarray(points, dtype=float)
                if points_arr.ndim != 2 or points_arr.shape[1] != 2:
                    continue

                x_vals.append(np.mean(points_arr[:, 0]))
                y_vals.append(np.mean(points_arr[:, 1]))

            if x_vals and y_vals:
                self._points[group] = (np.asarray(x_vals), np.asarray(y_vals))

    def draw(self, colors: dict[str, str] | None = None) -> None:
        self.clear()

        if not self._points:
            print("[WARN] No scatter data to plot.")
            return

        size = self.plot_params.get("marker_size", 60)
        alpha = self.plot_params.get("alpha", 0.8)

        for group, (x_values, y_values) in self._points.items():
            color = colors.get(group) if isinstance(colors, dict) else None
            self.ax.scatter(x_values, y_values, s=size, alpha=alpha, label=group, color=color)

        if self.plot_params.get("show_line", False):
            all_x = np.concatenate([values[0] for values in self._points.values()])
            all_y = np.concatenate([values[1] for values in self._points.values()])

            if len(all_x) > 1:
                coeffs = np.polyfit(all_x, all_y, 1)
                x_line = np.linspace(all_x.min(), all_x.max(), 100)
                y_line = coeffs[0] * x_line + coeffs[1]
                self.ax.plot(x_line, y_line, linestyle="-", linewidth=1, color="red")

        self.ax.legend(frameon=False)
        self.safe_set_lim("set_xlim", self.plot_params.get("xlim"))
        self.safe_set_lim("set_ylim", self.plot_params.get("ylim"))
        self.apply_grid_and_spines(axis="y")
        self.save_limits()

    # ---------- helpers ----------

    def _load_scalar(self, filepath: str, selected_channels: list[int]) -> float | None:
        try:
            mat = scipy.io.loadmat(filepath, squeeze_me=True, struct_as_record=False)
        except Exception:
            return None

        data = None
        for key in ("param", "vector", "values", "valores"):
            if key in mat:
                data = np.asarray(mat[key]).squeeze()
                break
        if data is None:
            return None

        data = self.normalize_data(data)
        if data is None:
            return None

        if selected_channels:
            try:
                data = data[selected_channels]
            except Exception:
                return None

        return float(np.mean(data))

    def _base_name(self, filepath: str) -> str:
        name = os.path.basename(filepath)
        name = re.sub(r"_param-[^_]+", "", name) # remove param info
        name = re.sub(r"_band-[^_]+", "", name) # remove band info
        return name
