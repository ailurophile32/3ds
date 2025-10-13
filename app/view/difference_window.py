"""
差分云图窗口

用于显示两层数据差分的2D云图（发散色标，0 为白）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFormLayout,
    QDoubleSpinBox, QFileDialog, QWidget, QGroupBox
)
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm


@dataclass
class DifferenceStats:
    min_value: float
    max_value: float
    mean_value: float
    std_value: float
    count: int

    @staticmethod
    def from_array(arr: np.ndarray) -> "DifferenceStats":
        valid = arr[~np.isnan(arr)]
        if valid.size == 0:
            return DifferenceStats(np.nan, np.nan, np.nan, np.nan, 0)
        return DifferenceStats(
            float(np.min(valid)),
            float(np.max(valid)),
            float(np.mean(valid)),
            float(np.std(valid)),
            int(valid.size),
        )


class DifferenceWindow(QDialog):
    """差分结果展示窗口（2D Matplotlib）"""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        xi_grid: np.ndarray,
        yi_grid: np.ndarray,
        diff_values: np.ndarray,
        title: str = "差分云图",
        vlimit: Optional[Tuple[float, float]] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(False)
        self.resize(900, 700)

        self._xi = xi_grid
        self._yi = yi_grid
        self._diff = diff_values

        self._stats = DifferenceStats.from_array(diff_values)

        # 计算对称范围（若未指定）
        if vlimit is None:
            vmax = np.nanmax(np.abs(self._diff)) if np.isfinite(self._diff).any() else 1.0
            vmin = -vmax
        else:
            vmin, vmax = vlimit
        self._vmin = float(vmin)
        self._vmax = float(vmax)

        self._init_ui()
        self._render()

    # -------- UI 构建 --------
    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        # 顶部统计区域
        stats_group = QGroupBox("差分统计信息")
        form = QFormLayout(stats_group)
        self.label_range = QLabel()
        self.label_mean = QLabel()
        self.label_std = QLabel()
        self.label_count = QLabel()
        form.addRow("范围(MPa):", self.label_range)
        form.addRow("均值(MPa):", self.label_mean)
        form.addRow("标准差(MPa):", self.label_std)
        form.addRow("数据点数:", self.label_count)
        layout.addWidget(stats_group)

        # 画布
        self.figure = Figure(figsize=(6, 5), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas, 1)

        # 底部控制栏
        controls = QHBoxLayout()
        controls.addWidget(QLabel("显示范围:"))
        self.vmin_spin = QDoubleSpinBox()
        self.vmin_spin.setRange(-1e6, 1e6)
        self.vmin_spin.setDecimals(3)
        self.vmin_spin.setValue(self._vmin)
        self.vmin_spin.valueChanged.connect(self._on_vlimit_changed)
        controls.addWidget(self.vmin_spin)

        self.vmax_spin = QDoubleSpinBox()
        self.vmax_spin.setRange(-1e6, 1e6)
        self.vmax_spin.setDecimals(3)
        self.vmax_spin.setValue(self._vmax)
        self.vmax_spin.valueChanged.connect(self._on_vlimit_changed)
        controls.addWidget(self.vmax_spin)

        self.btn_symmetric = QPushButton("对称±max")
        self.btn_symmetric.clicked.connect(self._on_symmetric_clicked)
        controls.addWidget(self.btn_symmetric)

        controls.addStretch()

        self.btn_save = QPushButton("保存图像…")
        self.btn_save.clicked.connect(self._on_save_clicked)
        controls.addWidget(self.btn_save)

        layout.addLayout(controls)

        self._update_stats_labels()

    # -------- 渲染逻辑 --------
    @staticmethod
    def _diverging_cmap() -> LinearSegmentedColormap:
        # 蓝-白-红，确保 0 为白色
        return LinearSegmentedColormap.from_list("diff", ["#2166ac", "#ffffff", "#b2182b"], N=256)

    def _render(self) -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_title("差分云图 (0 为白)")
        ax.set_xlabel("X (μm)")
        ax.set_ylabel("Y (μm)")

        # 使用 TwoSlopeNorm 让 0 对应中点
        norm = TwoSlopeNorm(vmin=self._vmin, vcenter=0.0, vmax=self._vmax)
        cmap = self._diverging_cmap()

        # pcolormesh 要求网格为 2D，diff 与网格维度匹配
        pcm = ax.pcolormesh(self._xi, self._yi, self._diff, cmap=cmap, norm=norm, shading="auto")
        cbar = self.figure.colorbar(pcm, ax=ax)
        cbar.set_label("差分 (MPa)")

        ax.set_aspect("equal", adjustable="box")
        self.canvas.draw_idle()

    def _update_stats_labels(self) -> None:
        self.label_range.setText(f"{self._stats.min_value:.3f}  ~  {self._stats.max_value:.3f}")
        self.label_mean.setText(f"{self._stats.mean_value:.3f}")
        self.label_std.setText(f"{self._stats.std_value:.3f}")
        self.label_count.setText(f"{self._stats.count}")

    # -------- 事件处理 --------
    def _on_vlimit_changed(self, _value: float) -> None:
        vmin = self.vmin_spin.value()
        vmax = self.vmax_spin.value()
        if vmin >= vmax:
            return
        self._vmin, self._vmax = float(vmin), float(vmax)
        self._render()

    def _on_symmetric_clicked(self) -> None:
        vmax = float(np.nanmax(np.abs(self._diff))) if np.isfinite(self._diff).any() else 1.0
        self.vmin_spin.blockSignals(True)
        self.vmax_spin.blockSignals(True)
        self.vmin_spin.setValue(-vmax)
        self.vmax_spin.setValue(vmax)
        self.vmin_spin.blockSignals(False)
        self.vmax_spin.blockSignals(False)
        self._vmin, self._vmax = -vmax, vmax
        self._render()

    def _on_save_clicked(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(self, "保存差分云图", "difference_map.png", "PNG (*.png);;PDF (*.pdf);;SVG (*.svg)")
        if not file_path:
            return
        try:
            self.figure.savefig(file_path, dpi=200)
        except Exception as e:
            # 轻量提示，复用父窗口的消息处理策略由外部决定
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "保存失败", f"无法保存图像: {e}")
