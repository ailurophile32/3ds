"""
热力图数据模型模块

包含处理和生成热力图的核心类，负责所有数据处理逻辑。
"""
import datetime
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
from app.utils.config_loader import get_config_loader


class HeatmapModel(BaseModel):
    """热力图数据模型类，处理数据加载、处理和热力图生成"""
    
    def __init__(self):
        """初始化热力图模型"""
        super().__init__()  # 调用基类初始化
        self.data_sets = []  # 存储多个数据集，每个元素是(数据, Z轴深度, 文件名)的元组
        self.fig_2d = None  # 当前选中的2D图形
        self.plotly_fig: Optional[go.Figure] = None  # Plotly图形，添加类型提示
        
        # 初始化配置加载器
        self.config_loader = get_config_loader()
        
        # 加载配置（自动处理迁移）
        self._load_configuration()
        
        # 初始化X轴翻转状态
        self._x_axis_flipped = self._config.get('ui_settings', {}).get('x_axis_flipped', False)
        
        # 设置Plotly的默认模板
        pio.templates.default = "plotly_white"
        
        # 创建自定义蓝白红色标，确保0值为白色
        self._custom_colormap = self._create_custom_blue_white_red_colormap()
        
        # 初始化操作日志记录
        self._operation_logs = []
        self._max_log_entries = 1000  # 最大日志条目数
        self._enable_logging = True  # 启用日志记录
        
        # 初始化性能监控
        self._performance_stats = {
            'interpolation_times': [],
            'memory_usage': [],
            'data_processing_times': []
        }
    
    def _load_configuration(self):
        """加载配置，自动处理向后兼容性和迁移"""
        try:
            # 加载配置（自动处理迁移）
            config_data = self.config_loader.load_config()
            
            # 初始化配置参数
            self._config['performance_settings'] = config_data.get(
                'performance_settings', 
                DefaultSettings.get_performance_settings()
            )
            self._config['colorbar_settings'] = config_data.get(
                'colorbar_settings', 
                DefaultSettings.get_colorbar_settings()
            )
            
            # UI设置
            ui_settings = config_data.get('ui_settings', {})
            self._config['current_colormap'] = ui_settings.get('current_colormap', 'coolwarm')
            self._config['current_interpolation'] = ui_settings.get('current_interpolation', 'rbf')
            
            # 存储完整配置用于后续保存
            self._config.update(config_data)
            
            print("配置加载完成，支持向后兼容性")
            
        except Exception as e:
            print(f"配置加载失败，使用默认设置: {e}")
            # 使用默认配置
            self._config['performance_settings'] = DefaultSettings.get_performance_settings()
            self._config['colorbar_settings'] = DefaultSettings.get_colorbar_settings()
            self._config['current_colormap'] = 'coolwarm'
            self._config['current_interpolation'] = 'rbf'
    
    def save_configuration(self):
        """保存当前配置"""
        try:
            # 更新UI设置
            if 'ui_settings' not in self._config:
                self._config['ui_settings'] = {}
            
            self._config['ui_settings'].update({
                'current_colormap': self._config.get('current_colormap', 'coolwarm'),
                'current_interpolation': self._config.get('current_interpolation', 'rbf'),
                'x_axis_flipped': getattr(self, '_x_axis_flipped', False)
            })
            
            # 保存配置
            success = self.config_loader.save_config(self._config)
            if success:
                print("配置保存成功")
            else:
                print("配置保存失败")
            
            return success
            
        except Exception as e:
            print(f"保存配置时发生错误: {e}")
            return False
    
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
        """通用插值方法 - 性能优化版本
        
        优化的插值方法，特别针对大数据集进行性能优化：
        1. 智能数据采样，减少计算复杂度
        2. 内存使用优化，避免不必要的数据复制
        3. 分块处理大数据集，防止内存溢出
        4. 缓存机制，避免重复计算
        
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
        
        # 性能优化：检查数据大小并应用智能采样
        data_size = len(x)
        max_points = self.performance_settings.get('max_points', 50000)
        
        # 记录性能信息
        import time
        start_time = time.time()
        
        try:
            # 大数据集优化：智能采样
            if data_size > max_points:
                self._log_operation(f"大数据集检测 ({data_size} 点)，应用智能采样到 {max_points} 点")
                
                # 使用分层采样保持数据分布特征
                sample_indices = self._intelligent_sampling(x, y, values, max_points)
                x_sampled = x[sample_indices]
                y_sampled = y[sample_indices]
                values_sampled = values[sample_indices]
                
                # 记录采样信息
                self._log_operation(f"智能采样完成，从 {data_size} 点采样到 {len(sample_indices)} 点")
            else:
                # 避免不必要的数据复制
                x_sampled, y_sampled, values_sampled = x, y, values
            
            # 内存优化：检查网格大小
            grid_size = xi_grid.size
            if grid_size > 1000000:  # 1M points
                self._log_operation(f"大网格检测 ({grid_size} 点)，可能需要分块处理")
                return self._chunked_interpolation(x_sampled, y_sampled, values_sampled, 
                                                 xi_grid, yi_grid, method)
            
            # 标准插值处理
            zi = self._perform_interpolation(x_sampled, y_sampled, values_sampled, 
                                           xi_grid, yi_grid, method)
            
            # 记录性能信息
            elapsed_time = time.time() - start_time
            self._log_operation(f"插值完成，方法: {method}, 耗时: {elapsed_time:.3f}s, "
                              f"数据点: {len(x_sampled)}, 网格: {grid_size}")
            
            return zi
            
        except MemoryError as e:
            self._log_error(f"内存不足，插值失败: {e}")
            # 尝试降级处理
            return self._fallback_interpolation(x, y, values, xi_grid, yi_grid)
        except Exception as e:
            self._log_error(f"插值失败: {method}, 错误: {str(e)}")
            # 如果指定方法失败，回退到线性插值
            return self._perform_interpolation(x_sampled if 'x_sampled' in locals() else x, 
                                             y_sampled if 'y_sampled' in locals() else y, 
                                             values_sampled if 'values_sampled' in locals() else values,
                                             xi_grid, yi_grid, 'linear')
    
    def _intelligent_sampling(self, x: np.ndarray, y: np.ndarray, values: np.ndarray, 
                            target_points: int) -> np.ndarray:
        """智能数据采样，保持数据分布特征
        
        使用分层采样策略，确保采样后的数据仍能代表原始数据的分布特征：
        1. 保留极值点（最大值、最小值附近的点）
        2. 均匀空间采样，保持空间分布
        3. 保留数据密度变化区域的代表点
        
        Args:
            x, y, values: 原始数据
            target_points: 目标采样点数
            
        Returns:
            np.ndarray: 采样索引数组
        """
        try:
            n_points = len(x)
            if n_points <= target_points:
                return np.arange(n_points)
            
            # 1. 保留极值点 (10% 的目标点数)
            extreme_count = max(int(target_points * 0.1), 20)
            
            # 找到最大值和最小值附近的点
            max_idx = np.argmax(values)
            min_idx = np.argmin(values)
            
            # 找到极值附近的点
            max_neighbors = self._find_neighbors(x, y, x[max_idx], y[max_idx], extreme_count // 2)
            min_neighbors = self._find_neighbors(x, y, x[min_idx], y[min_idx], extreme_count // 2)
            
            extreme_indices = np.unique(np.concatenate([max_neighbors, min_neighbors]))
            
            # 2. 剩余点数用于均匀空间采样
            remaining_points = target_points - len(extreme_indices)
            
            # 创建空间网格进行均匀采样
            x_range = x.max() - x.min()
            y_range = y.max() - y.min()
            
            # 计算网格大小
            grid_size = int(np.sqrt(remaining_points))
            x_bins = np.linspace(x.min(), x.max(), grid_size + 1)
            y_bins = np.linspace(y.min(), y.max(), grid_size + 1)
            
            # 在每个网格单元中选择代表点
            spatial_indices = []
            for i in range(grid_size):
                for j in range(grid_size):
                    # 找到在当前网格单元中的点
                    mask = ((x >= x_bins[i]) & (x < x_bins[i+1]) & 
                           (y >= y_bins[j]) & (y < y_bins[j+1]))
                    cell_indices = np.where(mask)[0]
                    
                    if len(cell_indices) > 0:
                        # 在单元中选择一个代表点（选择最接近单元中心的点）
                        cell_center_x = (x_bins[i] + x_bins[i+1]) / 2
                        cell_center_y = (y_bins[j] + y_bins[j+1]) / 2
                        
                        distances = ((x[cell_indices] - cell_center_x)**2 + 
                                   (y[cell_indices] - cell_center_y)**2)
                        best_idx = cell_indices[np.argmin(distances)]
                        spatial_indices.append(best_idx)
            
            # 合并极值点和空间采样点
            all_indices = np.unique(np.concatenate([extreme_indices, spatial_indices]))
            
            # 如果还需要更多点，随机补充
            if len(all_indices) < target_points:
                remaining_mask = np.ones(n_points, dtype=bool)
                remaining_mask[all_indices] = False
                remaining_candidates = np.where(remaining_mask)[0]
                
                if len(remaining_candidates) > 0:
                    additional_count = min(target_points - len(all_indices), len(remaining_candidates))
                    additional_indices = np.random.choice(remaining_candidates, additional_count, replace=False)
                    all_indices = np.concatenate([all_indices, additional_indices])
            
            return all_indices[:target_points]
            
        except Exception as e:
            self._log_error(f"智能采样失败: {e}")
            # 回退到简单随机采样
            return np.random.choice(len(x), min(target_points, len(x)), replace=False)
    
    def _find_neighbors(self, x: np.ndarray, y: np.ndarray, center_x: float, center_y: float, 
                       count: int) -> np.ndarray:
        """找到指定点附近的邻居点"""
        distances = (x - center_x)**2 + (y - center_y)**2
        return np.argsort(distances)[:count]
    
    def _chunked_interpolation(self, x: np.ndarray, y: np.ndarray, values: np.ndarray,
                             xi_grid: np.ndarray, yi_grid: np.ndarray, method: str) -> np.ndarray:
        """分块插值处理，用于大网格数据
        
        将大网格分成小块进行插值，避免内存溢出
        """
        try:
            self._log_operation("开始分块插值处理")
            
            # 计算合适的块大小
            chunk_size = 500  # 每个维度的块大小
            result = np.full_like(xi_grid, np.nan)
            
            rows, cols = xi_grid.shape
            
            for i in range(0, rows, chunk_size):
                for j in range(0, cols, chunk_size):
                    # 定义当前块的边界
                    row_end = min(i + chunk_size, rows)
                    col_end = min(j + chunk_size, cols)
                    
                    # 提取当前块
                    xi_chunk = xi_grid[i:row_end, j:col_end]
                    yi_chunk = yi_grid[i:row_end, j:col_end]
                    
                    # 对当前块进行插值
                    zi_chunk = self._perform_interpolation(x, y, values, xi_chunk, yi_chunk, method)
                    
                    # 将结果存储到对应位置
                    result[i:row_end, j:col_end] = zi_chunk
            
            self._log_operation("分块插值处理完成")
            return result
            
        except Exception as e:
            self._log_error(f"分块插值失败: {e}")
            raise
    
    def _perform_interpolation(self, x: np.ndarray, y: np.ndarray, values: np.ndarray,
                             xi_grid: np.ndarray, yi_grid: np.ndarray, method: str) -> np.ndarray:
        """执行实际的插值计算"""
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
    
    def _fallback_interpolation(self, x: np.ndarray, y: np.ndarray, values: np.ndarray,
                              xi_grid: np.ndarray, yi_grid: np.ndarray) -> np.ndarray:
        """降级插值处理，用于内存不足的情况"""
        try:
            self._log_operation("内存不足，启用降级插值处理")
            
            # 大幅减少数据点
            max_fallback_points = 1000
            if len(x) > max_fallback_points:
                indices = np.random.choice(len(x), max_fallback_points, replace=False)
                x_reduced = x[indices]
                y_reduced = y[indices]
                values_reduced = values[indices]
            else:
                x_reduced, y_reduced, values_reduced = x, y, values
            
            # 降低网格分辨率
            original_shape = xi_grid.shape
            reduced_resolution = 100  # 降低到100x100
            
            if original_shape[0] > reduced_resolution:
                # 创建低分辨率网格
                x_min, x_max = xi_grid.min(), xi_grid.max()
                y_min, y_max = yi_grid.min(), yi_grid.max()
                
                xi_low = np.linspace(x_min, x_max, reduced_resolution)
                yi_low = np.linspace(y_min, y_max, reduced_resolution)
                xi_grid_low, yi_grid_low = np.meshgrid(xi_low, yi_low)
                
                # 在低分辨率网格上插值
                zi_low = griddata((x_reduced, y_reduced), values_reduced, 
                                (xi_grid_low, yi_grid_low), method='linear', fill_value=np.nan)
                
                # 将结果插值回原始分辨率
                from scipy.ndimage import zoom
                zoom_factor = (original_shape[0] / reduced_resolution, original_shape[1] / reduced_resolution)
                zi = zoom(zi_low, zoom_factor, order=1)
                
                # 确保输出形状正确
                if zi.shape != original_shape:
                    zi = np.resize(zi, original_shape)
            else:
                # 直接使用线性插值
                zi = griddata((x_reduced, y_reduced), values_reduced, 
                            (xi_grid, yi_grid), method='linear', fill_value=np.nan)
            
            self._log_operation("降级插值处理完成")
            return zi
            
        except Exception as e:
            self._log_error(f"降级插值也失败: {e}")
            # 最后的保底方案：返回全零数组
            return np.zeros_like(xi_grid)
        
    def load_csv(self, file_path: str, z_depth: float = 0.0) -> bool:
        """加载CSV文件 - 增强版本，包含性能监控和错误处理
        
        Args:
            file_path: CSV文件路径
            z_depth: Z轴深度值
            
        Returns:
            bool: 加载是否成功
        """
        import time
        start_time = time.time()
        file_name = Path(file_path).name
        
        try:
            self._log_operation(f"开始加载CSV文件: {file_name}")
            
            # 检查文件是否存在
            if not Path(file_path).exists():
                error_msg = f"文件不存在: {file_path}"
                self._log_error(error_msg)
                self.notify_observers('load_error', error_msg)
                return False
            
            # 检查文件大小
            file_size = Path(file_path).stat().st_size
            if file_size > 100 * 1024 * 1024:  # 100MB
                self._log_operation(f"大文件警告: {file_name} ({file_size/1024/1024:.1f}MB)", 'WARNING')
            
            # 尝试加载数据
            data = None
            encoding_used = None
            
            # 首先尝试UTF-8编码
            try:
                data = pd.read_csv(file_path, encoding='utf-8')
                encoding_used = 'utf-8'
                self._log_operation(f"使用UTF-8编码成功加载: {file_name}")
            except UnicodeDecodeError:
                # 如果UTF-8失败，尝试其他编码
                encodings_to_try = ['gbk', 'gb2312', 'latin1', 'cp1252']
                for encoding in encodings_to_try:
                    try:
                        data = pd.read_csv(file_path, encoding=encoding)
                        encoding_used = encoding
                        self._log_operation(f"使用{encoding}编码成功加载: {file_name}")
                        break
                    except (UnicodeDecodeError, UnicodeError):
                        continue
                
                if data is None:
                    error_msg = f"无法使用任何编码加载文件: {file_name}"
                    self._log_error(error_msg)
                    self.notify_observers('load_error', error_msg)
                    return False
            
            # 验证数据格式
            required_columns = ['X', 'Y', 'Value']
            missing_columns = [col for col in required_columns if col not in data.columns]
            if missing_columns:
                error_msg = f"CSV文件缺少必需的列: {missing_columns}"
                self._log_error(error_msg)
                self.notify_observers('load_error', error_msg)
                return False
            
            # 数据质量检查
            original_count = len(data)
            
            # 移除包含NaN值的行
            data_clean = data.dropna(subset=required_columns)
            if len(data_clean) < original_count:
                removed_count = original_count - len(data_clean)
                self._log_operation(f"移除了 {removed_count} 行包含NaN值的数据", 'WARNING')
            
            # 检查是否还有有效数据
            if len(data_clean) == 0:
                error_msg = f"文件 {file_name} 没有有效的数据行"
                self._log_error(error_msg)
                self.notify_observers('load_error', error_msg)
                return False
            
            # 检查数据范围的合理性
            try:
                x_range = data_clean['X'].max() - data_clean['X'].min()
                y_range = data_clean['Y'].max() - data_clean['Y'].min()
                value_range = data_clean['Value'].max() - data_clean['Value'].min()
                
                if x_range <= 0 or y_range <= 0:
                    self._log_operation(f"数据范围异常: X范围={x_range}, Y范围={y_range}", 'WARNING')
                
                if value_range <= 0:
                    self._log_operation(f"应力值范围异常: {value_range}", 'WARNING')
                
            except Exception as range_error:
                self._log_error(f"数据范围检查失败: {range_error}", range_error)
            
            # 记录数据统计信息
            data_stats = {
                'total_points': len(data_clean),
                'x_range': (float(data_clean['X'].min()), float(data_clean['X'].max())),
                'y_range': (float(data_clean['Y'].min()), float(data_clean['Y'].max())),
                'value_range': (float(data_clean['Value'].min()), float(data_clean['Value'].max())),
                'file_size_mb': file_size / 1024 / 1024,
                'encoding': encoding_used
            }
            
            print(f"成功加载数据: {len(data_clean)} 个数据点")
            print(f"X范围: {data_stats['x_range'][0]:.1f} - {data_stats['x_range'][1]:.1f} μm")
            print(f"Y范围: {data_stats['y_range'][0]:.1f} - {data_stats['y_range'][1]:.1f} μm")
            print(f"应力值范围: {data_stats['value_range'][0]:.2f} - {data_stats['value_range'][1]:.2f} MPa")
            
            # 将数据集添加到列表
            self.data_sets.append((data_clean, z_depth, file_name))
            
            # 记录性能信息
            load_duration = time.time() - start_time
            self._log_performance(f"CSV加载 - {file_name}", load_duration, len(data_clean))
            
            # 通知观察者数据集已添加
            self.notify_observers('dataset_added', {
                'index': len(self.data_sets) - 1,
                'file_name': file_name,
                'z_depth': z_depth,
                'data_count': len(data_clean),
                'data_stats': data_stats,
                'load_duration': load_duration
            })
            
            self._log_operation(f"CSV文件加载完成: {file_name}, 耗时: {load_duration:.3f}s")
            return True
            
        except pd.errors.EmptyDataError:
            error_msg = f"CSV文件为空: {file_name}"
            self._log_error(error_msg)
            self.notify_observers('load_error', error_msg)
            return False
        except pd.errors.ParserError as e:
            error_msg = f"CSV文件格式错误: {file_name}, 错误: {str(e)}"
            self._log_error(error_msg, e)
            self.notify_observers('load_error', error_msg)
            return False
        except MemoryError:
            error_msg = f"内存不足，无法加载大文件: {file_name}"
            self._log_error(error_msg)
            self.notify_observers('load_error', error_msg)
            return False
        except Exception as e:
            error_msg = f"加载CSV文件失败: {file_name}, 错误: {str(e)}"
            self._log_error(error_msg, e)
            self.notify_observers('load_error', error_msg)
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
        
        # 保存配置以确保持久化
        self.save_configuration()
        
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
        return self.safe_smart_range_calculation(values)
    
    def _add_colorbar_annotations(self, cbar, vmin: float, vmax: float):
        """为matplotlib色标条添加max/min标注
        
        Args:
            cbar: matplotlib colorbar对象
            vmin: 最小值
            vmax: 最大值
        """
        cbar_ax = cbar.ax
        
        # 在色标条顶部添加最大值标注
        cbar_ax.text(1.15, 1.02, f'max: {vmax:.0f}', transform=cbar_ax.transAxes, 
                    fontsize=10, ha='left', va='bottom', fontfamily='sans-serif')
        
        # 在色标条底部添加最小值标注
        cbar_ax.text(1.15, -0.02, f'min: {vmin:.0f}', transform=cbar_ax.transAxes,
                    fontsize=10, ha='left', va='top', fontfamily='sans-serif')
    
    def get_effective_range(self, dataset_index: int = None) -> Tuple[float, float]:
        """获取有效的色标范围
        
        简化的范围计算逻辑：
        1. 如果用户设置了手动范围，优先使用手动值
        2. 否则根据智能范围计算设置自动计算
        3. 应用错误处理确保返回有效范围
        
        Args:
            dataset_index: 数据集索引，如果为None则计算所有数据集的范围
            
        Returns:
            Tuple[float, float]: (最小值, 最大值)
        """
        # 检查是否有手动设置的范围值
        manual_vmin = self.colorbar_settings.get('vmin')
        manual_vmax = self.colorbar_settings.get('vmax')
        
        # 如果用户设置了完整的手动范围，直接使用并验证
        if manual_vmin is not None and manual_vmax is not None:
            return self.handle_invalid_data_range(manual_vmin, manual_vmax)
        
        # 否则根据智能范围计算设置自动计算
        smart_range = self.colorbar_settings.get('smart_range', False)
        vmin, vmax = self.get_data_range(dataset_index, smart_range=smart_range)
        
        # 如果只设置了部分手动范围，进行混合使用
        if manual_vmin is not None:
            vmin = manual_vmin
        if manual_vmax is not None:
            vmax = manual_vmax
            
        return self.handle_invalid_data_range(vmin, vmax)
    
    def _calculate_smart_range(self, values: np.ndarray) -> Tuple[float, float]:
        """计算智能色标卡范围
        
        优化的智能范围计算算法，确保在各种数据情况下的稳定性：
        1. 使用稳健的统计方法去除异常值
        2. 根据数据分布特征自适应调整范围
        3. 确保范围对称性（如果数据围绕零分布）
        4. 添加边界情况处理，提高算法稳定性
        
        Args:
            values: 数据值数组
            
        Returns:
            Tuple[float, float]: (智能最小值, 智能最大值)
        """
        # 移除NaN和无穷值，确保数据有效性
        clean_values = values[np.isfinite(values)]
        if len(clean_values) == 0:
            return (0.0, 1.0)
        
        # 如果数据点太少，直接使用最小最大值
        if len(clean_values) < 10:
            return (float(np.min(clean_values)), float(np.max(clean_values)))
        
        # 基本统计信息
        mean_val = np.mean(clean_values)
        std_val = np.std(clean_values)
        median_val = np.median(clean_values)
        
        # 使用更稳健的百分位数方法去除异常值
        # 根据数据分布调整百分位数阈值
        if std_val > 0:
            # 计算变异系数来判断数据分散程度
            cv = std_val / abs(mean_val) if abs(mean_val) > 1e-10 else float('inf')
            
            if cv > 2.0:  # 高变异性数据，使用更保守的百分位数
                p_low = np.percentile(clean_values, 2.5)
                p_high = np.percentile(clean_values, 97.5)
            elif cv > 1.0:  # 中等变异性数据
                p_low = np.percentile(clean_values, 1.0)
                p_high = np.percentile(clean_values, 99.0)
            else:  # 低变异性数据，可以使用更宽的范围
                p_low = np.percentile(clean_values, 0.5)
                p_high = np.percentile(clean_values, 99.5)
        else:
            # 标准差为0，所有值相同
            return (float(clean_values[0]), float(clean_values[0]))
        
        # 使用改进的IQR方法作为备选
        q1 = np.percentile(clean_values, 25)
        q3 = np.percentile(clean_values, 75)
        iqr = q3 - q1
        
        if iqr > 0:
            # 使用自适应的IQR倍数
            iqr_multiplier = 1.5 if cv <= 1.0 else 2.0  # 高变异性数据使用更大的倍数
            lower_bound = q1 - iqr_multiplier * iqr
            upper_bound = q3 + iqr_multiplier * iqr
            
            # 选择更合适的范围
            vmin = max(p_low, lower_bound)
            vmax = min(p_high, upper_bound)
        else:
            # IQR为0，使用百分位数结果
            vmin = p_low
            vmax = p_high
        
        # 确保范围不会过小，使用自适应的最小范围
        min_range = max(std_val * 0.1, abs(median_val) * 0.01, 1e-6)
        if vmax - vmin < min_range:
            center = (vmin + vmax) / 2
            half_range = min_range / 2
            vmin = center - half_range
            vmax = center + half_range
        
        # 检查数据是否围绕零对称分布（改进的对称性检测）
        zero_ratio = abs(mean_val) / (std_val + 1e-10)  # 避免除零
        if zero_ratio < 0.5 and vmin < 0 < vmax:  # 数据大致围绕零分布且跨越零点
            # 使用对称范围，有利于应力数据的可视化
            max_abs = max(abs(vmin), abs(vmax))
            # 添加小的不对称性容忍度，避免过度对称化
            asymmetry_tolerance = max_abs * 0.1
            if abs(abs(vmin) - abs(vmax)) < asymmetry_tolerance:
                vmin = -max_abs
                vmax = max_abs
        
        # 添加适度的边距以确保所有重要数据都可见
        range_span = vmax - vmin
        margin_ratio = 0.02 if range_span > abs(mean_val) else 0.05  # 自适应边距
        range_margin = range_span * margin_ratio
        vmin -= range_margin
        vmax += range_margin
        
        # 美化数值：智能四舍五入到合适的精度
        magnitude = max(abs(vmin), abs(vmax))
        if magnitude >= 1000:
            # 大数值：四舍五入到10的倍数
            vmin = np.floor(vmin / 10) * 10
            vmax = np.ceil(vmax / 10) * 10
        elif magnitude >= 100:
            # 中大数值：四舍五入到整数
            vmin = np.floor(vmin)
            vmax = np.ceil(vmax)
        elif magnitude >= 10:
            # 中等数值：四舍五入到0.1
            vmin = np.floor(vmin * 10) / 10
            vmax = np.ceil(vmax * 10) / 10
        elif magnitude >= 1:
            # 小数值：四舍五入到0.01
            vmin = np.floor(vmin * 100) / 100
            vmax = np.ceil(vmax * 100) / 100
        else:
            # 很小的数值：四舍五入到0.001
            vmin = np.floor(vmin * 1000) / 1000
            vmax = np.ceil(vmax * 1000) / 1000
        
        return (float(vmin), float(vmax))
    
    def handle_invalid_data_range(self, vmin: float, vmax: float) -> Tuple[float, float]:
        """处理无效的数据范围
        
        增强的异常数据范围处理，包含更全面的验证和修复逻辑：
        1. 检测并修复无效的数值（NaN、无穷大等）
        2. 处理范围过小或颠倒的情况
        3. 提供合理的默认值和警告信息
        
        Args:
            vmin: 最小值
            vmax: 最大值
            
        Returns:
            Tuple[float, float]: 修正后的(最小值, 最大值)
        """
        import math
        
        # 检查NaN值
        if math.isnan(vmin) or math.isnan(vmax):
            print(f"警告: 数据范围包含NaN值 (vmin={vmin}, vmax={vmax})，使用默认范围")
            return (0.0, 1.0)
        
        # 检查无穷大值
        if math.isinf(vmin) or math.isinf(vmax):
            print(f"警告: 数据范围包含无穷大值 (vmin={vmin}, vmax={vmax})，使用默认范围")
            return (0.0, 1.0)
        
        # 检查范围是否颠倒
        if vmin > vmax:
            print(f"警告: 数据范围颠倒 (vmin={vmin} > vmax={vmax})，自动交换")
            vmin, vmax = vmax, vmin
        
        # 检查范围是否相等
        if abs(vmax - vmin) < 1e-12:  # 使用更小的阈值检测相等
            if abs(vmin) < 1e-12:  # 如果都接近0
                print(f"警告: 数据范围过小且接近零 (vmin={vmin}, vmax={vmax})，使用默认范围")
                return (0.0, 1.0)
            else:
                # 如果不接近0，创建一个小的对称范围
                center = (vmin + vmax) / 2
                half_range = max(abs(center) * 0.01, 0.01)  # 至少1%的范围或0.01
                print(f"警告: 数据范围过小 (vmin={vmin}, vmax={vmax})，扩展为对称范围")
                return (center - half_range, center + half_range)
        
        # 检查范围是否过大（可能的数据错误）
        range_span = vmax - vmin
        magnitude = max(abs(vmin), abs(vmax))
        if magnitude > 1e10:  # 非常大的数值，可能是数据错误
            print(f"警告: 数据范围过大 (vmin={vmin}, vmax={vmax})，可能存在数据错误")
            # 不自动修复，但给出警告，让用户知道可能的问题
        
        # 检查范围是否合理（避免极端的范围比例）
        if range_span > 0 and magnitude > 0:
            ratio = range_span / magnitude
            if ratio > 1e6:  # 范围跨度相对于数值大小过大
                print(f"警告: 数据范围跨度异常大 (范围={range_span:.2e}, 量级={magnitude:.2e})")
        
        return (float(vmin), float(vmax))
    
    def safe_smart_range_calculation(self, values: np.ndarray) -> Tuple[float, float]:
        """安全的智能范围计算，包含多层失败回退机制
        
        提供稳健的智能范围计算，确保在各种异常情况下都能返回有效结果：
        1. 首先尝试完整的智能范围计算
        2. 如果失败，回退到简化的百分位数方法
        3. 再失败则使用原始数据范围
        4. 最后使用默认范围作为保底
        
        Args:
            values: 数据值数组
            
        Returns:
            Tuple[float, float]: (智能最小值, 智能最大值)
        """
        # 输入验证
        if values is None or len(values) == 0:
            print("警告: 输入数据为空，使用默认范围")
            return (0.0, 1.0)
        
        try:
            # 第一层：尝试完整的智能范围计算
            return self._calculate_smart_range(values)
        except Exception as e:
            print(f"智能范围计算失败: {e}")
            
            try:
                # 第二层：回退到简化的百分位数方法
                clean_values = values[np.isfinite(values)]
                if len(clean_values) == 0:
                    return (0.0, 1.0)
                
                if len(clean_values) < 3:
                    # 数据点太少，直接使用最小最大值
                    return (float(np.min(clean_values)), float(np.max(clean_values)))
                
                # 使用简单的百分位数方法
                vmin = float(np.percentile(clean_values, 5))
                vmax = float(np.percentile(clean_values, 95))
                
                # 确保范围有效
                if vmin >= vmax:
                    vmin = float(np.min(clean_values))
                    vmax = float(np.max(clean_values))
                
                print(f"使用简化百分位数方法: vmin={vmin:.3f}, vmax={vmax:.3f}")
                return (vmin, vmax)
                
            except Exception as fallback_error:
                print(f"简化百分位数方法也失败: {fallback_error}")
                
                try:
                    # 第三层：回退到原始数据范围
                    clean_values = values[np.isfinite(values)]
                    if len(clean_values) == 0:
                        return (0.0, 1.0)
                    
                    vmin = float(np.min(clean_values))
                    vmax = float(np.max(clean_values))
                    print(f"使用原始数据范围: vmin={vmin:.3f}, vmax={vmax:.3f}")
                    return (vmin, vmax)
                    
                except Exception as final_error:
                    # 第四层：最后的保底方案
                    print(f"所有范围计算方法都失败: {final_error}")
                    print("使用默认范围 (0.0, 1.0)")
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
        zi = self._interpolate_data(x, y, values, xi_grid, yi_grid)
        
        # 创建圆形遮罩
        distances = np.sqrt((xi_grid - x_center)**2 + (yi_grid - y_center)**2)
        mask = distances > radius
        zi[mask] = np.nan
        
        # 创建图形
        self.fig_2d = Figure(figsize=figsize, facecolor='white')
        ax = self.fig_2d.add_subplot(111)
        
        # 确定色标卡范围 - 使用新的统一范围计算逻辑
        vmin, vmax = self.get_effective_range(dataset_index)
        
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
        
        # 添加max/min标注
        self._add_colorbar_annotations(cbar, norm_vmin, norm_vmax)
        
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
            import time
            start_time = time.time()
            
            print("DEBUG: 开始创建 Plotly 3D 方格地毯热力图...")
            self._log_operation("开始创建Plotly 3D热力图")
            
            self.plotly_fig = make_subplots(
                rows=1, cols=1,
                specs=[[{'type': 'scene'}]],
                subplot_titles=[" "]
            )
            
            # 使用原始数据范围计算逻辑，不使用get_effective_range（与重置范围逻辑一致）
            # 确保colorbar_settings中的vmin/vmax已被清除或正确设置
            self._global_vmin, self._global_vmax = self.get_data_range(None, smart_range=False)
            print(f"DEBUG: 3D热力图使用原始数据范围: vmin={self._global_vmin:.2f}, vmax={self._global_vmax:.2f}")
            
            # 预先计算统一的色标设置，确保所有Surface使用相同范围
            plotly_colorscale, norm_vmin, norm_vmax = self._get_custom_plotly_colorscale(
                self._global_vmin, self._global_vmax
            )
            print(f"DEBUG: 统一色标范围: norm_vmin={norm_vmin:.2f}, norm_vmax={norm_vmax:.2f}")
            
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
                    
                    # 使用预先计算的统一色标设置
                    print(f"DEBUG: Surface {dataset_index} 使用统一色标范围: norm_vmin={norm_vmin:.2f}, norm_vmax={norm_vmax:.2f}")
                    
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
                                 title=dict(
                                     text="应力 (MPa)",
                                     side="right",
                                     font=dict(size=12, family="sans-serif")
                                 ),
                                 thickness=20,
                                 len=0.6,  # 色标卡高度为60%
                                 y=0.5,    # 垂直居中
                                 yanchor="middle",
                                 x=1.02,
                                 tickfont=dict(size=10, family="sans-serif")
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
            
            # 获取用于annotations的色标范围（与Surface使用相同的范围）
            first_norm_vmin, first_norm_vmax = norm_vmin, norm_vmax
            
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
                # 在色标上下位置添加max/min文本标签
                annotations=[
                    # 最大值标签 - 放置在色标上方
                    dict(
                        x=1.02, y=0.6,
                        xref='paper', yref='paper',
                        text=f'max: {first_norm_vmax:.0f}',
                        showarrow=False,
                        font=dict(size=12, color='black', family='sans-serif', weight='bold'),
                        xanchor='left',
                        yanchor='middle'
                    ),
                    # 最小值标签 - 放置在色标下方
                    dict(
                        x=1.02, y=0.18,
                        xref='paper', yref='paper', 
                        text=f'min: {first_norm_vmin:.0f}',
                        showarrow=False,
                        font=dict(size=12, color='black', family='sans-serif', weight='bold'),
                        xanchor='left',
                        yanchor='middle'
                    )
                ]
            )
            
            # 强制更新colorbar范围以确保显示正确的最大最小值
            # 这是关键修复：确保colorbar范围与Surface的cmin/cmax完全一致
            self.plotly_fig.update_coloraxes(
                cmin=norm_vmin,
                cmax=norm_vmax,
                cauto=False
            )
            
            # 另一种方法：直接更新所有traces的colorbar
            for trace in self.plotly_fig.data:
                if hasattr(trace, 'colorbar') and trace.colorbar is not None:
                    trace.update(
                        cmin=norm_vmin,
                        cmax=norm_vmax,
                        cauto=False
                    )
            
            print(f"DEBUG: 已强制更新colorbar范围为: {norm_vmin:.2f} - {norm_vmax:.2f}")
            
            # 简化配置以减少内存占用
            self.plotly_fig.update_layout(
                uirevision='true',  # 减少UI状态更新
                hovermode=False,    # 禁用悬停模式以减少事件处理
                autosize=True       # 自动调整大小
            )
            
            print("DEBUG: Plotly 3D 方格地毯热力图创建完成。")
            
            # 记录性能统计
            total_duration = time.time() - start_time
            total_points = sum(len(data) for data, _, _ in self.data_sets)
            self._log_performance(f"3D热力图创建", total_duration, total_points)
            
            self._log_operation(f"Plotly 3D热力图创建完成，耗时: {total_duration:.3f}s, "
                              f"数据集: {len(self.data_sets)}, 总数据点: {total_points}")
            
            return self.plotly_fig

        except MemoryError as e:
            error_message = "内存不足，无法创建3D热力图。请尝试减少数据点数量或降低分辨率。"
            self._log_error(error_message, e)
            
            # 提供用户友好的错误提示和建议
            self.notify_observers('memory_error', {
                'message': error_message,
                'suggestions': [
                    "降低分辨率设置（当前: {})".format(self.performance_settings['resolution']),
                    "减少数据点数量（当前: {} 个数据集)".format(len(self.data_sets)),
                    "关闭显示原始数据点选项",
                    "增加系统内存或关闭其他应用程序"
                ]
            })
            return None
        except Exception as e:
            error_message = f'创建Plotly 3D图形时发生错误: {str(e)}'
            self._log_error(error_message, e)
            
            # 提供详细的错误信息给开发者
            self.notify_observers('plotly_error', {
                'message': error_message,
                'exception_type': type(e).__name__,
                'data_sets_count': len(self.data_sets),
                'resolution': self.performance_settings['resolution']
            })
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
    
    def _log_operation(self, message: str, level: str = 'INFO'):
        """记录操作日志，便于问题诊断
        
        Args:
            message: 日志消息
            level: 日志级别 ('INFO', 'WARNING', 'ERROR')
        """
        if not self._enable_logging:
            return
        
        import datetime
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        log_entry = f"[{timestamp}] [{level}] {message}"
        
        # 添加到内存日志
        self._operation_logs.append(log_entry)
        
        # 限制日志条目数量，避免内存泄漏
        if len(self._operation_logs) > self._max_log_entries:
            self._operation_logs = self._operation_logs[-self._max_log_entries//2:]  # 保留一半
        
        # 同时输出到控制台（可选）
        if level == 'ERROR':
            print(f"错误: {message}")
        elif level == 'WARNING':
            print(f"警告: {message}")
        elif self._config.get('debug_mode', False):  # 只在调试模式下显示INFO日志
            print(f"信息: {message}")
    
    def _log_error(self, message: str, exception: Exception = None):
        """记录错误日志，包含详细的异常信息
        
        Args:
            message: 错误消息
            exception: 异常对象（可选）
        """
        if exception:
            import traceback
            error_details = f"{message}\n异常类型: {type(exception).__name__}\n异常信息: {str(exception)}\n堆栈跟踪:\n{traceback.format_exc()}"
        else:
            error_details = message
        
        self._log_operation(error_details, 'ERROR')
        
        # 通知观察者发生了错误
        self.notify_observers('error_occurred', {
            'message': message,
            'exception': str(exception) if exception else None,
            'timestamp': datetime.datetime.now().isoformat()
        })
    
    def _log_performance(self, operation: str, duration: float, data_size: int = None):
        """记录性能统计信息
        
        Args:
            operation: 操作名称
            duration: 操作耗时（秒）
            data_size: 数据大小（可选）
        """
        try:
            import psutil
            import os
            
            # 获取当前内存使用情况
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            # 记录性能数据
            perf_entry = {
                'operation': operation,
                'duration': duration,
                'memory_mb': memory_mb,
                'data_size': data_size,
                'timestamp': datetime.datetime.now().isoformat()
            }
            
            # 分类存储性能统计
            if 'interpolation' in operation.lower():
                self._performance_stats['interpolation_times'].append(perf_entry)
            elif 'processing' in operation.lower():
                self._performance_stats['data_processing_times'].append(perf_entry)
            
            self._performance_stats['memory_usage'].append(memory_mb)
            
            # 限制性能统计数据量
            max_stats = 100
            for key in self._performance_stats:
                if isinstance(self._performance_stats[key], list) and len(self._performance_stats[key]) > max_stats:
                    self._performance_stats[key] = self._performance_stats[key][-max_stats//2:]
            
            # 记录到日志
            log_msg = f"性能统计 - {operation}: {duration:.3f}s, 内存: {memory_mb:.1f}MB"
            if data_size:
                log_msg += f", 数据量: {data_size}"
            self._log_operation(log_msg, 'INFO')
            
        except ImportError:
            # 如果psutil不可用，只记录基本信息
            log_msg = f"性能统计 - {operation}: {duration:.3f}s"
            if data_size:
                log_msg += f", 数据量: {data_size}"
            self._log_operation(log_msg, 'INFO')
        except Exception as e:
            self._log_operation(f"性能统计记录失败: {e}", 'WARNING')
    
    def get_operation_logs(self, level: str = None, limit: int = None) -> List[str]:
        """获取操作日志
        
        Args:
            level: 过滤日志级别（可选）
            limit: 限制返回的日志条目数（可选）
            
        Returns:
            List[str]: 日志条目列表
        """
        logs = self._operation_logs
        
        # 按级别过滤
        if level:
            logs = [log for log in logs if f'[{level}]' in log]
        
        # 限制数量
        if limit:
            logs = logs[-limit:]
        
        return logs
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息
        
        Returns:
            Dict[str, Any]: 性能统计数据
        """
        stats = self._performance_stats.copy()
        
        # 计算统计摘要
        if stats['interpolation_times']:
            durations = [entry['duration'] for entry in stats['interpolation_times']]
            stats['interpolation_summary'] = {
                'count': len(durations),
                'avg_duration': sum(durations) / len(durations),
                'max_duration': max(durations),
                'min_duration': min(durations)
            }
        
        if stats['memory_usage']:
            stats['memory_summary'] = {
                'current_mb': stats['memory_usage'][-1] if stats['memory_usage'] else 0,
                'max_mb': max(stats['memory_usage']),
                'avg_mb': sum(stats['memory_usage']) / len(stats['memory_usage'])
            }
        
        return stats
    
    def clear_logs(self):
        """清空操作日志"""
        self._operation_logs.clear()
        self._log_operation("操作日志已清空", 'INFO')
    
    def export_logs(self, file_path: str) -> bool:
        """导出操作日志到文件
        
        Args:
            file_path: 导出文件路径
            
        Returns:
            bool: 导出是否成功
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("SiC应力可视化应用 - 操作日志\n")
                f.write("=" * 50 + "\n\n")
                
                for log_entry in self._operation_logs:
                    f.write(log_entry + "\n")
                
                # 添加性能统计摘要
                f.write("\n" + "=" * 50 + "\n")
                f.write("性能统计摘要\n")
                f.write("=" * 50 + "\n")
                
                stats = self.get_performance_stats()
                if 'interpolation_summary' in stats:
                    summary = stats['interpolation_summary']
                    f.write(f"插值操作统计:\n")
                    f.write(f"  总次数: {summary['count']}\n")
                    f.write(f"  平均耗时: {summary['avg_duration']:.3f}s\n")
                    f.write(f"  最大耗时: {summary['max_duration']:.3f}s\n")
                    f.write(f"  最小耗时: {summary['min_duration']:.3f}s\n\n")
                
                if 'memory_summary' in stats:
                    summary = stats['memory_summary']
                    f.write(f"内存使用统计:\n")
                    f.write(f"  当前使用: {summary['current_mb']:.1f}MB\n")
                    f.write(f"  最大使用: {summary['max_mb']:.1f}MB\n")
                    f.write(f"  平均使用: {summary['avg_mb']:.1f}MB\n")
            
            self._log_operation(f"日志已导出到: {file_path}", 'INFO')
            return True
            
        except Exception as e:
            self._log_error(f"导出日志失败: {e}", e)
            return False