"""
热力图数据模型模块

包含处理和生成热力图的核心类，负责所有数据处理逻辑。
"""
import json
import os
import traceback
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from matplotlib.figure import Figure
from matplotlib.patches import Circle
from matplotlib.colors import LinearSegmentedColormap
from plotly.subplots import make_subplots
from scipy.interpolate import griddata, Rbf

from app.model.base_model import BaseModel
from app.utils.config import DefaultSettings


class HeatmapModel(BaseModel):
    """热力图数据模型类，处理数据加载、处理和热力图生成"""
    
    def __init__(self):
        """初始化热力图模型"""
        super().__init__()  # 调用基类初始化
        self.data_sets = []  # 存储多个数据集，每个元素是(数据, Z轴深度, 文件名)的元组
        self.fig_2d = None  # 当前选中的2D图形
        self.plotly_fig: Optional[go.Figure] = None  # Plotly图形，添加类型提示
        
        # 初始化X轴翻转状态
        self._x_axis_flipped = False  # 默认不翻转X轴
        
        # 初始化配置参数
        self._config['performance_settings'] = DefaultSettings.get_performance_settings()
        self._config['colorbar_settings'] = DefaultSettings.get_colorbar_settings()
        self._config['current_colormap'] = 'coolwarm'  # 默认色标
        self._config['current_interpolation'] = 'rbf'  # 默认插值方法
        
        # 设置Plotly的默认模板
        pio.templates.default = "plotly_white"
        
        # 创建自定义蓝白红色标，确保0值为白色
        self._custom_colormap = self._create_custom_blue_white_red_colormap()
    
    @property
    def performance_settings(self) -> Dict[str, Any]:
        """获取性能设置"""
        return self._config['performance_settings']
    
    @property
    def colorbar_settings(self) -> Dict[str, Any]:
        """获取色标卡设置"""
        return self._config['colorbar_settings']
    
    @property
    def current_colormap(self) -> str:
        """获取当前色标"""
        return self._config['current_colormap']
    
    @current_colormap.setter
    def current_colormap(self, value: str):
        """设置当前色标"""
        self._config['current_colormap'] = value
        self.notify_observers('colormap_changed', value)
    
    @property
    def current_interpolation(self) -> str:
        """获取当前插值方法"""
        return self._config['current_interpolation']
    
    @current_interpolation.setter
    def current_interpolation(self, value: str):
        """设置当前插值方法"""
        self._config['current_interpolation'] = value
        self.notify_observers('interpolation_changed', value)
        
    def get_plotly_colorscale(self, matplotlib_cmap: str) -> str:
        """将matplotlib色标名称转换为Plotly色标名称
        
        Args:
            matplotlib_cmap: matplotlib色标名称
            
        Returns:
            str: 对应的Plotly色标名称
        """
        colormap_mapping = DefaultSettings.get_plotly_colorscale_mapping()
        return colormap_mapping.get(matplotlib_cmap, 'RdBu_r')
    
    def _create_custom_blue_white_red_colormap(self):
        """创建自定义的蓝白红色标，确保0值始终为白色
        
        Returns:
            LinearSegmentedColormap: 自定义色标对象
        """
        # 定义颜色节点：蓝色 -> 白色 -> 红色
        colors = ['#0066CC', '#FFFFFF', '#CC0000']  # 深蓝 -> 纯白 -> 深红
        n_bins = 256  # 色标分辨率
        
        # 创建线性分段色标
        custom_cmap = LinearSegmentedColormap.from_list(
            'custom_blue_white_red', colors, N=n_bins
        )
        
        return custom_cmap
    
    def _get_normalized_colormap(self, vmin: float, vmax: float):
        """获取标准化的色标，确保0值对应白色
        
        Args:
            vmin: 数据最小值
            vmax: 数据最大值
            
        Returns:
            tuple: (色标对象, 标准化的vmin, 标准化的vmax)
        """
        if self.current_colormap == 'coolwarm':
            # 对于蓝白红配色，确保0值对应白色
            if vmin < 0 and vmax > 0:
                # 数据跨越0值，创建动态色标确保0值为白色
                # 计算0值在数据范围中的相对位置
                zero_position = -vmin / (vmax - vmin)
                
                # 创建动态色标，0值位置对应白色
                colors = ['#0066CC', '#FFFFFF', '#CC0000']  # 蓝-白-红
                positions = [0.0, zero_position, 1.0]
                
                # 确保位置在有效范围内
                zero_position = max(0.01, min(0.99, zero_position))
                positions = [0.0, zero_position, 1.0]
                
                # 创建分段色标
                cmap_data = list(zip(positions, colors))
                dynamic_cmap = LinearSegmentedColormap.from_list(
                    'dynamic_blue_white_red', cmap_data, N=256
                )
                return dynamic_cmap, vmin, vmax
            elif vmin >= 0:
                # 全为正值，使用白色到红色的部分
                colors = ['#FFFFFF', '#CC0000']
                partial_cmap = LinearSegmentedColormap.from_list(
                    'white_red', colors, N=256
                )
                return partial_cmap, vmin, vmax
            else:
                # 全为负值，使用蓝色到白色的部分
                colors = ['#0066CC', '#FFFFFF']
                partial_cmap = LinearSegmentedColormap.from_list(
                    'blue_white', colors, N=256
                )
                return partial_cmap, vmin, vmax
        else:
            # 其他色标保持原样
            return self.current_colormap, vmin, vmax
    
    def _get_custom_plotly_colorscale(self, vmin: float, vmax: float):
        """获取自定义的Plotly色标，确保0值对应白色
        
        Args:
            vmin: 数据最小值
            vmax: 数据最大值
            
        Returns:
            tuple: (Plotly色标列表, 标准化的vmin, 标准化的vmax)
        """
        if self.current_colormap == 'coolwarm':
            if vmin < 0 and vmax > 0:
                # 数据跨越0值，创建动态蓝白红色标
                # 计算0值在数据范围中的相对位置
                zero_position = -vmin / (vmax - vmin)
                
                # 确保位置在有效范围内
                zero_position = max(0.01, min(0.99, zero_position))
                
                # 创建动态色标，0值位置对应白色
                colorscale = [
                    [0.0, '#0066CC'],           # 深蓝
                    [zero_position * 0.5, '#4D9FDB'],  # 浅蓝（0值位置的一半）
                    [zero_position, '#FFFFFF'],  # 纯白（0值）
                    [zero_position + (1 - zero_position) * 0.5, '#DB4D4D'],  # 浅红
                    [1.0, '#CC0000']            # 深红
                ]
                return colorscale, vmin, vmax
            elif vmin >= 0:
                # 全为正值，白色到红色
                colorscale = [
                    [0.0, '#FFFFFF'],  # 纯白
                    [0.5, '#FF6666'],  # 浅红
                    [1.0, '#CC0000']   # 深红
                ]
                return colorscale, vmin, vmax
            else:
                # 全为负值，蓝色到白色
                colorscale = [
                    [0.0, '#0066CC'],  # 深蓝
                    [0.5, '#6699FF'],  # 浅蓝
                    [1.0, '#FFFFFF']   # 纯白
                ]
                return colorscale, vmin, vmax
        else:
            # 其他色标使用默认映射
            return self.get_plotly_colorscale(self.current_colormap), vmin, vmax
    
    def _interpolate_data(self, x: np.ndarray, y: np.ndarray, values: np.ndarray, 
                         xi_grid: np.ndarray, yi_grid: np.ndarray, method: str = None) -> np.ndarray:
        """通用插值方法
        
        Args:
            x: X坐标数组
            y: Y坐标数组
            values: 数值数组
            xi_grid: 插值目标X网格
            yi_grid: 插值目标Y网格
            method: 插值方法，如果为None则使用当前设置的方法
            
        Returns:
            np.ndarray: 插值后的数据网格
        """
        if method is None:
            method = self.current_interpolation
        
        try:
            if method == 'rbf':
                # RBF插值 - 最佳质量，优化参数提升性能和质量
                # 尝试使用thin_plate函数，smooth参数从0.1优化到0.01以提高精度
                try:
                    rbf_func = Rbf(x, y, values, function='thin_plate', smooth=0.01)
                    zi = rbf_func(xi_grid, yi_grid)
                except Exception:
                    # 如果thin_plate失败，尝试gaussian函数
                    try:
                        rbf_func = Rbf(x, y, values, function='gaussian', smooth=0.05)
                        zi = rbf_func(xi_grid, yi_grid)
                    except Exception:
                        # 最后回退到原始multiquadric函数，但使用优化的smooth参数
                        rbf_func = Rbf(x, y, values, function='multiquadric', smooth=0.05)
                        zi = rbf_func(xi_grid, yi_grid)
            elif method == 'cubic':
                # 三次插值 - 平滑
                zi = griddata((x, y), values, (xi_grid, yi_grid), method='cubic', fill_value=np.nan)
            elif method == 'nearest':
                # 最近邻插值 - 保真
                zi = griddata((x, y), values, (xi_grid, yi_grid), method='nearest', fill_value=np.nan)
            else:
                # 线性插值 - 默认和快速
                zi = griddata((x, y), values, (xi_grid, yi_grid), method='linear', fill_value=np.nan)
            
            return zi
            
        except Exception as e:
            print(f"警告: {method}插值失败，回退到线性插值: {str(e)}")
            # 如果指定方法失败，回退到线性插值
            return griddata((x, y), values, (xi_grid, yi_grid), method='linear', fill_value=np.nan)
        
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
            
            # 通知观察者数据集已添加
            self.notify_observers('dataset_added', {
                'index': len(self.data_sets) - 1,
                'file_name': file_name,
                'z_depth': z_depth,
                'data_count': len(data)
            })
            
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
                
                # 通知观察者数据集已添加
                self.notify_observers('dataset_added', {
                    'index': len(self.data_sets) - 1,
                    'file_name': file_name,
                    'z_depth': z_depth,
                    'data_count': len(data)
                })
                
                return True
            except Exception as e:
                print(f"加载CSV文件失败: {e}")
                self.notify_observers('load_error', str(e))
                return False
        except Exception as e:
            print(f"加载CSV文件失败: {e}")
            self.notify_observers('load_error', str(e))
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
            
            # 通知观察者Z轴深度已更新
            self.notify_observers('z_depth_updated', {
                'index': index,
                'file_name': file_name,
                'z_depth': z_depth
            })
    
    def remove_dataset(self, index: int):
        """删除特定索引的数据集
        
        Args:
            index: 要删除的数据集索引
        """
        if 0 <= index < len(self.data_sets):
            _, _, file_name = self.data_sets.pop(index)
            print(f"已移除数据集: {file_name}")
            
            # 通知观察者数据集已移除
            self.notify_observers('dataset_removed', {
                'index': index,
                'file_name': file_name
            })
    
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
        
        # 通知观察者色标卡设置已更新
        self.notify_observers('colorbar_settings_updated', settings)
    
    def update_performance_settings(self, settings: Dict[str, Any]):
        """更新性能设置
        
        Args:
            settings: 性能设置字典
        """
        self.performance_settings.update(settings)
        print(f"性能设置已更新: {settings}")
        
        # 通知观察者性能设置已更新
        self.notify_observers('performance_settings_updated', settings)
    
    def get_data_range(self, dataset_index: int = None, smart_range: bool = True) -> Tuple[float, float]:
        """获取数据的值范围，支持智能范围计算
        
        Args:
            dataset_index: 数据集索引，如果为None则计算所有数据集的范围
            smart_range: 是否使用智能范围计算（去除异常值，使用百分位数）
            
        Returns:
            Tuple[float, float]: (最小值, 最大值)
        """
        if len(self.data_sets) == 0:
            return (0.0, 1.0)
        
        # 收集数据值
        if dataset_index is not None:
            if 0 <= dataset_index < len(self.data_sets):
                data, _, _ = self.data_sets[dataset_index]
                values = data['Value'].values
            else:
                return (0.0, 1.0)
        else:
            # 计算所有数据集的范围
            all_values = []
            for data, _, _ in self.data_sets:
                all_values.extend(data['Value'].values)
            values = np.array(all_values) if all_values else np.array([0.0, 1.0])
        
        if len(values) == 0:
            return (0.0, 1.0)
        
        if not smart_range:
            # 传统方法：直接使用最小值和最大值
            return (float(np.min(values)), float(np.max(values)))
        
        # 智能范围计算
        return self._calculate_smart_range(values)
    
    def _calculate_smart_range(self, values: np.ndarray) -> Tuple[float, float]:
        """计算智能色标卡范围
        
        使用统计方法去除异常值，提供更好的视觉效果：
        1. 使用百分位数去除极端异常值
        2. 根据数据分布特征调整范围
        3. 确保范围对称性（如果数据围绕零分布）
        
        Args:
            values: 数据值数组
            
        Returns:
            Tuple[float, float]: (智能最小值, 智能最大值)
        """
        # 移除NaN值
        clean_values = values[~np.isnan(values)]
        if len(clean_values) == 0:
            return (0.0, 1.0)
        
        # 基本统计信息
        mean_val = np.mean(clean_values)
        std_val = np.std(clean_values)
        
        # 使用百分位数去除极端异常值（保留99.5%的数据）
        p_low = np.percentile(clean_values, 0.25)   # 下四分位数
        p_high = np.percentile(clean_values, 99.75)  # 上四分位数
        
        # 计算四分位距（IQR）用于检测异常值
        q1 = np.percentile(clean_values, 25)
        q3 = np.percentile(clean_values, 75)
        iqr = q3 - q1
        
        # 使用IQR方法定义合理范围（1.5倍IQR规则的改进版）
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        # 在百分位数和IQR方法之间选择更保守的范围
        vmin = max(p_low, lower_bound)
        vmax = min(p_high, upper_bound)
        
        # 确保范围不会过小
        if vmax - vmin < std_val * 0.1:  # 如果范围太小，扩展到至少0.1个标准差
            center = (vmin + vmax) / 2
            half_range = max(std_val * 0.5, abs(vmax - vmin) / 2)
            vmin = center - half_range
            vmax = center + half_range
        
        # 检查数据是否围绕零对称分布
        if abs(mean_val) < std_val * 0.5:  # 数据大致围绕零分布
            # 使对称范围，有利于应力数据的可视化
            max_abs = max(abs(vmin), abs(vmax))
            vmin = -max_abs
            vmax = max_abs
        
        # 添加小的边距以确保所有重要数据都可见（5%边距）
        range_margin = (vmax - vmin) * 0.05
        vmin -= range_margin
        vmax += range_margin
        
        # 美化数值：四舍五入到合适的精度
        magnitude = max(abs(vmin), abs(vmax))
        if magnitude > 100:
            # 大数值：四舍五入到整数
            vmin = np.floor(vmin)
            vmax = np.ceil(vmax)
        elif magnitude > 10:
            # 中等数值：四舍五入到0.1
            vmin = np.floor(vmin * 10) / 10
            vmax = np.ceil(vmax * 10) / 10
        else:
            # 小数值：四舍五入到0.01
            vmin = np.floor(vmin * 100) / 100
            vmax = np.ceil(vmax * 100) / 100
        
        return (float(vmin), float(vmax))
    
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
        zi = self._interpolate_data(x, y, values, xi_grid, yi_grid)
        
        # 创建圆形遮罩
        distances = np.sqrt((xi_grid - x_center)**2 + (yi_grid - y_center)**2)
        mask = distances > radius
        zi[mask] = np.nan
        
        # 创建图形
        self.fig_2d = Figure(figsize=figsize, facecolor='white')
        ax = self.fig_2d.add_subplot(111)
        
        # 确定色标卡范围
        if self.colorbar_settings['auto_range']:
            # 自动模式：根据智能范围设置计算合适的范围
            if self.colorbar_settings['smart_range']:
                # 使用智能范围计算
                vmin, vmax = self._calculate_smart_range(values)
            else:
                # 使用传统方法：直接使用数据的最小值和最大值
                vmin, vmax = float(np.min(values)), float(np.max(values))
        else:
            vmin = self.colorbar_settings['vmin']
            vmax = self.colorbar_settings['vmax']
        
        # 获取优化的色标和范围
        colormap, norm_vmin, norm_vmax = self._get_normalized_colormap(vmin, vmax)
        
        # 绘制热力图
        im = ax.imshow(zi, extent=[x_center-radius, x_center+radius, 
                                  y_center-radius, y_center+radius],
                      origin='lower', cmap=colormap, aspect='equal',
                      vmin=norm_vmin, vmax=norm_vmax)
        
        # 添加圆形边界
        circle = Circle((x_center, y_center), radius, fill=False, 
                       edgecolor='black', linewidth=2)
        ax.add_patch(circle)
        
        # 设置坐标轴（确保中文正常显示）
        ax.set_xlim(x_center - radius * 1.1, x_center + radius * 1.1)
        ax.set_ylim(y_center - radius * 1.1, y_center + radius * 1.1)
        
        # 检查是否需要翻转X轴显示
        if hasattr(self, '_x_axis_flipped') and self._x_axis_flipped:
            # X轴需要翻转显示
            ax.invert_xaxis()
        ax.set_xlabel('X坐标 (μm)', fontsize=12, fontfamily='sans-serif')
        ax.set_ylabel('Y坐标 (μm)', fontsize=12, fontfamily='sans-serif')
        ax.set_title(f'SiC应力分布2D热力图 (Z={z_depth}μm)\n{file_name}', 
                     fontsize=14, fontweight='bold', fontfamily='sans-serif')
        
        # 添加颜色条
        cbar = self.fig_2d.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label('应力 (MPa)', fontsize=12, fontfamily='sans-serif')
        # 设置色标卡的层级较低，确保鼠标悬停标签显示在上方
        cbar.ax.set_zorder(1)
        
        # 添加原始数据点
        ax.scatter(x, y, c='white', s=1, alpha=0.3, edgecolors='none')
        
        # 存储数据用于鼠标悬停功能
        self.fig_2d._heatmap_data = {
            'xi_grid': xi_grid,
            'yi_grid': yi_grid,
            'zi': zi,
            'x_center': x_center,
            'y_center': y_center,
            'radius': radius,
            'z_depth': z_depth
        }
        
        self.fig_2d.tight_layout()
        return self.fig_2d
    
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
            
            # 使用与2D热力图相同的色标卡设置：计算全局范围
            if self.colorbar_settings.get('auto_range', True):
                # 自动模式：使用智能范围计算或原始数据范围
                smart_range = self.colorbar_settings.get('smart_range', True)
                self._global_vmin, self._global_vmax = self.get_data_range(smart_range=smart_range)
            else:
                # 手动模式：使用用户设置的范围
                self._global_vmin = self.colorbar_settings.get('vmin', 0)
                self._global_vmax = self.colorbar_settings.get('vmax', 1)
            
            # 为每个数据集创建方格地毯图层
            for dataset_index, (data, z_depth, file_name) in enumerate(self.data_sets):
                try:
                    print(f"DEBUG: 处理数据集 {dataset_index}: {file_name} at Z={z_depth}")
                    x = data['X'].values
                    y = data['Y'].values
                    values = data['Value'].values
                    
                    # 计算数据的中心点和半径
                    x_center = (x.max() + x.min()) / 2
                    y_center = (y.max() + y.min()) / 2
                    radius = max(x.max() - x.min(), y.max() - y.min()) / 2
                    
                    # 创建规则网格用于方格显示
                    resolution = self.performance_settings['resolution']
                    xi = np.linspace(x_center - radius, x_center + radius, resolution)
                    yi = np.linspace(y_center - radius, y_center + radius, resolution)
                    xi_grid, yi_grid = np.meshgrid(xi, yi)
                    
                    # 网格数据保持原始方向，翻转效果通过坐标轴配置实现
                    
                    # 数据插值到网格
                    if len(x) < 4:
                        print(f"警告: 数据集 {file_name} 点数过少 ({len(x)})，无法进行插值，跳过。")
                        continue
                    
                    try:
                        zi_grid = self._interpolate_data(x, y, values, xi_grid, yi_grid)
                    except Exception as interp_error:
                        print(f"警告: 数据集 {file_name} 插值失败: {str(interp_error)}，跳过。")
                        continue
                    
                    # 应用圆形遮罩，去除方形边角
                    grid_distances = np.sqrt((xi_grid - x_center)**2 + (yi_grid - y_center)**2)
                    # 使用合理的圆形边界，保留足够的数据
                    mask_grid = grid_distances > radius * 0.98  # 适度收缩边界
                    zi_grid[mask_grid] = np.nan
                    
                    # 检查是否有有效数据
                    valid_data_count = np.sum(~np.isnan(zi_grid))
                    if valid_data_count == 0:
                        print(f"警告: 数据集 {file_name} 的插值网格全为 NaN，跳过。")
                        continue
                    elif valid_data_count < 10:
                        print(f"警告: 数据集 {file_name} 有效数据点过少 ({valid_data_count})，可能显示效果不佳。")
                    
                    # 创建方格地毯图效果 - 使用Surface但设置为平面
                    print(f"DEBUG: 为 {file_name} 添加方格地毯图层")
                    
                    # 获取方格样式设置
                    grid_width = self.performance_settings.get('grid_width', 1)
                    # 使用主透明度设置，如果没有设置则使用方格透明度作为后备
                    alpha_value = self.performance_settings.get('alpha', 1.0)
                    
                    # 创建遮罩后的Z值，保持原始z_depth值不变
                    z_masked = np.full_like(zi_grid, z_depth)
                    z_masked[np.isnan(zi_grid)] = np.nan
                    
                    # 获取优化的Plotly色标和范围
                    plotly_colorscale, norm_vmin, norm_vmax = self._get_custom_plotly_colorscale(
                        self._global_vmin, self._global_vmax
                    )
                    
                    self.plotly_fig.add_trace(
                         go.Surface(
                             x=xi_grid,
                             y=yi_grid,
                             z=z_masked,  # 使用遮罩后的Z值
                             surfacecolor=zi_grid,
                             colorscale=plotly_colorscale,
                             cmin=norm_vmin,  # 设置颜色范围最小值
                             cmax=norm_vmax,  # 设置颜色范围最大值
                             cauto=False,  # 禁用自动颜色范围
                             opacity=alpha_value,
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
                                 x=dict(show=False, color="white", width=grid_width),
                                 y=dict(show=False, color="white", width=grid_width),
                                 z=dict(show=False)
                             ),
                             # 添加悬停信息
                             hovertemplate="<b>%{fullData.name}</b><br>" +
                                         "X: %{x:.1f}μm<br>" +
                                         "Y: %{y:.1f}μm<br>" +
                                         "Z: %{z:.1f}μm<br>" +
                                         "应力: %{surfacecolor:.2f} MPa<extra></extra>",
                             # 调整光照效果减少高亮反射和泛白
                             lighting=dict(
                                 ambient=0.4,  # 降低环境光，减少整体亮度
                                 diffuse=0.6,  # 适度降低漫反射，保持细节可见
                                 specular=0.05,  # 进一步降低镜面反射，减少高光
                                 roughness=0.8,  # 增加表面粗糙度，减少反射
                                 fresnel=0.1   # 降低菲涅尔反射强度
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
                            z_sampled = np.full_like(x_sampled, z_depth + 0.1)  # 稍微抬高避免重叠
                        else:
                            x_sampled, y_sampled = x, y
                            z_sampled = np.full_like(x_sampled, z_depth + 0.1)
                        
                        # 应用严格的圆形遮罩，与表面图保持一致
                        distances = np.sqrt((x_sampled - x_center)**2 + (y_sampled - y_center)**2)
                        mask = distances <= radius * 0.95  # 使用与表面图相同的严格边界
                        
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
                    
                except Exception as dataset_error:
                    print(f"警告: 处理数据集 {file_name} 时出错: {str(dataset_error)}")
                    continue
            
            print("DEBUG: 配置3D场景布局...")
            
            # 配置3D场景的坐标轴
            scene_config = dict(
                xaxis_title='X坐标 (μm)',
                yaxis_title='Y坐标 (μm)',
                zaxis_title='Z深度 (μm)',
                aspectmode='manual',  # 改为手动模式以自定义比例
                aspectratio=dict(x=1, y=1, z=1.5 * self.performance_settings.get('z_scale', 1.0)),
                camera=dict(
                    eye=dict(x=1.8, y=1.8, z=1.2)  # 调整相机角度，减少直视反射
                ),
                bgcolor='rgba(240,240,240,1)',  # 设置较暗的背景色，减少对比度
                # 确保Y轴与2D热力图保持一致的方向
                yaxis=dict(
                    title='Y坐标 (μm)',
                    autorange='reversed'  # 反转Y轴以与2D热力图保持一致
                ),
                # X轴默认正常显示（从左到右递增）
                xaxis=dict(
                    title='X坐标 (μm)'
                    # 不设置autorange，保持默认的正常显示
                )
            )
            
            # 如果X轴未翻转，才反转X轴显示（修正逻辑）
            if not (hasattr(self, '_x_axis_flipped') and self._x_axis_flipped):
                scene_config['xaxis']['autorange'] = 'reversed'  # 反转X轴范围
            
            self.plotly_fig.update_layout(
                scene=scene_config,
                title_text="SiC应力3D切片",
                margin=dict(l=0, r=0, t=50, b=0),
                legend=dict(
                    yanchor="top",
                    y=0.99,
                    xanchor="left",
                    x=0.01,
                    bgcolor="rgba(255,255,255,0.5)"
                ),
                template="plotly_white",
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
            
    def flip_x_axis(self):
        """翻转X轴显示方向，不修改原始数据
        
        只切换X轴显示方向标记，在生成热力图时应用翻转效果
        """
        if len(self.data_sets) == 0:
            raise ValueError("没有数据集可以翻转")
        
        try:
            # 切换翻转状态标记
            self._x_axis_flipped = not getattr(self, '_x_axis_flipped', False)
            
            flip_status = "已翻转" if self._x_axis_flipped else "已恢复"
            print(f"X轴显示方向{flip_status}，共影响 {len(self.data_sets)} 个数据集")
            
            # 通知观察者X轴翻转状态已更新
            self.notify_observers('x_axis_flipped', {
                'count': len(self.data_sets),
                'flipped': self._x_axis_flipped
            })
            
        except Exception as e:
            print(f"翻转X轴时发生错误: {e}")
            raise