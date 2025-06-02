import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from scipy.interpolate import griddata
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any
import sys
import traceback # 导入traceback
import matplotlib
from matplotlib.figure import Figure
# 使用PySide6兼容的matplotlib后端
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
import json
import tempfile
import os

# PySide6 组件导入
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, 
    QPushButton, QFileDialog, QLabel, QInputDialog, QMessageBox,
    QTabWidget, QDoubleSpinBox, QFormLayout, QDialog, QListWidget, QGroupBox, QFrame,
    QSlider, QCheckBox, QComboBox, QProgressBar, QScrollArea
)
from PySide6.QtCore import Qt, QUrl, QSize
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtGui import QFont, QIcon

# 解决中文乱码问题
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
matplotlib.rcParams['font.family'] = 'sans-serif'

# 设置Plotly的默认模板
pio.templates.default = "plotly_white"


class CircularHeatmapGenerator:
    """生成圆形热力图的核心类"""
    
    def __init__(self):
        self.data_sets = []  # 存储多个数据集，每个元素是(数据, Z轴深度, 文件名)的元组
        self.fig_2d = None  # 当前选中的2D图形
        self.fig_3d = None  # 3D图形（包含所有深度层）
        self.plotly_fig: Optional[go.Figure] = None  # Plotly图形，添加类型提示
        self.performance_settings = {
            'resolution': 200,       # 默认降低分辨率以提高性能
            'max_points': 10000,     # 限制点的最大数量
            'point_size': 20,        # 点大小
            'alpha': 1.0,           # 透明度
            'show_points': False,   # 是否显示原始数据点
            'decimation': 1,        # 数据抽样率 (取每 N 个点)
            'z_scale': 0.5          # Z轴间距缩放比例
        }
        # 添加色标卡范围设置
        self.colorbar_settings = {
            'auto_range': True,     # 是否自动设置范围
            'vmin': None,          # 手动设置的最小值
            'vmax': None           # 手动设置的最大值
        }
        
    def load_csv(self, file_path: str, z_depth: float = 0.0) -> bool:
        """加载CSV文件
        
        Args:
            file_path: CSV文件路径
            z_depth: Z轴深度值
            
        Returns:
            bool: 加载是否成功
        """
        try:
            data = pd.read_csv(file_path, encoding='utf-8')
            file_name = Path(file_path).name
            print(f"成功加载数据: {len(data)} 个数据点")
            print(f"X范围: {data['X'].min():.1f} - {data['X'].max():.1f} μm")
            print(f"Y范围: {data['Y'].min():.1f} - {data['Y'].max():.1f} μm")
            print(f"应力值范围: {data['Value'].min():.2f} - {data['Value'].max():.2f} MPa")
            
            # 将数据集添加到列表
            self.data_sets.append((data, z_depth, file_name))
            return True
        except UnicodeDecodeError:
            # 如果UTF-8失败，尝试其他编码
            try:
                data = pd.read_csv(file_path, encoding='gbk')
                file_name = Path(file_path).name
                print(f"成功加载数据: {len(data)} 个数据点")
                print(f"X范围: {data['X'].min():.1f} - {data['X'].max():.1f} μm")
                print(f"Y范围: {data['Y'].min():.1f} - {data['Y'].max():.1f} μm")
                print(f"应力值范围: {data['Value'].min():.2f} - {data['Value'].max():.2f} MPa")
                
                # 将数据集添加到列表
                self.data_sets.append((data, z_depth, file_name))
                return True
            except Exception as e:
                print(f"加载CSV文件失败: {e}")
                return False
        except Exception as e:
            print(f"加载CSV文件失败: {e}")
            return False
    
    def update_z_depth(self, index: int, z_depth: float):
        """更新特定数据集的Z轴深度值
        
        Args:
            index: 数据集索引
            z_depth: 新的Z轴深度值
        """
        if 0 <= index < len(self.data_sets):
            data, _, file_name = self.data_sets[index]
            self.data_sets[index] = (data, z_depth, file_name)
            print(f"已更新 {file_name} 的Z轴深度为: {z_depth} μm")
    
    def remove_dataset(self, index: int):
        """删除特定索引的数据集
        
        Args:
            index: 要删除的数据集索引
        """
        if 0 <= index < len(self.data_sets):
            _, _, file_name = self.data_sets.pop(index)
            print(f"已移除数据集: {file_name}")
    
    def get_dataset_count(self) -> int:
        """获取数据集数量"""
        return len(self.data_sets)
    
    def update_colorbar_settings(self, settings: Dict[str, Any]):
        """更新色标卡设置
        
        Args:
            settings: 色标卡设置字典
        """
        self.colorbar_settings.update(settings)
        print(f"色标卡设置已更新: {settings}")
    
    def get_data_range(self, dataset_index: int = None) -> Tuple[float, float]:
        """获取数据的值范围
        
        Args:
            dataset_index: 数据集索引，如果为None则计算所有数据集的范围
            
        Returns:
            Tuple[float, float]: (最小值, 最大值)
        """
        if len(self.data_sets) == 0:
            return (0.0, 1.0)
        
        if dataset_index is not None:
            if 0 <= dataset_index < len(self.data_sets):
                data, _, _ = self.data_sets[dataset_index]
                return (data['Value'].min(), data['Value'].max())
            else:
                return (0.0, 1.0)
        else:
            # 计算所有数据集的范围
            all_values = []
            for data, _, _ in self.data_sets:
                all_values.extend(data['Value'].values)
            if all_values:
                return (min(all_values), max(all_values))
            else:
                return (0.0, 1.0)
    
    def create_circular_heatmap_2d(self, dataset_index: int = 0, resolution: int = 200, figsize: Tuple[int, int] = (10, 10)) -> Figure:
        """创建特定数据集的2D圆形热力图
        
        Args:
            dataset_index: 数据集索引
            resolution: 网格分辨率
            figsize: 图形大小
            
        Returns:
            Figure: matplotlib图形对象
        """
        if len(self.data_sets) == 0:
            raise ValueError("请先加载CSV数据")
        
        if dataset_index < 0 or dataset_index >= len(self.data_sets):
            raise ValueError(f"数据集索引无效: {dataset_index}")
        
        # 获取选定的数据集
        data, z_depth, file_name = self.data_sets[dataset_index]
        
        # 提取坐标和数值
        x = data['X'].values
        y = data['Y'].values
        values = data['Value'].values
        
        # 计算数据的中心点和半径
        x_center = (x.max() + x.min()) / 2
        y_center = (y.max() + y.min()) / 2
        radius = max(x.max() - x.min(), y.max() - y.min()) / 2
        
        # 创建圆形网格
        xi = np.linspace(x_center - radius, x_center + radius, resolution)
        yi = np.linspace(y_center - radius, y_center + radius, resolution)
        xi_grid, yi_grid = np.meshgrid(xi, yi)
        
        # 插值生成热力图数据
        zi = griddata((x, y), values, (xi_grid, yi_grid), method='cubic', fill_value=np.nan)
        
        # 创建圆形遮罩
        distances = np.sqrt((xi_grid - x_center)**2 + (yi_grid - y_center)**2)
        mask = distances > radius
        zi[mask] = np.nan
        
        # 创建图形
        self.fig_2d = Figure(figsize=figsize, facecolor='white')
        ax = self.fig_2d.add_subplot(111)
        
        # 确定色标卡范围
        if self.colorbar_settings['auto_range']:
            vmin, vmax = None, None  # matplotlib自动设置
        else:
            vmin = self.colorbar_settings['vmin']
            vmax = self.colorbar_settings['vmax']
        
        # 绘制热力图
        im = ax.imshow(zi, extent=[x_center-radius, x_center+radius, 
                                  y_center-radius, y_center+radius],
                      origin='lower', cmap='RdYlBu_r', aspect='equal',
                      vmin=vmin, vmax=vmax)
        
        # 添加圆形边界
        circle = Circle((x_center, y_center), radius, fill=False, 
                       edgecolor='black', linewidth=2)
        ax.add_patch(circle)
        
        # 设置坐标轴（确保中文正常显示）
        ax.set_xlim(x_center - radius * 1.1, x_center + radius * 1.1)
        ax.set_ylim(y_center - radius * 1.1, y_center + radius * 1.1)
        ax.set_xlabel('X坐标 (μm)', fontsize=12, fontfamily='sans-serif')
        ax.set_ylabel('Y坐标 (μm)', fontsize=12, fontfamily='sans-serif')
        ax.set_title(f'SiC应力分布2D热力图 (Z={z_depth}μm)\n{file_name}', 
                     fontsize=14, fontweight='bold', fontfamily='sans-serif')
        
        # 添加颜色条
        cbar = self.fig_2d.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label('应力 (MPa)', fontsize=12, fontfamily='sans-serif')
        
        # 添加原始数据点
        ax.scatter(x, y, c='white', s=1, alpha=0.3, edgecolors='none')
        
        self.fig_2d.tight_layout()
        return self.fig_2d
    
    def update_performance_settings(self, settings: Dict[str, Any]):
        """更新性能设置
        
        Args:
            settings: 性能设置字典
        """
        self.performance_settings.update(settings)
        print(f"性能设置已更新: {settings}")
    
    def create_plotly_3d_heatmap(self) -> Optional[go.Figure]:
        """使用Plotly创建3D热力图 - 方格地毯图样式
        
        Returns:
            go.Figure or None: Plotly图形对象, 如果发生错误则返回None
        """
        if len(self.data_sets) == 0:
            print("错误: 没有加载CSV数据用于生成3D热力图。")
            return None
        
        try:
            print("DEBUG: 开始创建 Plotly 3D 方格地毯热力图...")
            
            self.plotly_fig = make_subplots(
                rows=1, cols=1,
                specs=[[{'type': 'scene'}]],
                subplot_titles=[" "]
            )
            
            # 为每个数据集创建方格地毯图层
            for dataset_index, (data, z_depth, file_name) in enumerate(self.data_sets):
                try:
                    print(f"DEBUG: 处理数据集 {dataset_index}: {file_name} at Z={z_depth}")
                    x = data['X'].values
                    y = data['Y'].values
                    values = data['Value'].values
                    
                    x_center = (x.max() + x.min()) / 2
                    y_center = (y.max() + y.min()) / 2
                    radius = max(x.max() - x.min(), y.max() - y.min()) / 2
                    
                    # 创建规则网格用于方格显示
                    resolution = self.performance_settings['resolution']
                    xi = np.linspace(x_center - radius, x_center + radius, resolution)
                    yi = np.linspace(y_center - radius, y_center + radius, resolution)
                    xi_grid, yi_grid = np.meshgrid(xi, yi)
                    
                    # 数据插值到网格
                    if len(x) < 4:
                        print(f"警告: 数据集 {file_name} 点数过少 ({len(x)})，无法进行插值，跳过。")
                        continue
                    
                    zi_grid = griddata((x, y), values, (xi_grid, yi_grid), method='linear', fill_value=np.nan)
                    
                    # 应用严格的圆形遮罩，完全去除方形边角
                    grid_distances = np.sqrt((xi_grid - x_center)**2 + (yi_grid - y_center)**2)
                    # 使用更严格的圆形边界，确保只显示中间圆形数据
                    mask_grid = grid_distances > radius * 0.95  # 大幅收缩边界确保完全圆形
                    zi_grid[mask_grid] = np.nan
                    
                    if np.all(np.isnan(zi_grid)):
                        print(f"警告: 数据集 {file_name} 的插值网格全为 NaN，跳过。")
                        continue
                    
                    # 创建方格地毯图效果 - 使用Surface但设置为平面
                    print(f"DEBUG: 为 {file_name} 添加方格地毯图层")
                    
                    # 获取方格样式设置
                    grid_width = self.performance_settings.get('grid_width', 1)
                    carpet_alpha = self.performance_settings.get('carpet_alpha', 0.8)
                    
                    # 计算有效数据的范围用于颜色映射
                    valid_data = zi_grid[~np.isnan(zi_grid)]
                    if len(valid_data) > 0:
                        vmin, vmax = np.min(valid_data), np.max(valid_data)
                    else:
                        vmin, vmax = 0, 1
                    
                    # 创建遮罩后的Z值，保持原始z_depth值不变
                    z_masked = np.full_like(zi_grid, z_depth)
                    z_masked[np.isnan(zi_grid)] = np.nan
                    
                    self.plotly_fig.add_trace(
                         go.Surface(
                             x=xi_grid,
                             y=yi_grid,
                             z=z_masked,  # 使用遮罩后的Z值
                             surfacecolor=zi_grid,
                             colorscale='RdBu_r',
                             cmin=vmin,  # 设置颜色范围最小值
                             cmax=vmax,  # 设置颜色范围最大值
                             cauto=False,  # 禁用自动颜色范围
                             opacity=carpet_alpha,
                             showscale=(dataset_index == 0),  # 仅为第一个轨迹显示色条
                             # 确保NaN值显示为透明
                             connectgaps=False,  # 不连接NaN值之间的间隙
                             hidesurface=False,  # 显示表面
                             colorbar=dict(
                                 title="应力值 (MPa)",
                                 thickness=20,
                                 x=1.02,
                                 title_font=dict(size=12),
                                 tickfont=dict(size=10)
                             ) if dataset_index == 0 else None,
                             name=f"{file_name} (Z={z_depth}μm)",
                             # 设置表面样式为方格效果
                             contours=dict(
                                 x=dict(show=True, color="white", width=grid_width),
                                 y=dict(show=True, color="white", width=grid_width),
                                 z=dict(show=False)
                             ),
                             # 添加悬停信息
                             hovertemplate="<b>%{fullData.name}</b><br>" +
                                         "X: %{x:.1f}μm<br>" +
                                         "Y: %{y:.1f}μm<br>" +
                                         "Z: %{z:.1f}μm<br>" +
                                         "应力: %{surfacecolor:.2f} MPa<extra></extra>",
                             # 添加光照效果使方格更明显
                             lighting=dict(
                                 ambient=0.8,
                                 diffuse=0.8,
                                 specular=0.1
                             ),
                             lightposition=dict(
                                 x=100,
                                 y=100,
                                 z=1000
                             )
                         )
                     )
                    
                    # 可选：添加原始数据点作为参考
                    if self.performance_settings.get('show_points', False):
                        # 对原始数据进行采样以减少点数
                        decimation = self.performance_settings['decimation']
                        if decimation > 1:
                            indices = np.arange(0, len(x), decimation)
                            x_sampled = x[indices]
                            y_sampled = y[indices]
                            values_sampled = values[indices]
                            z_sampled = np.full_like(x_sampled, z_depth + 0.1)  # 稍微抬高避免重叠
                        else:
                            x_sampled, y_sampled, values_sampled = x, y, values
                            z_sampled = np.full_like(x_sampled, z_depth + 0.1)
                        
                        # 应用严格的圆形遮罩，与表面图保持一致
                        distances = np.sqrt((x_sampled - x_center)**2 + (y_sampled - y_center)**2)
                        mask = distances <= radius *0.95  # 使用与表面图相同的严格边界
                        
                        if np.any(mask):
                            self.plotly_fig.add_trace(
                                go.Scatter3d(
                                    x=x_sampled[mask],
                                    y=y_sampled[mask],
                                    z=z_sampled[mask],
                                    mode='markers',
                                    marker=dict(
                                        size=2,
                                        color='white',
                                        opacity=0.6,
                                        line=dict(width=0.5, color='black')
                                    ),
                                    showlegend=False,
                                    hoverinfo='skip',
                                    name=f"{file_name} 数据点"
                                )
                            )
                    
                    # 方格地毯图已经替代了原有的表面渲染功能
                except Exception as dataset_error:
                    print(f"警告: 处理数据集 {file_name} 时出错: {str(dataset_error)}")
                    continue
            
            print("DEBUG: 配置3D场景布局...")
            self.plotly_fig.update_layout(
                scene=dict(
                    xaxis_title='X坐标 (μm)',
                    yaxis_title='Y坐标 (μm)',
                    zaxis_title='Z深度 (μm)',
                    aspectmode='manual',  # 改为手动模式以自定义比例
                    aspectratio=dict(x=1, y=1, z=1.5 * self.performance_settings.get('z_scale', 1.0)),  # 通过调节z轴显示比例来控制间距视觉效果
                    camera=dict(
                        eye=dict(x=1.5, y=1.5, z=1)
                    )
                ),
                title_text="SiC应力3D切片",
                margin=dict(l=0, r=0, t=50, b=0),
                legend=dict(
                    yanchor="top",
                    y=0.99,
                    xanchor="left",
                    x=0.01,
                    bgcolor="rgba(255,255,255,0.5)"
                ),
                template="plotly_white"
            )
            
            # 简化配置以减少内存占用
            self.plotly_fig.update_layout(
                uirevision='true',  # 减少UI状态更新
                hovermode=False,    # 禁用悬停模式以减少事件处理
                autosize=True       # 自动调整大小
            )
            
            print("DEBUG: Plotly 3D 方格地毯热力图创建完成。")
            return self.plotly_fig

        except MemoryError:
            error_message = "内存不足，无法创建3D热力图。请尝试减少数据点数量或降低分辨率。"
            print(error_message)
            return None
        except Exception as e:
            error_message = f'创建Plotly 3D图形时发生错误: {str(e)}\nTraceback: {traceback.format_exc()}'
            print(error_message)
            return None
    
    def save_heatmap(self, output_path: str, figure_type: str = '2d', dpi: int = 300):
        """保存热力图
        
        Args:
            output_path: 输出文件路径
            figure_type: 图形类型 ('2d' 或 '3d' 或 'plotly')
            dpi: 图像分辨率
        """
        if figure_type == '2d':
            if self.fig_2d is None:
                raise ValueError("请先加载2D热力图")
            self.fig_2d.savefig(output_path, dpi=dpi, bbox_inches='tight')
            print(f"2D热力图已保存到: {output_path}")
        elif figure_type == '3d':
            if self.fig_3d is None:
                raise ValueError("请先加载3D热力图")
            self.fig_3d.savefig(output_path, dpi=dpi, bbox_inches='tight')
            print(f"3D热力图已保存到: {output_path}")
        elif figure_type == 'plotly':
            if self.plotly_fig is None:
                raise ValueError("请先加载Plotly热力图")
            
            # 使用Plotly原生导出功能，根据文件扩展名保存为不同格式
            ext = Path(output_path).suffix.lower()
            if ext == '.html':
                pio.write_html(self.plotly_fig, output_path)
            elif ext in ['.png', '.jpg', '.jpeg', '.pdf', '.svg']:
                # 直接使用plotly的原生图片导出功能
                pio.write_image(self.plotly_fig, output_path, width=1920, height=1080, scale=2)
            elif ext == '.json':
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(json.dumps(self.plotly_fig.to_dict()))
            else:
                # 默认导出为PNG格式
                pio.write_image(self.plotly_fig, output_path, width=1920, height=1080, scale=2)
            
            print(f"Plotly热力图已保存到: {output_path}")
        else:
            raise ValueError(f"不支持的图形类型: {figure_type}")


