"""
趋势对比视图模块

提供多层数据趋势对比的可视化展示界面
"""

from typing import List, Dict, Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QPushButton, QScrollArea,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QListWidget, QAbstractItemView, QListWidgetItem, QSizePolicy, QLayout,
    QComboBox
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class TrendView(QWidget):
    """趋势对比视图组件"""
    
    def __init__(self, parent=None):
        """初始化趋势对比视图"""
        super().__init__(parent)
        # 数据与选择状态
        self._datasets = []  # [(data, z_depth, file_name), ...]
        self._checked_indices = set()  # 以原始索引为基准的勾选集合
        # 排序已移除，列表保持原始顺序
        self.init_ui()
        
        # 回调函数
        self.on_compare_layers = None  # 现在传递多个层索引的列表
        self.on_refresh_trend = None
        self.on_calculate_difference = None
    
    def init_ui(self):
        """初始化用户界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)
        
        # 先创建下方滚动内容，再把“选择对比层”放到内容末尾
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        # 内容容器
        content_widget = QWidget()
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setSpacing(12)
        
        # 占位标签（初始显示）
        self.placeholder_label = QLabel("请加载多层数据以查看趋势对比分析")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #7f8c8d; font-size: 14px;")
        self.content_layout.addWidget(self.placeholder_label)
        
        # ------- 重新构建并添加“选择对比层”分组至内容底部 -------
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
        self.refresh_button = QPushButton("刷新趋势分析")
        self.refresh_button.setObjectName("SuccessButton")
        self.refresh_button.clicked.connect(self._on_refresh_clicked)
        self.refresh_button.setCursor(Qt.PointingHandCursor)
        self.refresh_button.setStyleSheet(
            "#SuccessButton { background-color: #27ae60; color: #ffffff; border: 1px solid #1f8f4e; border-radius: 4px; padding: 6px 12px; }"
            "#SuccessButton:hover:!disabled { background-color: #229954; }"
            "#SuccessButton:pressed:!disabled { background-color: #1a7a44; }"
            "#SuccessButton:disabled { background-color: #e0e0e0; color: #8c8c8c; border-color: #cccccc; }"
        )
        action_bar.addWidget(self.refresh_button)
        layer_selection_layout.addLayout(action_bar)

        self.content_layout.addWidget(self.layer_selection_group)

        # ------- 差分云图控制区（位于选择分组下方） -------
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
    
    def update_layer_list(self, datasets: list):
        """更新层列表
        
        Args:
            datasets: 数据集列表 [(data, z_depth, file_name), ...]
        """
        # 存储数据并初始化选中集合（默认全选以便直接对比）
        self._datasets = datasets or []
        if len(self._datasets) >= 2:
            self._checked_indices = set(range(len(self._datasets)))
        else:
            self._checked_indices = set()
        self._refresh_layer_items()
        self._update_compare_button_state()
        # 同步差分选择器
        self._populate_diff_controls()
    
    def clear_content(self):
        """清除所有内容"""
        # 保留“选择对比层”和“差分云图”分组，只清除其他内容
        for i in reversed(range(self.content_layout.count())):
            item = self.content_layout.itemAt(i)
            widget = item.widget()
            if widget:
                keep_layer_selector = hasattr(self, 'layer_selection_group') and widget is self.layer_selection_group
                keep_diff_group = hasattr(self, 'diff_group') and widget is self.diff_group
                if not keep_layer_selector and not keep_diff_group:
                    widget.setParent(None)
                    widget.deleteLater()
        
        # 重新添加占位标签（放在选择分组之前）
        self.placeholder_label = QLabel("请加载多层数据以查看趋势对比分析")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #7f8c8d; font-size: 14px;")
        if hasattr(self, 'layer_selection_group') and self.layer_selection_group:
            insert_index = self.content_layout.indexOf(self.layer_selection_group)
            if insert_index == -1:
                self.content_layout.addWidget(self.placeholder_label)
            else:
                self.content_layout.insertWidget(insert_index, self.placeholder_label)
        else:
            self.content_layout.addWidget(self.placeholder_label)
    
    def clear_comparison_results(self):
        """仅清除选择分组下方的对比结果部件，保留趋势分析图与选择分组。
        用于用户切换对比层时的局部刷新。
        """
        if not hasattr(self, 'layer_selection_group') or not self.layer_selection_group:
            return
        selector_index = self.content_layout.indexOf(self.layer_selection_group)
        # 删除选择分组之后的所有部件
        for i in reversed(range(self.content_layout.count())):
            if i > selector_index:
                item = self.content_layout.itemAt(i)
                widget = item.widget()
                if widget:
                    widget.setParent(None)
                    widget.deleteLater()
        # 重新确保差分分组存在于底部
        if hasattr(self, 'diff_group') and self.diff_group:
            if self.content_layout.indexOf(self.diff_group) == -1:
                self.content_layout.addWidget(self.diff_group)

    def add_chart(self, fig: Figure, title: str):
        """添加图表
        
        Args:
            fig: matplotlib Figure对象
            title: 图表标题
        """
        # 移除占位标签（如果存在）
        if hasattr(self, 'placeholder_label') and self.placeholder_label:
            self.placeholder_label.deleteLater()
            self.placeholder_label = None
        
        # 创建图表容器
        chart_frame = QFrame()
        chart_frame.setFrameStyle(QFrame.Box)
        chart_frame.setStyleSheet("QFrame { border: 1px solid #ddd; border-radius: 4px; background: white; }")
        chart_layout = QVBoxLayout(chart_frame)
        chart_layout.setContentsMargins(8, 8, 8, 8)
        
        # 标题
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #2c3e50;")
        chart_layout.addWidget(title_label)
        
        # 图表
        canvas = FigureCanvas(fig)
        canvas.setMinimumHeight(300)
        chart_layout.addWidget(canvas)
        
        # 确保图表插入到“选择对比层”之前，使分组固定在底部
        if hasattr(self, 'layer_selection_group') and self.layer_selection_group:
            insert_index = self.content_layout.indexOf(self.layer_selection_group)
            if insert_index == -1:
                self.content_layout.addWidget(chart_frame)
            else:
                self.content_layout.insertWidget(insert_index, chart_frame)
        else:
            self.content_layout.addWidget(chart_frame)

    def add_chart_below_selector(self, fig: Figure, title: str):
        """在选择对比层分组之后添加图表（用于对比类图表）
        
        这样趋势分析图保持在分组之上，而对比结果图表固定出现在分组之下。
        """
        # 移除占位标签（如果存在）
        if hasattr(self, 'placeholder_label') and self.placeholder_label:
            self.placeholder_label.deleteLater()
            self.placeholder_label = None
        
        chart_frame = QFrame()
        chart_frame.setFrameStyle(QFrame.Box)
        chart_frame.setStyleSheet("QFrame { border: 1px solid #ddd; border-radius: 4px; background: white; }")
        chart_layout = QVBoxLayout(chart_frame)
        chart_layout.setContentsMargins(8, 8, 8, 8)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #2c3e50;")
        chart_layout.addWidget(title_label)
        
        canvas = FigureCanvas(fig)
        canvas.setMinimumHeight(300)
        chart_layout.addWidget(canvas)
        
        if hasattr(self, 'layer_selection_group') and self.layer_selection_group:
            insert_index = self.content_layout.indexOf(self.layer_selection_group)
            if insert_index == -1:
                self.content_layout.addWidget(chart_frame)
            else:
                self.content_layout.insertWidget(insert_index + 1, chart_frame)
        else:
            self.content_layout.addWidget(chart_frame)
    
    def add_comparison_table(self, comparison_data: Dict[str, Any]):
        """添加对比表格
        
        Args:
            comparison_data: 对比数据，支持多层对比
        """
        # 移除占位标签（如果存在）
        if hasattr(self, 'placeholder_label') and self.placeholder_label:
            self.placeholder_label.deleteLater()
            self.placeholder_label = None
        
        # 创建表格容器
        layer_count = comparison_data.get('layer_count', 0)
        table_frame = QGroupBox(f"多层对比分析 ({layer_count}层)")
        table_layout = QVBoxLayout(table_frame)
        
        # 创建表格
        table = QTableWidget()
        
        # 检查是否为多层对比
        if 'layers_stats' in comparison_data:
            # 多层对比：每层一列
            layers_stats = comparison_data['layers_stats']
            table.setColumnCount(len(layers_stats) + 1)
            
            # 设置表头
            headers = ["指标"]
            for layer_stat in layers_stats:
                headers.append(f"{layer_stat['file_name']}\n(Z={layer_stat['z_depth']}μm)")
            table.setHorizontalHeaderLabels(headers)
            
            # 填充数据
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
                    if isinstance(value, float):
                        value_str = f"{value:.2f}"
                    else:
                        value_str = str(value)
                    table.setItem(row, col + 1, QTableWidgetItem(value_str))
            
            table.horizontalHeader().setStretchLastSection(True)
            
        else:
            # 兼容旧的双层对比格式
            table.setColumnCount(2)
            table.setHorizontalHeaderLabels(["指标", "数值"])
            table.horizontalHeader().setStretchLastSection(True)
            
            # 填充旧格式数据
            metrics = [
                ("层1名称", "layer1_name", ""),
                ("层1深度", "layer1_z", "μm"),
                ("层1均值", "layer1_mean", "MPa"),
                ("层1标准差", "layer1_std", "MPa"),
                ("", "", ""),  # 分隔行
                ("层2名称", "layer2_name", ""),
                ("层2深度", "layer2_z", "μm"),
                ("层2均值", "layer2_mean", "MPa"),
                ("层2标准差", "layer2_std", "MPa"),
            ]
            
            table.setRowCount(len(metrics))
            
            for i, (label, key, unit) in enumerate(metrics):
                if label == "":  # 分隔行
                    item = QTableWidgetItem("")
                    item.setBackground(Qt.lightGray)
                    table.setItem(i, 0, item)
                    table.setItem(i, 1, QTableWidgetItem(""))
                    continue
                
                value = comparison_data.get(key, "")
                
                if isinstance(value, float):
                    value_str = f"{value:.4f}"
                    if unit:
                        value_str = f"{value_str} {unit}"
                    table.setItem(i, 1, QTableWidgetItem(value_str))
                else:
                    value_str = str(value)
                    if unit:
                        value_str = f"{value_str} {unit}"
                    table.setItem(i, 1, QTableWidgetItem(value_str))
                
                table.setItem(i, 0, QTableWidgetItem(label))
        
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setAlternatingRowColors(True)
        
        table_layout.addWidget(table)
        # 对比表格放在“选择对比层”之后
        insert_index = self.content_layout.indexOf(self.layer_selection_group) + 1
        self.content_layout.insertWidget(insert_index, table_frame)
    
    def add_anomaly_table(self, anomalies: List[Dict[str, Any]]):
        """添加异常层表格
        
        Args:
            anomalies: 异常层列表
        """
        # 创建表格容器
        table_frame = QGroupBox("异常层检测")
        table_layout = QVBoxLayout(table_frame)
        
        if not anomalies:
            label = QLabel("未检测到异常层")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color: #27ae60; padding: 20px;")
            table_layout.addWidget(label)
        else:
            # 创建表格
            table = QTableWidget()
            table.setColumnCount(5)
            table.setHorizontalHeaderLabels(["文件名", "Z深度(μm)", "均值(MPa)", "偏差(MPa)", "Z-Score"])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            table.setEditTriggers(QTableWidget.NoEditTriggers)
            table.setAlternatingRowColors(True)
            
            table.setRowCount(len(anomalies))
            
            for i, anomaly in enumerate(anomalies):
                table.setItem(i, 0, QTableWidgetItem(anomaly['file_name']))
                table.setItem(i, 1, QTableWidgetItem(f"{anomaly['z_depth']:.1f}"))
                table.setItem(i, 2, QTableWidgetItem(f"{anomaly['mean_value']:.2f}"))
                
                # 偏差标红
                deviation_item = QTableWidgetItem(f"{anomaly['deviation']:.2f}")
                deviation_item.setForeground(Qt.red)
                table.setItem(i, 3, deviation_item)
                
                table.setItem(i, 4, QTableWidgetItem(f"{anomaly['z_score']:.2f}"))
            
            table_layout.addWidget(table)
        
        # 异常层表格属于趋势分析范畴，放在选择分组之前
        if hasattr(self, 'layer_selection_group') and self.layer_selection_group:
            insert_index = self.content_layout.indexOf(self.layer_selection_group)
            if insert_index == -1:
                self.content_layout.addWidget(table_frame)
            else:
                self.content_layout.insertWidget(insert_index, table_frame)
        else:
            self.content_layout.addWidget(table_frame)
    
    def _on_select_all(self):
        """全选按钮事件（将所有层勾选）"""
        self._set_all_items_checked(True)
        self._update_compare_button_state()
    
    def _on_deselect_all(self):
        """清空按钮事件（取消所有勾选）"""
        self._set_all_items_checked(False)
        self._update_compare_button_state()
    
    def _on_compare_clicked(self):
        """对比按钮点击事件"""
        if self.on_compare_layers:
            # 基于勾选状态收集索引
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

    def _on_item_changed(self, _item: QListWidgetItem):
        """列表项勾选状态变化时更新按钮状态"""
        # 同步内部勾选集合
        self._sync_checked_set_from_view()
        self._update_compare_button_state()
        self._update_selection_count_label()

    def _update_compare_button_state(self):
        """根据勾选数量启用/禁用对比按钮"""
        checked_count = len(self._checked_indices)
        self.compare_button.setEnabled(checked_count >= 2)

    def _set_all_items_checked(self, checked: bool):
        """批量设置所有项为勾选/未勾选"""
        if checked:
            self._checked_indices = set(range(len(self._datasets)))
        else:
            self._checked_indices = set()
        self._refresh_layer_items()
        self._update_selection_count_label()
    
    def _on_refresh_clicked(self):
        """刷新按钮点击事件"""
        if self.on_refresh_trend:
            self.on_refresh_trend()

    def _populate_diff_controls(self):
        """根据当前数据集填充差分选择器"""
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

    def _on_calculate_difference_clicked(self):
        """差分按钮点击事件"""
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

    # -------- 布局工具栏相关逻辑 --------
    def _on_invert_selection(self):
        all_indices = set(range(len(self._datasets)))
        self._checked_indices = all_indices.difference(self._checked_indices)
        self._refresh_layer_items()
        self._update_selection_count_label()

    def _update_selection_count_label(self):
        self.selection_count_label.setText(f"已选 {len(self._checked_indices)}/{len(self._datasets)}")

    def _sync_checked_set_from_view(self):
        # 根据界面项勾选状态回写到集合
        checked = set()
        for row in range(self.layer_list.count()):
            item = self.layer_list.item(row)
            original_index = item.data(Qt.UserRole)
            if item.checkState() == Qt.Checked:
                checked.add(original_index)
        self._checked_indices = checked

    def _filtered_sorted_indices(self) -> List[int]:
        # 直接返回原始顺序
        return list(range(len(self._datasets)))

    def _refresh_layer_items(self):
        # 根据过滤/排序重新渲染列表，但勾选集合保持不变
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

