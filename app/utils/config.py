"""
应用配置模块

存储应用程序的全局配置和默认设置，便于集中管理。
"""
from typing import Dict, Any


class DefaultSettings:
    """默认设置类，提供应用程序各部分的默认配置值"""
    
    @staticmethod
    def get_performance_settings() -> Dict[str, Any]:
        """获取默认性能设置 - 优化版本
        
        针对大数据集和内存使用进行优化的性能设置
        
        Returns:
            Dict[str, Any]: 性能设置字典
        """
        return {
            'resolution': 200,      # 网格分辨率，平衡质量和性能
            'max_points': 50000,    # 最大数据点数，超过时自动采样
            'point_size': 20,       # 数据点显示大小
            'alpha': 1.0,          # 透明度设置
            'show_points': False,   # 是否显示原始数据点
            'decimation': 1,        # 数据抽样率（1=不抽样）
            'grid_width': 5,        # 网格线宽度
            'z_scale': 0.5,         # Z轴缩放比例
            
            # 新增的性能优化选项
            'enable_chunked_processing': True,    # 启用分块处理
            'chunk_size': 500,                    # 分块大小
            'memory_limit_mb': 1024,              # 内存使用限制（MB）
            'enable_smart_sampling': True,        # 启用智能采样
            'cache_interpolation': False,         # 缓存插值结果（实验性）
            'parallel_processing': False,         # 并行处理（实验性）
            'optimize_for_memory': True,          # 内存优化模式
            'auto_gc': True,                      # 自动垃圾回收
            'performance_monitoring': True,       # 性能监控
            'detailed_logging': False,            # 详细日志记录
            
            # 错误处理选项
            'fallback_on_memory_error': True,     # 内存错误时自动降级
            'max_retry_attempts': 3,              # 最大重试次数
            'error_recovery_mode': 'auto',        # 错误恢复模式（auto/manual/none）
        }
    
    @staticmethod
    def get_colorbar_settings() -> Dict[str, Any]:
        """获取默认色标卡设置
        
        Returns:
            Dict[str, Any]: 色标卡设置字典
        """
        return {
            'smart_range': False,   # 是否使用智能范围计算（默认不启用）
            'vmin': None,          # 手动设置的最小值
            'vmax': None           # 手动设置的最大值
        }
    
    @staticmethod
    def get_colormap_options() -> Dict[str, str]:
        """获取色标映射选项
        
        Returns:
            Dict[str, str]: 色标名称到显示名称的映射
        """
        return {
            'coolwarm': '蓝白红 - 推荐',
            'RdYlBu_r': '蓝黄红',
            'Spectral': '光谱色',
            'jet': 'Jet'
        }
    
    @staticmethod
    def get_interpolation_options() -> Dict[str, str]:
        """获取插值方法选项
        
        Returns:
            Dict[str, str]: 插值方法名称到显示名称的映射
        """
        return {
            'linear': '线性插值 - 快速',
            'cubic': '三次插值 - 平滑',
            'nearest': '最近邻插值 - 保真',
            'rbf': 'RBF插值 - 最佳（推荐）'
        }
    
    @staticmethod
    def get_plotly_colorscale_mapping() -> Dict[str, str]:
        """获取matplotlib到Plotly的色标映射
        
        Returns:
            Dict[str, str]: matplotlib色标到Plotly色标的映射
        """
        return {
            'coolwarm': 'RdBu_r',  # 使用反向RdBu实现蓝白红效果
            'RdYlBu_r': 'RdYlBu_r',
            'Spectral': 'Spectral',
            'jet': 'Jet'
        }