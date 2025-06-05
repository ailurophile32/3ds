"""
热力图视图模块

包含应用程序的主要视图界面，负责所有UI元素的显示和交互界面。
"""
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List, Tuple

import numpy as np
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QWidget, 
    QPushButton, QFileDialog, QLabel, QInputDialog, QMessageBox,
    QListWidget, QGroupBox, QFrame, QSlider, QCheckBox, QComboBox,
    QFormLayout, QScrollArea, QDoubleSpinBox
)
from matplotlib.backend_bases import MouseEvent
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from app.utils.config import DefaultSettings
from app.utils.widgets import PlotlyWebView, ZDepthInputDialog, PerformanceSettingsDialog
from app.view.base_view import BaseView


class HeatmapView(BaseView):
    """热力图查看器主视图"""
    
    def __init__(self):
        """初始化热力图视图"""
        super().__init__(title='SiC三维应力分析', width=1400, height=900)
        self.current_dataset_index = 0
        self.plotly_view: Optional[PlotlyWebView] = None
        self.hover_annotation = None  # 用于显示悬停信息的文本注释
        self.current_view_type = None  # '2d' 或 'plotly'
        self.current_canvas = None
        
        # 初始化回调函数字典
        self.callbacks.update({
            'on_load_csv': None,
            'on_remove_csv': None,
            'on_set_z_depth': None,
            'on_generate_2d': None,
            'on_generate_3d': None,
            'on_save_heatmap': None,
            'on_z_scale_changed': None,
            'on_colormap_changed': None,
            'on_auto_range_changed': None,
            'on_smart_range_changed': None,
            'on_reset_range': None,
            'on_apply_range': None,
            'on_show_performance_settings': None,
            'on_csv_selection_changed': None,
            'on_flip_x_axis': None
        })
        
        self.init_ui()
    
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
        
        # CSV文件管理区域
        csv_group = QGroupBox("CSV文件管理")
        csv_layout = QVBoxLayout(csv_group)
        
        # CSV列表
        self.csv_list_widget = QListWidget()
        self.csv_list_widget.itemSelectionChanged.connect(self._on_csv_selection_changed)
        # 添加双击事件处理，双击文件名自动生成2D热力图
        self.csv_list_widget.itemDoubleClicked.connect(self._on_csv_double_clicked)
        csv_layout.addWidget(self.csv_list_widget)
        
        # CSV操作按钮
        csv_buttons = QHBoxLayout()
        
        self.load_button = QPushButton('添加CSV')
        self.load_button.clicked.connect(self._on_load_button_clicked)
        csv_buttons.addWidget(self.load_button)
        
        self.remove_button = QPushButton('移除CSV')
        self.remove_button.clicked.connect(self._on_remove_button_clicked)
        self.remove_button.setEnabled(False)
        csv_buttons.addWidget(self.remove_button)
        
        self.z_input_button = QPushButton('设置Z轴深度')
        self.z_input_button.clicked.connect(self._on_z_input_button_clicked)
        self.z_input_button.setEnabled(False)
        csv_buttons.addWidget(self.z_input_button)
        
        csv_layout.addLayout(csv_buttons)
        self.left_layout.addWidget(csv_group)
        
        # 热力图生成控制区域
        control_group = QGroupBox("热力图控制")
        control_layout = QVBoxLayout(control_group)
        
        # 生成按钮区域
        generate_buttons = QHBoxLayout()
        
        self.generate_2d_button = QPushButton('生成2D热力图')
        self.generate_2d_button.clicked.connect(self._on_generate_2d_clicked)
        self.generate_2d_button.setEnabled(False)
        generate_buttons.addWidget(self.generate_2d_button)
        
        self.generate_3d_button = QPushButton('生成3D多层热力图')
        self.generate_3d_button.clicked.connect(self._on_generate_3d_clicked)
        self.generate_3d_button.setEnabled(False)
        generate_buttons.addWidget(self.generate_3d_button)
        
        control_layout.addLayout(generate_buttons)
        
        # X轴翻转控制区域
        self.flip_x_checkbox = QCheckBox('翻转X轴方向')
        self.flip_x_checkbox.stateChanged.connect(self._on_flip_x_changed)
        self.flip_x_checkbox.setEnabled(False)
        self.flip_x_checkbox.setToolTip('将X轴方向从递增改为递减，同时镜像图像数据')
        control_layout.addWidget(self.flip_x_checkbox)
        
        # 色标卡控制区域
        colorbar_group = QGroupBox("热力图色标卡设置")
        colorbar_layout = QVBoxLayout(colorbar_group)
        
        # 自动/手动切换
        self.auto_range_checkbox = QCheckBox('自动设置色标卡范围')
        self.auto_range_checkbox.setChecked(True)
        self.auto_range_checkbox.stateChanged.connect(self._on_auto_range_changed)
        colorbar_layout.addWidget(self.auto_range_checkbox)
        
        # 智能范围计算选项
        self.smart_range_checkbox = QCheckBox('使用智能范围计算（推荐）')
        self.smart_range_checkbox.setChecked(True)
        self.smart_range_checkbox.setToolTip('智能范围计算会自动去除异常值，提供更好的视觉效果')
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
        colormap_layout.addRow('色标样式:', self.colormap_combo)
        colorbar_layout.addLayout(colormap_layout)
        
        # 手动范围设置
        manual_range_layout = QFormLayout()
        
        self.vmin_spinbox = QDoubleSpinBox()
        self.vmin_spinbox.setRange(-99999.0, 99999.0)
        self.vmin_spinbox.setDecimals(2)
        self.vmin_spinbox.setValue(0.0)
        self.vmin_spinbox.setEnabled(False)
        # 记录初始值，用于检测是否真的发生了变化
        self._vmin_last_value = 0.0
        manual_range_layout.addRow('最小值 (MPa):', self.vmin_spinbox)
        
        self.vmax_spinbox = QDoubleSpinBox()
        self.vmax_spinbox.setRange(-99999.0, 99999.0)
        self.vmax_spinbox.setDecimals(2)
        self.vmax_spinbox.setValue(100.0)
        self.vmax_spinbox.setEnabled(False)
        # 记录初始值，用于检测是否真的发生了变化
        self._vmax_last_value = 100.0
        manual_range_layout.addRow('最大值 (MPa):', self.vmax_spinbox)
        
        colorbar_layout.addLayout(manual_range_layout)
        
        # 数据范围显示
        self.data_range_label = QLabel('当前数据范围: 未加载数据')
        self.data_range_label.setStyleSheet('color: gray; font-size: 10px;')
        colorbar_layout.addWidget(self.data_range_label)
        
        # 快速设置按钮
        quick_buttons_layout = QHBoxLayout()
        
        self.reset_range_button = QPushButton('重置为数据范围')
        self.reset_range_button.clicked.connect(self._on_reset_range_clicked)
        self.reset_range_button.setEnabled(False)
        quick_buttons_layout.addWidget(self.reset_range_button)
        
        self.apply_range_button = QPushButton('应用设置')
        self.apply_range_button.clicked.connect(self._on_apply_range_clicked)
        self.apply_range_button.setEnabled(False)
        quick_buttons_layout.addWidget(self.apply_range_button)
        
        colorbar_layout.addLayout(quick_buttons_layout)
        control_layout.addWidget(colorbar_group)
        
        # 添加性能设置按钮
        self.performance_button = QPushButton('3D性能设置')
        self.performance_button.clicked.connect(self._on_performance_button_clicked)
        control_layout.addWidget(self.performance_button)
        
        # 保存按钮
        self.save_button = QPushButton('保存当前图像')
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
        self.z_scale_slider.setMinimum(1)   # 对应 0.1
        self.z_scale_slider.setMaximum(20)  # 对应 2.0
        self.z_scale_slider.setValue(5)     # 默认 0.5
        self.z_scale_slider.setTickInterval(2)
        self.z_scale_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        # 连接滑块事件：拖动时只更新标签，松开时才刷新图像
        self.z_scale_slider.valueChanged.connect(self._on_z_scale_value_changed)
        self.z_scale_slider.sliderReleased.connect(self._on_z_scale_released)
        
        # 防止鼠标移出区域后的误操作
        self.z_scale_slider.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.z_scale_slider.installEventFilter(self)
        
        # 美化滑块样式
        self.z_scale_slider.setStyleSheet("""
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
        """)
        
        z_scale_slider_layout.addWidget(self.z_scale_slider)
        
        # 最大值标签
        max_label = QLabel("2.0")
        max_label.setStyleSheet("color: #7f8c8d; font-size: 10px;")
        z_scale_slider_layout.addWidget(max_label)
        z_scale_layout.addLayout(z_scale_slider_layout)
        self.left_layout.addWidget(z_scale_group)
        
        # 状态标签
        self.status_label = QLabel('请添加CSV文件开始')
        self.status_label.setAlignment(Qt.AlignCenter)
        self.left_layout.addWidget(self.status_label)
        
        # 右侧可视化区域
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        h_splitter.addWidget(right_panel, 3)  # 右侧面板占更多空间
        
        # 创建可视化图形区域（一个框架）
        self.visualization_frame = QFrame()
        self.visualization_layout = QVBoxLayout(self.visualization_frame)
        right_layout.addWidget(self.visualization_frame)
    
    def _on_load_button_clicked(self):
        """处理加载按钮点击事件"""
        self.trigger_callback('on_load_csv')
    
    def _on_remove_button_clicked(self):
        """处理移除按钮点击事件"""
        if self.csv_list_widget.currentRow() >= 0:
            self.trigger_callback('on_remove_csv', self.csv_list_widget.currentRow())
    
    def _on_csv_selection_changed(self):
        """处理CSV列表选择变更事件"""
        row = self.csv_list_widget.currentRow()
        self.current_dataset_index = row
        
        # 根据选择状态启用/禁用按钮
        has_selection = row >= 0
        self.remove_button.setEnabled(has_selection)
        self.z_input_button.setEnabled(has_selection)
        self.generate_2d_button.setEnabled(has_selection)
        self.flip_x_button.setEnabled(has_selection)
        
        if has_selection:
            self.trigger_callback('on_csv_selection_changed', row)
    
    def _on_z_input_button_clicked(self):
        """处理设置Z轴深度按钮点击事件"""
        selected_items = self.csv_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "警告", "请选择一个CSV文件！")
            return
        
        # 获取选中项的索引
        selected_index = self.csv_list_widget.row(selected_items[0])
        
        # 调用正确的回调函数
        if self.callbacks.get('on_set_z_depth'):
            self.callbacks['on_set_z_depth'](selected_index)
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
            self.trigger_callback('on_generate_2d', row)
            self.update_status(f'双击生成2D热力图: {item.text()}')
    
    def _on_generate_2d_clicked(self):
        """处理生成2D热力图按钮点击事件"""
        if self.csv_list_widget.currentRow() >= 0:
            self.trigger_callback('on_generate_2d', self.csv_list_widget.currentRow())
    
    def _on_generate_3d_clicked(self):
        """处理生成3D热力图按钮点击事件"""
        self.trigger_callback('on_generate_3d')
    
    def _on_save_button_clicked(self):
        """处理保存热力图按钮点击事件"""
        if self.current_view_type:
            self.trigger_callback('on_save_heatmap', self.current_view_type)
    
    def _on_colormap_changed(self):
        """处理色标变更事件"""
        colormap_name = self.colormap_combo.currentData()
        self.trigger_callback('on_colormap_changed', colormap_name)
    
    def _on_auto_range_changed(self, state):
        """处理自动范围设置变更事件"""
        is_auto = state == Qt.Checked
        self.vmin_spinbox.setEnabled(not is_auto)
        self.vmax_spinbox.setEnabled(not is_auto)
        self.reset_range_button.setEnabled(not is_auto)
        self.apply_range_button.setEnabled(not is_auto)
        self.smart_range_checkbox.setEnabled(is_auto)
        
        self.trigger_callback('on_auto_range_changed', is_auto)
    
    def _on_smart_range_changed(self, state):
        """处理智能范围计算变更事件"""
        is_smart = state == Qt.Checked
        self.trigger_callback('on_smart_range_changed', is_smart)
    
    def _on_reset_range_clicked(self):
        """处理重置范围按钮点击事件"""
        self.trigger_callback('on_reset_range', self.current_dataset_index)
    
    def _on_apply_range_clicked(self):
        """处理应用范围按钮点击事件"""
        settings = {
            'vmin': self.vmin_spinbox.value(),
            'vmax': self.vmax_spinbox.value()
        }
        self.trigger_callback('on_apply_range', settings)
    
    def _on_performance_button_clicked(self):
        """处理性能设置按钮点击事件"""
        self.trigger_callback('on_show_performance_settings')
    
    def _on_flip_x_changed(self, state):
        """处理翻转X轴勾选框状态变化事件"""
        self.trigger_callback('on_flip_x_axis')
    
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
        self.reset_range_button.setEnabled(has_datasets and not self.auto_range_checkbox.isChecked())
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
    
    def update_data_range_display(self, vmin: float, vmax: float, vmin_raw: float = None, vmax_raw: float = None):
        """更新数据范围显示
        
        Args:
            vmin: 最小值（可能经过智能范围计算）
            vmax: 最大值（可能经过智能范围计算）
            vmin_raw: 原始最小值（未经过智能范围计算）
            vmax_raw: 原始最大值（未经过智能范围计算）
        """
        if vmin_raw is not None and vmax_raw is not None:
            self.data_range_label.setText(
                f'智能范围: {vmin:.2f} - {vmax:.2f} MPa\n'
                f'原始范围: {vmin_raw:.2f} - {vmax_raw:.2f} MPa'
            )
        else:
            self.data_range_label.setText(f'当前数据范围: {vmin:.2f} - {vmax:.2f} MPa')
    
    def set_range_values(self, vmin: float, vmax: float):
        """设置手动范围值
        
        Args:
            vmin: 最小值
            vmax: 最大值
        """
        self.vmin_spinbox.setValue(vmin)
        self.vmax_spinbox.setValue(vmax)
        self._vmin_last_value = vmin
        self._vmax_last_value = vmax
    
    def show_2d_figure(self, fig: Figure):
        """显示2D热力图
        
        Args:
            fig: matplotlib Figure对象
        """
        self._clear_visualization()
        
        # 创建新的2D画布
        self.current_canvas = FigureCanvas(fig)
        
        # 添加鼠标悬停事件处理
        if hasattr(fig, '_heatmap_data'):
            self._setup_mouse_hover_events(fig)
        
        # 显示图形
        self.visualization_layout.addWidget(self.current_canvas)
        self.current_view_type = '2d'
        self.save_button.setEnabled(True)
    
    def show_3d_figure(self, fig):
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
        
        self.current_view_type = 'plotly'
        self.save_button.setEnabled(True)
    
    def _clear_visualization(self):
        """清除可视化区域的内容"""
        # 清除当前可视化控件
        if self.current_view_type == '2d' and self.current_canvas:
            self.visualization_layout.removeWidget(self.current_canvas)
            self.current_canvas.deleteLater()
            self.current_canvas = None
            self.hover_annotation = None
        elif self.current_view_type == 'plotly' and self.plotly_view:
            self.visualization_layout.removeWidget(self.plotly_view)
            # 不删除plotly_view对象，而是隐藏它以便重用
            self.plotly_view.hide()
    
    def _setup_mouse_hover_events(self, fig: Figure):
        """设置鼠标悬停事件处理
        
        Args:
            fig: matplotlib Figure对象
        """
        if hasattr(fig, '_heatmap_data'):
            # 连接鼠标移动事件
            self.current_canvas.mpl_connect('motion_notify_event', self._on_mouse_move)
            # 连接鼠标离开事件
            self.current_canvas.mpl_connect('axes_leave_event', self._on_mouse_leave)
    
    def _on_mouse_move(self, event: MouseEvent):
        """鼠标移动事件处理
        
        Args:
            event: matplotlib鼠标事件对象
        """
        if event.inaxes is None or not self.current_canvas or not hasattr(self.current_canvas.figure, '_heatmap_data'):
            return
        
        try:
            # 获取热力图数据
            heatmap_data = self.current_canvas.figure._heatmap_data
            xi_grid = heatmap_data['xi_grid']
            yi_grid = heatmap_data['yi_grid']
            zi = heatmap_data['zi']
            x_center = heatmap_data['x_center']
            y_center = heatmap_data['y_center']
            radius = heatmap_data['radius']
            z_depth = heatmap_data['z_depth']
            
            # 获取鼠标位置
            x_mouse, y_mouse = event.xdata, event.ydata
            
            # 检查鼠标是否在圆形区域内
            distance_from_center = np.sqrt((x_mouse - x_center)**2 + (y_mouse - y_center)**2)
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
            self._show_hover_annotation(x_mouse, y_mouse, pressure_value, z_depth, event.inaxes)
            
        except Exception as e:
            print(f"鼠标悬停事件处理错误: {e}")
    
    def _on_mouse_leave(self, event):
        """鼠标离开坐标轴事件处理
        
        Args:
            event: matplotlib鼠标事件对象
        """
        self._hide_hover_annotation()
    
    def _show_hover_annotation(self, x: float, y: float, pressure: float, z_depth: float, ax):
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
            hover_text = f'X: {x:.1f} μm\nY: {y:.1f} μm\nZ: {z_depth:.1f} μm\n应力: {pressure:.2f} MPa'
            
            # 创建注释，跟随鼠标显示在左上方
            self.hover_annotation = ax.annotate(
                hover_text,
                xy=(x, y),
                xytext=(-80, 30),  # 偏移到鼠标左上方
                textcoords='offset points',
                bbox=dict(
                    boxstyle='round,pad=0.5',
                    facecolor='yellow',
                    alpha=0.9,
                    edgecolor='black',
                    linewidth=1
                ),
                fontsize=10,
                fontfamily='sans-serif',
                ha='left',
                va='bottom',
                zorder=10000  # 设置更高的层级
            )
            
            # 刷新画布
            self.current_canvas.draw_idle()
            
        except Exception as e:
            print(f"显示悬停注释错误: {e}")
    
    def _hide_hover_annotation(self):
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
        
        if figure_type == '2d':
            default_name = 'circular_heatmap_2d.png'
            file_filter = 'PNG文件 (*.png);;PDF文件 (*.pdf);;SVG文件 (*.svg)'
        elif figure_type == 'plotly':
            default_name = 'stress_3d_visualization.png'
            file_filter = 'PNG文件 (*.png);;PDF文件 (*.pdf);;SVG文件 (*.svg);;HTML文件 (*.html);;JSON文件 (*.json)'
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, '保存热力图', default_name, file_filter
        )
        
        return file_path
    
    def update_flip_x_status(self, is_flipped: bool):
        """更新X轴翻转勾选框状态
        
        Args:
            is_flipped: 是否已翻转X轴
        """
        # 暂时断开信号连接，避免触发回调
        self.flip_x_checkbox.blockSignals(True)
        self.flip_x_checkbox.setChecked(is_flipped)
        self.flip_x_checkbox.blockSignals(False)
    
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