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
            
            # 实现新的数据加载默认行为逻辑
            self.on_data_loaded()
            
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
        self.view.register_callback('on_files_dropped', self.on_files_dropped)  # 新增：拖拽文件处理
        self.view.register_callback('on_remove_csv', self.on_remove_csv)
        self.view.register_callback('on_set_z_depth', self.on_set_z_depth)
        self.view.register_callback('on_generate_2d', self.on_generate_2d)
        self.view.register_callback('on_generate_3d', self.on_generate_3d)
        self.view.register_callback('on_save_heatmap', self.on_save_heatmap)
        self.view.register_callback('on_z_scale_changed', self.on_z_scale_changed)
        self.view.register_callback('on_colormap_changed', self.on_colormap_changed)
        self.view.register_callback('on_interpolation_changed', self.on_interpolation_changed)
        self.view.register_callback('on_manual_range_input', self.on_manual_range_input)
        self.view.register_callback('on_smart_range_changed', self.on_smart_range_changed)
        self.view.register_callback('on_reset_range', self.on_reset_range)
        self.view.register_callback('on_apply_range', self.on_apply_range)
        self.view.register_callback('on_show_performance_settings', self.on_show_performance_settings)
        self.view.register_callback('on_csv_selection_changed', self.on_csv_selection_changed)
        self.view.register_callback('on_flip_x_axis', self.on_flip_x_axis)
        
        # 初始化视图状态，同步模型的翻转状态到视图
        self.view.update_flip_x_status(self.model._x_axis_flipped)
    
    def on_load_csv(self, file_paths=None):
        """处理加载CSV文件事件
        
        支持两种入口：
        1) 由CSVFileManager选择文件后通过信号传入 file_paths
        2) 无参数时，在此处弹出文件选择对话框
        """
        try:
            # 若未提供文件路径，则由控制器弹出文件选择框
            if not file_paths:
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
                    self._apply_import_initial_logic(last_index)
                    self._apply_import_initial_logic(last_index)
        except Exception as e:
            self.handle_exception(e, "加载CSV文件")
    
    def on_files_dropped(self, file_paths):
        """处理拖拽文件事件
        
        Args:
            file_paths: 拖拽的文件路径列表
        """
        try:
            # 过滤出CSV文件
            csv_files = [path for path in file_paths if path.lower().endswith('.csv')]
            
            if not csv_files:
                self.view.show_error('错误', '请拖拽CSV文件')
                return
            
            first_file_loaded = False
            for file_path in csv_files:
                # 弹出Z轴深度设置对话框
                z_depth, ok = self.view.show_z_depth_dialog()
                
                if ok:
                    if self.model.load_csv(file_path, z_depth):
                        first_file_loaded = True
                    else:
                        self.view.show_error('错误', f'加载失败: {file_path}')
                else:
                    # 用户取消了Z轴深度设置，停止处理后续文件
                    break
            
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
                    self._apply_import_initial_logic(last_index)
        except Exception as e:
            self.handle_exception(e, "处理拖拽文件")
    
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
            # 实现范围变化时的实时显示更新
            self.update_data_range_display()
            
            # 根据当前模式更新范围值显示
            if self.model.colorbar_settings.get('smart_range', False):
                # 智能范围模式：使用智能计算的范围
                vmin, vmax = self.model.get_data_range(index, smart_range=True)
                self.view.set_range_values(vmin, vmax)
            else:
                # 手动模式：显示当前数据集的原始范围，让用户了解数据分布
                vmin, vmax = self.model.get_data_range(index, smart_range=False)
                self.view.set_range_values(vmin, vmax)
                # 同时更新模型的设置，这样生成的热力图会使用正确的范围
                self.model.update_colorbar_settings({
                    'vmin': vmin,
                    'vmax': vmax
                })
    
    def on_generate_2d(self, index: int):
        """处理生成2D热力图事件
        
        Args:
            index: 数据集索引
        """
        try:
            # 切换到2D视图时隐藏右侧预览
            if hasattr(self.view, "preview_scroll_area"):
                self.view.clear_layer_previews()
                self.view.preview_scroll_area.hide()

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
            
            # 获取当前智能范围设置状态
            current_smart_range = self.model.colorbar_settings.get('smart_range', False)
            
            if current_smart_range:
                # 智能范围模式：使用智能计算的范围
                vmin, vmax = self.model.get_data_range(None, smart_range=True)
                # 保持智能范围设置，清除手动设置的范围值
                self.model.update_colorbar_settings({
                    'smart_range': True,  # 保持智能范围启用
                    'vmin': None,  # 清除手动设置的最小值
                    'vmax': None   # 清除手动设置的最大值
                })
            else:
                # 手动范围模式：获取当前设置的范围值或使用原始数据范围
                manual_vmin = self.model.colorbar_settings.get('vmin')
                manual_vmax = self.model.colorbar_settings.get('vmax')
                
                if manual_vmin is not None and manual_vmax is not None:
                    # 使用当前手动设置的范围
                    vmin, vmax = manual_vmin, manual_vmax
                else:
                    # 没有手动设置，使用原始数据范围
                    vmin, vmax = self.model.get_data_range(None, smart_range=False)
                    self.model.update_colorbar_settings({
                        'smart_range': False,  # 保持手动范围模式
                        'vmin': vmin,  # 设置为所有数据集的最小值
                        'vmax': vmax   # 设置为所有数据集的最大值
                    })
            
            # 更新视图显示（保持当前的智能范围状态）
            self.view.update_smart_range_status(current_smart_range)
            self.view.set_range_values(vmin, vmax)
            
            # 显示3D图形（确保色标范围已正确设置）
            self.view.show_3d_figure(fig)
            
            # 更新数据范围显示为3D模式（显示所有数据集的综合范围）
            self.update_data_range_display()

            # 生成并显示右侧2D层缩略图预览
            try:
                images, labels = self.model.generate_layer_thumbnails()
                self.view.clear_layer_previews()
                self.view.update_layer_previews(images, labels)
            except Exception as preview_e:
                print(f"生成或更新层预览失败: {preview_e}")

            # 设置控件状态（根据智能范围启用情况切换）
            if current_smart_range:
                self.view.vmin_spinbox.setEnabled(False)
                self.view.vmax_spinbox.setEnabled(False)
                self.view.apply_range_button.setEnabled(False)
            else:
                self.view.vmin_spinbox.setEnabled(True)
                self.view.vmax_spinbox.setEnabled(True)
                self.view.apply_range_button.setEnabled(False)  # 默认不启用，直到用户手动修改
            self.view.reset_range_button.setEnabled(True)
            
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
    
    def on_data_loaded(self):
        """数据加载后的新处理逻辑"""
        # 获取当前的智能范围设置，默认保持原有状态
        current_smart_range = self.model.colorbar_settings.get('smart_range', False)

        # 首次启动时，根据当前视图类型决定使用哪个数据集的范围
        if self.model.get_dataset_count() > 0:
            if self.view.current_view_type == 'plotly':
                target_index = None  # 3D视图模式：使用所有数据集的综合范围
            else:
                target_index = self.model.get_dataset_count() - 1  # 2D：使用最后一个（新加载）

            if current_smart_range:
                vmin, vmax = self.model.get_data_range(target_index, smart_range=True)
                # 保持智能范围启用，清除手动设置
                self.model.update_colorbar_settings({
                    'smart_range': True,
                    'vmin': None,
                    'vmax': None
                })
            else:
                vmin, vmax = self.model.get_data_range(target_index, smart_range=False)
                # 手动模式下，用原始范围初始化
                self.model.update_colorbar_settings({
                    'smart_range': False,
                    'vmin': vmin,
                    'vmax': vmax
                })
        else:
            vmin, vmax = 0, 100  # 默认范围

        # 更新视图显示（不强制修改智能范围为 False，保持与模型一致）
        self.view.update_smart_range_status(current_smart_range)
        self.view.set_range_values(vmin, vmax)
        self.update_data_range_display()

        # 设置控件状态：智能范围启用时禁用手动输入；否则启用
        if current_smart_range:
            self.view.vmin_spinbox.setEnabled(False)
            self.view.vmax_spinbox.setEnabled(False)
            self.view.apply_range_button.setEnabled(False)
        else:
            self.view.vmin_spinbox.setEnabled(True)
            self.view.vmax_spinbox.setEnabled(True)
            self.view.apply_range_button.setEnabled(False)  # 默认不启用，直到用户手动修改
        self.view.reset_range_button.setEnabled(True)

    def on_manual_range_input(self):
        """用户手动输入范围时的处理逻辑"""
        # 用户开始输入时，自动禁用智能范围计算
        if self.view.smart_range_checkbox.isChecked():
            self.view.update_smart_range_status(False)
            self.model.update_colorbar_settings({'smart_range': False})
            self.view.update_status('检测到手动输入，已自动禁用智能范围计算')
        
        # 启用应用按钮
        self.view.apply_range_button.setEnabled(True)
        
        # 验证手动输入的范围
        vmin = self.view.vmin_spinbox.value()
        vmax = self.view.vmax_spinbox.value()
        
        # 更新手动范围设置到模型（临时存储，应用时正式生效）
        self.model.update_colorbar_settings({
            'vmin': vmin,
            'vmax': vmax
        })
        
        # 实现范围变化时的实时显示更新
        self.update_data_range_display()
        
        if not self.validate_manual_range(vmin, vmax):
            # 如果验证失败，禁用应用按钮
            self.view.apply_range_button.setEnabled(False)
    
    def on_smart_range_changed(self, smart_range: bool):
        """处理智能范围计算设置变更事件
        
        Args:
            smart_range: 是否使用智能范围计算
        """
        # 更新模型设置，同时清除手动设置的范围值
        self.model.update_colorbar_settings({
            'smart_range': smart_range,
            'vmin': None,  # 清除手动设置的最小值
            'vmax': None   # 清除手动设置的最大值
        })
        
        # 同步更新视图中的智能范围复选框状态
        self.view.update_smart_range_status(smart_range)
        
        if smart_range:
            self.view.update_status('已启用智能范围计算 - 将自动去除异常值')
            # 智能范围启用时，禁用手动输入框并自动更新范围
            self.view.vmin_spinbox.setEnabled(False)
            self.view.vmax_spinbox.setEnabled(False)
            self.view.apply_range_button.setEnabled(False)
            
            # 如果有数据，自动更新到智能范围
            if self.model.get_dataset_count() > 0:
                # 修复：确保 current_dataset_index 有效，如果无效则使用第一个数据集
                current_index = self.view.current_dataset_index
                if current_index < 0 or current_index >= self.model.get_dataset_count():
                    current_index = 0
                    self.view.current_dataset_index = 0
                    # 同步更新列表选择
                    if self.view.csv_list_widget.count() > 0:
                        self.view.csv_list_widget.setCurrentRow(0)
                
                vmin, vmax = self.model.get_data_range(current_index, smart_range=True)
                self.view.set_range_values(vmin, vmax)
                # 实现范围变化时的实时显示更新
                self.update_data_range_display()
                
                # 自动刷新热力图显示
                if self.view.current_view_type == '2d':
                    self.on_generate_2d(current_index)
                elif self.view.current_view_type == 'plotly':
                    self.on_generate_3d()
        else:
            self.view.update_status('已禁用智能范围计算 - 可手动设置范围')
            # 智能范围禁用时，启用手动输入框和应用按钮
            self.view.vmin_spinbox.setEnabled(True)
            self.view.vmax_spinbox.setEnabled(True)
            self.view.apply_range_button.setEnabled(True)
            
            # 如果有数据，回退到原始数据范围
            if self.model.get_dataset_count() > 0:
                # 修复：确保 current_dataset_index 有效，如果无效则使用第一个数据集
                current_index = self.view.current_dataset_index
                if current_index < 0 or current_index >= self.model.get_dataset_count():
                    current_index = 0
                    self.view.current_dataset_index = 0
                    # 同步更新列表选择
                    if self.view.csv_list_widget.count() > 0:
                        self.view.csv_list_widget.setCurrentRow(0)
                
                vmin, vmax = self.model.get_data_range(current_index, smart_range=False)
                self.view.set_range_values(vmin, vmax)
                # 实现范围变化时的实时显示更新
                self.update_data_range_display()
                
                # 自动刷新热力图显示
                if self.view.current_view_type == '2d':
                    self.on_generate_2d(current_index)
                elif self.view.current_view_type == 'plotly':
                    self.on_generate_3d()
    
    def on_reset_range(self, dataset_index: int):
        """处理重置范围事件 - 优化版本
        
        重置按钮功能，恢复到原始数据范围：
        1. 恢复到原始数据范围
        2. 清除手动设置的范围值
        3. 将智能范围计算设为未勾选状态
        4. 提供清晰的视觉状态指示
        5. 自动刷新热力图显示
        
        Args:
            dataset_index: 数据集索引
        """
        if 0 <= dataset_index < self.model.get_dataset_count():
            try:
                # 1. 清除手动设置的范围值，并将智能范围设为未勾选
                self.view.update_smart_range_status(False)
                self.model.update_colorbar_settings({
                    'smart_range': False,  # 设为未勾选状态
                    'vmin': None,  # 清除手动设置的最小值
                    'vmax': None   # 清除手动设置的最大值
                })
                
                # 2. 获取原始数据范围
                # 根据当前视图类型决定使用哪个数据集的范围
                if self.view.current_view_type == 'plotly':
                    # 3D视图模式：使用所有数据集的综合范围
                    vmin, vmax = self.model.get_data_range(None, smart_range=False)
                else:
                    # 2D视图模式：使用指定数据集的范围
                    vmin, vmax = self.model.get_data_range(dataset_index, smart_range=False)
                
                # 3. 更新视图显示
                self.view.set_range_values(vmin, vmax)
                self.update_data_range_display()
                
                # 4. 更新控件状态 - 智能范围未勾选，启用手动输入
                self.view.vmin_spinbox.setEnabled(True)
                self.view.vmax_spinbox.setEnabled(True)
                self.view.apply_range_button.setEnabled(False)  # 重置后不需要应用
                
                # 5. 重置输入框样式，提供清晰的视觉反馈
                self.view._reset_spinbox_style()
                
                # 6. 实现范围重置后的热力图自动刷新逻辑
                self._auto_refresh_heatmap_after_reset()
                
                # 7. 添加操作反馈，提供清晰的视觉状态指示
                self.view.update_status(f'✓ 已重置为原始数据范围: {vmin:.2f} - {vmax:.2f} MPa')
                
                # 8. 可选：显示成功提示（短暂显示）
                self._show_operation_feedback("重置成功", "已恢复到原始数据范围", "success")
                
            except Exception as e:
                # 错误处理和用户反馈
                error_msg = f"重置范围失败: {str(e)}"
                self.view.update_status(f"❌ {error_msg}")
                self.view.message_handler.show_error("重置失败", error_msg)
                print(f"重置范围错误: {e}")
        else:
            self.view.update_status("❌ 无效的数据集索引，无法重置范围")
            self.view.message_handler.show_warning("重置失败", "请选择有效的数据集")
    
    def on_apply_range(self, settings):
        """处理应用范围设置事件 - 优化版本
        
        优化应用按钮的启用/禁用状态管理：
        1. 增强输入验证和错误处理
        2. 实现范围应用后的热力图自动刷新逻辑
        3. 添加操作反馈，提供清晰的视觉状态指示
        4. 优化按钮状态管理
        
        Args:
            settings: 包含vmin和vmax的设置字典
        """
        try:
            # 1. 在应用设置前进行最终验证
            vmin = settings.get('vmin', 0)
            vmax = settings.get('vmax', 100)
            
            if not self.validate_manual_range(vmin, vmax):
                # 验证失败，提供明确的错误反馈
                self.view.update_status("❌ 范围验证失败，请检查输入值")
                self._show_operation_feedback("应用失败", "输入的范围值无效", "error")
                return
            
            # 2. 更新模型设置，确保智能范围计算被禁用
            enhanced_settings = {
                'smart_range': False,  # 确保手动模式
                'vmin': vmin,
                'vmax': vmax
            }
            self.model.update_colorbar_settings(enhanced_settings)
            
            # 3. 实现范围应用后的热力图自动刷新逻辑
            refresh_success = self._auto_refresh_heatmap_after_apply()
            
            if refresh_success:
                # 4. 优化应用按钮的启用/禁用状态管理
                self.view.apply_range_button.setEnabled(False)  # 应用后禁用，直到下次修改
                self.view.reset_apply_button_style()  # 重置按钮样式
                
                # 5. 更新数据范围显示
                self.update_data_range_display()
                
                # 6. 添加操作反馈，提供清晰的视觉状态指示
                self.view.update_status(f'✓ 手动范围已应用: {vmin:.2f} - {vmax:.2f} MPa')
                self._show_operation_feedback("应用成功", f"范围设置已更新并刷新显示", "success")
                
                # 7. 重置输入框样式为正常状态
                self.view._reset_spinbox_style()
            else:
                # 刷新失败的处理
                self.view.update_status("⚠️ 范围已应用，但图形刷新失败")
                self._show_operation_feedback("部分成功", "范围已设置，请手动重新生成图形", "warning")
                
        except Exception as e:
            # 错误处理和用户反馈
            error_msg = f"应用范围设置失败: {str(e)}"
            self.view.update_status(f"❌ {error_msg}")
            self.view.message_handler.show_error("应用失败", error_msg)
            self._show_operation_feedback("应用失败", "发生未知错误", "error")
            print(f"应用范围设置错误: {e}")
    
    
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
        """更新数据范围显示 - 增强版本
        
        增强数据范围显示功能：
        1. 实现智能范围和原始范围的同时显示
        2. 添加当前使用范围类型的清晰标识
        3. 实现范围变化时的实时显示更新
        4. 优化范围显示格式，提高可读性
        5. 在3D视图模式下显示所有数据集的综合范围
        """
        if self.model.get_dataset_count() == 0:
            # 没有数据时显示默认信息
            self.view.update_data_range_display(0, 0, smart_range_enabled=self.model.colorbar_settings.get('smart_range', False))
            return
            
        # 获取智能范围计算选项
        smart_range = self.model.colorbar_settings.get('smart_range', False)
        
        # 根据当前视图类型决定使用哪个数据集的范围
        if self.view.current_view_type == 'plotly':
            # 3D视图模式：显示所有数据集的综合范围
            vmin_smart, vmax_smart = self.model.get_data_range(None, smart_range=True)  # None表示所有数据集
            vmin_raw, vmax_raw = self.model.get_data_range(None, smart_range=False)
        else:
            # 2D视图模式：显示当前选中数据集的范围
            current_index = self.view.current_dataset_index
            if 0 <= current_index < self.model.get_dataset_count():
                vmin_smart, vmax_smart = self.model.get_data_range(current_index, smart_range=True)
                vmin_raw, vmax_raw = self.model.get_data_range(current_index, smart_range=False)
            else:
                self.view.update_data_range_display(0, 0, smart_range_enabled=smart_range)
                return
        
        if smart_range:
            # 智能范围模式：显示智能范围作为主要信息，原始范围作为参考
            self.view.update_data_range_display(vmin_smart, vmax_smart, vmin_raw, vmax_raw, smart_range_enabled=True)
            # 智能范围模式下，自动更新输入框显示值（但不启用）
            self.view.set_range_values(vmin_smart, vmax_smart)
        else:
            # 手动模式：显示原始数据范围作为参考，当前手动设置作为主要信息
            # 获取当前手动设置的范围
            manual_vmin = self.model.colorbar_settings.get('vmin')
            manual_vmax = self.model.colorbar_settings.get('vmax')
            
            if manual_vmin is not None and manual_vmax is not None:
                # 有手动设置，显示手动范围作为主要信息，原始数据范围作为参考
                # 注意：update_data_range_display 的 vmin/vmax 形参代表“数据范围基线”，而非手动值
                # 这里应传入当前数据的原始范围作为基线，以便在视图中用当前输入框（手动值）与数据范围进行对比
                self.view.update_data_range_display(vmin_raw, vmax_raw, vmin_raw, vmax_raw, smart_range_enabled=False)
                # 在3D模式下，也要更新输入框显示手动设置的范围
                if self.view.current_view_type == 'plotly':
                    self.view.set_range_values(manual_vmin, manual_vmax)
            else:
                # 没有手动设置，显示原始数据范围并更新输入框
                self.view.update_data_range_display(vmin_raw, vmax_raw, vmin_raw, vmax_raw, smart_range_enabled=False)
                self.view.set_range_values(vmin_raw, vmax_raw)
    
    def on_interpolation_changed(self, interpolation_method: str):
        """处理插值方法变更事件
        
        Args:
            interpolation_method: 插值方法名称
        """
        self.model.current_interpolation = interpolation_method
        self.view.update_status(f'插值方法已切换为: {interpolation_method}')
        
        # 根据当前视图类型重新生成图形
        if self.model.get_dataset_count() > 0:
            if self.view.current_view_type == '2d':
                self.on_generate_2d(self.view.current_dataset_index)
            elif self.view.current_view_type == 'plotly':
                self.on_generate_3d()
    
    def validate_manual_range(self, vmin: float, vmax: float) -> bool:
        """验证用户手动输入的范围
        
        Args:
            vmin: 最小值
            vmax: 最大值
            
        Returns:
            bool: 验证是否通过
        """
        if vmin >= vmax:
            self.view.message_handler.show_warning("范围错误", "最小值必须小于最大值")
            return False
        
        # 检查范围是否过小 - 使用更严格的阈值
        if abs(vmax - vmin) < 1e-6:
            self.view.message_handler.show_warning("范围错误", "范围过小，可能导致显示异常")
            return False
        
        # 检查范围是否过大（可能导致性能问题）
        if abs(vmax - vmin) > 1e6:
            self.view.message_handler.show_warning("范围警告", "范围过大，可能影响显示效果")
            # 不返回False，只是警告
        
        return True

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
    
    def _auto_refresh_heatmap_after_reset(self):
        """重置后自动刷新热力图显示
        
        实现重置范围后的热力图自动刷新逻辑，确保用户能立即看到变化效果
        """
        try:
            if self.view.current_view_type == '2d':
                # 重新生成2D图
                current_index = self.view.current_dataset_index
                if 0 <= current_index < self.model.get_dataset_count():
                    self.on_generate_2d(current_index)
                    return True
            elif self.view.current_view_type == 'plotly':
                # 重新生成3D图
                self.on_generate_3d()
                return True
            else:
                # 没有当前显示的图形，不需要刷新
                return True
        except Exception as e:
            print(f"自动刷新热力图失败: {e}")
            return False
    
    def _auto_refresh_heatmap_after_apply(self) -> bool:
        """应用设置后自动刷新热力图显示
        
        实现范围应用后的热力图自动刷新逻辑，确保新的范围设置立即生效
        
        Returns:
            bool: 刷新是否成功
        """
        try:
            if self.view.current_view_type == '2d':
                # 重新生成2D图
                current_index = self.view.current_dataset_index
                if 0 <= current_index < self.model.get_dataset_count():
                    self.on_generate_2d(current_index)
                    return True
                else:
                    return False
            elif self.view.current_view_type == 'plotly':
                # 重新生成3D图
                self.on_generate_3d()
                return True
            else:
                # 没有当前显示的图形，提示用户生成图形
                self.view.update_status("范围已设置，请生成热力图查看效果")
                return True
        except Exception as e:
            print(f"自动刷新热力图失败: {e}")
            return False
    
    def _show_operation_feedback(self, title: str, message: str, feedback_type: str = "info"):
        """显示操作反馈，提供清晰的视觉状态指示
        
        为用户操作提供即时的视觉反馈，增强用户体验
        
        Args:
            title: 反馈标题
            message: 反馈消息
            feedback_type: 反馈类型 ("success", "warning", "error", "info")
        """
        try:
            # 根据反馈类型选择合适的显示方式
            if feedback_type == "success":
                # 成功操作 - 可以使用状态栏显示，避免打断用户
                pass  # 已在调用处更新状态栏
            elif feedback_type == "warning":
                # 警告 - 显示警告对话框
                self.view.message_handler.show_warning(title, message)
            elif feedback_type == "error":
                # 错误 - 显示错误对话框
                self.view.message_handler.show_error(title, message)
            else:
                # 信息 - 使用状态栏显示
                pass  # 已在调用处更新状态栏
                
        except Exception as e:
            print(f"显示操作反馈失败: {e}")
            # 回退到简单的状态栏显示
            self.view.update_status(f"{title}: {message}")

    def _apply_import_initial_logic(self, last_index: int) -> None:
        """导入完成后的统一初始逻辑
        
        目标：
        - 默认关闭智能范围（smart_range=False）
        - 使用原始范围作为手动初始值（vmin/vmax）
        - 同步更新视图控件状态与范围显示
        - 根据当前视图类型自动生成 2D/3D 热力图
        
        Args:
            last_index: 刚导入/当前选中的数据集索引
        """
        if last_index < 0:
            return
        
        # 选中数据集
        self.view.csv_list_widget.setCurrentRow(last_index)
        
        # 依据视图类型选择范围基准
        if self.view.current_view_type == 'plotly':
            target_index = None  # 3D 视图：使用所有数据集综合范围
        else:
            target_index = last_index  # 2D 视图：使用当前数据集范围
        
        # 计算原始范围并设置为手动初始值
        vmin, vmax = self.model.get_data_range(target_index, smart_range=False)
        self.model.update_colorbar_settings({
            'smart_range': False,
            'vmin': vmin,
            'vmax': vmax
        })
        
        # 同步视图状态
        self.view.update_smart_range_status(False)
        self.view.set_range_values(vmin, vmax)
        self.update_data_range_display()
        self.view.vmin_spinbox.setEnabled(True)
        self.view.vmax_spinbox.setEnabled(True)
        self.view.apply_range_button.setEnabled(False)
        
        # 自动生成热力图
        if self.view.current_view_type == 'plotly':
            self.on_generate_3d()
        else:
            self.on_generate_2d(last_index)