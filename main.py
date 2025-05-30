import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from scipy.interpolate import griddata
from pathlib import Path
from typing import Tuple, Optional, List
import sys
import matplotlib
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.tri import Triangulation
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, 
    QPushButton, QFileDialog, QLabel, QInputDialog, QMessageBox,
    QTabWidget, QDoubleSpinBox, QFormLayout, QDialog, QListWidget, QGroupBox, QFrame
)
from PySide6.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# 解决中文乱码问题
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
matplotlib.rcParams['font.family'] = 'sans-serif'


class CircularHeatmapGenerator:
    """生成圆形热力图的核心类"""
    
    def __init__(self):
        self.data_sets = []  # 存储多个数据集，每个元素是(数据, Z轴深度, 文件名)的元组
        self.fig_2d = None  # 当前选中的2D图形
        self.fig_3d = None  # 3D图形（包含所有深度层）
        
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
        
        # 绘制热力图
        im = ax.imshow(zi, extent=[x_center-radius, x_center+radius, 
                                  y_center-radius, y_center+radius],
                      origin='lower', cmap='RdYlBu_r', aspect='equal')
        
        # 添加圆形边界
        circle = Circle((x_center, y_center), radius, fill=False, 
                       edgecolor='black', linewidth=2)
        ax.add_patch(circle)
        
        # 设置坐标轴（确保中文正常显示）
        ax.set_xlim(x_center - radius * 1.1, x_center + radius * 1.1)
        ax.set_ylim(y_center - radius * 1.1, y_center + radius * 1.1)
        ax.set_xlabel('X坐标 (μm)', fontsize=12, fontfamily='sans-serif')
        ax.set_ylabel('Y坐标 (μm)', fontsize=12, fontfamily='sans-serif')
        ax.set_title(f'SiC应力分布2D圆形热力图 (Z={z_depth}μm)\n{file_name}', 
                     fontsize=14, fontweight='bold', fontfamily='sans-serif')
        
        # 添加颜色条
        cbar = self.fig_2d.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label('应力值 (MPa)', fontsize=12, fontfamily='sans-serif')
        
        # 添加原始数据点
        ax.scatter(x, y, c='white', s=1, alpha=0.3, edgecolors='none')
        
        self.fig_2d.tight_layout()
        return self.fig_2d
    
    def create_circular_heatmap_3d(self, resolution: int = 100, figsize: Tuple[int, int] = (12, 10)) -> Figure:
        """创建所有数据集的3D圆形热力图
        
        Args:
            resolution: 网格分辨率
            figsize: 图形大小
            
        Returns:
            Figure: matplotlib图形对象
        """
        if len(self.data_sets) == 0:
            raise ValueError("请先加载CSV数据")
        
        # 创建3D图形
        self.fig_3d = Figure(figsize=figsize, facecolor='white')
        ax = self.fig_3d.add_subplot(111, projection='3d')
        
        # 确定全局的Z轴范围
        z_values = [z for _, z, _ in self.data_sets]
        z_min = min(z_values) - 1
        z_max = max(z_values) + 1
        
        # 为每个数据集生成一个圆形热力图层
        for dataset_index, (data, z_depth, file_name) in enumerate(self.data_sets):
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
            
            # 创建Z轴坐标（统一深度）
            z_grid = np.full_like(xi_grid, z_depth)
            
            # 将面片划分为三角形，只绘制圆形区域内的部分
            triangles = []
            vertices = []
            colors = []
            
            # 转换为归一化颜色值
            norm = plt.Normalize(np.nanmin(zi), np.nanmax(zi))
            cmap = plt.cm.RdYlBu_r
            
            for i in range(resolution-1):
                for j in range(resolution-1):
                    # 检查当前网格的四个顶点是否都在圆内
                    points = [
                        (i, j), (i+1, j), (i, j+1), (i+1, j+1)
                    ]
                    points_in_circle = [(not mask[p[0], p[1]]) for p in points]
                    
                    # 只有当至少有三个点在圆内时才添加三角形
                    if sum(points_in_circle) >= 3:
                        # 创建两个三角形，组成一个方格
                        if not mask[i, j] and not mask[i+1, j] and not mask[i, j+1]:
                            idx1 = len(vertices)
                            vertices.append([xi_grid[i, j], yi_grid[i, j], z_grid[i, j]])
                            vertices.append([xi_grid[i+1, j], yi_grid[i+1, j], z_grid[i+1, j]])
                            vertices.append([xi_grid[i, j+1], yi_grid[i, j+1], z_grid[i, j+1]])
                            triangles.append([idx1, idx1+1, idx1+2])
                            
                            # 添加颜色
                            avg_z = (zi[i, j] + zi[i+1, j] + zi[i, j+1]) / 3
                            if not np.isnan(avg_z):
                                colors.append(cmap(norm(avg_z)))
                            else:
                                colors.append((1, 1, 1, 0))  # 透明
                        
                        if not mask[i+1, j] and not mask[i+1, j+1] and not mask[i, j+1]:
                            idx2 = len(vertices)
                            vertices.append([xi_grid[i+1, j], yi_grid[i+1, j], z_grid[i+1, j]])
                            vertices.append([xi_grid[i+1, j+1], yi_grid[i+1, j+1], z_grid[i+1, j+1]])
                            vertices.append([xi_grid[i, j+1], yi_grid[i, j+1], z_grid[i, j+1]])
                            triangles.append([idx2, idx2+1, idx2+2])
                            
                            # 添加颜色
                            avg_z = (zi[i+1, j] + zi[i+1, j+1] + zi[i, j+1]) / 3
                            if not np.isnan(avg_z):
                                colors.append(cmap(norm(avg_z)))
                            else:
                                colors.append((1, 1, 1, 0))  # 透明
            
            # 如果有足够的三角形
            if triangles:
                vertices = np.array(vertices)
                triangles = np.array(triangles)
                
                # 创建三角形网格
                tri_collection = Poly3DCollection([vertices[t] for t in triangles])
                tri_collection.set_facecolors(colors)
                tri_collection.set_edgecolors('none')  # 不显示边缘线
                tri_collection.set_alpha(0.8)  # 设置透明度
                ax.add_collection3d(tri_collection)
            
            # 绘制每个层的原始数据点
            z_points = np.full_like(x, z_depth)
            scatter = ax.scatter(x, y, z_points, c=values, cmap='RdYlBu_r', s=10, alpha=0.6)
            
            # 添加Z坐标标签
            ax.text(x_center, y_center, z_depth, f"Z={z_depth}μm\n{file_name}", 
                    fontsize=8, ha='center', va='center')
        
        # 设置坐标轴
        ax.set_xlabel('X坐标 (μm)', fontsize=12, fontfamily='sans-serif')
        ax.set_ylabel('Y坐标 (μm)', fontsize=12, fontfamily='sans-serif')
        ax.set_zlabel('Z深度 (μm)', fontsize=12, fontfamily='sans-serif')
        ax.set_title(f'SiC应力分布3D热力图 (多层)', fontsize=14, fontweight='bold', fontfamily='sans-serif')
        
        # 设置Z轴范围
        ax.set_zlim(z_min, z_max)
        
        # 添加颜色条
        cbar = self.fig_3d.colorbar(scatter, ax=ax, shrink=0.6, aspect=20)
        cbar.set_label('应力值 (MPa)', fontsize=12, fontfamily='sans-serif')
        
        # 设置视角
        ax.view_init(elev=25, azim=45)
        
        self.fig_3d.tight_layout()
        return self.fig_3d
    
    def save_heatmap(self, output_path: str, figure_type: str = '2d', dpi: int = 300):
        """保存热力图
        
        Args:
            output_path: 输出文件路径
            figure_type: 图形类型 ('2d' 或 '3d')
            dpi: 图像分辨率
        """
        fig = self.fig_2d if figure_type == '2d' else self.fig_3d
        if fig is None:
            raise ValueError(f"请先生成{figure_type.upper()}热力图")
        
        fig.savefig(output_path, dpi=dpi, bbox_inches='tight')
        print(f"{figure_type.upper()}热力图已保存到: {output_path}")


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


