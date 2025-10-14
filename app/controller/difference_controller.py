"""
差分对比控制器模块

负责协调 DifferenceView 与 TrendModel/HeatmapModel，处理多层对比与差分计算
"""

from typing import List
import numpy as np
from PySide6.QtWidgets import QMessageBox
from matplotlib.figure import Figure

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
            xi, yi, diff = self._heatmap_model.calculate_difference_map(minuend_index, subtrahend_index)
            win = DifferenceWindow(
                parent=self.view,
                xi_grid=xi,
                yi_grid=yi,
                diff_values=diff,
                title="差分云图 (被减数 - 减数)"
            )
            win.show()
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self.view, "错误", f"计算差分失败: {str(e)}")

    # -------- 绘图 --------
    def _generate_multi_layer_charts(self, indices: List[int], comparison: dict):
        fig1 = self._create_multi_layer_bar_chart(comparison)
        self.view.add_chart_below_selector(fig1, f"多层统计指标对比 ({len(indices)}层)")

        fig2 = self._create_multi_layer_boxplot(indices)
        self.view.add_chart_below_selector(fig2, "多层应力分布对比")

        if len(indices) <= 5:
            fig3 = self._create_multi_layer_histogram(indices)
            self.view.add_chart_below_selector(fig3, "多层应力分布直方图")

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
        self.view.add_chart_below_selector(self._create_distribution_comparison(v1, v2, comparison), "应力分布对比")
        self.view.add_chart_below_selector(self._create_boxplot_comparison(v1, v2, comparison), "统计特征对比")

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


