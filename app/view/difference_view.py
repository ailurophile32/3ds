"""
差分对比视图模块

提供多层数据选择对比与差分分析界面
"""

from typing import List, Dict, Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QPushButton, QScrollArea,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QListWidget, QAbstractItemView, QListWidgetItem, QSizePolicy, QLayout,
    QComboBox, QAbstractScrollArea, QToolTip
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class DifferenceView(QWidget):
    """差分对比视图组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._datasets = []  # [(data, z_depth, file_name), ...]
        self._checked_indices = set()

        # 回调函数
        self.on_compare_layers = None
        self.on_calculate_difference = None

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.NoFrame)

        content_widget = QWidget()
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setSpacing(12)

        self.placeholder_label = QLabel("请加载多层数据以进行差分与对比分析")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #7f8c8d; font-size: 14px;")
        self.content_layout.addWidget(self.placeholder_label)

        # 选择对比层
        self.layer_selection_group = QGroupBox("选择对比层")
        self.layer_selection_group.setFlat(True)
        self.layer_selection_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.layer_selection_group.setStyleSheet(
            """
            QGroupBox { padding-top: 6px; margin-top: 2px; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0px 2px; }
            """
        )
        layer_selection_layout = QVBoxLayout(self.layer_selection_group)
        layer_selection_layout.setContentsMargins(8, 10, 8, 8)
        layer_selection_layout.setSpacing(4)
        layer_selection_layout.setSizeConstraint(QLayout.SetMinimumSize)

        tools_bar = QHBoxLayout()
        self.select_all_button = QPushButton("全选")
        self.select_all_button.clicked.connect(self._on_select_all)
        tools_bar.addWidget(self.select_all_button)
        self.invert_selection_button = QPushButton("反选")
        self.invert_selection_button.clicked.connect(self._on_invert_selection)
        tools_bar.addWidget(self.invert_selection_button)
        self.deselect_all_button = QPushButton("清空")
        self.deselect_all_button.clicked.connect(self._on_deselect_all)
        tools_bar.addWidget(self.deselect_all_button)
        self.selection_count_label = QLabel("已选 0/0")
        self.selection_count_label.setStyleSheet("color:#7f8c8d;")
        tools_bar.addWidget(self.selection_count_label)
        tools_bar.addStretch()
        layer_selection_layout.addLayout(tools_bar)

        self.layer_list = QListWidget()
        self.layer_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.layer_list.setMinimumHeight(72)
        self.layer_list.setMaximumHeight(140)
        self.layer_list.setStyleSheet("QListWidget { padding: 0px; margin: 0px; }")
        self.layer_list.itemChanged.connect(self._on_item_changed)
        layer_selection_layout.addWidget(self.layer_list)

        action_bar = QHBoxLayout()
        action_bar.addStretch()
        self.compare_button = QPushButton("开始多层对比")
        self.compare_button.setObjectName("PrimaryButton")
        self.compare_button.clicked.connect(self._on_compare_clicked)
        self.compare_button.setEnabled(False)
        self.compare_button.setCursor(Qt.PointingHandCursor)
        self.compare_button.setStyleSheet(
            "#PrimaryButton { background-color: #2d7ff9; color: #ffffff; border: 1px solid #1b66c9; border-radius: 4px; padding: 6px 12px; font-weight: bold; }"
            "#PrimaryButton:hover:!disabled { background-color: #256de5; }"
            "#PrimaryButton:pressed:!disabled { background-color: #1f5dc4; }"
            "#PrimaryButton:disabled { background-color: #e0e0e0; color: #8c8c8c; border-color: #cccccc; }"
        )
        action_bar.addWidget(self.compare_button)
        layer_selection_layout.addLayout(action_bar)

        self.content_layout.addWidget(self.layer_selection_group)

        # 差分云图控制区
        self.diff_group = QGroupBox("差分云图")
        self.diff_group.setFlat(True)
        diff_layout = QHBoxLayout(self.diff_group)
        diff_layout.setContentsMargins(8, 8, 8, 8)

        self.diff_minuend_combo = QComboBox()
        self.diff_subtrahend_combo = QComboBox()
        self.diff_button = QPushButton("计算差分")
        self.diff_button.setEnabled(False)
        self.diff_button.clicked.connect(self._on_calculate_difference_clicked)

        diff_layout.addWidget(QLabel("被减数:"))
        diff_layout.addWidget(self.diff_minuend_combo)
        diff_layout.addWidget(QLabel("减数:"))
        diff_layout.addWidget(self.diff_subtrahend_combo)
        diff_layout.addStretch()
        diff_layout.addWidget(self.diff_button)

        self.content_layout.addWidget(self.diff_group)

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

    # ===== 公共接口 =====
    def update_layer_list(self, datasets: list):
        self._datasets = datasets or []
        if len(self._datasets) >= 2:
            self._checked_indices = set(range(len(self._datasets)))
        else:
            self._checked_indices = set()
        self._refresh_layer_items()
        self._update_compare_button_state()
        self._populate_diff_controls()

    def clear_comparison_results(self):
        if not hasattr(self, 'layer_selection_group') or not self.layer_selection_group:
            return
        selector_index = self.content_layout.indexOf(self.layer_selection_group)
        for i in reversed(range(self.content_layout.count())):
            if i > selector_index:
                item = self.content_layout.itemAt(i)
                widget = item.widget()
                if widget and widget not in (self.diff_group,):
                    widget.setParent(None)
                    widget.deleteLater()
        # 确保差分分组在底部
        if self.content_layout.indexOf(self.diff_group) == -1:
            self.content_layout.addWidget(self.diff_group)

    def add_chart_below_selector(self, fig: Figure, title: str, info_text: str | None = None, summary_text: str | None = None):
        if hasattr(self, 'placeholder_label') and self.placeholder_label:
            self.placeholder_label.deleteLater()
            self.placeholder_label = None

        chart_frame = QFrame()
        chart_frame.setFrameStyle(QFrame.Box)
        chart_frame.setStyleSheet("QFrame { border: 1px solid #ddd; border-radius: 4px; background: white; }")
        chart_layout = QVBoxLayout(chart_frame)
        chart_layout.setContentsMargins(8, 8, 8, 8)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #2c3e50;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        if info_text:
            info_button = QPushButton("i")
            info_button.setFixedSize(20, 20)
            info_button.setStyleSheet("""
            QPushButton {
                border: 2px solid #ccc;
                border-radius: 10px;
                background-color: #f8f8f8;
                font-size: 11px;
                font-weight: bold;
                color: #666;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
                border-color: #999;
                color: #333;
            }
            """)
            header_layout.addWidget(info_button)
            def _show_tip():
                global_pos = info_button.mapToGlobal(info_button.rect().bottomRight())
                QToolTip.showText(global_pos, info_text, info_button)
            info_button.clicked.connect(_show_tip)
        chart_layout.addLayout(header_layout)

        canvas = FigureCanvas(fig)
        canvas.setMinimumHeight(300)
        chart_layout.addWidget(canvas)

        # 图表下方结论文本（可选）
        if summary_text:
            summary_label = QLabel(summary_text)
            summary_label.setWordWrap(True)
            summary_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            summary_label.setStyleSheet(
                "color: #2c3e50; background: #f7f9fc; border: 1px solid #e8eaf0;"
                "border-radius: 4px; padding: 10px; font-size: 12px;"
            )
            chart_layout.addWidget(summary_label)

        if hasattr(self, 'layer_selection_group') and self.layer_selection_group:
            insert_index = self.content_layout.indexOf(self.layer_selection_group)
            if insert_index == -1:
                self.content_layout.addWidget(chart_frame)
            else:
                self.content_layout.insertWidget(insert_index + 1, chart_frame)
        else:
            self.content_layout.addWidget(chart_frame)

    def add_chart_after_diff_controls(self, fig: Figure, title: str, info_text: str | None = None, summary_text: str | None = None):
        if hasattr(self, 'placeholder_label') and self.placeholder_label:
            self.placeholder_label.deleteLater()
            self.placeholder_label = None

        chart_frame = QFrame()
        chart_frame.setFrameStyle(QFrame.Box)
        chart_frame.setStyleSheet("QFrame { border: 1px solid #ddd; border-radius: 4px; background: white; }")
        chart_layout = QVBoxLayout(chart_frame)
        chart_layout.setContentsMargins(8, 8, 8, 8)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #2c3e50;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        if info_text:
            info_button = QPushButton("i")
            info_button.setFixedSize(20, 20)
            info_button.setStyleSheet("""
            QPushButton {
                border: 2px solid #ccc;
                border-radius: 10px;
                background-color: #f8f8f8;
                font-size: 11px;
                font-weight: bold;
                color: #666;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
                border-color: #999;
                color: #333;
            }
            """)
            header_layout.addWidget(info_button)
            def _show_tip():
                global_pos = info_button.mapToGlobal(info_button.rect().bottomRight())
                QToolTip.showText(global_pos, info_text, info_button)
            info_button.clicked.connect(_show_tip)
        chart_layout.addLayout(header_layout)

        canvas = FigureCanvas(fig)
        canvas.setMinimumHeight(300)
        chart_layout.addWidget(canvas)

        if summary_text:
            summary_label = QLabel(summary_text)
            summary_label.setWordWrap(True)
            summary_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            summary_label.setStyleSheet(
                "color: #2c3e50; background: #f7f9fc; border: 1px solid #e8eaf0;"
                "border-radius: 4px; padding: 10px; font-size: 12px;"
            )
            chart_layout.addWidget(summary_label)

        # 放在差分控件组之后（最后）
        if hasattr(self, 'diff_group') and self.diff_group:
            insert_index = self.content_layout.indexOf(self.diff_group)
            if insert_index == -1:
                self.content_layout.addWidget(chart_frame)
            else:
                self.content_layout.insertWidget(insert_index + 1, chart_frame)
        else:
            self.content_layout.addWidget(chart_frame)

    def add_comparison_table(self, comparison_data: Dict[str, Any]):
        if hasattr(self, 'placeholder_label') and self.placeholder_label:
            self.placeholder_label.deleteLater()
            self.placeholder_label = None

        layer_count = comparison_data.get('layer_count', 0)
        table_frame = QGroupBox(f"多层对比分析 ({layer_count}层)")
        table_layout = QVBoxLayout(table_frame)

        table = QTableWidget()

        if 'layers_stats' in comparison_data:
            layers_stats = comparison_data['layers_stats']
            table.setColumnCount(len(layers_stats) + 1)
            headers = ["指标"]
            for layer_stat in layers_stats:
                headers.append(f"{layer_stat['file_name']}\n(Z={layer_stat['z_depth']}μm)")
            table.setHorizontalHeaderLabels(headers)

            metrics = [
                ("均值 (MPa)", "mean"),
                ("中位数 (MPa)", "median"),
                ("标准差 (MPa)", "std"),
                ("最小值 (MPa)", "min"),
                ("最大值 (MPa)", "max"),
                ("变异系数 (%)", "cv"),
                ("数据点数", "count"),
            ]
            table.setRowCount(len(metrics))
            for row, (metric_name, key) in enumerate(metrics):
                table.setItem(row, 0, QTableWidgetItem(metric_name))
                for col, layer_stat in enumerate(layers_stats):
                    value = layer_stat.get(key, "N/A")
                    value_str = f"{value:.2f}" if isinstance(value, float) else str(value)
                    table.setItem(row, col + 1, QTableWidgetItem(value_str))

            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            table.verticalHeader().setVisible(False)
            table.setWordWrap(True)
            table.setAlternatingRowColors(True)
            table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
            table.resizeRowsToContents()
            min_row_h = 26
            for r in range(table.rowCount()):
                if table.rowHeight(r) < min_row_h:
                    table.setRowHeight(r, min_row_h)
            header_h = table.horizontalHeader().height()
            rows_h = sum(table.rowHeight(r) for r in range(table.rowCount()))
            table.setMinimumHeight(header_h + rows_h + 16)
        else:
            table.setColumnCount(2)
            table.setHorizontalHeaderLabels(["指标", "数值"])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            table.verticalHeader().setVisible(False)
            table.setWordWrap(True)
            table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
            table.resizeRowsToContents()
            min_row_h = 26
            for r in range(table.rowCount()):
                if table.rowHeight(r) < min_row_h:
                    table.setRowHeight(r, min_row_h)
            header_h = table.horizontalHeader().height()
            rows_h = sum(table.rowHeight(r) for r in range(table.rowCount()))
            table.setMinimumHeight(header_h + rows_h + 16)

        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table_layout.addWidget(table)

        insert_index = self.content_layout.indexOf(self.layer_selection_group) + 1
        self.content_layout.insertWidget(insert_index, table_frame)

    # ===== 事件处理 =====
    def _on_select_all(self):
        self._set_all_items_checked(True)
        self._update_compare_button_state()

    def _on_deselect_all(self):
        self._set_all_items_checked(False)
        self._update_compare_button_state()

    def _on_invert_selection(self):
        all_indices = set(range(len(self._datasets)))
        self._checked_indices = all_indices.difference(self._checked_indices)
        self._refresh_layer_items()
        self._update_selection_count_label()

    def _on_item_changed(self, _item: QListWidgetItem):
        self._sync_checked_set_from_view()
        self._update_compare_button_state()
        self._update_selection_count_label()

    def _on_compare_clicked(self):
        if self.on_compare_layers is None:
            return
        indices: List[int] = []
        for row in range(self.layer_list.count()):
            item = self.layer_list.item(row)
            if item.checkState() == Qt.Checked:
                indices.append(item.data(Qt.UserRole))
        if len(indices) < 2:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "提示", "请至少勾选2个层进行对比")
            return
        indices.sort()
        self.on_compare_layers(indices)

    def _on_calculate_difference_clicked(self):
        if not self.on_calculate_difference:
            return
        idx_a = self.diff_minuend_combo.currentData()
        idx_b = self.diff_subtrahend_combo.currentData()
        if idx_a is None or idx_b is None:
            return
        if idx_a == idx_b:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "提示", "请选择两个不同的层进行差分")
            return
        self.on_calculate_difference(int(idx_a), int(idx_b))

    # ===== 内部工具 =====
    def _update_compare_button_state(self):
        checked_count = len(self._checked_indices)
        self.compare_button.setEnabled(checked_count >= 2)

    def _set_all_items_checked(self, checked: bool):
        if checked:
            self._checked_indices = set(range(len(self._datasets)))
        else:
            self._checked_indices = set()
        self._refresh_layer_items()
        self._update_selection_count_label()

    def _update_selection_count_label(self):
        self.selection_count_label.setText(f"已选 {len(self._checked_indices)}/{len(self._datasets)}")

    def _sync_checked_set_from_view(self):
        checked = set()
        for row in range(self.layer_list.count()):
            item = self.layer_list.item(row)
            original_index = item.data(Qt.UserRole)
            if item.checkState() == Qt.Checked:
                checked.add(original_index)
        self._checked_indices = checked

    def _filtered_sorted_indices(self) -> List[int]:
        return list(range(len(self._datasets)))

    def _refresh_layer_items(self):
        self.layer_list.blockSignals(True)
        self.layer_list.clear()
        for i in self._filtered_sorted_indices():
            _data, z_depth, file_name = self._datasets[i]
            label = f"{file_name} (Z={z_depth}μm)"
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if i in self._checked_indices else Qt.Unchecked)
            item.setData(Qt.UserRole, i)
            self.layer_list.addItem(item)
        self.layer_list.blockSignals(False)
        self._update_compare_button_state()

    def _populate_diff_controls(self):
        try:
            self.diff_minuend_combo.blockSignals(True)
            self.diff_subtrahend_combo.blockSignals(True)
            self.diff_minuend_combo.clear()
            self.diff_subtrahend_combo.clear()
            for i, (_data, z_depth, file_name) in enumerate(self._datasets):
                label = f"{file_name} (Z={z_depth}μm)"
                self.diff_minuend_combo.addItem(label, i)
                self.diff_subtrahend_combo.addItem(label, i)
            self.diff_button.setEnabled(len(self._datasets) >= 2)
        finally:
            self.diff_minuend_combo.blockSignals(False)
            self.diff_subtrahend_combo.blockSignals(False)


