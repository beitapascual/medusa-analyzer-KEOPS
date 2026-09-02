from __future__ import annotations

import itertools

import matplotlib.colors as mcolors
import numpy as np
import scipy.io

from .base_plot import BasePlot


class ViolinPlot(BasePlot):
    """
    Violin plot for per-group distributions (Seaborn backend).
    """

    def __init__(self, ax, plot_params=None, tabs_widget=None):
        super().__init__(ax, plot_params, tabs_widget)
        self._group_values = {}

    def load_data(self, filtered_files: dict[str, list[str]], selected_channels: list[int]) -> None:
        self._group_values.clear()

        for group_name, file_list in filtered_files.items():
            subject_values = []

            for filepath in file_list:
                try:
                    mat = scipy.io.loadmat(filepath, squeeze_me=True, struct_as_record=False)
                except Exception as error:
                    print(f"[ERROR] Cannot load {filepath}: {error}")
                    continue

                data = None
                for key in ("data", "vector", "values", "valores", "param"):
                    if key in mat:
                        data = np.asarray(mat[key]).squeeze()
                        break

                if data is None:
                    for value in mat.values():
                        if isinstance(value, np.ndarray) and value.ndim == 1:
                            data = value
                            break

                if data is None:
                    continue

                data = self.normalize_data(data)
                max_idx = data.shape[0] - 1
                valid_channels = [channel for channel in selected_channels if 0 <= channel <= max_idx] or [0]

                value = np.mean(data[valid_channels])
                subject_id = self.extract_subject_id(filepath)
                subject_values.append((subject_id, value))

            if subject_values:
                values = self.aggregate_subject_data(subject_values)
                if values.size > 0:
                    self._group_values[group_name] = values

        current_tab = self.current_tab()
        if current_tab is not None and not hasattr(current_tab, "statistics"):
            self.prepare_stats_data(current_tab)

    def draw(self, colors: dict[str, str] | None = None) -> None:
        self.clear()

        if not self._group_values:
            print("[WARN] No ViolinPlot data to plot.")
            return

        try:
            import pandas as pd
            import seaborn as sns
        except ImportError as error:
            raise ImportError("ViolinPlot requires pandas and seaborn. Install the project requirements.") from error

        # Create a dataframe for seaborn
        df = pd.DataFrame([{"group": group, "value": value}
            for group, values in self._group_values.items()
            for value in values])

        # Obtain colors for each group
        group_order = list(self._group_values.keys())
        violin_alpha = self.plot_params.get("violin_transparency", 0.6)
        palette = None
        if isinstance(colors, dict):
            palette = {group: mcolors.to_rgba(colors.get(group, "#999999"), alpha=violin_alpha)
                for group in group_order}

        # Plot violin
        sns.violinplot(data=df, x="group", y="value", hue="group", order=group_order, ax=self.ax,
            palette=palette, inner=None, cut=2, linewidth=1, saturation=1, zorder=1)

        plot_strip = bool(self.plot_params.get("plot_strip", True))
        if plot_strip:
            # Strip
            sns.stripplot(data=df, x="group", y="value", hue="group", order=group_order, ax=self.ax,
                palette=palette, edgecolor="#000000", linewidth=0.3, size=7, jitter=True, alpha=0.7,
                zorder=10, legend=False)

        plot_boxplot = bool(self.plot_params.get("plot_boxplot", True))
        if plot_boxplot:
            # Boxplot overlay optional
            sns.boxplot(data=df, x="group", y="value", order=group_order, ax=self.ax, width=0.15,
                showcaps=True, showfliers=False, boxprops={"facecolor": "none", "zorder": 20},
                medianprops={"color": "black", "linewidth": 1.5}, whiskerprops={"linewidth": 1},
                capprops={"linewidth": 1, "zorder": 20})

        # ---- Mean / Median lines (optional) ----
        plot_mean = bool(self.plot_params.get("plot_mean_line", False))
        plot_median = bool(self.plot_params.get("plot_median_line", False))
        if plot_mean or plot_median:
            means = df.groupby("group")["value"].mean()
            medians = df.groupby("group")["value"].median()

            half_width = 0.25  # controls line length inside violin
            for index, group in enumerate(group_order):
                if plot_mean and group in means:
                    self.ax.hlines(y=means[group], xmin=index - half_width, xmax=index + half_width,
                        colors="black", linestyles="--", linewidth=1.2, zorder=2)

                if plot_median and group in medians:
                    self.ax.hlines(y=medians[group], xmin=index - half_width, xmax=index + half_width,
                        colors="black", linestyles=":", linewidth=1.2, zorder=2)

        stats_checkbox = bool(self.plot_params.get("plot_stats", False))
        current_tab = self.current_tab()
        if stats_checkbox and current_tab is not None and hasattr(self.tabs_widget, "controller"):
            if "statistical_results" not in current_tab.statistics:
                self.tabs_widget.controller.stats_report(current_tab, skip_report=True)

            pairs = list(itertools.combinations(group_order, 2))
            pairwise_res = current_tab.statistics["statistical_results"]["pairwise"]
            y_max = df["value"].max()
            if pd.isna(y_max):
                return

            y_range = y_max - df["value"].min()
            h_line = y_max + 0.05 * y_range
            step = 0.08 * y_range

            line_count = 0
            for group_a, group_b in pairs:
                result = pairwise_res[(group_a, group_b)]
                p_adj = result["p_values_corr"] if result["p_values_corr"] else result["p_values"]

                if p_adj < 0.05:
                    if p_adj < 0.001:
                        label = "***"
                    elif p_adj < 0.01:
                        label = "**"
                    else:
                        label = "*"

                    x1, x2 = group_order.index(group_a), group_order.index(group_b)
                    curr_h = h_line + (line_count * step)
                    self.ax.plot([x1, x1, x2, x2], [curr_h, curr_h + step * 0.15, curr_h + step * 0.15, curr_h],
                        lw=1.2, c="#222222")
                    self.ax.text((x1 + x2) * 0.5, curr_h + step * 0.15, label, ha="center", va="bottom",
                        color="#222222", fontsize=12)
                    line_count += 1

        self.safe_set_lim("set_ylim", self.plot_params.get("ylim"))
        self.apply_grid_and_spines(axis="y")
        self.save_limits()

    def prepare_stats_data(self, current_tab) -> None:
        groups = []
        data = []
        for group_name, values in self._group_values.items():
            data.extend(values)
            groups.extend([group_name] * len(values))

        current_tab.statistics = {}
        current_tab.statistics["data"] = data
        current_tab.statistics["groups"] = groups
