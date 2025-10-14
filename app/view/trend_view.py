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
    QComboBox, QAbstractScrollArea
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
        
        # 趋势页仅保留刷新按钮，不再包含对比与差分控件
        toolbar = QHBoxLayout()
        toolbar.addStretch()
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
        toolbar.addWidget(self.refresh_button)
        self.content_layout.addLayout(toolbar)
        
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
    
    def update_layer_list(self, datasets: list):
        """更新层列表
        
        Args:
            datasets: 数据集列表 [(data, z_depth, file_name), ...]
        """
        # 趋势页仅记录数据集，不再维护对比/差分相关UI
        self._datasets = datasets or []
    
    def clear_content(self):
        """清除所有内容"""
        # 趋势页只清理内容即可
        for i in reversed(range(self.content_layout.count())):
            item = self.content_layout.itemAt(i)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
        
        # 重新添加占位标签（放在选择分组之前）
        self.placeholder_label = QLabel("请加载多层数据以查看趋势对比分析")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #7f8c8d; font-size: 14px;")
        self.content_layout.addWidget(self.placeholder_label)
    
    def clear_comparison_results(self):
        return

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
        # 兼容老接口，趋势页不再使用该方法
        self.add_chart(fig, title)
    
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
            
            # 关键：所有列等比填充，避免列被压缩导致“异常显示”
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            table.verticalHeader().setVisible(False)
            table.setWordWrap(True)
            table.setAlternatingRowColors(True)
            table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
            table.resizeRowsToContents()
            # 保底行高避免文本不可见
            min_row_h = 26
            for r in range(table.rowCount()):
                if table.rowHeight(r) < min_row_h:
                    table.setRowHeight(r, min_row_h)
            # 设置最小高度以完整显示内容
            header_h = table.horizontalHeader().height()
            rows_h = sum(table.rowHeight(r) for r in range(table.rowCount()))
            table.setMinimumHeight(header_h + rows_h + 16)
            
        else:
            # 兼容旧的双层对比格式
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
        # 趋势页直接追加表格
        self.content_layout.addWidget(table_frame)
    
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
        return

    def _on_deselect_all(self):
        return

    def _on_compare_clicked(self):
        return

    def _on_item_changed(self, _item: QListWidgetItem):
        return

    def _update_compare_button_state(self):
        return

    def _set_all_items_checked(self, checked: bool):
        return
    
    def _on_refresh_clicked(self):
        """刷新按钮点击事件"""
        if self.on_refresh_trend:
            self.on_refresh_trend()

    def _populate_diff_controls(self):
        return

    def _on_calculate_difference_clicked(self):
        return

    # -------- 布局工具栏相关逻辑 --------
    def _on_invert_selection(self):
        return

    def _update_selection_count_label(self):
        return

    def _sync_checked_set_from_view(self):
        return

    def _filtered_sorted_indices(self) -> List[int]:
        return list(range(len(self._datasets)))

    def _refresh_layer_items(self):
        return

