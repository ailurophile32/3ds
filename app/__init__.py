"""
SiC应力可视化应用程序

基于MVC架构的SiC（碳化硅）应力分布可视化应用程序，
支持2D圆形热力图和3D多层热力图的生成与交互。

此应用程序使用PySide6构建GUI界面，使用Matplotlib和Plotly生成可视化图表。
"""

__version__ = '1.0.0'
__author__ = 'SiC应力可视化团队'

# 导出主要模块，便于从app包直接导入
from app.model.heatmap_model import HeatmapModel
from app.view.heatmap_view import HeatmapView
from app.controller.heatmap_controller import HeatmapController

# 导出工具类
from app.utils.config import DefaultSettings
from app.utils.message_handler import MessageHandler
from app.utils.widgets import PlotlyWebView, ZDepthInputDialog, PerformanceSettingsDialog

__all__ = [
    'HeatmapModel',
    'HeatmapView',
    'HeatmapController',
    'DefaultSettings',
    'MessageHandler',
    'PlotlyWebView',
    'ZDepthInputDialog',
    'PerformanceSettingsDialog'
]

# 设置matplotlib全局配置
import matplotlib.pyplot as plt
import matplotlib

# 解决中文乱码问题
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
matplotlib.rcParams['font.family'] = 'sans-serif' 