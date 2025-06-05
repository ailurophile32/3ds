"""
应用配置模块

存储应用程序的全局配置和默认设置，便于集中管理。
"""
from typing import Dict, Any


class DefaultSettings:
    """默认设置类，提供应用程序各部分的默认配置值"""
    
    @staticmethod
    def get_performance_settings() -> Dict[str, Any]:
        """获取默认性能设置
        
        Returns:
            Dict[str, Any]: 性能设置字典
        """
        return {
            'resolution': 200,      # 最大分辨率，获得最精细的网格
            'max_points': 50000,    # 增加最大点数限制
            'point_size': 20,       # 最大点大小，更清晰可见
            'alpha': 0.85,          # 适度透明，减少反射和泛白效果
            'show_points': False,    # 显示原始数据点，获得完整信息
            'decimation': 1,        # 不进行数据抽样，保持完整精度
            'grid_width': 5,        # 最大网格线宽度，更清晰的网格
            'z_scale': 0.5          # 增加Z轴缩放，更好的3D效果
        }
    
    @staticmethod
    def get_colorbar_settings() -> Dict[str, Any]:
        """获取默认色标卡设置
        
        Returns:
            Dict[str, Any]: 色标卡设置字典
        """
        return {
            'auto_range': True,     # 是否自动设置范围
            'smart_range': True,    # 是否使用智能范围计算
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