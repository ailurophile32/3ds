"""
差分对比控制器模块

负责协调 DifferenceView 与 TrendModel/HeatmapModel，处理多层对比与差分计算
"""

from typing import List
import numpy as np
from PySide6.QtWidgets import QMessageBox
from matplotlib.figure import Figure
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

from app.view.difference_view import DifferenceView
from app.model.trend_model import TrendModel
from app.model.heatmap_model import HeatmapModel
from app.view.difference_window import DifferenceWindow


class DifferenceController:
    """差分对比控制器"""

    def __init__(self, model: TrendModel, view: DifferenceView, *, heatmap_model: HeatmapModel | None = None, parent=None):
        self.model = model
        self.view = view
        self._heatmap_model = heatmap_model
        self._parent = parent

        # 绑定视图回调
        self.view.on_compare_layers = self.on_compare_layers
        self.view.on_calculate_difference = self.on_calculate_difference

    def set_data_sets(self, data_sets):
        self.model.set_data_sets(data_sets)
        self.view.update_layer_list(data_sets)

    def on_compare_layers(self, indices: List[int]):
        try:
            self.view.clear_comparison_results()
            if len(indices) == 2:
                comparison = self.model.calculate_layer_comparison(indices[0], indices[1])
                if not comparison:
                    QMessageBox.warning(self.view, "错误", "无法计算层间对比数据")
                    return
                self.view.add_comparison_table(comparison)
                self._generate_pairwise_charts(indices[0], indices[1], comparison)
            else:
                comparison = self.model.calculate_multi_layer_comparison(indices)
                if not comparison:
                    QMessageBox.warning(self.view, "错误", "无法计算多层对比数据")
                    return
                self.view.add_comparison_table(comparison)
                self._generate_multi_layer_charts(indices, comparison)
        except Exception as e:
            print(f"差分对比错误: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self.view, "错误", f"差分对比失败: {str(e)}")

    def on_calculate_difference(self, minuend_index: int, subtrahend_index: int):
        try:
            if self._heatmap_model is None:
                QMessageBox.warning(self.view, "错误", "模型未就绪，无法计算差分")
                return
            # 计算差分栅格
            xi, yi, diff = self._heatmap_model.calculate_difference_map(minuend_index, subtrahend_index)
            # 生成内嵌差分图
            fig = self._create_difference_heatmap(xi, yi, diff)
            info = "差分为被减数-减数；色标 0 为白，红/蓝分别代表正/负差。"
            summary = self._build_diff_summary(diff)
            layer1_name = self.model.data_sets[minuend_index][2]
            layer2_name = self.model.data_sets[subtrahend_index][2]
            title = f"差分云图：{layer1_name} - {layer2_name}"
            # 位置：放在差分控件组之后
            self.view.add_chart_after_diff_controls(fig, title, info, summary)
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self.view, "错误", f"计算差分失败: {str(e)}")

    # -------- 绘图 --------
    def _generate_multi_layer_charts(self, indices: List[int], comparison: dict):
        fig1 = self._create_multi_layer_bar_chart(comparison)
        info1 = "分别对比各层的均值、标准差、变异系数与极值范围，定位差异显著的层。"
        summary1 = self._build_multi_bar_summary(comparison)
        self.view.add_chart_below_selector(
            fig1, f"多层统计指标对比 ({len(indices)}层)", info1, summary1
        )

        fig2 = self._create_multi_layer_boxplot(indices)
        info2 = "多层箱线图并列显示，观察多层的分布、离群点与中位数差异。"
        summary2 = self._build_multi_box_summary(indices)
        self.view.add_chart_below_selector(
            fig2, "多层应力分布对比", info2, summary2
        )

        if len(indices) <= 5:
            fig3 = self._create_multi_layer_histogram(indices)
            info3 = "各层直方图以不同颜色叠加，便于比较整体分布形状与位置差异。"
            summary3 = self._build_multi_hist_summary(indices)
            self.view.add_chart_below_selector(
                fig3, "多层应力分布直方图", info3, summary3
            )

    def _create_multi_layer_bar_chart(self, comparison: dict) -> Figure:
        fig = Figure(figsize=(12, 7), constrained_layout=True)
        layers_stats = comparison['layers_stats']
        names = [ (s['file_name'][:15] + '...') if len(s['file_name']) > 15 else s['file_name'] for s in layers_stats ]
        axes = [fig.add_subplot(2, 2, i+1) for i in range(4)]

        means = [s['mean'] for s in layers_stats]
        axes[0].bar(range(len(means)), means, color='steelblue', alpha=0.7)
        axes[0].set_title('均值对比', fontweight='bold'); axes[0].set_ylabel('应力 (MPa)')
        axes[0].set_xticks(range(len(names))); axes[0].set_xticklabels(names, rotation=45, ha='right'); axes[0].grid(True, alpha=0.3, axis='y')

        stds = [s['std'] for s in layers_stats]
        axes[1].bar(range(len(stds)), stds, color='coral', alpha=0.7)
        axes[1].set_title('标准差对比', fontweight='bold'); axes[1].set_ylabel('标准差 (MPa)')
        axes[1].set_xticks(range(len(names))); axes[1].set_xticklabels(names, rotation=45, ha='right'); axes[1].grid(True, alpha=0.3, axis='y')

        cvs = [s['cv'] for s in layers_stats]
        axes[2].bar(range(len(cvs)), cvs, color='mediumseagreen', alpha=0.7)
        axes[2].set_title('变异系数对比', fontweight='bold'); axes[2].set_ylabel('变异系数 (%)')
        axes[2].set_xticks(range(len(names))); axes[2].set_xticklabels(names, rotation=45, ha='right'); axes[2].grid(True, alpha=0.3, axis='y')

        ranges = [s['max'] - s['min'] for s in layers_stats]
        axes[3].bar(range(len(ranges)), ranges, color='orchid', alpha=0.7)
        axes[3].set_title('极值范围对比', fontweight='bold'); axes[3].set_ylabel('极值范围 (MPa)')
        axes[3].set_xticks(range(len(names))); axes[3].set_xticklabels(names, rotation=45, ha='right'); axes[3].grid(True, alpha=0.3, axis='y')
        return fig

    def _create_multi_layer_boxplot(self, indices: List[int]) -> Figure:
        fig = Figure(figsize=(12, 6), constrained_layout=True)
        ax = fig.add_subplot(111)
        data_list = []
        labels = []
        for idx in indices:
            data, _z, file_name = self.model.data_sets[idx]
            if 'Value' in data.columns:
                arr = data['Value'].values
                valid = arr[~np.isnan(arr)]
                data_list.append(valid)
                labels.append(file_name[:20] + '...' if len(file_name) > 20 else file_name)
        bp = ax.boxplot(data_list, labels=labels, patch_artist=True)
        colors = ['lightblue', 'lightcoral', 'lightgreen', 'lightyellow', 'lightpink', 'lightgray']
        for patch, color in zip(bp['boxes'], colors * (len(data_list)//len(colors) + 1)):
            patch.set_facecolor(color); patch.set_alpha(0.7)
        ax.set_ylabel('应力 (MPa)'); ax.set_title('多层应力分布箱线图', fontweight='bold'); ax.grid(True, alpha=0.3, axis='y')
        for lab in ax.get_xticklabels(): lab.set_rotation(45); lab.set_ha('right')
        return fig

    def _create_multi_layer_histogram(self, indices: List[int]) -> Figure:
        fig = Figure(figsize=(12, 6), constrained_layout=True)
        ax = fig.add_subplot(111)
        colors = ['steelblue', 'orange', 'green', 'red', 'purple']
        for i, idx in enumerate(indices):
            data, z_depth, file_name = self.model.data_sets[idx]
            if 'Value' in data.columns:
                vals = data['Value'].values
                valid = vals[~np.isnan(vals)]
                short = file_name[:15] + '...' if len(file_name) > 15 else file_name
                ax.hist(valid, bins=30, alpha=0.5, label=f"{short} (Z={z_depth}μm)", color=colors[i % len(colors)], density=True)
        ax.set_xlabel('应力 (MPa)'); ax.set_ylabel('概率密度'); ax.set_title('多层应力分布叠加直方图'); ax.legend(loc='best', fontsize=9); ax.grid(True, alpha=0.3)
        return fig

    def _generate_pairwise_charts(self, index1: int, index2: int, comparison: dict):
        data1, _, _ = self.model.data_sets[index1]
        data2, _, _ = self.model.data_sets[index2]
        if 'Value' not in data1.columns or 'Value' not in data2.columns:
            return
        s1 = data1['Value'].values; s2 = data2['Value'].values
        v1 = s1[~np.isnan(s1)]; v2 = s2[~np.isnan(s2)]
        fig_dist = self._create_distribution_comparison(v1, v2, comparison)
        info_dist = "两层分布直方图叠加，虚线为各自均值；用于直接比较总体分布与均值差异。"
        summary_dist = self._build_pair_dist_summary(v1, v2, comparison)
        self.view.add_chart_below_selector(
            fig_dist, "应力分布对比", info_dist, summary_dist
        )
        fig_box = self._create_boxplot_comparison(v1, v2, comparison)
        info_box = "两层箱线图并列展示Q1/Q2/Q3与异常值，快速比较离散程度与集中趋势。"
        summary_box = self._build_pair_box_summary(v1, v2, comparison)
        self.view.add_chart_below_selector(
            fig_box, "统计特征对比", info_box, summary_box
        )

    def _create_distribution_comparison(self, s1: np.ndarray, s2: np.ndarray, comparison: dict) -> Figure:
        fig = Figure(figsize=(10, 6), constrained_layout=True)
        ax = fig.add_subplot(111)
        ax.hist(s1, bins=30, alpha=0.6, label=comparison['layer1_name'], color='steelblue', density=True)
        ax.hist(s2, bins=30, alpha=0.6, label=comparison['layer2_name'], color='orange', density=True)
        ax.axvline(comparison['layer1_mean'], color='steelblue', linestyle='--', linewidth=2, label=f"均值1: {comparison['layer1_mean']:.2f}")
        ax.axvline(comparison['layer2_mean'], color='orange', linestyle='--', linewidth=2, label=f"均值2: {comparison['layer2_mean']:.2f}")
        ax.set_xlabel('应力 (MPa)'); ax.set_ylabel('概率密度'); ax.set_title('两层应力分布对比'); ax.legend(loc='best', fontsize=9); ax.grid(True, alpha=0.3)
        return fig

    def _create_boxplot_comparison(self, s1: np.ndarray, s2: np.ndarray, comparison: dict) -> Figure:
        fig = Figure(figsize=(10, 6), constrained_layout=True)
        ax = fig.add_subplot(111)
        bp = ax.boxplot([s1, s2], labels=[comparison['layer1_name'], comparison['layer2_name']], patch_artist=True)
        colors = ['lightblue', 'lightcoral']
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color); patch.set_alpha(0.7)
        if comparison.get('significant'):
            y_max = max(np.max(s1), np.max(s2))
            ax.text(1.5, y_max * 1.05, f"p={comparison['p_value']:.4f} *", ha='center', fontsize=10, color='red', fontweight='bold')
        ax.set_ylabel('应力 (MPa)'); ax.set_title('两层应力统计特征对比'); ax.grid(True, alpha=0.3, axis='y')
        return fig

    # -------- 差分云图（内嵌） --------
    @staticmethod
    def _diverging_cmap() -> LinearSegmentedColormap:
        # 蓝-白-红，确保 0 为白色
        return LinearSegmentedColormap.from_list("diff", ["#2166ac", "#ffffff", "#b2182b"], N=256)

    def _create_difference_heatmap(self, xi, yi, diff) -> Figure:
        fig = Figure(figsize=(10, 6), constrained_layout=True)
        ax = fig.add_subplot(111)
        ax.set_title("差分云图 (0 为白)")
        ax.set_xlabel("X (μm)")
        ax.set_ylabel("Y (μm)")
        norm = TwoSlopeNorm(vmin=float(np.nanmin(diff)), vcenter=0.0, vmax=float(np.nanmax(diff)))
        cmap = self._diverging_cmap()
        pcm = ax.pcolormesh(xi, yi, diff, cmap=cmap, norm=norm, shading="auto")
        cbar = fig.colorbar(pcm, ax=ax)
        cbar.set_label("差分 (MPa)")
        ax.set_aspect("equal", adjustable="box")
        return fig

    def _build_diff_summary(self, diff) -> str:
        try:
            arr = np.array(diff)
            valid = arr[~np.isnan(arr)]
            if valid.size == 0:
                return "结论：差分无有效数据。"
            mean = float(np.mean(valid))
            std = float(np.std(valid, ddof=1)) if valid.size > 1 else 0.0
            vmin = float(np.min(valid)); vmax = float(np.max(valid))
            pos_ratio = float(np.mean(valid > 0)) * 100.0
            neg_ratio = 100.0 - pos_ratio
            direction = "整体偏正" if mean > 0 else ("整体偏负" if mean < 0 else "整体接近零")
            return (
                f"结论：{direction}（均值 {mean:.2f} MPa，σ={std:.2f} MPa），"
                f"范围 [{vmin:.2f}, {vmax:.2f}] MPa；正/负区域 {pos_ratio:.1f}%/{neg_ratio:.1f}%。"
            )
        except Exception:
            return "结论生成失败：输入数据异常。"

    # -------- 结论生成（差分对比） --------
    def _build_pair_dist_summary(self, v1: np.ndarray, v2: np.ndarray, cmp: dict) -> str:
        try:
            m1, m2 = float(np.mean(v1)), float(np.mean(v2))
            std1, std2 = float(np.std(v1, ddof=1)), float(np.std(v2, ddof=1))
            delta = m1 - m2
            direction = "层1均值更高" if delta > 0 else ("层2均值更高" if delta < 0 else "两层均值接近")
            p = float(cmp.get('p_value', 1.0)) if 'p_value' in cmp else 1.0
            sig = "显著" if p < 0.05 else "不显著"
            return (
                f"结论：{direction}（Δ均值={delta:.2f} MPa），波动分别为 {std1:.2f}/{std2:.2f} MPa。"
                f"均值差异统计学上{sig}（p={p:.4f}）。"
            )
        except Exception:
            return "结论生成失败：输入数据异常。"

    def _build_pair_box_summary(self, v1: np.ndarray, v2: np.ndarray, cmp: dict) -> str:
        try:
            q_med = lambda v: float(np.median(v)) if len(v) > 0 else 0.0
            med1, med2 = q_med(v1), q_med(v2)
            iqr1 = float(np.percentile(v1, 75) - np.percentile(v1, 25)) if len(v1) > 0 else 0.0
            iqr2 = float(np.percentile(v2, 75) - np.percentile(v2, 25)) if len(v2) > 0 else 0.0
            direction = "层1中位数更高" if med1 > med2 else ("层2中位数更高" if med2 > med1 else "两层中位数接近")
            sig = "显著" if cmp.get('significant', False) else "不显著"
            return (
                f"结论：{direction}（Q2差={med1 - med2:.2f} MPa）；离散IQR分别为 {iqr1:.2f}/{iqr2:.2f} MPa。"
                f"统计结论{sig}（p={cmp.get('p_value', 1.0):.4f}）。"
            )
        except Exception:
            return "结论生成失败：输入数据异常。"

    def _build_multi_bar_summary(self, comparison: dict) -> str:
        try:
            layers = comparison.get('layers_stats', [])
            if not layers:
                return ""
            import numpy as np
            means = [s['mean'] for s in layers]
            stds = [s['std'] for s in layers]
            max_layer = layers[int(np.argmax(means))]['file_name']
            min_layer = layers[int(np.argmin(means))]['file_name']
            return (
                f"结论：均值最高层为 {max_layer}，最低层为 {min_layer}。"
                f"整体离散（标准差）中位数为 {float(np.median(stds)):.2f} MPa。"
            )
        except Exception:
            return ""

    def _build_multi_box_summary(self, indices: List[int]) -> str:
        try:
            import numpy as np
            iqrs = []
            for idx in indices:
                data, _z, _ = self.model.data_sets[idx]
                if 'Value' in data.columns:
                    v = data['Value'].values
                    v = v[~np.isnan(v)]
                    if len(v) > 0:
                        iqrs.append(float(np.percentile(v, 75) - np.percentile(v, 25)))
            if not iqrs:
                return ""
            level = '较低' if np.median(iqrs) < 0.2 else '中等/偏高'
            return f"结论：各层IQR中位数约 {float(np.median(iqrs)):.2f} MPa，离散程度整体{level}。"
        except Exception:
            return ""

    def _build_multi_hist_summary(self, indices: List[int]) -> str:
        try:
            import numpy as np
            means = []
            for idx in indices:
                data, _z, _ = self.model.data_sets[idx]
                if 'Value' in data.columns:
                    v = data['Value'].values
                    v = v[~np.isnan(v)]
                    if len(v) > 0:
                        means.append(float(np.mean(v)))
            if not means:
                return ""
            spread = float(np.ptp(means))
            flag = '明显' if spread > 5 else '有限'
            return f"结论：各层均值分布跨度约 {spread:.2f} MPa，层间整体水平差异{flag}。"
        except Exception:
            return ""


