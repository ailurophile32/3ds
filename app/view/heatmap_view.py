"""
热力图视图模块

包含应用程序的主要视图界面，负责所有UI元素的显示和交互界面。
"""

from pathlib import Path
from typing import Optional, Dict, Any, Callable, List, Tuple

import numpy as np
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QPushButton,
    QFileDialog,
    QLabel,
    QInputDialog,
    QMessageBox,
    QListWidget,
    QGroupBox,
    QFrame,
    QSlider,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QScrollArea,
    QDoubleSpinBox,
)
from matplotlib.backend_bases import MouseEvent
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from app.utils.config import DefaultSettings
from app.utils.widgets import (
    PlotlyWebView,
    ZDepthInputDialog,
    PerformanceSettingsDialog,
    CSVFileManager,
)
from app.view.base_view import BaseView


class HeatmapView(BaseView):
    """热力图查看器主视图"""

    def __init__(self):
        """初始化热力图视图"""
        super().__init__(title="SiC三维应力分析", width=1400, height=900)
        self.current_dataset_index = 0
        self.plotly_view: Optional[PlotlyWebView] = None
        self.hover_annotation = None  # 用于显示悬停信息的文本注释
        self.current_view_type = None  # '2d' 或 'plotly'
        self.current_canvas = None

        # 初始化回调函数字典
        self.callbacks.update(
            {
                "on_load_csv": None,
                "on_files_dropped": None,  # 新增：拖拽文件处理
                "on_remove_csv": None,
                "on_set_z_depth": None,
                "on_generate_2d": None,
                "on_generate_3d": None,
                "on_save_heatmap": None,
                "on_z_scale_changed": None,
                "on_colormap_changed": None,
                "on_interpolation_changed": None,
                "on_smart_range_changed": None,
                "on_manual_range_input": None,
                "on_reset_range": None,
                "on_apply_range": None,
                "on_show_performance_settings": None,
                "on_csv_selection_changed": None,
                "on_flip_x_axis": None,
            }
        )

        self.init_ui()

    def init_colorbar_controls(self):
        """初始化色标卡控件的新逻辑"""
        # 智能范围计算默认不启用
        self.smart_range_checkbox.setChecked(False)

        # 手动输入框默认启用，因为智能范围默认不勾选
        self.vmin_spinbox.setEnabled(True)
        self.vmax_spinbox.setEnabled(True)

        # 按钮状态根据数据加载情况动态调整
        self.reset_range_button.setEnabled(False)
        self.apply_range_button.setEnabled(False)

    def init_ui(self):
        """初始化用户界面"""
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 水平分割布局
        h_splitter = QHBoxLayout()
        main_layout.addLayout(h_splitter, 1)

        # 左侧控制面板
        left_panel = QWidget()
        self.left_layout = QVBoxLayout(left_panel)
        h_splitter.addWidget(left_panel, 1)

        # CSV文件管理区域 - 使用新的拖拽组件
        self.csv_file_manager = CSVFileManager()
        
        # 连接信号到回调函数
        self.csv_file_manager.files_dropped.connect(self._on_files_dropped)
        self.csv_file_manager.files_added.connect(self._on_load_button_clicked)
        self.csv_file_manager.file_removed.connect(self._on_remove_button_clicked)
        self.csv_file_manager.z_depth_requested.connect(self._on_z_input_button_clicked)
        self.csv_file_manager.file_selected.connect(self._on_csv_selection_changed)
        
        # 保持对CSV列表的引用以兼容现有代码
        self.csv_list_widget = self.csv_file_manager.csv_list_widget
        self.remove_button = self.csv_file_manager.remove_button
        self.z_input_button = self.csv_file_manager.z_depth_button
        
        # 添加双击事件处理
        self.csv_list_widget.itemDoubleClicked.connect(self._on_csv_double_clicked)
        
        self.left_layout.addWidget(self.csv_file_manager)

        # 热力图生成控制区域
        control_group = QGroupBox("热力图控制")
        control_layout = QVBoxLayout(control_group)

        # 生成按钮区域
        generate_buttons = QHBoxLayout()

        self.generate_2d_button = QPushButton("生成2D热力图")
        self.generate_2d_button.clicked.connect(self._on_generate_2d_clicked)
        self.generate_2d_button.setEnabled(False)
        generate_buttons.addWidget(self.generate_2d_button)

        self.generate_3d_button = QPushButton("生成3D多层热力图")
        self.generate_3d_button.clicked.connect(self._on_generate_3d_clicked)
        self.generate_3d_button.setEnabled(False)
        generate_buttons.addWidget(self.generate_3d_button)

        control_layout.addLayout(generate_buttons)

        # X轴翻转控制区域
        self.flip_x_checkbox = QCheckBox("翻转X轴方向")
        self.flip_x_checkbox.stateChanged.connect(self._on_flip_x_changed)
        self.flip_x_checkbox.setEnabled(False)
        self.flip_x_checkbox.setToolTip("将X轴方向从递增改为递减，同时镜像图像数据")
        control_layout.addWidget(self.flip_x_checkbox)

        # 色标卡控制区域
        colorbar_group = QGroupBox("热力图色标卡设置")
        colorbar_layout = QVBoxLayout(colorbar_group)

        # 智能范围计算选项
        self.smart_range_checkbox = QCheckBox("使用智能范围计算（推荐）")
        self.smart_range_checkbox.setChecked(False)
        self.smart_range_checkbox.setToolTip(
            "智能范围计算会自动去除异常值，提供更好的视觉效果"
        )
        self.smart_range_checkbox.stateChanged.connect(self._on_smart_range_changed)
        colorbar_layout.addWidget(self.smart_range_checkbox)

        # 色标选择
        colormap_layout = QFormLayout()
        self.colormap_combo = QComboBox()

        # 添加精选的色标选项
        colormap_options = DefaultSettings.get_colormap_options()
        for value, display_name in colormap_options.items():
            self.colormap_combo.addItem(display_name, value)

        self.colormap_combo.setCurrentIndex(0)  # 默认选择第一个
        self.colormap_combo.currentTextChanged.connect(self._on_colormap_changed)
        colormap_layout.addRow("色标样式:", self.colormap_combo)

        # 插值方法选择
        self.interpolation_combo = QComboBox()

        # 添加插值方法选项
        interpolation_options = DefaultSettings.get_interpolation_options()
        for value, display_name in interpolation_options.items():
            self.interpolation_combo.addItem(display_name, value)

        # 默认选择RBF插值（最佳方法）
        rbf_index = list(interpolation_options.keys()).index("rbf")
        self.interpolation_combo.setCurrentIndex(rbf_index)
        self.interpolation_combo.currentTextChanged.connect(
            self._on_interpolation_changed
        )
        colormap_layout.addRow("插值方法:", self.interpolation_combo)

        colorbar_layout.addLayout(colormap_layout)

        # 手动范围设置
        manual_range_layout = QFormLayout()

        self.vmin_spinbox = QDoubleSpinBox()
        self.vmin_spinbox.setRange(-99999.0, 99999.0)
        self.vmin_spinbox.setDecimals(2)
        self.vmin_spinbox.setValue(0.0)
        self.vmin_spinbox.setEnabled(True)   # 默认启用，因为智能范围计算默认不启用
        self.vmin_spinbox.setToolTip(
            "手动设置色标卡最小值。修改此值将自动禁用智能范围计算。"
        )
        # 记录初始值，用于检测是否真的发生了变化
        self._vmin_last_value = 0.0
        # 连接值变化事件，用于检测手动输入
        self.vmin_spinbox.valueChanged.connect(self._on_manual_range_input)
        # 连接焦点事件，提供更好的用户反馈
        self.vmin_spinbox.focusInEvent = self._create_focus_handler(
            self.vmin_spinbox.focusInEvent, "vmin"
        )
        manual_range_layout.addRow("最小值 (MPa):", self.vmin_spinbox)

        self.vmax_spinbox = QDoubleSpinBox()
        self.vmax_spinbox.setRange(-99999.0, 99999.0)
        self.vmax_spinbox.setDecimals(2)
        self.vmax_spinbox.setValue(100.0)
        self.vmax_spinbox.setEnabled(True)   # 默认启用，因为智能范围计算默认不启用
        self.vmax_spinbox.setToolTip(
            "手动设置色标卡最大值。修改此值将自动禁用智能范围计算。"
        )
        # 记录初始值，用于检测是否真的发生了变化
        self._vmax_last_value = 100.0
        # 连接值变化事件，用于检测手动输入
        self.vmax_spinbox.valueChanged.connect(self._on_manual_range_input)
        # 连接焦点事件，提供更好的用户反馈
        self.vmax_spinbox.focusInEvent = self._create_focus_handler(
            self.vmax_spinbox.focusInEvent, "vmax"
        )
        manual_range_layout.addRow("最大值 (MPa):", self.vmax_spinbox)

        colorbar_layout.addLayout(manual_range_layout)

        # 数据范围显示
        self.data_range_label = QLabel("当前数据范围: 未加载数据")
        self.data_range_label.setStyleSheet("color: gray; font-size: 10px;")
        colorbar_layout.addWidget(self.data_range_label)

        # 快速设置按钮
        quick_buttons_layout = QHBoxLayout()

        self.reset_range_button = QPushButton("重置为数据范围")
        self.reset_range_button.clicked.connect(self._on_reset_range_clicked)
        self.reset_range_button.setEnabled(False)  # 默认禁用，数据加载后启用
        quick_buttons_layout.addWidget(self.reset_range_button)

        self.apply_range_button = QPushButton("应用设置")
        self.apply_range_button.clicked.connect(self._on_apply_range_clicked)
        self.apply_range_button.setEnabled(False)  # 默认禁用，手动输入时启用
        quick_buttons_layout.addWidget(self.apply_range_button)

        colorbar_layout.addLayout(quick_buttons_layout)
        control_layout.addWidget(colorbar_group)

        # 添加性能设置按钮
        self.performance_button = QPushButton("3D性能设置")
        self.performance_button.clicked.connect(self._on_performance_button_clicked)
        control_layout.addWidget(self.performance_button)

        # 保存按钮
        self.save_button = QPushButton("保存当前图像")
        self.save_button.clicked.connect(self._on_save_button_clicked)
        self.save_button.setEnabled(False)
        control_layout.addWidget(self.save_button)

        self.left_layout.addWidget(control_group)

        # Z轴缩放比例控制区域
        z_scale_group = QGroupBox("Z轴缩放设置")
        z_scale_layout = QVBoxLayout(z_scale_group)

        # Z轴缩放比例标签
        self.z_scale_label = QLabel("Z轴缩放比例: 0.5")
        self.z_scale_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        z_scale_layout.addWidget(self.z_scale_label)

        # Z轴缩放滑块容器
        z_scale_slider_layout = QHBoxLayout()

        # 最小值标签
        min_label = QLabel("0.1")
        min_label.setStyleSheet("color: #7f8c8d; font-size: 10px;")
        z_scale_slider_layout.addWidget(min_label)

        # 滑块
        self.z_scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.z_scale_slider.setMinimum(1)  # 对应 0.1
        self.z_scale_slider.setMaximum(20)  # 对应 2.0
        self.z_scale_slider.setValue(5)  # 默认 0.5
        self.z_scale_slider.setTickInterval(2)
        self.z_scale_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        # 连接滑块事件：拖动时只更新标签，松开时才刷新图像
        self.z_scale_slider.valueChanged.connect(self._on_z_scale_value_changed)
        self.z_scale_slider.sliderReleased.connect(self._on_z_scale_released)

        # 防止鼠标移出区域后的误操作
        self.z_scale_slider.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.z_scale_slider.installEventFilter(self)

        # 美化滑块样式
        self.z_scale_slider.setStyleSheet(
            """
            QSlider::groove:horizontal {
                border: 1px solid #bdc3c7;
                height: 8px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ecf0f1, stop:1 #bdc3c7);
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3498db, stop:1 #2980b9);
                border: 1px solid #2c3e50;
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #5dade2, stop:1 #3498db);
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3498db, stop:1 #2980b9);
                border: 1px solid #2c3e50;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::add-page:horizontal {
                background: #ecf0f1;
                border: 1px solid #bdc3c7;
                height: 8px;
                border-radius: 4px;
            }
        """
        )

        z_scale_slider_layout.addWidget(self.z_scale_slider)

        # 最大值标签
        max_label = QLabel("2.0")
        max_label.setStyleSheet("color: #7f8c8d; font-size: 10px;")
        z_scale_slider_layout.addWidget(max_label)
        z_scale_layout.addLayout(z_scale_slider_layout)
        self.left_layout.addWidget(z_scale_group)

        # 状态标签
        self.status_label = QLabel("请添加CSV文件开始")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.left_layout.addWidget(self.status_label)

        # 右侧可视化区域 - 使用标签页系统
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        h_splitter.addWidget(right_panel, 3)  # 右侧面板占更多空间

        # 创建标签页控件
        from PySide6.QtWidgets import QTabWidget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)
        right_layout.addWidget(self.tab_widget)

        # === 标签页1: 可视化 ===
        visualization_tab = QWidget()
        visualization_tab_layout = QVBoxLayout(visualization_tab)
        visualization_tab_layout.setContentsMargins(0, 0, 0, 0)

        # 可视化+预览容器
        visual_container = QWidget()
        visual_container_layout = QHBoxLayout(visual_container)
        visual_container_layout.setContentsMargins(0, 0, 0, 0)
        visual_container_layout.setSpacing(12)

        # 创建可视化图形区域（一个框架)
        self.visualization_frame = QFrame()
        self.visualization_layout = QVBoxLayout(self.visualization_frame)
        self.visualization_frame.setMinimumSize(QSize(600, 400))
        visual_container_layout.addWidget(self.visualization_frame, 1)

        # 右侧2D层缩略图滚动栏
        self.preview_scroll_area = QScrollArea()
        self.preview_scroll_area.setWidgetResizable(True)
        self.preview_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.preview_scroll_area.setMinimumWidth(220)

        self.preview_container = QWidget()
        self.preview_layout = QVBoxLayout(self.preview_container)
        self.preview_layout.setContentsMargins(6, 6, 6, 6)
        self.preview_layout.setSpacing(8)
        self.preview_layout.addStretch(1)
        self.preview_scroll_area.setWidget(self.preview_container)
        self.preview_scroll_area.hide()  # 初始隐藏，仅在3D模式下显示

        visual_container_layout.addWidget(self.preview_scroll_area)
        visualization_tab_layout.addWidget(visual_container, 1)
        self.tab_widget.addTab(visualization_tab, "可视化")

        # === 标签页2: 统计分析 ===
        from app.view.statistics_view import StatisticsView
        self.statistics_view = StatisticsView()
        self.tab_widget.addTab(self.statistics_view, "统计分析")

        # === 标签页3: 趋势对比 ===
        from app.view.trend_view import TrendView
        self.trend_view = TrendView()
        self.tab_widget.addTab(self.trend_view, "趋势对比")

        # === 标签页4: 梯度分析 ===
        gradient_tab = QWidget()
        gradient_tab_layout = QVBoxLayout(gradient_tab)
        placeholder_label_3 = QLabel("梯度分析功能即将推出...")
        placeholder_label_3.setAlignment(Qt.AlignCenter)
        placeholder_label_3.setStyleSheet("color: #7f8c8d; font-size: 14px;")
        gradient_tab_layout.addWidget(placeholder_label_3)
        self.tab_widget.addTab(gradient_tab, "梯度分析")

    def _on_files_dropped(self, file_paths):
        """处理拖拽文件事件"""
        self.trigger_callback("on_files_dropped", file_paths)
    
    def _on_load_button_clicked(self, file_paths):
        """处理加载按钮点击事件（接收CSVFileManager传来的文件路径列表）"""
        self.trigger_callback("on_load_csv", file_paths)

    def _on_remove_button_clicked(self, index=None):
        """处理移除按钮点击事件"""
        # 如果没有传递索引参数，则从选中项获取
        if index is None:
            index = self.csv_list_widget.currentRow()
        
        if index >= 0:
            self.trigger_callback("on_remove_csv", index)

    def _on_csv_selection_changed(self, index=None):
        """处理CSV列表选择变更事件"""
        # 如果没有传递索引参数，则从选中项获取
        if index is None:
            index = self.csv_list_widget.currentRow()
        
        self.current_dataset_index = index

        # 根据选择状态启用/禁用按钮
        has_selection = index >= 0
        self.remove_button.setEnabled(has_selection)
        self.z_input_button.setEnabled(has_selection)
        self.generate_2d_button.setEnabled(has_selection)
        self.flip_x_checkbox.setEnabled(has_selection)

        if has_selection:
            self.trigger_callback("on_csv_selection_changed", index)

    def _on_z_input_button_clicked(self, index=None):
        """处理设置Z轴深度按钮点击事件"""
        # 如果没有传递索引参数，则从选中项获取
        if index is None:
            selected_items = self.csv_list_widget.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "警告", "请选择一个CSV文件！")
                return
            index = self.csv_list_widget.row(selected_items[0])

        # 调用正确的回调函数
        if self.callbacks.get("on_set_z_depth"):
            self.callbacks["on_set_z_depth"](index)
        else:
            QMessageBox.warning(self, "错误", "回调函数未注册！")

    def _on_z_scale_value_changed(self, value):
        """滑块值变化时只更新标签显示，不刷新图像"""
        z_scale = value / 10.0
        self.z_scale_label.setText(f"Z轴缩放比例: {z_scale:.1f}")

    def _on_z_scale_released(self):
        """滑块松开时才刷新图像"""
        value = self.z_scale_slider.value()
        z_scale = value / 10.0
        self.callbacks["on_z_scale_changed"](z_scale)

    def eventFilter(self, obj, event):
        """事件过滤器，防止鼠标移出滑块区域后的误操作"""
        if obj == self.z_scale_slider:
            if event.type() == event.Type.Leave:
                # 鼠标离开滑块区域时，确保滑块失去焦点
                self.z_scale_slider.clearFocus()
            elif event.type() == event.Type.MouseButtonPress:
                # 鼠标按下时获得焦点
                self.z_scale_slider.setFocus()
        return super().eventFilter(obj, event)

    def _on_csv_double_clicked(self, item):
        """处理CSV文件双击事件，自动生成2D热力图"""
        row = self.csv_list_widget.row(item)
        if row >= 0:
            # 先设置当前选中项，这会触发选择变更事件
            self.csv_list_widget.setCurrentRow(row)
            # 然后生成2D热力图
            self.trigger_callback("on_generate_2d", row)
            self.update_status(f"双击生成2D热力图: {item.text()}")

    def _on_generate_2d_clicked(self):
        """处理生成2D热力图按钮点击事件"""
        if self.csv_list_widget.currentRow() >= 0:
            self.trigger_callback("on_generate_2d", self.csv_list_widget.currentRow())

    def _on_generate_3d_clicked(self):
        """处理生成3D热力图按钮点击事件"""
        self.trigger_callback("on_generate_3d")

    def _on_save_button_clicked(self):
        """处理保存热力图按钮点击事件"""
        if self.current_view_type:
            self.trigger_callback("on_save_heatmap", self.current_view_type)

    def _on_colormap_changed(self):
        """处理色标变更事件"""
        colormap_name = self.colormap_combo.currentData()
        self.trigger_callback("on_colormap_changed", colormap_name)

    def _on_interpolation_changed(self):
        """处理插值方法变更事件"""
        interpolation_method = self.interpolation_combo.currentData()
        self.trigger_callback("on_interpolation_changed", interpolation_method)

    def _on_smart_range_changed(self, state):
        """处理智能范围计算变更事件"""
        is_smart = state == 2  # Qt.CheckState.Checked = 2

        # 根据智能范围计算状态更新手动输入框的启用状态
        self.vmin_spinbox.setEnabled(not is_smart)
        self.vmax_spinbox.setEnabled(not is_smart)

        # 如果启用智能范围计算，禁用应用按钮并重置样式
        if is_smart:
            self.apply_range_button.setEnabled(False)
            # 重置输入框样式
            self._reset_spinbox_style()

        self.trigger_callback("on_smart_range_changed", is_smart)

    def _reset_spinbox_style(self):
        """重置输入框样式为PySide官方默认状态"""
        # 清除自定义样式，使用PySide官方默认样式
        self.vmin_spinbox.setStyleSheet("")
        self.vmax_spinbox.setStyleSheet("")

    def _create_focus_handler(self, original_handler, spinbox_type):
        """创建焦点事件处理器

        Args:
            original_handler: 原始的焦点事件处理器
            spinbox_type: 输入框类型 ('vmin' 或 'vmax')

        Returns:
            function: 新的焦点事件处理器
        """

        def focus_handler(event):
            # 调用原始处理器
            original_handler(event)

            # 如果智能范围计算启用且用户点击了输入框，提供提示
            if self.smart_range_checkbox.isChecked():
                if spinbox_type == "vmin":
                    self.update_status("提示：修改最小值将自动禁用智能范围计算")
                else:
                    self.update_status("提示：修改最大值将自动禁用智能范围计算")

        return focus_handler

    def _on_reset_range_clicked(self):
        """处理重置范围按钮点击事件 - 优化版本
        
        提供更好的用户体验和视觉反馈
        """
        # 提供即时的视觉反馈
        self._set_reset_button_loading_state(True)
        
        try:
            # 触发重置操作
            self.trigger_callback("on_reset_range", self.current_dataset_index)
            
            # 重置按钮样式和应用按钮样式
            self.reset_apply_button_style()
            
        finally:
            # 恢复按钮状态
            self._set_reset_button_loading_state(False)
    
    def _set_reset_button_loading_state(self, is_loading: bool):
        """设置重置按钮的加载状态
        
        在重置操作期间提供视觉反馈
        
        Args:
            is_loading: 是否处于加载状态
        """
        if is_loading:
            self.reset_range_button.setText("重置中...")
            self.reset_range_button.setEnabled(False)
            self.reset_range_button.setStyleSheet("""
                QPushButton {
                    background-color: #f39c12;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                }
            """)
        else:
            self.reset_range_button.setText("重置为数据范围")
            self.reset_range_button.setEnabled(True)
            self.reset_range_button.setStyleSheet("")  # 恢复默认样式

    def _on_apply_range_clicked(self):
        """处理应用范围按钮点击事件 - 优化版本
        
        提供更好的用户体验和视觉反馈
        """
        # 获取当前设置
        vmin = self.vmin_spinbox.value()
        vmax = self.vmax_spinbox.value()
        
        # 最后一次验证
        if not self._validate_range_input(vmin, vmax):
            self.update_status("❌ 无法应用：范围值无效")
            return
        
        # 提供即时的视觉反馈
        self._set_apply_button_loading_state(True)
        
        try:
            settings = {
                "vmin": vmin,
                "vmax": vmax,
            }
            
            # 触发应用操作
            self.trigger_callback("on_apply_range", settings)
            
        finally:
            # 恢复按钮状态（控制器会在成功后进一步更新状态）
            self._set_apply_button_loading_state(False)
    
    def _set_apply_button_loading_state(self, is_loading: bool):
        """设置应用按钮的加载状态
        
        在应用操作期间提供视觉反馈
        
        Args:
            is_loading: 是否处于加载状态
        """
        if is_loading:
            self.apply_range_button.setText("应用中...")
            self.apply_range_button.setEnabled(False)
            self.apply_range_button.setStyleSheet("""
                QPushButton {
                    background-color: #f39c12;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                }
            """)
        else:
            # 注意：这里不直接恢复启用状态，让控制器决定最终状态
            pass

    def _on_manual_range_input(self):
        """处理手动范围输入事件 - 优化版本
        
        优化应用按钮的启用/禁用状态管理，提供更好的用户体验
        """
        # 检查是否真的发生了值变化（避免程序设置值时触发）
        current_vmin = self.vmin_spinbox.value()
        current_vmax = self.vmax_spinbox.value()

        # 只有当值真正改变且不是程序设置时才处理
        if (
            current_vmin != self._vmin_last_value
            or current_vmax != self._vmax_last_value
        ):
            # 用户开始手动输入时，自动禁用智能范围计算
            if self.smart_range_checkbox.isChecked():
                self.update_smart_range_status(False)
                # 启用手动输入框
                self.vmin_spinbox.setEnabled(True)
                self.vmax_spinbox.setEnabled(True)

            # 进行基本的实时验证
            is_valid_range = self._validate_range_input(current_vmin, current_vmax)

            # 优化应用按钮的启用/禁用状态管理
            self._update_apply_button_state(is_valid_range, current_vmin, current_vmax)

            # 触发回调通知控制器
            self.trigger_callback("on_manual_range_input")

            # 更新记录的值
            self._vmin_last_value = current_vmin
            self._vmax_last_value = current_vmax

    def _validate_range_input(self, vmin: float, vmax: float) -> bool:
        """验证范围输入的基本有效性（实时验证）

        Args:
            vmin: 最小值
            vmax: 最大值

        Returns:
            bool: 是否为有效范围
        """
        # 基本验证：最小值必须小于最大值
        if vmin >= vmax:
            # 更新状态显示错误信息
            self.update_status("错误：最小值必须小于最大值")
            # 设置错误样式
            self._set_spinbox_validation_style(False)
            return False

        # 检查范围是否过小
        if abs(vmax - vmin) < 1e-6:
            self.update_status("警告：范围过小，可能导致显示异常")
            self._set_spinbox_validation_style(False)
            return False

        # 范围有效
        self.update_status("手动范围输入有效，可以应用设置")
        self._set_spinbox_validation_style(True)
        return True

    def _set_spinbox_validation_style(self, is_valid: bool):
        """设置输入框的验证样式

        Args:
            is_valid: 输入是否有效
        """
        # 使用PySide官方默认样式，不设置自定义样式
        # 验证状态通过其他方式反馈（如状态栏消息）
        self.vmin_spinbox.setStyleSheet("")
        self.vmax_spinbox.setStyleSheet("")
    
    def _update_apply_button_state(self, is_valid_range: bool, vmin: float, vmax: float):
        """优化应用按钮的启用/禁用状态管理
        
        提供更智能的按钮状态管理，包括视觉反馈和状态指示
        
        Args:
            is_valid_range: 范围是否有效
            vmin: 最小值
            vmax: 最大值
        """
        if is_valid_range:
            # 范围有效，启用应用按钮并提供视觉反馈
            self.apply_range_button.setEnabled(True)
            
            # 设置按钮样式以提供清晰的视觉状态指示
            self.apply_range_button.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
                QPushButton:pressed {
                    background-color: #21618c;
                }
            """)
            
            # 更新按钮文本以提供更多信息
            self.apply_range_button.setText(f"应用设置 ({vmin:.1f} - {vmax:.1f})")
        else:
            # 范围无效，禁用应用按钮
            self.apply_range_button.setEnabled(False)
            
            # 设置禁用状态的样式
            self.apply_range_button.setStyleSheet("""
                QPushButton {
                    background-color: #bdc3c7;
                    color: #7f8c8d;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                }
            """)
            
            # 恢复默认按钮文本
            self.apply_range_button.setText("应用设置")
    
    def reset_apply_button_style(self):
        """重置应用按钮样式到默认状态
        
        在应用设置后调用，提供清晰的视觉状态指示
        """
        self.apply_range_button.setStyleSheet("")  # 恢复默认样式
        self.apply_range_button.setText("应用设置")  # 恢复默认文本

    def _on_performance_button_clicked(self):
        """处理性能设置按钮点击事件"""
        self.trigger_callback("on_show_performance_settings")

    def _on_flip_x_changed(self, state):
        """处理翻转X轴勾选框状态变化事件"""
        self.trigger_callback("on_flip_x_axis")

    def update_dataset_list(self, data_sets: List[Tuple]):
        """更新数据集列表显示

        Args:
            data_sets: 数据集列表[(数据, Z轴深度, 文件名), ...]
        """
        self.csv_list_widget.clear()
        for data, z_depth, file_name in data_sets:
            self.csv_list_widget.addItem(f"{file_name} (Z={z_depth}μm)")

        # 更新按钮状态
        has_datasets = len(data_sets) > 0
        self.remove_button.setEnabled(has_datasets)
        self.z_input_button.setEnabled(has_datasets)
        self.generate_2d_button.setEnabled(has_datasets)
        self.generate_3d_button.setEnabled(has_datasets)
        self.flip_x_checkbox.setEnabled(has_datasets)
        self.reset_range_button.setEnabled(has_datasets)
        self.apply_range_button.setEnabled(has_datasets)

        # 如果之前有选中的项目，尝试维持选择状态
        if has_datasets and self.current_dataset_index >= 0:
            if self.current_dataset_index < len(data_sets):
                self.csv_list_widget.setCurrentRow(self.current_dataset_index)
            else:
                # 如果当前选中索引超出范围，选择最后一项
                self.csv_list_widget.setCurrentRow(len(data_sets) - 1)
                self.current_dataset_index = len(data_sets) - 1

    def update_z_depth_display(self, index: int, z_depth: float):
        """更新特定数据集的Z轴深度显示

        Args:
            index: 数据集索引
            z_depth: 新的Z轴深度值
        """
        item = self.csv_list_widget.item(index)
        if item:
            current_text = item.text()
            file_name = current_text.split(" (Z=")[0]
            item.setText(f"{file_name} (Z={z_depth}μm)")


    def _format_smart_range_display(self, vmin: float, vmax: float, vmin_raw: float, vmax_raw: float, range_info: str) -> str:
        """格式化智能范围显示文本
        
        Args:
            vmin: 智能范围最小值
            vmax: 智能范围最大值
            vmin_raw: 原始范围最小值
            vmax_raw: 原始范围最大值
            range_info: 范围优化信息
            
        Returns:
            str: 格式化的显示文本
        """
        # 计算范围中心点，用于判断数据分布特征
        smart_center = (vmin + vmax) / 2
        raw_center = (vmin_raw + vmax_raw) / 2
        
        # 判断数据是否跨越零点
        crosses_zero = vmin < 0 < vmax
        zero_indicator = " 🎯" if crosses_zero else ""
        
        # 计算异常值移除情况
        outliers_removed = ""
        if abs(vmin - vmin_raw) > 0.01 or abs(vmax - vmax_raw) > 0.01:
            outliers_removed = " (已移除异常值)"
        
        return (
            f'<div style="line-height: 1.4;">'
            f'<b style="color: #27ae60; font-size: 11px;">🤖 智能范围{zero_indicator}:</b> '
            f'<span style="color: #2c3e50; font-weight: bold;">{vmin:.2f} - {vmax:.2f} MPa</span>'
            f'<span style="color: #27ae60; font-size: 9px;">{range_info}{outliers_removed}</span><br>'
            f'<span style="color: #7f8c8d; font-size: 9px;">📊 原始范围: {vmin_raw:.2f} - {vmax_raw:.2f} MPa</span><br>'
            f'<span style="color: #95a5a6; font-size: 8px;">💡 中心点: {smart_center:.2f} MPa | 跨度: {vmax - vmin:.2f} MPa</span>'
            f'</div>'
        )
    
    def _format_smart_range_only_display(self, vmin: float, vmax: float) -> str:
        """格式化仅智能范围的显示文本
        
        Args:
            vmin: 智能范围最小值
            vmax: 智能范围最大值
            
        Returns:
            str: 格式化的显示文本
        """
        crosses_zero = vmin < 0 < vmax
        zero_indicator = " 🎯" if crosses_zero else ""
        center = (vmin + vmax) / 2
        
        return (
            f'<div style="line-height: 1.4;">'
            f'<b style="color: #27ae60; font-size: 11px;">🤖 智能范围{zero_indicator}:</b> '
            f'<span style="color: #2c3e50; font-weight: bold;">{vmin:.2f} - {vmax:.2f} MPa</span><br>'
            f'<span style="color: #95a5a6; font-size: 8px;">💡 中心点: {center:.2f} MPa | 跨度: {vmax - vmin:.2f} MPa</span>'
            f'</div>'
        )
    
    def _format_manual_range_display(self, current_vmin: float, current_vmax: float, 
                                   vmin: float, vmax: float, vmin_raw: float = None, vmax_raw: float = None) -> str:
        """格式化手动范围显示文本
        
        Args:
            current_vmin: 当前手动设置的最小值
            current_vmax: 当前手动设置的最大值
            vmin: 数据范围最小值
            vmax: 数据范围最大值
            vmin_raw: 原始数据范围最小值
            vmax_raw: 原始数据范围最大值
            
        Returns:
            str: 格式化的显示文本
        """
        # 检查手动范围是否与数据范围相同
        is_same_as_data = (abs(current_vmin - vmin) < 0.01 and abs(current_vmax - vmax) < 0.01)
        
        # 判断手动范围的特征
        crosses_zero = current_vmin < 0 < current_vmax
        zero_indicator = " 🎯" if crosses_zero else ""
        
        # 确定范围状态
        if is_same_as_data:
            range_status = " (与数据范围相同)"
            status_color = "#f39c12"
        else:
            # 检查是否超出数据范围
            extends_beyond = current_vmin < vmin or current_vmax > vmax
            if extends_beyond:
                range_status = " (扩展范围)"
                status_color = "#e74c3c"
            else:
                range_status = " (自定义范围)"
                status_color = "#3498db"
        
        # 计算范围覆盖率
        if vmin_raw is not None and vmax_raw is not None:
            data_span = vmax_raw - vmin_raw
            if data_span > 0:
                coverage = min(100, max(0, ((min(current_vmax, vmax_raw) - max(current_vmin, vmin_raw)) / data_span) * 100))
                coverage_info = f" | 数据覆盖: {coverage:.0f}%"
            else:
                coverage_info = ""
        else:
            coverage_info = ""
        
        center = (current_vmin + current_vmax) / 2
        
        return (
            f'<div style="line-height: 1.4;">'
            f'<b style="color: {status_color}; font-size: 11px;">✋ 手动范围{zero_indicator}:</b> '
            f'<span style="color: #2c3e50; font-weight: bold;">{current_vmin:.2f} - {current_vmax:.2f} MPa</span>'
            f'<span style="color: {status_color}; font-size: 9px;">{range_status}</span><br>'
            f'<span style="color: #7f8c8d; font-size: 9px;">📊 数据范围: {vmin:.2f} - {vmax:.2f} MPa</span><br>'
            f'<span style="color: #95a5a6; font-size: 8px;">💡 中心点: {center:.2f} MPa | 跨度: {current_vmax - current_vmin:.2f} MPa{coverage_info}</span>'
            f'</div>'
        )
    
    def _update_range_span_info(self, range_span: float, vmin: Optional[float] = None, vmax: Optional[float] = None, 
                               vmin_raw: Optional[float] = None, vmax_raw: Optional[float] = None):
        """更新范围跨度信息显示 - 增强版本
        
        提供额外的范围信息，帮助用户理解数据分布
        
        Args:
            range_span: 当前范围跨度
            vmin: 当前范围最小值
            vmax: 当前范围最大值
            vmin_raw: 原始数据最小值
            vmax_raw: 原始数据最大值
        """
        # 构建详细的工具提示信息
        tooltip_lines = [
            f"📏 当前范围跨度: {range_span:.2f} MPa"
        ]
        
        # 添加范围分析
        if range_span < 1.0:
            tooltip_lines.append("💡 范围较小，适合查看细微变化")
            tooltip_lines.append("🔍 建议：可用于精密分析")
        elif range_span > 1000.0:
            tooltip_lines.append("⚠️ 范围较大，可能包含异常值")
            tooltip_lines.append("🔍 建议：考虑启用智能范围计算")
        else:
            tooltip_lines.append("✅ 范围适中，显示效果良好")
        
        # 添加数据分布信息
        if vmin is not None and vmax is not None:
            center = (vmin + vmax) / 2
            tooltip_lines.append(f"📍 范围中心: {center:.2f} MPa")
            
            if vmin < 0 < vmax:
                zero_position = abs(vmin) / range_span
                tooltip_lines.append(f"🎯 零点位置: {zero_position:.1%}")
        
        # 添加优化信息（如果有原始数据）
        if vmin_raw is not None and vmax_raw is not None:
            original_span = vmax_raw - vmin_raw
            if original_span > 0 and abs(original_span - range_span) > 0.01:
                optimization = ((original_span - range_span) / original_span) * 100
                if optimization > 0:
                    tooltip_lines.append(f"🚀 范围优化: 减少了 {optimization:.1f}%")
                else:
                    tooltip_lines.append(f"📈 范围扩展: 增加了 {abs(optimization):.1f}%")
        
        # 添加使用建议
        tooltip_lines.append("")
        tooltip_lines.append("💡 使用提示:")
        if self.smart_range_checkbox.isChecked():
            tooltip_lines.append("• 当前使用智能范围，自动优化显示")
            tooltip_lines.append("• 取消勾选可手动调整范围")
        else:
            tooltip_lines.append("• 当前使用手动范围")
            tooltip_lines.append("• 勾选智能范围可自动优化")
        
        tooltip_info = "\n".join(tooltip_lines)
        self.data_range_label.setToolTip(tooltip_info)

    def _update_display_style_based_on_range_type(self) -> None:
        """根据范围类型更新显示样式
        
        实现范围变化时的实时显示更新，添加动态样式效果
        """
        # 根据当前模式设置标签样式
        if self.smart_range_checkbox.isChecked():
            # 智能范围模式 - 绿色主题
            self.data_range_label.setStyleSheet("""
                QLabel {
                    background-color: #f8fff8;
                    border: 1px solid #27ae60;
                    border-radius: 4px;
                    padding: 8px;
                    margin: 2px;
                }
            """)
        else:
            # 手动范围模式 - 蓝色主题
            self.data_range_label.setStyleSheet("""
                QLabel {
                    background-color: #f8fbff;
                    border: 1px solid #3498db;
                    border-radius: 4px;
                    padding: 8px;
                    margin: 2px;
                }
            """)
        
        # 确保标签支持富文本显示
        self.data_range_label.setTextFormat(Qt.TextFormat.RichText)
        self.data_range_label.setWordWrap(True)
        self.data_range_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

    def set_range_values(self, vmin: float, vmax: float) -> None:
        """设置手动范围值

        该方法在设置 SpinBox 值时会临时屏蔽相关信号，
        以避免误触发手动输入检测逻辑，从而保持 UI 与模型状态一致。

        Args:
            vmin: 手动范围最小值
            vmax: 手动范围最大值
        """
        # 暂时断开信号连接，避免触发手动输入检测
        self.vmin_spinbox.blockSignals(True)
        self.vmax_spinbox.blockSignals(True)

        self.vmin_spinbox.setValue(vmin)
        self.vmax_spinbox.setValue(vmax)
        self._vmin_last_value = vmin
        self._vmax_last_value = vmax

        # 重新连接信号
        self.vmin_spinbox.blockSignals(False)
        self.vmax_spinbox.blockSignals(False)

    def show_2d_figure(self, fig: Figure) -> None:
        """显示2D热力图

        Args:
            fig: matplotlib Figure对象
        """
        self._clear_visualization()

        # 创建新的2D画布
        self.current_canvas = FigureCanvas(fig)

        # 添加鼠标悬停事件处理
        if hasattr(fig, "_heatmap_data"):
            self._setup_mouse_hover_events(fig)

        # 显示图形
        self.visualization_layout.addWidget(self.current_canvas)
        self.current_view_type = "2d"
        self.save_button.setEnabled(True)
        # 隐藏右侧预览栏（仅3D模式使用）
        if hasattr(self, "preview_scroll_area"):
            self.preview_scroll_area.hide()

    def show_3d_figure(self, fig: Any) -> None:
        """显示3D Plotly热力图

        Args:
            fig: plotly Figure对象
        """
        self._clear_visualization()

        # 确保WebView正确初始化
        if not self.plotly_view:
            self.plotly_view = PlotlyWebView(self)
            self.plotly_view.setMinimumSize(QSize(600, 400))

        # 先添加到布局中，再显示内容
        self.visualization_layout.addWidget(self.plotly_view)
        self.plotly_view.show()
        QApplication.processEvents()  # 确保WebView完全显示

        # 显示Plotly图形
        self.plotly_view.display_figure(fig)

        self.current_view_type = "plotly"
        self.save_button.setEnabled(True)

    def _clear_visualization(self) -> None:
        """清除可视化区域的内容"""
        # 清除当前可视化控件
        if self.current_view_type == "2d" and self.current_canvas:
            self.visualization_layout.removeWidget(self.current_canvas)
            self.current_canvas.deleteLater()
            self.current_canvas = None
            self.hover_annotation = None
        elif self.current_view_type == "plotly" and self.plotly_view:
            self.visualization_layout.removeWidget(self.plotly_view)
            # 不删除plotly_view对象，而是隐藏它以便重用
            self.plotly_view.hide()
        # 注意：不清理或修改右侧预览区域，由专用方法管理

    def _setup_mouse_hover_events(self, fig: Figure) -> None:
        """设置鼠标悬停事件处理

        Args:
            fig: matplotlib Figure对象
        """
        if hasattr(fig, "_heatmap_data"):
            # 连接鼠标移动事件
            self.current_canvas.mpl_connect("motion_notify_event", self._on_mouse_move)
            # 连接鼠标离开事件
            self.current_canvas.mpl_connect("axes_leave_event", self._on_mouse_leave)

    def _on_mouse_move(self, event: MouseEvent) -> None:
        """鼠标移动事件处理

        Args:
            event: matplotlib鼠标事件对象
        """
        if (
            event.inaxes is None
            or not self.current_canvas
            or not hasattr(self.current_canvas.figure, "_heatmap_data")
        ):
            return

        try:
            # 获取热力图数据
            heatmap_data = self.current_canvas.figure._heatmap_data
            xi_grid = heatmap_data["xi_grid"]
            yi_grid = heatmap_data["yi_grid"]
            zi = heatmap_data["zi"]
            x_center = heatmap_data["x_center"]
            y_center = heatmap_data["y_center"]
            radius = heatmap_data["radius"]
            z_depth = heatmap_data["z_depth"]

            # 获取鼠标位置
            x_mouse, y_mouse = event.xdata, event.ydata

            # 检查鼠标是否在圆形区域内
            distance_from_center = np.sqrt(
                (x_mouse - x_center) ** 2 + (y_mouse - y_center) ** 2
            )
            if distance_from_center > radius:
                self._hide_hover_annotation()
                return

            # 找到最近的网格点
            # 计算在网格中的索引
            resolution = xi_grid.shape[0]
            x_extent = xi_grid.max() - xi_grid.min()
            y_extent = yi_grid.max() - yi_grid.min()

            # 将鼠标坐标转换为网格索引
            i = int((y_mouse - yi_grid.min()) / y_extent * (resolution - 1))
            j = int((x_mouse - xi_grid.min()) / x_extent * (resolution - 1))

            # 确保索引在有效范围内
            i = max(0, min(i, resolution - 1))
            j = max(0, min(j, resolution - 1))

            # 获取对应的压力值
            pressure_value = zi[i, j]

            # 如果压力值是NaN（在圆形区域外），隐藏注释
            if np.isnan(pressure_value):
                self._hide_hover_annotation()
                return

            # 显示悬停信息
            self._show_hover_annotation(
                x_mouse, y_mouse, pressure_value, z_depth, event.inaxes
            )

        except Exception as e:
            print(f"鼠标悬停事件处理错误: {e}")

    def _on_mouse_leave(self, event: MouseEvent) -> None:
        """鼠标离开坐标轴事件处理

        Args:
            event: matplotlib鼠标事件对象
        """
        self._hide_hover_annotation()

    def _show_hover_annotation(
        self, x: float, y: float, pressure: float, z_depth: float, ax
    ) -> None:
        """显示悬停信息注释

        Args:
            x: X坐标
            y: Y坐标
            pressure: 压力值
            z_depth: Z轴深度
            ax: matplotlib坐标轴对象
        """
        try:
            # 移除之前的注释
            self._hide_hover_annotation()

            # 创建悬停信息文本
            hover_text = f"X: {x:.1f} μm\nY: {y:.1f} μm\nZ: {z_depth:.1f} μm\n应力: {pressure:.2f} MPa"

            # 创建注释，跟随鼠标显示在左上方
            self.hover_annotation = ax.annotate(
                hover_text,
                xy=(x, y),
                xytext=(-80, 30),  # 偏移到鼠标左上方
                textcoords="offset points",
                bbox=dict(
                    boxstyle="round,pad=0.5",
                    facecolor="yellow",
                    alpha=0.9,
                    edgecolor="black",
                    linewidth=1,
                ),
                fontsize=10,
                fontfamily="sans-serif",
                ha="left",
                va="bottom",
                zorder=10000,  # 设置更高的层级
            )

            # 刷新画布
            self.current_canvas.draw_idle()

        except Exception as e:
            print(f"显示悬停注释错误: {e}")

    def _hide_hover_annotation(self) -> None:
        """隐藏悬停信息注释"""
        try:
            if self.hover_annotation is not None:
                self.hover_annotation.remove()
                self.hover_annotation = None
                # 刷新画布
                if self.current_canvas:
                    self.current_canvas.draw_idle()
        except Exception as e:
            print(f"隐藏悬停注释错误: {e}")

    def get_save_file_path(self, figure_type: str) -> str:
        """获取保存文件路径

        Args:
            figure_type: 图形类型 ('2d' 或 'plotly')

        Returns:
            str: 文件保存路径，如果用户取消则返回空字符串
        """
        default_name = ""
        file_filter = ""

        if figure_type == "2d":
            default_name = "circular_heatmap_2d.png"
            file_filter = "PNG文件 (*.png);;PDF文件 (*.pdf);;SVG文件 (*.svg)"
        elif figure_type == "plotly":
            default_name = "stress_3d_visualization.png"
            file_filter = "PNG文件 (*.png);;PDF文件 (*.pdf);;SVG文件 (*.svg);;HTML文件 (*.html);;JSON文件 (*.json)"

        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存热力图", default_name, file_filter
        )

        return file_path

    def update_flip_x_status(self, is_flipped: bool) -> None:
        """更新X轴翻转勾选框状态

        Args:
            is_flipped: 是否已翻转X轴
        """
        # 暂时断开信号连接，避免触发回调
        self.flip_x_checkbox.blockSignals(True)
        self.flip_x_checkbox.setChecked(is_flipped)
        self.flip_x_checkbox.blockSignals(False)

    def update_smart_range_status(self, is_smart: bool) -> None:
        """更新智能范围勾选框状态

        Args:
            is_smart: 是否启用智能范围
        """
        # 暂时断开信号连接，避免触发回调
        self.smart_range_checkbox.blockSignals(True)
        self.smart_range_checkbox.setChecked(is_smart)
        self.smart_range_checkbox.blockSignals(False)

    def show_z_depth_dialog(self, current_z: float = 0.0) -> Tuple[float, bool]:
        """显示Z轴深度设置对话框

        Args:
            current_z: 当前Z轴深度值

        Returns:
            Tuple[float, bool]: (Z轴深度值, 用户是否点击了确认)
        """
        dialog = ZDepthInputDialog(self, current_z)
        if dialog.exec():
            return dialog.get_z_depth(), True
        return current_z, False

    def clear_layer_previews(self) -> None:
        """清空右侧2D层预览内容"""
        try:
            if hasattr(self, "preview_layout") and self.preview_layout is not None:
                # 删除除最后一个stretch外的所有项目
                while self.preview_layout.count() > 1:
                    item = self.preview_layout.takeAt(0)
                    widget = item.widget()
                    if widget is not None:
                        widget.deleteLater()
        except Exception as e:
            print(f"清空预览失败: {e}")

    def update_layer_previews(self, images: List[np.ndarray], labels: Optional[List[str]] = None, thumb_width: int = 180) -> None:
        """更新右侧2D层缩略图预览

        Args:
            images: RGBA或RGB的numpy数组列表 (H, W, 3/4)
            labels: 每个缩略图下方的文本标签
            thumb_width: 每张缩略图的显示宽度
        """
        try:
            self.clear_layer_previews()
            if images is None or len(images) == 0:
                self.preview_scroll_area.hide()
                return

            for idx, img in enumerate(images):
                # 创建容器
                card = QFrame()
                card.setObjectName("previewCard")
                card.setStyleSheet("#previewCard { background: white; border: 1px solid #e0e0e0; border-radius: 8px; }")
                v = QVBoxLayout(card)
                v.setContentsMargins(6, 6, 6, 6)
                v.setSpacing(6)

                # 将numpy图像转换为QPixmap
                h, w = img.shape[0], img.shape[1]
                if img.dtype != np.uint8:
                    img = np.clip(img, 0, 255).astype(np.uint8)
                channels = img.shape[2] if img.ndim == 3 else 1
                if channels == 4:
                    fmt = QImage.Format_RGBA8888
                elif channels == 3:
                    fmt = QImage.Format_RGB888
                else:
                    # 灰度转为RGB
                    img = np.repeat(img.reshape(h, w, 1), 3, axis=2)
                    fmt = QImage.Format_RGB888
                qimg = QImage(img.data, w, h, img.strides[0], fmt)
                pix = QPixmap.fromImage(qimg)

                # 按宽度等比缩放
                scaled = pix.scaledToWidth(thumb_width, Qt.SmoothTransformation)
                pic = QLabel()
                pic.setAlignment(Qt.AlignCenter)
                pic.setFrameStyle(QFrame.NoFrame)
                pic.setPixmap(scaled)
                pic.setStyleSheet("border: none; background: transparent;")
                v.addWidget(pic)

                # 标签
                if labels and idx < len(labels):
                    text = QLabel(labels[idx])
                else:
                    text = QLabel(f"Layer {idx+1}")
                text.setAlignment(Qt.AlignCenter)
                text.setFrameStyle(QFrame.NoFrame)
                text.setStyleSheet("color: #2c3e50; font-size: 11px; border: none; background: transparent;")
                v.addWidget(text)

                self.preview_layout.insertWidget(self.preview_layout.count() - 1, card)

            # 显示预览区域
            self.preview_scroll_area.show()
        except Exception as e:
            print(f"更新预览失败: {e}")

    def update_dataset_list(self, data_sets: List[Tuple]):
        """更新数据集列表显示

        Args:
            data_sets: 数据集列表[(数据, Z轴深度, 文件名), ...]
        """
        self.csv_list_widget.clear()
        for data, z_depth, file_name in data_sets:
            self.csv_list_widget.addItem(f"{file_name} (Z={z_depth}μm)")

        # 更新按钮状态
        has_datasets = len(data_sets) > 0
        self.remove_button.setEnabled(has_datasets)
        self.z_input_button.setEnabled(has_datasets)
        self.generate_2d_button.setEnabled(has_datasets)
        self.generate_3d_button.setEnabled(has_datasets)
        self.flip_x_checkbox.setEnabled(has_datasets)
        self.reset_range_button.setEnabled(has_datasets)
        self.apply_range_button.setEnabled(has_datasets)

        # 如果之前有选中的项目，尝试维持选择状态
        if has_datasets and self.current_dataset_index >= 0:
            if self.current_dataset_index < len(data_sets):
                self.csv_list_widget.setCurrentRow(self.current_dataset_index)
            else:
                # 如果当前选中索引超出范围，选择最后一项
                self.csv_list_widget.setCurrentRow(len(data_sets) - 1)
                self.current_dataset_index = len(data_sets) - 1

    def update_z_depth_display(self, index: int, z_depth: float):
        """更新特定数据集的Z轴深度显示

        Args:
            index: 数据集索引
            z_depth: 新的Z轴深度值
        """
        item = self.csv_list_widget.item(index)
        if item:
            current_text = item.text()
            file_name = current_text.split(" (Z=")[0]
            item.setText(f"{file_name} (Z={z_depth}μm)")

    def update_status(self, message: str):
        """更新状态栏消息

        Args:
            message: 状态消息
        """
        self.status_label.setText(message)

    def update_data_range_display(
        self, vmin: float, vmax: float, vmin_raw: float = None, vmax_raw: float = None, smart_range_enabled: bool | None = None
    ):
        """更新数据范围显示 - 增强版本
        
        增强数据范围显示功能：
        1. 实现智能范围和原始范围的同时显示
        2. 添加当前使用范围类型的清晰标识
        3. 实现范围变化时的实时显示更新
        4. 优化范围显示格式，提高可读性

        Args:
            vmin: 最小值（可能经过智能范围计算）
            vmax: 最大值（可能经过智能范围计算）
            vmin_raw: 原始最小值（未经过智能范围计算）
            vmax_raw: 原始最大值（未经过智能范围计算）
            smart_range_enabled: 可选，明确指定当前是否启用智能范围；若为 None，则以复选框状态为准
        """
        # 以参数为准决定当前显示模式，未提供则回退到复选框状态
        use_smart = smart_range_enabled if smart_range_enabled is not None else self.smart_range_checkbox.isChecked()

        # 生成显示内容
        if use_smart:
            # 智能范围：优先显示与原始范围的对比信息
            if vmin_raw is not None and vmax_raw is not None:
                original_span = vmax_raw - vmin_raw
                smart_span = vmax - vmin
                if original_span > 0:
                    range_reduction = ((original_span - smart_span) / original_span) * 100
                    range_info = f" (优化 {range_reduction:.1f}%)" if range_reduction > 1 else ""
                else:
                    range_info = ""
                label_html = self._format_smart_range_display(vmin, vmax, vmin_raw, vmax_raw, range_info)
            else:
                # 仅有智能范围，无原始范围可对比
                label_html = self._format_smart_range_only_display(vmin, vmax)
        else:
            # 手动范围：与数据范围对比（若提供原始范围则以原始为准）
            data_vmin = vmin_raw if vmin_raw is not None else vmin
            data_vmax = vmax_raw if vmax_raw is not None else vmax
            label_html = self._format_manual_range_display(
                current_vmin=self.vmin_spinbox.value(),
                current_vmax=self.vmax_spinbox.value(),
                vmin=data_vmin,
                vmax=data_vmax,
                vmin_raw=vmin_raw,
                vmax_raw=vmax_raw,
            )

        # 应用到界面
        self.data_range_label.setText(label_html)
        self._update_display_style_based_on_range_type()

        # 更新额外的范围跨度提示信息（用于 tooltip）
        try:
            if use_smart:
                current_span = max(0.0, (vmax - vmin))
                self._update_range_span_info(current_span, vmin=vmin, vmax=vmax, vmin_raw=vmin_raw, vmax_raw=vmax_raw)
            else:
                manual_vmin = self.vmin_spinbox.value()
                manual_vmax = self.vmax_spinbox.value()
                current_span = max(0.0, (manual_vmax - manual_vmin))
                data_vmin = vmin_raw if vmin_raw is not None else vmin
                data_vmax = vmax_raw if vmax_raw is not None else vmax
                self._update_range_span_info(current_span, vmin=data_vmin, vmax=data_vmax, vmin_raw=vmin_raw, vmax_raw=vmax_raw)
        except Exception:
            # 安静失败，避免影响主流程
            pass
