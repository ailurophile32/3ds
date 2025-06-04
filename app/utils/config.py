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
            'resolution': 200,       # 默认分辨率
            'max_points': 10000,     # 限制点的最大数量
            'point_size': 20,        # 点大小
            'alpha': 1.0,           # 透明度
            'show_points': False,   # 是否显示原始数据点
            'decimation': 1,        # 数据抽样率 (取每 N 个点)   
            'grid_width': 1         # 网格线宽度
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