class HeatmapViewer(QMainWindow):
    """热力图查看器GUI"""
    
    def __init__(self):
        super().__init__()
        self.generator = CircularHeatmapGenerator()
        self.current_dataset_index = 0
        self.init_ui()
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle('SiC应力圆形热力图生成器 - 多层3D可视化')
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
        left_layout = QVBoxLayout(left_panel)
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
        left_layout.addWidget(csv_group)
        
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
        
        # 保存按钮
        self.save_button = QPushButton('保存当前图像')
        self.save_button.clicked.connect(self.save_heatmap)
        self.save_button.setEnabled(False)
        control_layout.addWidget(self.save_button)
        
        left_layout.addWidget(control_group)
        
        # 状态标签
        self.status_label = QLabel('请添加CSV文件开始')
        self.status_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.status_label)
        
        # 右侧可视化区域
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        h_splitter.addWidget(right_panel, 3)  # 右侧面板占更多空间
        
        # 创建可视化图形区域（一个框架）
        self.visualization_frame = QFrame()
        self.visualization_layout = QVBoxLayout(self.visualization_frame)
        right_layout.addWidget(self.visualization_frame)
        
        # 当前视图类型
        self.current_view_type = None  # '2d' 或 '3d'
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
                f'请为 {Path(file_path).name} 设置Z轴深度值 (μm):', 
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
                self.status_label.setText('请添加CSV文件开始')
            else:
                self.status_label.setText('已移除CSV文件')
    
    def on_csv_selection_changed(self):
        """CSV列表选择项变更时的处理"""
        self.current_dataset_index = self.csv_list_widget.currentRow()
        if self.current_dataset_index >= 0:
            self.remove_button.setEnabled(True)
            self.z_input_button.setEnabled(True)
            self.generate_2d_button.setEnabled(True)
        else:
            self.remove_button.setEnabled(False)
            self.z_input_button.setEnabled(False)
            self.generate_2d_button.setEnabled(False)
    
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
    
    def generate_3d_heatmap(self):
        """生成3D热力图"""
        if self.generator.get_dataset_count() == 0:
            return
            
        try:
            fig = self.generator.create_circular_heatmap_3d()
            
            # 清除当前可视化区域
            self._clear_visualization()
            
            # 创建新的3D画布
            self.current_canvas = FigureCanvas(fig)
            self.visualization_layout.addWidget(self.current_canvas)
            self.current_view_type = '3d'
            
            self.status_label.setText('3D多层热力图生成完成')
            self.save_button.setEnabled(True)
            
        except Exception as e:
            QMessageBox.critical(self, '错误', f'生成3D热力图失败: {str(e)}')
    
    def _clear_visualization(self):
        """清除可视化区域的内容"""
        if self.current_canvas:
            self.visualization_layout.removeWidget(self.current_canvas)
            self.current_canvas.deleteLater()
            self.current_canvas = None
    
    def save_heatmap(self):
        """保存热力图"""
        if not self.current_view_type:
            return
            
        figure_type = self.current_view_type
        
        default_name = f'circular_heatmap_{figure_type}.png'
        file_path, _ = QFileDialog.getSaveFileName(
            self, '保存热力图', default_name, 
            'PNG文件 (*.png);;PDF文件 (*.pdf);;SVG文件 (*.svg)'
        )
        
        if file_path:
            try:
                self.generator.save_heatmap(file_path, figure_type)
                self.status_label.setText(f'已保存{figure_type.upper()}图像到: {Path(file_path).name}')
            except Exception as e:
                QMessageBox.critical(self, '错误', f'保存失败: {str(e)}')


def main():
    """主函数"""
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
                fig_3d = generator.create_circular_heatmap_3d()
                output_3d = "multi_layer_3d_heatmap.png"
                generator.save_heatmap(output_3d, '3d')
                print(f"多层3D热力图已生成并保存为: {output_3d}")
            else:
                # 单层也生成3D图
                fig_3d = generator.create_circular_heatmap_3d()
                data, z_depth, file_name = generator.data_sets[0]
                output_3d = f"{file_name.replace('.csv', '')}_3d_z{z_depth}.png"
                generator.save_heatmap(output_3d, '3d')
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
        
        viewer = HeatmapViewer()
        viewer.show()
        sys.exit(app.exec())


if __name__ == "__main__":
    main()