class ZDepthInputDialog(QDialog):
    """Z轴深度输入对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.z_depth = 0.0
        self.init_ui()
    
    def init_ui(self):
        """初始化界面"""
        layout = QFormLayout()
        
        # Z轴深度输入
        self.z_spinbox = QDoubleSpinBox()
        self.z_spinbox.setRange(-10000.0, 10000.0)
        self.z_spinbox.setValue(0.0)
        self.z_spinbox.setSuffix(' μm')
        self.z_spinbox.setDecimals(2)
        
        layout.addRow('Z轴深度:', self.z_spinbox)
        self.setLayout(layout)
    
    def get_z_depth(self) -> float:
        """获取Z轴深度值"""
        return self.z_spinbox.value()


class PerformanceSettingsDialog(QDialog):
    """性能设置对话框"""
    
    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self.settings = current_settings or {}
        self.init_ui()
    
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("3D性能设置")
        layout = QFormLayout()
        
        # 分辨率滑块
        self.resolution_slider = QSlider(Qt.Horizontal)
        self.resolution_slider.setRange(20, 200)
        self.resolution_slider.setValue(self.settings.get('resolution', 60))
        self.resolution_label = QLabel(f"分辨率: {self.resolution_slider.value()}")
        self.resolution_slider.valueChanged.connect(
            lambda value: self.resolution_label.setText(f"分辨率: {value}"))
        layout.addRow(self.resolution_label, self.resolution_slider)
        
        # 点大小滑块
        self.point_size_slider = QSlider(Qt.Horizontal)
        self.point_size_slider.setRange(1, 20)
        self.point_size_slider.setValue(self.settings.get('point_size', 5))
        self.point_size_label = QLabel(f"点大小: {self.point_size_slider.value()}")
        self.point_size_slider.valueChanged.connect(
            lambda value: self.point_size_label.setText(f"点大小: {value}"))
        layout.addRow(self.point_size_label, self.point_size_slider)
        
        # 透明度滑块
        self.alpha_slider = QSlider(Qt.Horizontal)
        self.alpha_slider.setRange(1, 10)
        self.alpha_slider.setValue(int(self.settings.get('alpha', 0.7) * 10))
        self.alpha_label = QLabel(f"透明度: {self.alpha_slider.value() / 10}")
        self.alpha_slider.valueChanged.connect(
            lambda value: self.alpha_label.setText(f"透明度: {value / 10}"))
        layout.addRow(self.alpha_label, self.alpha_slider)
        
        # 数据抽样率
        self.decimation_combo = QComboBox()
        decimation_options = [1, 2, 5, 10, 20]
        for option in decimation_options:
            self.decimation_combo.addItem(f"1/{option}", option)
        # 设置当前值
        current_decimation = self.settings.get('decimation', 2)
        index = decimation_options.index(current_decimation) if current_decimation in decimation_options else 1
        self.decimation_combo.setCurrentIndex(index)
        layout.addRow("数据抽样率:", self.decimation_combo)
        
        # 显示原始数据点
        self.show_points_checkbox = QCheckBox()
        self.show_points_checkbox.setChecked(self.settings.get('show_points', False))  # 默认关闭，因为方格图更清晰
        layout.addRow("显示原始数据点:", self.show_points_checkbox)
        
        # 方格网格线宽度
        self.grid_width_slider = QSlider(Qt.Horizontal)
        self.grid_width_slider.setRange(1, 5)
        self.grid_width_slider.setValue(self.settings.get('grid_width', 1))
        self.grid_width_label = QLabel(f"网格线宽度: {self.grid_width_slider.value()}")
        self.grid_width_slider.valueChanged.connect(
            lambda value: self.grid_width_label.setText(f"网格线宽度: {value}"))
        layout.addRow(self.grid_width_label, self.grid_width_slider)
        
        # 方格透明度
        self.carpet_alpha_slider = QSlider(Qt.Horizontal)
        self.carpet_alpha_slider.setRange(3, 10)
        self.carpet_alpha_slider.setValue(int(self.settings.get('carpet_alpha', 1) * 10))
        self.carpet_alpha_label = QLabel(f"方格透明度: {self.carpet_alpha_slider.value() / 10}")
        self.carpet_alpha_slider.valueChanged.connect(
            lambda value: self.carpet_alpha_label.setText(f"方格透明度: {value / 10}"))
        layout.addRow(self.carpet_alpha_label, self.carpet_alpha_slider)
        

        
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
    
    def get_settings(self):
        """获取设置值"""
        return {
            'resolution': self.resolution_slider.value(),
            'point_size': self.point_size_slider.value(),
            'alpha': self.alpha_slider.value() / 10,
            'decimation': self.decimation_combo.currentData(),
            'show_points': self.show_points_checkbox.isChecked(),
            'grid_width': self.grid_width_slider.value(),
            'carpet_alpha': self.carpet_alpha_slider.value() / 10,

        }


class PlotlyWebView(QWebEngineView):
    """用于显示Plotly图表的WebView"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.temp_file: Optional[str] = None
        self.setMinimumSize(QSize(600, 400))
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
            QMessageBox.warning(self.parent(), "加载失败", 
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
                QMessageBox.critical(self, "错误", f"创建临时文件失败: {str(temp_file_error)}")
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
                    include_plotlyjs='inline',  # 内嵌plotly.js库，避免CDN网络问题
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
                QMessageBox.critical(self, "错误", f"写入HTML文件失败: {str(write_error)}")
                self._cleanup_temp_file()
                return
            
            try:
                # 使用file://协议确保正确的URL格式
                local_url = QUrl.fromLocalFile(os.path.abspath(self.temp_file))
                print(f"DEBUG: Attempting to load URL in QWebEngineView: {local_url.toString()}")
                
                if not local_url.isValid():
                    print(f"错误: 生成的本地文件URL无效: {self.temp_file}")
                    QMessageBox.critical(self, "错误", f"无法加载图表，因为生成的URL无效: {self.temp_file}")
                    self._cleanup_temp_file()
                    return

                # 设置加载超时处理
                QApplication.processEvents()  # 确保UI响应
                self.load(local_url)
                print(f"DEBUG: QWebEngineView.load() called with URL: {local_url.toString()}")
                
                # 显示加载提示
                if hasattr(self.parent(), 'status_label'):
                    self.parent().status_label.setText('正在加载3D图表，请稍候...')
                
            except Exception as load_error:
                print(f"错误: 加载URL到WebView失败: {str(load_error)}")
                QMessageBox.critical(self, "错误", f"加载URL到WebView失败: {str(load_error)}")
                self._cleanup_temp_file()
                return
            
        except Exception as e:
            error_message = f'PlotlyWebView.display_figure 发生错误: {str(e)}\nTraceback: {traceback.format_exc()}'
            print(error_message)
            QMessageBox.critical(self, "显示错误", f"在显示3D图形时发生内部错误，详情请查看控制台。\n{str(e)}")
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
        print(f"DEBUG: PlotlyWebView.__del__ called for {self}")
        self._cleanup_temp_file()


class HeatmapViewer(QMainWindow):
    """热力图查看器GUI"""
    
    def __init__(self):
        super().__init__()
        self.generator = CircularHeatmapGenerator()
        self.current_dataset_index = 0
        self.plotly_view: Optional[PlotlyWebView] = None # 类型提示
        self.init_ui()
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle('SiC三维应力分析')
        self.setGeometry(100, 100, 1400, 900)
        
        # 设置应用程序字体
        font = self.font()
        font.setFamily('Microsoft YaHei')
        self.setFont(font)
        
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
        self.csv_list_widget.itemSelectionChanged.connect(self.on_csv_selection_changed)
        csv_layout.addWidget(self.csv_list_widget)
        
        # CSV操作按钮
        csv_buttons = QHBoxLayout()
        
        self.load_button = QPushButton('添加CSV')
        self.load_button.clicked.connect(self.load_csv_file)
        csv_buttons.addWidget(self.load_button)
        
        self.remove_button = QPushButton('移除CSV')
        self.remove_button.clicked.connect(self.remove_csv_file)
        self.remove_button.setEnabled(False)
        csv_buttons.addWidget(self.remove_button)
        
        self.z_input_button = QPushButton('设置Z轴深度')
        self.z_input_button.clicked.connect(self.set_z_depth)
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
        self.generate_2d_button.clicked.connect(self.generate_2d_heatmap)
        self.generate_2d_button.setEnabled(False)
        generate_buttons.addWidget(self.generate_2d_button)
        
        self.generate_3d_button = QPushButton('生成3D多层热力图')
        self.generate_3d_button.clicked.connect(self.generate_3d_heatmap)
        self.generate_3d_button.setEnabled(False)
        generate_buttons.addWidget(self.generate_3d_button)
        
        control_layout.addLayout(generate_buttons)
        
        # Z轴间距控制
        z_control_layout = QHBoxLayout()
        z_control_layout.addWidget(QLabel('Z轴间距:'))
        
        self.z_scale_slider = QSlider(Qt.Horizontal)
        self.z_scale_slider.setRange(1, 50)  # 0.1倍到5.0倍
        self.z_scale_slider.setValue(int(self.generator.performance_settings.get('z_scale', 0.5) * 10))
        self.z_scale_label = QLabel(f"{self.z_scale_slider.value() / 10:.1f}x")
        self.z_scale_slider.valueChanged.connect(self.on_z_scale_changed)
        
        z_control_layout.addWidget(self.z_scale_slider)
        z_control_layout.addWidget(self.z_scale_label)
        control_layout.addLayout(z_control_layout)
        
        # 色标卡控制区域
        colorbar_group = QGroupBox("2D热力图色标卡设置")
        colorbar_layout = QVBoxLayout(colorbar_group)
        
        # 自动/手动切换
        self.auto_range_checkbox = QCheckBox('自动设置色标卡范围')
        self.auto_range_checkbox.setChecked(True)
        self.auto_range_checkbox.stateChanged.connect(self.on_auto_range_changed)
        colorbar_layout.addWidget(self.auto_range_checkbox)
        
        # 手动范围设置
        manual_range_layout = QFormLayout()
        
        self.vmin_spinbox = QDoubleSpinBox()
        self.vmin_spinbox.setRange(-99999.0, 99999.0)
        self.vmin_spinbox.setDecimals(2)
        self.vmin_spinbox.setValue(0.0)
        self.vmin_spinbox.setEnabled(False)
        self.vmin_spinbox.valueChanged.connect(self.on_colorbar_range_changed)
        manual_range_layout.addRow('最小值 (MPa):', self.vmin_spinbox)
        
        self.vmax_spinbox = QDoubleSpinBox()
        self.vmax_spinbox.setRange(-99999.0, 99999.0)
        self.vmax_spinbox.setDecimals(2)
        self.vmax_spinbox.setValue(100.0)
        self.vmax_spinbox.setEnabled(False)
        self.vmax_spinbox.valueChanged.connect(self.on_colorbar_range_changed)
        manual_range_layout.addRow('最大值 (MPa):', self.vmax_spinbox)
        
        colorbar_layout.addLayout(manual_range_layout)
        
        # 数据范围显示
        self.data_range_label = QLabel('当前数据范围: 未加载数据')
        self.data_range_label.setStyleSheet('color: gray; font-size: 10px;')
        colorbar_layout.addWidget(self.data_range_label)
        
        # 快速设置按钮
        quick_buttons_layout = QHBoxLayout()
        
        self.reset_range_button = QPushButton('重置为数据范围')
        self.reset_range_button.clicked.connect(self.reset_to_data_range)
        self.reset_range_button.setEnabled(False)
        quick_buttons_layout.addWidget(self.reset_range_button)
        
        self.apply_range_button = QPushButton('应用设置')
        self.apply_range_button.clicked.connect(self.apply_colorbar_settings)
        self.apply_range_button.setEnabled(False)
        quick_buttons_layout.addWidget(self.apply_range_button)
        
        colorbar_layout.addLayout(quick_buttons_layout)
        control_layout.addWidget(colorbar_group)
        
        # 添加性能设置按钮
        self.performance_button = QPushButton('3D性能设置')
        self.performance_button.clicked.connect(self.show_performance_settings)
        control_layout.addWidget(self.performance_button)
        
        # 保存按钮
        self.save_button = QPushButton('保存当前图像')
        self.save_button.clicked.connect(self.save_heatmap)
        self.save_button.setEnabled(False)
        control_layout.addWidget(self.save_button)
        
        # 添加帮助按钮
        self.help_button = QPushButton('性能优化帮助')
        self.help_button.clicked.connect(self.show_help_dialog)
        control_layout.addWidget(self.help_button)
        
        self.left_layout.addWidget(control_group)
        
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
        
        # 当前视图类型
        self.current_view_type = None  # '2d' 或 '3d' 或 'plotly'
        self.current_canvas = None
    
    def load_csv_file(self):
        """加载CSV文件"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, '选择CSV文件', '', 'CSV文件 (*.csv)'
        )
        
        if not file_paths:
            return
            
        for file_path in file_paths:
            # 弹出Z轴深度设置对话框
            z_depth, ok = QInputDialog.getDouble(
                self, 'Z轴深度设置', 
                f'请为 {Path(file_path).name} 设置Z轴深度值 (μm): ', 
                0.0, -10000.0, 10000.0, 2
            )
            
            if ok:
                if self.generator.load_csv(file_path, z_depth):
                    # 添加到列表
                    item_text = f"{Path(file_path).name} (Z={z_depth}μm)"
                    self.csv_list_widget.addItem(item_text)
                    self.status_label.setText(f'已加载: {Path(file_path).name}')
                    self.remove_button.setEnabled(True)
                    self.z_input_button.setEnabled(True)
                    self.generate_2d_button.setEnabled(True)
                    
                    # 启用色标卡控制
                    self.reset_range_button.setEnabled(not self.auto_range_checkbox.isChecked())
                    self.apply_range_button.setEnabled(True)
                    
                    # 更新数据范围显示
                    self.update_data_range_display()
                    
                    # 如果有至少一个数据集，启用3D按钮
                    if self.generator.get_dataset_count() > 0:
                        self.generate_3d_button.setEnabled(True)
                else:
                    self.status_label.setText(f'加载失败: {Path(file_path).name}')
    
    def remove_csv_file(self):
        """移除选中的CSV文件"""
        current_row = self.csv_list_widget.currentRow()
        if current_row >= 0:
            self.generator.remove_dataset(current_row)
            self.csv_list_widget.takeItem(current_row)
            
            # 更新按钮状态
            if self.csv_list_widget.count() == 0:
                self.remove_button.setEnabled(False)
                self.z_input_button.setEnabled(False)
                self.generate_2d_button.setEnabled(False)
                self.generate_3d_button.setEnabled(False)
                self.reset_range_button.setEnabled(False)
                self.apply_range_button.setEnabled(False)
                self.data_range_label.setText('当前数据范围: 未加载数据')
                self.status_label.setText('请添加CSV文件开始')
            else:
                self.status_label.setText('已移除CSV文件')
                # 更新数据范围显示
                self.update_data_range_display()
    
    def on_csv_selection_changed(self):
        """CSV列表选择项变更时的处理"""
        self.current_dataset_index = self.csv_list_widget.currentRow()
        if self.current_dataset_index >= 0:
            self.remove_button.setEnabled(True)
            self.z_input_button.setEnabled(True)
            self.generate_2d_button.setEnabled(True)
            
            # 更新数据范围显示
            self.update_data_range_display()
        else:
            self.remove_button.setEnabled(False)
            self.z_input_button.setEnabled(False)
            self.generate_2d_button.setEnabled(False)
            self.data_range_label.setText('当前数据范围: 未选择数据')
    
    def set_z_depth(self):
        """设置Z轴深度"""
        current_row = self.csv_list_widget.currentRow()
        if current_row < 0:
            return
            
        # 获取当前数据集信息
        data, current_z, file_name = self.generator.data_sets[current_row]
        
        # 显示设置对话框
        z_depth, ok = QInputDialog.getDouble(
            self, 'Z轴深度设置', 
            f'请为 {file_name} 设置Z轴深度值 (μm):', 
            current_z, -10000.0, 10000.0, 2
        )
        
        if ok:
            self.generator.update_z_depth(current_row, z_depth)
            # 更新列表显示
            self.csv_list_widget.item(current_row).setText(f"{file_name} (Z={z_depth}μm)")
            self.status_label.setText(f'{file_name} Z轴深度已设置为: {z_depth} μm')
    
    def generate_2d_heatmap(self):
        """生成2D热力图"""
        current_row = self.csv_list_widget.currentRow()
        if current_row < 0:
            return
            
        try:
            fig = self.generator.create_circular_heatmap_2d(current_row)
            
            # 清除当前可视化区域
            self._clear_visualization()
            
            # 创建新的2D画布
            self.current_canvas = FigureCanvas(fig)
            self.visualization_layout.addWidget(self.current_canvas)
            self.current_view_type = '2d'
            
            self.status_label.setText('2D圆形热力图生成完成')
            self.save_button.setEnabled(True)
            
        except Exception as e:
            QMessageBox.critical(self, '错误', f'生成2D热力图失败: {str(e)}')
    
    def on_z_scale_changed(self, value):
        """Z轴间距滑块值变化时的处理"""
        z_scale = value / 10
        self.z_scale_label.setText(f"{z_scale:.1f}x")
        self.generator.update_performance_settings({'z_scale': z_scale})
        
        # 如果已经生成了3D图，实时更新
        if self.current_view_type == 'plotly' and self.plotly_view is not None:
            self.generate_3d_heatmap()
    
    def on_auto_range_changed(self, state):
        """自动范围复选框状态变化时的处理"""
        auto_range = state == Qt.Checked
        
        # 启用/禁用手动输入框
        self.vmin_spinbox.setEnabled(not auto_range)
        self.vmax_spinbox.setEnabled(not auto_range)
        self.reset_range_button.setEnabled(not auto_range and self.generator.get_dataset_count() > 0)
        
        # 更新生成器设置
        self.generator.update_colorbar_settings({'auto_range': auto_range})
        
        if auto_range:
            self.status_label.setText('已切换到自动色标卡范围')
        else:
            self.status_label.setText('已切换到手动色标卡范围')
            # 如果有数据，自动填充当前数据范围
            if self.generator.get_dataset_count() > 0:
                self.update_data_range_display()
    
    def on_colorbar_range_changed(self):
        """色标卡范围值变化时的处理"""
        if not self.auto_range_checkbox.isChecked():
            vmin = self.vmin_spinbox.value()
            vmax = self.vmax_spinbox.value()
            
            # 确保最小值小于最大值
            if vmin >= vmax:
                if self.sender() == self.vmin_spinbox:
                    self.vmax_spinbox.setValue(vmin + 1.0)
                else:
                    self.vmin_spinbox.setValue(vmax - 1.0)
            
            # 更新生成器设置
            self.generator.update_colorbar_settings({
                'vmin': self.vmin_spinbox.value(),
                'vmax': self.vmax_spinbox.value()
            })
    
    def reset_to_data_range(self):
        """重置色标卡范围为当前数据范围"""
        current_row = self.csv_list_widget.currentRow()
        if current_row >= 0:
            vmin, vmax = self.generator.get_data_range(current_row)
            self.vmin_spinbox.setValue(vmin)
            self.vmax_spinbox.setValue(vmax)
            self.status_label.setText(f'已重置色标卡范围为数据范围: {vmin:.2f} - {vmax:.2f} MPa')
    
    def apply_colorbar_settings(self):
        """应用色标卡设置并重新生成2D图"""
        if self.current_view_type == '2d':
            self.generate_2d_heatmap()
            self.status_label.setText('色标卡设置已应用')
        else:
            self.status_label.setText('请先生成2D热力图')
    
    def update_data_range_display(self):
        """更新数据范围显示"""
        current_row = self.csv_list_widget.currentRow()
        if current_row >= 0 and self.generator.get_dataset_count() > 0:
            vmin, vmax = self.generator.get_data_range(current_row)
            self.data_range_label.setText(f'当前数据范围: {vmin:.2f} - {vmax:.2f} MPa')
            
            # 如果是手动模式且输入框为默认值，自动填充数据范围
            if not self.auto_range_checkbox.isChecked():
                if self.vmin_spinbox.value() == 0.0 and self.vmax_spinbox.value() == 100.0:
                    self.vmin_spinbox.setValue(vmin)
                    self.vmax_spinbox.setValue(vmax)
        else:
            self.data_range_label.setText('当前数据范围: 未加载数据')
    
    def show_performance_settings(self):
        """显示性能设置对话框"""
        dialog = PerformanceSettingsDialog(self, self.generator.performance_settings)
        if dialog.exec():
            new_settings = dialog.get_settings()
            self.generator.update_performance_settings(new_settings)
            self.status_label.setText("3D性能设置已更新")
            
            # 如果已经生成了3D图，且设置发生变化，询问是否重新生成
            if self.current_view_type == 'plotly' and self.plotly_view is not None:
                reply = QMessageBox.question(
                    self, '更新视图', '设置已更改，是否重新生成3D视图？',
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
                )
                if reply == QMessageBox.Yes:
                    self.generate_3d_heatmap()
    
    def generate_3d_heatmap(self):
        """生成3D热力图"""
        if self.generator.get_dataset_count() == 0:
            self.status_label.setText('没有加载任何数据集，无法生成3D热力图。')
            QMessageBox.warning(self, '提示', '请先加载至少一个CSV数据集。')
            return
            
        try:
            # 创建进度对话框
            progress_dialog = QDialog(self)
            progress_dialog.setWindowTitle("生成3D热力图")
            progress_dialog.setFixedSize(400, 100)
            
            progress_layout = QVBoxLayout(progress_dialog)
            progress_label = QLabel("正在生成3D热力图，请稍候...")
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 0)  # 设置为不确定模式
            
            progress_layout.addWidget(progress_label)
            progress_layout.addWidget(progress_bar)
            
            # 非模态显示，不阻塞用户操作
            progress_dialog.setModal(False)
            progress_dialog.show()
            QApplication.processEvents()  # 确保对话框显示
            
            self.status_label.setText('正在准备生成3D多层热力图...')
            QApplication.processEvents()

            print("DEBUG: 调用 self.generator.create_plotly_3d_heatmap()")
            fig = self.generator.create_plotly_3d_heatmap()
            print(f"DEBUG: self.generator.create_plotly_3d_heatmap() 返回: {type(fig)}")
            
            if fig is None:
                progress_dialog.close()  # 关闭进度对话框
                QMessageBox.critical(self, '错误', '创建Plotly图形对象失败，请检查控制台输出获取详细信息。')
                self.status_label.setText('创建Plotly图形对象失败。')
                return

            progress_label.setText("3D图形已创建，正在准备显示...")
            QApplication.processEvents()
            
            self._clear_visualization()
            
            # 确保WebView正确初始化
            if not self.plotly_view:
                print("DEBUG: 创建 PlotlyWebView 实例")
                self.plotly_view = PlotlyWebView(self)
                # 确保WebView有足够的空间
                self.plotly_view.setMinimumSize(600, 400)
            
            # 先添加到布局中，再显示内容
            self.visualization_layout.addWidget(self.plotly_view)
            self.plotly_view.show()
            QApplication.processEvents()  # 确保WebView完全显示
            
            print("DEBUG: 调用 self.plotly_view.display_figure(fig)")
            self.plotly_view.display_figure(fig)
            print("DEBUG: self.plotly_view.display_figure(fig) 调用完成")
            
            self.current_view_type = 'plotly'
            
            # 加载完成后关闭进度对话框
            progress_dialog.close()
            
            self.status_label.setText('3D多层热力图生成完成 (WebGL渲染)')
            self.save_button.setEnabled(True)
            
        except Exception as e:
            if 'progress_dialog' in locals():
                progress_dialog.close()  # 确保关闭进度对话框
                
            error_message = f'生成3D热力图时发生严重错误: {str(e)}\nTraceback: {traceback.format_exc()}'
            print(error_message) 
            QMessageBox.critical(self, '严重错误', f"生成3D热力图时发生严重错误，详情请查看控制台输出：\n{str(e)}")
            self.status_label.setText(f'生成3D热力图失败: {str(e)}')
    
    def _clear_visualization(self):
        """清除可视化区域的内容"""
        # 清除当前可视化控件
        if self.current_view_type == '2d' and self.current_canvas:
            self.visualization_layout.removeWidget(self.current_canvas)
            self.current_canvas.deleteLater()
            self.current_canvas = None
        elif self.current_view_type == 'plotly' and self.plotly_view:
            self.visualization_layout.removeWidget(self.plotly_view)
            # 不删除plotly_view对象，而是隐藏它以便重用
            self.plotly_view.hide()
    
    def save_heatmap(self):
        """保存热力图"""
        if not self.current_view_type:
            QMessageBox.information(self, "提示", "当前没有可保存的图像。")
            return
            
        figure_type = self.current_view_type
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
        
        if file_path:
            try:
                if figure_type == '2d':
                    self.generator.save_heatmap(file_path, '2d')
                elif figure_type == 'plotly':
                    self.generator.save_heatmap(file_path, 'plotly')
                self.status_label.setText(f'已保存{figure_type.upper()}图像到: {Path(file_path).name}')
            except Exception as e:
                QMessageBox.critical(self, '错误', f'保存失败: {str(e)}')
    
    def show_help_dialog(self):
        """显示帮助对话框"""
        help_dialog = QDialog(self)
        help_dialog.setWindowTitle("性能优化帮助")
        help_dialog.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(help_dialog)
        
        # 创建帮助文本
        help_text = """
<h2>3D热力图性能优化指南</h2>

<h3>常见问题</h3>
<p>当处理大型数据集或多个数据集时，3D热力图生成可能会遇到以下问题：</p>
<ul>
    <li><b>程序崩溃或卡顿</b>: 通常是由于内存不足或处理能力有限</li>
    <li><b>渲染缓慢</b>: 3D渲染需要大量GPU资源</li>
    <li><b>浏览器显示白屏</b>: 可能是WebView加载大型HTML文件时超时</li>
</ul>

<h3>解决方案</h3>
<p>您可以通过以下方式优化性能：</p>

<h4>1. 使用性能设置</h4>
<ul>
    <li>降低<b>分辨率</b>: 减少网格密度，提高渲染速度</li>
    <li>增加<b>数据抽样率</b>: 降低显示的数据点数量</li>
    <li>减小<b>点大小</b>: 降低GPU渲染负担</li>
    <li>禁用<b>表面渲染</b>: 仅显示数据点可大幅提高性能</li>
</ul>

<h4>2. 数据处理</h4>
<ul>
    <li>分批处理数据: 每次只加载和处理部分数据</li>
    <li>降低CSV文件数量: 尝试合并相似深度的数据</li>
    <li>预处理数据: 在导入前使用其他工具对数据进行降采样</li>
</ul>

<h4>3. 系统优化</h4>
<ul>
    <li>关闭其他程序: 释放更多系统资源</li>
    <li>更新显卡驱动: 确保WebGL性能最优</li>
    <li>使用独立显卡: 如果系统有集成显卡和独立显卡</li>
</ul>
"""
        
        help_label = QLabel()
        help_label.setText(help_text)
        help_label.setWordWrap(True)
        help_label.setTextFormat(Qt.RichText)
        help_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        
        scroll_area = QScrollArea()
        scroll_area.setWidget(help_label)
        scroll_area.setWidgetResizable(True)
        
        layout.addWidget(scroll_area)
        
        # 添加关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(help_dialog.close)
        layout.addWidget(close_button)
        
        help_dialog.exec_()


def main():
    """主函数"""
    # 强制设置stdout和stderr编码为UTF-8 (Python 3.7+)
    if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            # print("标准输出编码已设置为UTF-8") # 避免这条信息本身乱码
        except Exception as e:
            pass # print(f"设置标准输出编码失败: {e}") # 避免这条信息本身乱码
            
    if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding != 'utf-8':
        try:
            sys.stderr.reconfigure(encoding='utf-8')
            # print("标准错误编码已设置为UTF-8", file=sys.stderr)
        except Exception as e:
            pass # print(f"设置标准错误编码失败: {e}", file=sys.stderr)

    # 设置控制台输出编码
    if sys.platform.startswith('win'):
        import locale
        try:
            # 尝试设置UTF-8编码
            locale.setlocale(locale.LC_ALL, 'zh_CN.UTF-8')
        except locale.Error:
            try:
                # 如果UTF-8失败，使用系统默认编码
                locale.setlocale(locale.LC_ALL, '')
            except locale.Error:
                pass
    
    # 检查是否有命令行参数指定CSV文件
    if len(sys.argv) > 1:
        # 命令行模式：直接生成热力图
        generator = CircularHeatmapGenerator()
        
        # 处理所有传入的CSV文件
        csv_files = sys.argv[1:]
        for i, csv_file in enumerate(csv_files):
            if Path(csv_file).exists():
                # 为每个CSV文件设置不同的Z深度
                z_depth = float(input(f"请为 {Path(csv_file).name} 输入Z轴深度值 (μm): ") or f"{i*10}.0")
                if generator.load_csv(csv_file, z_depth):
                    print(f"成功加载 {Path(csv_file).name}, Z轴深度: {z_depth}μm")
                else:
                    print(f"加载 {Path(csv_file).name} 失败")
            else:
                print(f"文件不存在: {csv_file}")
        
        # 检查是否成功加载了至少一个文件
        if generator.get_dataset_count() > 0:
            # 为每个CSV生成单独的2D图
            for i in range(generator.get_dataset_count()):
                data, z_depth, file_name = generator.data_sets[i]
                fig_2d = generator.create_circular_heatmap_2d(i)
                output_2d = f"{file_name.replace('.csv', '')}_2d_z{z_depth}.png"
                generator.save_heatmap(output_2d, '2d')
                print(f"{file_name}的2D热力图已生成并保存为: {output_2d}")
            
            # 生成包含所有层的3D图
            if generator.get_dataset_count() > 1:
                fig_3d = generator.create_plotly_3d_heatmap()
                output_3d = "multi_layer_3d_heatmap.html"
                generator.save_heatmap(output_3d, 'plotly')
                print(f"多层3D热力图已生成并保存为: {output_3d}")
            else:
                # 单层也生成3D图
                fig_3d = generator.create_plotly_3d_heatmap()
                data, z_depth, file_name = generator.data_sets[0]
                output_3d = f"{file_name.replace('.csv', '')}_3d_z{z_depth}.html"
                generator.save_heatmap(output_3d, 'plotly')
                print(f"{file_name}的3D热力图已生成并保存为: {output_3d}")
        else:
            print("未成功加载任何CSV文件")
    else:
        # GUI模式
        app = QApplication(sys.argv)
        
        # 设置应用程序字体
        font = app.font()
        font.setFamily('Microsoft YaHei')
        app.setFont(font)
        
        # 显示欢迎信息
        print("\n===== SiC应力圆形热力图生成器 - 多层3D可视化 =====")
        print("使用Plotly+WebGL高性能渲染引擎")
        print("支持交互式3D可视化，鼠标左键旋转，右键平移，滚轮缩放")
        print("=============================================\n")
        
        viewer = HeatmapViewer()
        viewer.show()
        sys.exit(app.exec())


if __name__ == "__main__":
    main()
