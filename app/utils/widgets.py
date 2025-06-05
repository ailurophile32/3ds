"""
可重用UI组件和控件工具

提供各种可重用的UI组件，简化视图层的构建，提高代码复用性。
"""
import os
import tempfile
import traceback
from typing import Optional, Callable, Dict, Any, Tuple

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFont
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QLabel, QSlider,
    QPushButton, QComboBox, QCheckBox, QDoubleSpinBox, QVBoxLayout
)
import plotly.graph_objects as go


class PlotlyWebView(QWebEngineView):
    """用于显示Plotly图表的WebView"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.temp_file: Optional[str] = None
        self.setMinimumSize(600, 400)
        print("DEBUG: PlotlyWebView initialized")
        
        # 添加加载完成和错误处理信号
        self.loadFinished.connect(self.on_load_finished)
        self.loadStarted.connect(self.on_load_started)
    
    def on_load_started(self):
        """加载开始时的处理"""
        print("DEBUG: WebView开始加载页面")
    
    def on_load_finished(self, success: bool):
        """加载完成时的处理"""
        if success:
            print("DEBUG: WebView页面加载成功")
            if hasattr(self.parent(), 'status_label'):
                self.parent().status_label.setText('3D热力图加载完成')
        else:
            print("ERROR: WebView页面加载失败")
            if hasattr(self.parent(), 'message_handler'):
                self.parent().message_handler.show_error("加载失败", 
                               "3D图表加载失败，请检查数据大小或尝试降低性能设置中的分辨率。")
            if hasattr(self.parent(), 'status_label'):
                self.parent().status_label.setText('3D图表加载失败')
    
    def display_figure(self, fig: go.Figure):
        """显示Plotly图形
        
        Args:
            fig: plotly.graph_objects.Figure对象
        """
        print("DEBUG: PlotlyWebView.display_figure called")
        try:
            # 清理旧的临时文件
            self._cleanup_temp_file()
            
            # 创建临时HTML文件，使用更安全的临时文件创建方式
            try:
                print("DEBUG: Attempting to create new temp file with mkstemp")
                # 使用系统临时目录，避免权限问题
                temp_dir = tempfile.gettempdir()
                fd, temp_file_path = tempfile.mkstemp(suffix='.html', dir=temp_dir)
                os.close(fd) # 确保文件描述符立即关闭
                self.temp_file = temp_file_path # 存储路径
                print(f"DEBUG: New temp file created: {self.temp_file}")
            except Exception as temp_file_error:
                print(f"错误: 创建临时文件失败: {str(temp_file_error)}")
                if hasattr(self.parent(), 'message_handler'):
                    self.parent().message_handler.show_error("错误", f"创建临时文件失败: {str(temp_file_error)}")
                return

            # 精简配置以减少HTML文件大小
            config = {
                'scrollZoom': True,
                'displayModeBar': True,
                'responsive': True,  # 响应式设计
                'toImageButtonOptions': {
                    'format': 'png',
                    'filename': 'stress_3d_plot',
                    'height': 800,
                    'width': 1000,
                    'scale': 1.5
                }
            }
            
            try:
                print(f"DEBUG: Attempting to write Plotly figure to HTML: {self.temp_file}")
                
                # 内嵌Plotly.js库以避免网络依赖问题
                fig.write_html(
                    self.temp_file,
                    include_plotlyjs=True,  # 内嵌plotly.js库，避免网络依赖
                    config=config,
                    include_mathjax=False,
                    full_html=True,
                    auto_open=False
                )
                print(f"DEBUG: Successfully wrote Plotly figure to HTML: {self.temp_file}")
                
                # 验证文件是否成功创建且有内容
                if not os.path.exists(self.temp_file):
                    raise FileNotFoundError(f"临时HTML文件创建失败: {self.temp_file}")
                
                file_size = os.path.getsize(self.temp_file)
                if file_size < 1000:  # 文件太小可能有问题
                    raise ValueError(f"生成的HTML文件异常小 ({file_size} bytes)，可能生成失败")
                
                print(f"DEBUG: HTML文件验证成功，大小: {file_size} bytes")
            except Exception as write_error:
                print(f"错误: 写入HTML文件失败: {str(write_error)}")
                if hasattr(self.parent(), 'message_handler'):
                    self.parent().message_handler.show_error("错误", f"写入HTML文件失败: {str(write_error)}")
                self._cleanup_temp_file()
                return
            
            try:
                # 使用file://协议确保正确的URL格式
                local_url = QUrl.fromLocalFile(os.path.abspath(self.temp_file))
                print(f"DEBUG: Attempting to load URL in QWebEngineView: {local_url.toString()}")
                
                if not local_url.isValid():
                    print(f"错误: 生成的本地文件URL无效: {self.temp_file}")
                    if hasattr(self.parent(), 'message_handler'):
                        self.parent().message_handler.show_error("错误", f"无法加载图表，因为生成的URL无效: {self.temp_file}")
                    self._cleanup_temp_file()
                    return

                self.load(local_url)
                print(f"DEBUG: QWebEngineView.load() called with URL: {local_url.toString()}")
                
                # 显示加载提示
                if hasattr(self.parent(), 'status_label'):
                    self.parent().status_label.setText('正在加载3D图表，请稍候...')
                
            except Exception as load_error:
                print(f"错误: 加载URL到WebView失败: {str(load_error)}")
                if hasattr(self.parent(), 'message_handler'):
                    self.parent().message_handler.show_error("错误", f"加载URL到WebView失败: {str(load_error)}")
                self._cleanup_temp_file()
                return
            
        except Exception as e:
            error_message = f'PlotlyWebView.display_figure 发生错误: {str(e)}\nTraceback: {traceback.format_exc()}'
            print(error_message)
            if hasattr(self.parent(), 'message_handler'):
                self.parent().message_handler.show_error("显示错误", f"在显示3D图形时发生内部错误，详情请查看控制台。\n{str(e)}")
        print("DEBUG: PlotlyWebView.display_figure finished")

    def _cleanup_temp_file(self):
        """安全清理临时文件"""
        if self.temp_file and os.path.exists(self.temp_file):
            try:
                print(f"DEBUG: Cleaning up temp file: {self.temp_file}")
                os.unlink(self.temp_file)
                print(f"DEBUG: Successfully cleaned up temp file: {self.temp_file}")
            except Exception as e:
                # 只记录错误，不抛出异常
                print(f"警告: 清理临时文件 {self.temp_file} 失败: {e}")
        self.temp_file = None

    def __del__(self):
        """清理临时文件"""
        print(f"DEBUG: PlotlyWebView.__del__ called")
        self._cleanup_temp_file()


class ZDepthInputDialog(QDialog):
    """Z轴深度输入对话框"""
    
    def __init__(self, parent=None, current_z=0.0):
        super().__init__(parent)
        self.z_depth = current_z
        self.init_ui()
    
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("Z轴深度设置")
        layout = QFormLayout()
        
        # Z轴深度输入
        self.z_spinbox = QDoubleSpinBox()
        self.z_spinbox.setRange(-10000.0, 10000.0)
        self.z_spinbox.setValue(self.z_depth)
        self.z_spinbox.setSuffix(' μm')
        self.z_spinbox.setDecimals(2)
        
        layout.addRow('Z轴深度:', self.z_spinbox)
        
        # 按钮
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("确定")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)
        
        layout.addRow("", button_layout)
        self.setLayout(layout)
        
        # 设置默认焦点和选中状态
        self.z_spinbox.setFocus()  # 设置输入框为默认焦点
        self.z_spinbox.selectAll()  # 选中输入框中的所有文本
        self.ok_button.setDefault(True)  # 设置确定按钮为默认按钮
    
    def get_z_depth(self) -> float:
        """获取Z轴深度值"""
        return self.z_spinbox.value()


class SettingItem:
    """设置项组件工厂类，用于创建通用的设置项UI组件"""
    
    @staticmethod
    def create_setting_with_info(label_widget, control_widget, tooltip_text, parent=None) -> QHBoxLayout:
        """创建带有信息提示的设置项布局
        
        Args:
            label_widget: 标签控件
            control_widget: 控制控件（滑块、复选框等）
            tooltip_text: 提示文本
            parent: 父控件，用于显示信息对话框
            
        Returns:
            QHBoxLayout: 包含标签、控件和信息按钮的布局
        """
        layout = QHBoxLayout()
        
        # 添加标签
        layout.addWidget(label_widget)
        
        # 添加控件
        layout.addWidget(control_widget)
        
        # 创建信息按钮
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
        info_button.setToolTip(tooltip_text)
        
        if parent:
            info_button.clicked.connect(lambda: parent.message_handler.show_info("参数说明", tooltip_text))
        
        layout.addWidget(info_button)
        
        return layout


from .config import DefaultSettings

class PerformanceSettingsDialog(QDialog):
    def __init__(self, parent=None, current_settings=None, message_handler=None):
        super().__init__(parent)
        # 使用配置文件的默认值作为fallback
        self.default_settings = DefaultSettings.get_performance_settings()
        self.settings = current_settings or self.default_settings
        self.message_handler = message_handler
        self.init_ui()
    
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("3D性能设置")
        layout = QFormLayout()
        
        # 分辨率滑块
        self.resolution_slider = QSlider(Qt.Horizontal)
        self.resolution_slider.setRange(20, 200)
        self.resolution_slider.setValue(
            self.settings.get('resolution', self.default_settings['resolution'])
        )
        self.resolution_label = QLabel(f"分辨率: {self.resolution_slider.value()}")
        self.resolution_slider.valueChanged.connect(
            lambda value: self.resolution_label.setText(f"分辨率: {value}"))
        resolution_layout = self._create_setting_with_info(
            self.resolution_label, self.resolution_slider,
            "控制3D热力图的网格密度。较低的分辨率可以显著提高渲染速度，但会降低图像精度。推荐范围：20-100。"
        )
        layout.addRow("", resolution_layout)
        
        # 点大小滑块
        self.point_size_slider = QSlider(Qt.Horizontal)
        self.point_size_slider.setRange(1, 20)
        self.point_size_slider.setValue(self.settings.get('point_size', 20))  # 默认最大值
        self.point_size_label = QLabel(f"点大小: {self.point_size_slider.value()}")
        self.point_size_slider.valueChanged.connect(
            lambda value: self.point_size_label.setText(f"点大小: {value}"))
        point_size_layout = self._create_setting_with_info(
            self.point_size_label, self.point_size_slider,
            "设置数据点的显示大小。较小的点可以减少GPU渲染负担，提高性能。"
        )
        layout.addRow("", point_size_layout)
        
        # 透明度滑块
        self.alpha_slider = QSlider(Qt.Horizontal)
        self.alpha_slider.setRange(1, 10)
        self.alpha_slider.setValue(int(self.settings.get('alpha', 1.0) * 10))  # 默认最大值（完全不透明）
        self.alpha_label = QLabel(f"透明度: {self.alpha_slider.value() / 10}")
        self.alpha_slider.valueChanged.connect(
            lambda value: self.alpha_label.setText(f"透明度: {value / 10}"))
        alpha_layout = self._create_setting_with_info(
            self.alpha_label, self.alpha_slider,
            "控制热力图的透明度。较低的透明度可以减少渲染复杂度，提高性能。"
        )
        layout.addRow("", alpha_layout)
        
        # 数据抽样率
        self.decimation_combo = QComboBox()
        decimation_options = [1, 2, 5, 10, 20]
        for option in decimation_options:
            self.decimation_combo.addItem(f"1/{option}", option)
        # 设置当前值
        current_decimation = self.settings.get('decimation', 1)  # 默认不抽样，保持最高精度
        index = decimation_options.index(current_decimation) if current_decimation in decimation_options else 0
        self.decimation_combo.setCurrentIndex(index)
        decimation_layout = self._create_setting_with_info(
            QLabel("数据抽样率:"), self.decimation_combo,
            "控制显示的数据点数量。1/5表示每5个点显示1个。较高的抽样率可以大幅提高性能，但会降低数据精度。"
        )
        layout.addRow("", decimation_layout)
        
        # 显示原始数据点
        self.show_points_checkbox = QCheckBox()
        self.show_points_checkbox.setChecked(self.settings.get('show_points', True))  # 默认开启，显示完整信息
        show_points_layout = self._create_setting_with_info(
            QLabel("显示原始数据点:"), self.show_points_checkbox,
            "是否在热力图上显示原始数据点。禁用此选项可以显著提高渲染性能，特别是对于大数据集。"
        )
        layout.addRow("", show_points_layout)
        
        # 方格网格线宽度
        self.grid_width_slider = QSlider(Qt.Horizontal)
        self.grid_width_slider.setRange(1, 5)
        self.grid_width_slider.setValue(self.settings.get('grid_width', 5))  # 默认最大值，最清晰的网格线
        self.grid_width_label = QLabel(f"网格线宽度: {self.grid_width_slider.value()}")
        self.grid_width_slider.valueChanged.connect(
            lambda value: self.grid_width_label.setText(f"网格线宽度: {value}"))
        grid_width_layout = self._create_setting_with_info(
            self.grid_width_label, self.grid_width_slider,
            "控制3D网格线的粗细。较细的线条可以减少渲染负担。"
        )
        layout.addRow("", grid_width_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("确定")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)
        
        layout.addRow("", button_layout)
        self.setLayout(layout)
    
    def _create_setting_with_info(self, label_widget, control_widget, tooltip_text):
        """创建带有信息提示的设置项布局"""
        layout = QHBoxLayout()
        
        # 添加标签
        layout.addWidget(label_widget)
        
        # 添加控件
        layout.addWidget(control_widget)
        
        # 创建信息按钮
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
        info_button.setToolTip(tooltip_text)
        info_button.clicked.connect(lambda: self._show_info_dialog(tooltip_text))
        
        layout.addWidget(info_button)
        
        return layout
    
    def _show_info_dialog(self, info_text):
        """显示信息对话框
        
        Args:
            info_text: 要显示的信息文本
        """
        if self.message_handler:
            self.message_handler.show_info("参数说明", info_text)
    
    def get_settings(self) -> Dict[str, Any]:
        """获取设置值"""
        return {
            'resolution': self.resolution_slider.value(),
            'point_size': self.point_size_slider.value(),
            'alpha': self.alpha_slider.value() / 10,
            'decimation': self.decimation_combo.currentData(),
            'show_points': self.show_points_checkbox.isChecked(),
            'grid_width': self.grid_width_slider.value(),
        }