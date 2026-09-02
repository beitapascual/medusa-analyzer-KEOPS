from __future__ import annotations

import numpy as np
import scipy.io

from .base_plot import BasePlot


class ERPPlot(BasePlot):
    """
    Plot of Event-Related Potentials (ERP).

    For each group:
    - Average epochs if present
    - Average selected channels
    - Average files by subject
    """

    def __init__(self, ax, plot_params=None, tabs_widget=None):
        super().__init__(ax, plot_params, tabs_widget)
        self._group_erps = {}
        self._time_vector = None

    def load_data(self, filtered_files: dict[str, list[str]], selected_channels: list[int]) -> None:
        self._group_erps.clear()
        self._time_vector = None

        # Loop to iterate through groups
        for group_name, file_list in filtered_files.items():
            subject_signals = []

            # Loop to iterate through all files for each group
            for filepath in file_list:
                try:
                    mat = scipy.io.loadmat(filepath, squeeze_me=True, struct_as_record=False)
                except Exception as error:
                    print(f"[ERROR] Cannot load .mat file {filepath}: {error}")
                    continue

                data = None
                if "epochs" in mat:
                    data = np.asarray(mat["epochs"])
                if data is None:
                    print(f"[WARN] No ERP data found in {filepath}")
                    continue

                data = self.normalize_data(data)
                if data.ndim != 2:
                    print(f"Only one trial available in {filepath}. Skipping")
                    continue

                _, n_channels = data.shape
                valid_channels = [channel for channel in selected_channels if 0 <= channel < n_channels]
                if not valid_channels:
                    valid_channels = [0]

                signal = np.mean(data[:, valid_channels], axis=1)
                subject_id = self.extract_subject_id(filepath)
                subject_signals.append((subject_id, signal))

            if not subject_signals:
                continue

            signals = self.aggregate_subject_data(subject_signals)
            if signals.size == 0:
                continue

            mean_signal = np.mean(signals, axis=0)
            std_signal = np.std(signals, axis=0)
            n_subjects = signals.shape[0]
            self._group_erps[group_name] = {"mean": mean_signal, "std": std_signal, "n": n_subjects,
                "all": signals}

            if self._time_vector is None:
                window = self.plot_params.get("_time_window")
                if window is not None:
                    start, end = window
                    self._time_vector = np.linspace(start, end, signals.shape[1])

        current_tab = self.current_tab() or self.tabs_widget
        if current_tab is not None and not hasattr(current_tab, "statistics"):
            self.prepare_stats_data(current_tab)

    def draw(self, colors: dict[str, str] | None = None) -> None:
        self.clear()

        if not self._group_erps:
            print("[WARN] No ERP data to plot.")
            return

        line_width = self.plot_params.get("line_width", 2)
        line_style = self.plot_params.get("line_style", "solid")
        plot_error = self.plot_params.get("plot_error", False)

        for group_name, data in self._group_erps.items():
            mean = data["mean"]
            std = data["std"]
            n_subjects = data["n"]
            color = colors.get(group_name) if isinstance(colors, dict) else None
            time_values = self._time_vector if self._time_vector is not None else np.arange(mean.size)

            self.ax.plot(time_values, mean, label=group_name, linewidth=line_width, linestyle=line_style,
                color=color)
            if plot_error and n_subjects > 1:
                ci = 1.96 * (std / np.sqrt(n_subjects))
                self.ax.fill_between(time_values, mean - ci, mean + ci, color=color, alpha=0.25)

        # Vertical zero-line
        if self._time_vector is not None and self._time_vector[0] <= 0 <= self._time_vector[-1]:
            self.ax.axvline(0, color="gray", linestyle="--", linewidth=1, alpha=0.8)

        stats_checkbox = bool(self.plot_params.get("plot_stats", False))
        current_tab = self.current_tab() or self.tabs_widget
        controller = getattr(self.tabs_widget, "controller", None) or getattr(current_tab, "controller", None)
        if stats_checkbox and current_tab is not None and controller is not None:
            if "statistical_results" not in current_tab.statistics:
                controller.stats_report(current_tab, is_continuous=True)

            p_vals = current_tab.statistics["statistical_results"]
            time_values = self._time_vector if self._time_vector is not None else np.arange(len(p_vals))
            self.ax.fill_between(time_values, 0, 1, where=(p_vals < 0.05), color="gray", alpha=0.3,
                transform=self.ax.get_xaxis_transform(), zorder=0, label="p < 0.05")

        self.ax.legend(frameon=False)
        self.safe_set_lim("set_xlim", self.plot_params.get("xlim"))
        self.safe_set_lim("set_ylim", self.plot_params.get("ylim"))
        self.apply_grid_and_spines(axis="both")
        self.save_limits()

    def prepare_stats_data(self, current_tab) -> None:
        groups = []
        data = []
        for group_name, values in self._group_erps.items():
            data.extend(values["all"])
            groups.extend([group_name] * values["all"].shape[0])

        current_tab.statistics = {}
        current_tab.statistics["data"] = data
        current_tab.statistics["groups"] = groups
