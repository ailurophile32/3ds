"""
统计分析视图模块

提供统计分析结果的可视化展示界面
"""

from typing import Dict, Any, Optional
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QGroupBox, QTableWidget, QTableWidgetItem,
    QComboBox, QPushButton, QScrollArea, QFrame,
    QSplitter, QToolTip
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class StatisticsView(QWidget):
    """统计分析视图组件"""
    
    def __init__(self, parent=None):
        """初始化统计分析视图"""
        super().__init__(parent)
        self.init_ui()
        
        # 回调函数
        self.on_dataset_changed = None
        self.on_outlier_method_changed = None
        self.on_export_statistics = None
    
    def init_ui(self):
        """初始化用户界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)
        
        # 顶部控制栏
        control_bar = QHBoxLayout()
        
        # 数据集选择
        control_bar.addWidget(QLabel("选择数据集:"))
        self.dataset_combo = QComboBox()
        self.dataset_combo.setMinimumWidth(200)
        self.dataset_combo.currentIndexChanged.connect(self._on_dataset_changed)
        control_bar.addWidget(self.dataset_combo)
        
        control_bar.addStretch()
        
        # 导出按钮
        self.export_button = QPushButton("导出统计报告")
        self.export_button.clicked.connect(self._on_export_clicked)
        self.export_button.setEnabled(False)
        control_bar.addWidget(self.export_button)
        
        main_layout.addLayout(control_bar)
        
        # 创建分割器（左右布局）
        splitter = QSplitter(Qt.Horizontal)
        
        # === 左侧：统计表格区域 ===
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 基础统计表格
        basic_group = QGroupBox("描述性统计")
        basic_layout = QVBoxLayout(basic_group)
        self.basic_table = self._create_statistics_table()
        basic_layout.addWidget(self.basic_table)
        left_layout.addWidget(basic_group)
        
        # 分布特征表格
        distribution_group = QGroupBox("分布特征")
        distribution_layout = QVBoxLayout(distribution_group)
        self.distribution_table = self._create_statistics_table()
        distribution_layout.addWidget(self.distribution_table)
        left_layout.addWidget(distribution_group)
        
        # 异常值检测
        outlier_group = QGroupBox("异常值检测")
        outlier_layout = QVBoxLayout(outlier_group)
        
        outlier_control = QHBoxLayout()
        outlier_control.addWidget(QLabel("检测方法:"))
        self.outlier_method_combo = QComboBox()
        self.outlier_method_combo.addItems(["IQR (四分位距)", "Z-Score (3σ)", "Isolation Forest"])
        self.outlier_method_combo.currentIndexChanged.connect(self._on_outlier_method_changed)
        outlier_control.addWidget(self.outlier_method_combo)
        outlier_control.addStretch()
        outlier_layout.addLayout(outlier_control)
        
        self.outlier_table = self._create_statistics_table()
        outlier_layout.addWidget(self.outlier_table)
        left_layout.addWidget(outlier_group)
        
        splitter.addWidget(left_panel)
        
        # === 右侧：可视化图表区域 ===
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 图表容器
        chart_container = QWidget()
        self.chart_layout = QVBoxLayout(chart_container)
        self.chart_layout.setSpacing(12)
        
        # 占位标签（初始显示）
        self.placeholder_label = QLabel("请选择数据集查看统计分析")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #7f8c8d; font-size: 14px;")
        self.chart_layout.addWidget(self.placeholder_label)
        
        scroll_area.setWidget(chart_container)
        right_layout.addWidget(scroll_area)
        
        splitter.addWidget(right_panel)
        
        # 设置分割比例
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        
        main_layout.addWidget(splitter)
    
    def _create_statistics_table(self) -> QTableWidget:
        """创建统计表格
        
        Returns:
            QTableWidget: 统计表格控件
        """
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["指标", "数值"])
        table.horizontalHeader().setStretchLastSection(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setMaximumHeight(300)
        return table
    
    def update_dataset_list(self, datasets: list):
        """更新数据集列表
        
        Args:
            datasets: 数据集列表 [(data, z_depth, file_name), ...]
        """
        self.dataset_combo.blockSignals(True)
        self.dataset_combo.clear()
        
        for data, z_depth, file_name in datasets:
            self.dataset_combo.addItem(f"{file_name} (Z={z_depth}μm)")
        
        self.dataset_combo.blockSignals(False)
        self.export_button.setEnabled(len(datasets) > 0)
        
        # 如果有数据集，自动选择第一个
        if len(datasets) > 0:
            self.dataset_combo.setCurrentIndex(0)
            self._on_dataset_changed(0)
    
    def display_basic_statistics(self, statistics: Dict[str, Any]):
        """显示基础统计信息
        
        Args:
            statistics: 统计数据字典
        """
        if not statistics:
            self.basic_table.setRowCount(0)
            return
        
        # 定义要显示的指标
        metrics = [
            ("样本数量", "count", "个"),
            ("缺失值", "missing", "个"),
            ("缺失率", "missing_ratio", "%"),
            ("平均值", "mean", "MPa"),
            ("中位数", "median", "MPa"),
            ("标准差", "std", "MPa"),
            ("变异系数", "cv", "%"),
            ("最小值", "min", "MPa"),
            ("最大值", "max", "MPa"),
            ("极差", "range", "MPa"),
            ("四分位距", "iqr", "MPa"),
            ("25%分位数", "q25", "MPa"),
            ("50%分位数", "q50", "MPa"),
            ("75%分位数", "q75", "MPa"),
            ("偏度", "skewness", ""),
            ("峰度", "kurtosis", ""),
        ]
        
        self.basic_table.setRowCount(len(metrics))
        
        for i, (label, key, unit) in enumerate(metrics):
            value = statistics.get(key, 0)
            
            # 格式化数值
            if isinstance(value, int):
                value_str = f"{value}"
            elif key in ['missing_ratio', 'cv']:
                value_str = f"{value:.2f}"
            else:
                value_str = f"{value:.4f}"
            
            # 添加单位
            if unit:
                value_str = f"{value_str} {unit}"
            
            self.basic_table.setItem(i, 0, QTableWidgetItem(label))
            self.basic_table.setItem(i, 1, QTableWidgetItem(value_str))
    
    def display_distribution_analysis(self, distribution: Dict[str, Any]):
        """显示分布特征分析
        
        Args:
            distribution: 分布特征数据
        """
        if not distribution:
            self.distribution_table.setRowCount(0)
            return
        
        metrics = [
            ("Shapiro-Wilk统计量", "shapiro_stat", ""),
            ("Shapiro-Wilk p值", "shapiro_p_value", ""),
            ("正态性(Shapiro)", "is_normal_shapiro", ""),
            ("K-S统计量", "ks_stat", ""),
            ("K-S p值", "ks_p_value", ""),
            ("正态性(K-S)", "is_normal_ks", ""),
        ]
        
        self.distribution_table.setRowCount(len(metrics))
        
        for i, (label, key, unit) in enumerate(metrics):
            value = distribution.get(key, 0)
            
            # 格式化数值
            if isinstance(value, bool):
                value_str = "是" if value else "否"
            elif isinstance(value, float):
                value_str = f"{value:.6f}"
            else:
                value_str = str(value)
            
            self.distribution_table.setItem(i, 0, QTableWidgetItem(label))
            self.distribution_table.setItem(i, 1, QTableWidgetItem(value_str))
    
    def display_outlier_detection(self, outliers: Dict[str, Any]):
        """显示异常值检测结果
        
        Args:
            outliers: 异常值检测数据
        """
        if not outliers:
            self.outlier_table.setRowCount(0)
            return
        
        metrics = [
            ("检测方法", "method", ""),
            ("异常值数量", "outlier_count", "个"),
            ("异常值比例", "outlier_ratio", "%"),
        ]
        
        # 如果使用IQR方法，显示边界
        if outliers.get('method') == 'iqr':
            metrics.extend([
                ("下界", "lower_bound", "MPa"),
                ("上界", "upper_bound", "MPa"),
            ])
        
        self.outlier_table.setRowCount(len(metrics))
        
        for i, (label, key, unit) in enumerate(metrics):
            value = outliers.get(key, 0)
            
            # 格式化数值
            if key == 'method':
                method_map = {'iqr': 'IQR', 'zscore': 'Z-Score', 'isolation_forest': 'Isolation Forest'}
                value_str = method_map.get(value, value)
            elif isinstance(value, int):
                value_str = str(value)
            elif isinstance(value, float):
                value_str = f"{value:.4f}"
            else:
                value_str = str(value)
            
            # 添加单位
            if unit:
                value_str = f"{value_str} {unit}"
            
            self.outlier_table.setItem(i, 0, QTableWidgetItem(label))
            self.outlier_table.setItem(i, 1, QTableWidgetItem(value_str))
    
    def clear_charts(self):
        """清除所有图表"""
        # 移除所有图表控件
        while self.chart_layout.count() > 0:
            item = self.chart_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        # 重新添加占位标签
        self.placeholder_label = QLabel("请选择数据集查看统计分析")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #7f8c8d; font-size: 14px;")
        self.chart_layout.addWidget(self.placeholder_label)
    
    def add_chart(self, fig: Figure, title: str, info_text: Optional[str] = None, summary_text: Optional[str] = None):
        """添加图表到视图
        
        Args:
            fig: matplotlib Figure对象
            title: 图表标题
            info_text: 悬浮说明文本（可选）
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
        
        # 标题 + 信息按钮
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
            # 单击显示悬浮文字（气泡提示），不展开面板
            def _show_tip():
                global_pos = info_button.mapToGlobal(info_button.rect().bottomRight())
                QToolTip.showText(global_pos, info_text, info_button)
            info_button.clicked.connect(_show_tip)
        chart_layout.addLayout(header_layout)
        
        # 图表
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
        
        self.chart_layout.addWidget(chart_frame)
    
    def _on_dataset_changed(self, index: int):
        """数据集选择变更事件"""
        if self.on_dataset_changed and index >= 0:
            self.on_dataset_changed(index)
    
    def _on_outlier_method_changed(self, index: int):
        """异常值检测方法变更事件"""
        if self.on_outlier_method_changed:
            method_map = {0: 'iqr', 1: 'zscore', 2: 'isolation_forest'}
            self.on_outlier_method_changed(method_map.get(index, 'iqr'))
    
    def _on_export_clicked(self):
        """导出按钮点击事件"""
        if self.on_export_statistics:
            self.on_export_statistics()

