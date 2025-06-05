"""
热力图控制器模块

负责协调模型层和视图层，处理用户交互
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QProgressDialog, QFileDialog
from typing import Any

from app.controller.base_controller import BaseController
from app.model.heatmap_model import HeatmapModel
from app.utils.widgets import PerformanceSettingsDialog
from app.view.heatmap_view import HeatmapView


class HeatmapController(BaseController):
    """热力图控制器，协调模型和视图"""
    
    def __init__(self, model: HeatmapModel, view: HeatmapView):
        """初始化热力图控制器
        
        Args:
            model: 热力图数据模型
            view: 热力图视图
        """
        super().__init__(model, view)
        self.init_callbacks()
    
    def on_model_changed(self, event_type: str, data: Any) -> None:
        """处理模型变化事件
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        if event_type == 'dataset_added':
            # 更新数据集列表显示
            self.view.update_dataset_list(self.model.data_sets)
            self.view.update_status(f"已添加数据集: {data['file_name']}")
            
            # 更新按钮状态
            self.view.generate_3d_button.setEnabled(self.model.get_dataset_count() > 0)
            
            # 更新数据范围显示
            self.update_data_range_display()
            
            # 如果当前在3D视图模式，自动重新生成3D热力图
            if self.view.current_view_type == 'plotly':
                self.on_generate_3d()
            
        elif event_type == 'dataset_removed':
            # 更新数据集列表显示
            self.view.update_dataset_list(self.model.data_sets)
            self.view.update_status(f"已移除数据集: {data['file_name']}")
            
            # 更新按钮状态
            self.view.generate_3d_button.setEnabled(self.model.get_dataset_count() > 0)
            
            # 更新数据范围显示
            self.update_data_range_display()
            
        elif event_type == 'z_depth_updated':
            # 更新Z轴深度显示
            self.view.update_z_depth_display(data['index'], data['z_depth'])
            self.view.update_status(f"已更新Z轴深度: {data['file_name']} -> {data['z_depth']} μm")
            
        elif event_type == 'colorbar_settings_updated':
            # 更新色标卡设置
            self.update_data_range_display()
            
        elif event_type == 'performance_settings_updated':
            # 性能设置已更新，可能需要重新生成图形
            self.view.update_status("性能设置已更新")
            
        elif event_type == 'colormap_changed':
            # 色标已变更，可能需要重新生成图形
            self.view.update_status("色标已变更")
    
    def init_callbacks(self):
        """初始化视图回调函数"""
        self.view.register_callback('on_load_csv', self.on_load_csv)
        self.view.register_callback('on_remove_csv', self.on_remove_csv)
        self.view.register_callback('on_set_z_depth', self.on_set_z_depth)
        self.view.register_callback('on_generate_2d', self.on_generate_2d)
        self.view.register_callback('on_generate_3d', self.on_generate_3d)
        self.view.register_callback('on_save_heatmap', self.on_save_heatmap)
        self.view.register_callback('on_z_scale_changed', self.on_z_scale_changed)
        self.view.register_callback('on_colormap_changed', self.on_colormap_changed)
        self.view.register_callback('on_auto_range_changed', self.on_auto_range_changed)
        self.view.register_callback('on_smart_range_changed', self.on_smart_range_changed)
        self.view.register_callback('on_reset_range', self.on_reset_range)
        self.view.register_callback('on_apply_range', self.on_apply_range)
        self.view.register_callback('on_show_performance_settings', self.on_show_performance_settings)
        self.view.register_callback('on_csv_selection_changed', self.on_csv_selection_changed)
        self.view.register_callback('on_flip_x_axis', self.on_flip_x_axis)
        
        # 初始化视图状态，同步模型的翻转状态到视图
        self.view.update_flip_x_status(self.model._x_axis_flipped)
    
    def on_load_csv(self):
        """处理加载CSV文件事件"""
        try:
            file_paths, _ = QFileDialog.getOpenFileNames(
                self.view, '选择CSV文件', '', 'CSV文件 (*.csv)'
            )
            
            if not file_paths:
                return
                
            first_file_loaded = False
            for file_path in file_paths:
                # 弹出Z轴深度设置对话框
                z_depth, ok = self.view.show_z_depth_dialog()
                
                if ok:
                    if self.model.load_csv(file_path, z_depth):
                        first_file_loaded = True
                    else:
                        self.view.show_error('错误', f'加载失败: {file_path}')
            
            # 自动选择最后一个数据集并根据当前视图类型生成相应热力图
            if first_file_loaded:
                last_index = len(self.model.data_sets) - 1
                if last_index >= 0:
                    self.view.csv_list_widget.setCurrentRow(last_index)
                    
                    # 根据当前视图类型自动生成热力图
                    if self.view.current_view_type == 'plotly':
                        # 如果当前在3D视图，生成3D热力图
                        self.on_generate_3d()
                    else:
                        # 否则生成2D热力图
                        self.on_generate_2d(last_index)
        except Exception as e:
            self.handle_exception(e, "加载CSV文件")
    
    def on_remove_csv(self, index: int):
        """处理移除CSV文件事件
        
        Args:
            index: 要移除的数据集索引
        """
        if 0 <= index < len(self.model.data_sets):
            self.model.remove_dataset(index)
            self.view.update_dataset_list(self.model.data_sets)
            self.view.update_status('已移除CSV文件')
            
            # 更新数据范围显示
            self.update_data_range_display()
    
    def on_set_z_depth(self, index: int):
        """处理Z轴深度设置事件
        
        Args:
            index: 数据集索引
        """
        if 0 <= index < len(self.model.data_sets):
            data, current_z, file_name = self.model.data_sets[index]
            z_depth, ok = self.view.show_z_depth_dialog(current_z)
            
            if ok:
                self.model.update_z_depth(index, z_depth)
                self.view.update_z_depth_display(index, z_depth)
                self.view.update_status(f'{file_name} Z轴深度已设置为: {z_depth} μm')
    
    def on_csv_selection_changed(self, index: int):
        """处理CSV列表选择变更事件
        
        Args:
            index: 新选中的数据集索引
        """
        if 0 <= index < len(self.model.data_sets):
            self.update_data_range_display()
    
    def on_generate_2d(self, index: int):
        """处理生成2D热力图事件
        
        Args:
            index: 数据集索引
        """
        try:
            fig = self.model.create_circular_heatmap_2d(index)
            self.view.show_2d_figure(fig)
            self.view.update_status('2D圆形热力图生成完成')
        except Exception as e:
            self.view.message_handler.show_error('错误', f'生成2D热力图失败: {str(e)}')
    
    def on_generate_3d(self):
        """处理生成3D热力图事件"""
        if self.model.get_dataset_count() == 0:
            self.view.update_status('没有加载任何数据集，无法生成3D热力图。')
            self.view.message_handler.show_warning('提示', '请先加载至少一个CSV数据集。')
            return
            
        try:
            # 创建进度对话框
            progress_dialog = QProgressDialog("正在生成3D热力图，请稍候...", None, 0, 0, self.view)
            progress_dialog.setWindowTitle("生成3D热力图")
            progress_dialog.setMinimumWidth(400)
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setCancelButton(None)  # 禁用取消按钮
            progress_dialog.show()
            QApplication.processEvents()  # 确保对话框显示
            
            self.view.update_status('正在准备生成3D多层热力图...')
            
            fig = self.model.create_plotly_3d_heatmap()
            
            if fig is None:
                progress_dialog.close()  # 关闭进度对话框
                self.view.message_handler.show_error('错误', '创建Plotly图形对象失败，请检查控制台输出获取详细信息。')
                self.view.update_status('创建Plotly图形对象失败。')
                return
                
            progress_dialog.setLabelText("3D图形已创建，正在准备显示...")
            QApplication.processEvents()
            
            # 显示3D图形
            self.view.show_3d_figure(fig)
            
            # 关闭进度对话框
            progress_dialog.close()
            
            self.view.update_status('3D多层热力图生成完成 (WebGL渲染)')
            
        except Exception as e:
            self.view.message_handler.show_error('严重错误', f"生成3D热力图时发生严重错误，详情请查看控制台输出：\n{str(e)}")
            self.view.update_status(f'生成3D热力图失败: {str(e)}')
    
    def on_save_heatmap(self, figure_type: str):
        """处理保存热力图事件
        
        Args:
            figure_type: 图形类型 ('2d' 或 'plotly')
        """
        file_path = self.view.get_save_file_path(figure_type)
        if file_path:
            try:
                self.model.save_heatmap(file_path, figure_type)
                self.view.update_status(f'已保存{figure_type.upper()}图像到: {file_path}')
            except Exception as e:
                self.view.message_handler.show_error('错误', f'保存失败: {str(e)}')
    
    def on_colormap_changed(self, colormap_name: str):
        """处理色标样式变更事件
        
        Args:
            colormap_name: 色标名称
        """
        self.model.current_colormap = colormap_name
        self.view.update_status(f'热力图色标已切换')
        
        # 根据当前视图类型重新生成图形
        if self.model.get_dataset_count() > 0:
            if self.view.current_view_type == '2d':
                self.on_generate_2d(self.view.current_dataset_index)
            elif self.view.current_view_type == 'plotly':
                self.on_generate_3d()
    
    def on_z_scale_changed(self, z_scale):
        """处理Z轴缩放比例变更事件"""
        self.model.update_performance_settings({'z_scale': z_scale})
        
        # 如果已经生成了3D图，实时更新
        if self.view.current_view_type == 'plotly' and self.view.plotly_view is not None:
            self.on_generate_3d()
        
        self.view.update_status(f'Z轴缩放比例已更改为: {z_scale:.1f}')
    
    def on_auto_range_changed(self, auto_range: bool):
        """处理自动范围设置变更事件
        
        Args:
            auto_range: 是否自动设置范围
        """
        self.model.update_colorbar_settings({'auto_range': auto_range})
        
        if auto_range:
            self.view.update_status('已切换到自动色标卡范围')
        else:
            self.view.update_status('已切换到手动色标卡范围')
            # 如果有数据，自动填充当前数据范围
            if self.model.get_dataset_count() > 0:
                self.update_data_range_display()
        
        # 重新生成当前视图
        if self.model.get_dataset_count() > 0:
            if self.view.current_view_type == '2d':
                self.on_generate_2d(self.view.current_dataset_index)
            elif self.view.current_view_type == 'plotly':
                self.on_generate_3d()
    
    def on_smart_range_changed(self, smart_range: bool):
        """处理智能范围计算设置变更事件
        
        Args:
            smart_range: 是否使用智能范围计算
        """
        self.model.update_colorbar_settings({'smart_range': smart_range})
        
        if smart_range:
            self.view.update_status('已启用智能范围计算 - 将自动去除异常值')
        else:
            self.view.update_status('已禁用智能范围计算 - 使用原始数据范围')
        
        # 如果当前是自动模式且有数据，更新显示并重新生成图形
        if self.model.colorbar_settings['auto_range'] and self.model.get_dataset_count() > 0:
            self.update_data_range_display()
            # 重新生成当前视图
            if self.view.current_view_type == '2d':
                self.on_generate_2d(self.view.current_dataset_index)
            elif self.view.current_view_type == 'plotly':
                self.on_generate_3d()
    
    def on_reset_range(self, dataset_index: int):
        """处理重置范围事件
        
        Args:
            dataset_index: 数据集索引
        """
        if 0 <= dataset_index < self.model.get_dataset_count():
            # 根据智能范围计算选项获取数据范围
            smart_range = self.model.colorbar_settings.get('smart_range', True)
            vmin, vmax = self.model.get_data_range(dataset_index, smart_range=smart_range)
            
            # 更新视图和模型
            self.view.set_range_values(vmin, vmax)
            self.model.update_colorbar_settings({
                'vmin': vmin,
                'vmax': vmax
            })
            
            range_type = "智能" if smart_range else "原始"
            self.view.update_status(f'已重置色标卡范围为{range_type}数据范围: {vmin:.2f} - {vmax:.2f} MPa')
    
    def on_apply_range(self, settings):
        """处理应用范围设置事件
        
        Args:
            settings: 包含vmin和vmax的设置字典
        """
        self.model.update_colorbar_settings(settings)
        
        if self.view.current_view_type == '2d':
            self.on_generate_2d(self.view.current_dataset_index)
            self.view.update_status('色标卡设置已应用到热力图')
        elif self.view.current_view_type == 'plotly':
            self.on_generate_3d()
            self.view.update_status('色标卡设置已应用到热力图')
        else:
            self.view.update_status('请先生成热力图')
    
    
    def on_show_performance_settings(self):
        """处理性能设置对话框事件"""
        dialog = PerformanceSettingsDialog(
            parent=self.view, 
            current_settings=self.model.performance_settings,
            message_handler=self.view.message_handler
        )
        
        if dialog.exec():
            new_settings = dialog.get_settings()
            self.model.update_performance_settings(new_settings)
            self.view.update_status("3D性能设置已更新")
            
            # 如果已经生成了3D图，且设置发生变化，询问是否重新生成
            if self.view.current_view_type == 'plotly' and self.view.plotly_view is not None:
                if self.view.message_handler.show_question('更新视图', '设置已更改，是否重新生成3D视图？'):
                    self.on_generate_3d()
    
    def update_data_range_display(self):
        """更新数据范围显示"""
        current_index = self.view.current_dataset_index
        if 0 <= current_index < self.model.get_dataset_count():
            # 根据智能范围计算选项获取数据范围
            smart_range = self.model.colorbar_settings.get('smart_range', True)
            vmin, vmax = self.model.get_data_range(current_index, smart_range=smart_range)
            
            # 同时获取原始范围用于对比显示
            vmin_raw, vmax_raw = self.model.get_data_range(current_index, smart_range=False)
            
            if smart_range:
                self.view.update_data_range_display(vmin, vmax, vmin_raw, vmax_raw)
            else:
                self.view.update_data_range_display(vmin, vmax)
            
            # 如果是手动模式且输入框为默认值，自动填充数据范围
            if not self.model.colorbar_settings.get('auto_range', True):
                if self.view.vmin_spinbox.value() == 0.0 and self.view.vmax_spinbox.value() == 100.0:
                    self.view.set_range_values(vmin, vmax)
                    self.model.update_colorbar_settings({
                        'vmin': vmin,
                        'vmax': vmax
                    })
        else:
            self.view.update_data_range_display(0, 0)
    
    def on_flip_x_axis(self):
        """处理翻转X轴事件"""
        try:
            # 翻转所有数据集的X轴数据
            self.model.flip_x_axis()
            
            # 更新视图中勾选框的状态
            is_flipped = getattr(self.model, '_x_axis_flipped', False)
            self.view.update_flip_x_status(is_flipped)
            
            # 更新状态
            flip_status = "已翻转" if is_flipped else "已恢复"
            self.view.update_status(f"X轴{flip_status}，影响所有数据集")
            
            # 如果当前有显示的图形，重新生成
            if self.view.current_view_type == '2d':
                # 重新生成2D图
                current_index = self.view.current_dataset_index
                if 0 <= current_index < self.model.get_dataset_count():
                    self.on_generate_2d(current_index)
            elif self.view.current_view_type == 'plotly':
                # 重新生成3D图
                self.on_generate_3d()
                
        except Exception as e:
            self.view.message_handler.show_error('翻转X轴失败', f'翻转X轴时发生错误：{str(e)}')
            print(f"翻转X轴错误: {e}")