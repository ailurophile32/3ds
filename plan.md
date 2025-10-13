# SiC应力分析工具 V1.1 - 高级数据分析模块开发计划

## 架构设计

### UI架构

- 在主窗口右侧添加**标签页(QTabWidget)**系统，包含：
- "可视化"标签：现有的2D/3D热力图显示区域
- "统计分析"标签：Epic 1功能
- "趋势对比"标签：Epic 2功能  
- "梯度分析"标签：Epic 3功能

### 数据流设计

- **Model层**：在`HeatmapModel`中添加统计计算、差分计算、梯度计算方法
- **View层**：创建新的分析视图类和差分窗口类
- **Controller层**：扩展`HeatmapController`处理新的分析交互

## 实施阶段

### 阶段1：UI框架重构 (Foundation)

**任务1.1：重构主视图添加标签页系统（已完成）**

- 文件：`app/view/heatmap_view.py`
- 修改`HeatmapView.init_ui()`方法
- 将现有的可视化区域包装到第一个标签页中
- 创建3个新的空标签页：统计分析、趋势对比、梯度分析
- 保持现有功能完全不受影响

**任务1.2：创建差分云图窗口类**

- 新建文件：`app/view/difference_window.py`
- 继承`QDialog`或`QMainWindow`
- 包含：matplotlib画布、色标设置、保存按钮
- 使用与主窗口一致的样式和色标逻辑

### 阶段2：Epic 1 - 单层应力场量化表征

**任务2.1：Model层添加统计计算方法**

- 文件：`app/model/heatmap_model.py`
- 新增方法：
- `calculate_statistics(dataset_index)` - 返回{mean, median, std, min, max, skewness, kurtosis}
- `calculate_all_statistics()` - 返回所有数据集的统计表格
- `calculate_histogram_data(dataset_index, bins)` - 返回直方图数据和KDE曲线

**任务2.2：创建统计分析视图组件（已完成）**

- 新建文件：`app/view/statistics_view.py`
- 创建`StatisticsPanel`类（QWidget）
- 包含：
- 统计表格（QTableWidget）- 每列一个数据层，每行一个统计指标
- "复制到剪贴板"按钮
- "导出为CSV"按钮
- 数据层选择下拉框（QComboBox）
- 直方图显示区域（matplotlib FigureCanvas）
- Bin数量调节滑块（QSlider，范围10-100）
- KDE曲线开关（QCheckBox）

**任务2.3：集成统计分析到主窗口（已完成）**

- 文件：`app/view/heatmap_view.py`
- 在"统计分析"标签页中实例化`StatisticsPanel`
- 文件：`app/controller/heatmap_controller.py`
- 添加回调处理：
- `on_update_statistics()` - 数据加载/更新时刷新统计表
- `on_export_statistics_csv()` - 导出统计数据
- `on_generate_histogram()` - 生成直方图

### 阶段3：Epic 2 - 跨层对比与关联分析

**任务3.1：Model层添加趋势分析方法**

- 文件：`app/model/heatmap_model.py`
- 新增方法：
- `calculate_trend_data()` - 返回{depths, means, stds}用于折线图
- `calculate_difference_map(index1, index2)` - 计算两层差分数据，返回插值网格和差分值
- `get_diverging_colormap_for_difference()` - 返回以0为中心的蓝-白-红色标

**任务3.2：创建趋势对比视图组件（已完成）**

- 新建文件：`app/view/trend_view.py`
- 创建`TrendPanel`类（QWidget）
- 包含：
- "生成趋势图"按钮
- 趋势图显示区域（matplotlib，2个子图：平均应力vs深度，标准差vs深度）
- 差分云图控制区：
- "被减数"层选择（QComboBox）
- "减数"层选择（QComboBox）
- "计算差分"按钮
- 差分范围显示标签

**任务3.3：实现差分云图窗口**

- 文件：`app/view/difference_window.py`
- 实现差分云图的完整显示逻辑：
- 使用发散型色标（蓝-白-红）
- 0值对应白色
- 显示差分统计信息
- 支持保存为图片

**任务3.4：集成趋势对比到主窗口（已完成）**

- 文件：`app/view/heatmap_view.py`
- 在"趋势对比"标签页中实例化`TrendPanel`
- 文件：`app/controller/heatmap_controller.py`
- 添加回调处理：
- `on_generate_trend_plots()` - 生成趋势折线图
- `on_calculate_difference()` - 计算差分并打开新窗口显示

### 阶段4：Epic 3 - 逐点梯度分析

**任务4.1：实现2D图点击交互**

- 文件：`app/view/heatmap_view.py`
- 在2D matplotlib图上添加：
- `mpl_connect('button_press_event', on_click_2d)` 事件处理
- 点击时在所有已加载数据层的相同坐标添加标记（Marker）
- 维护已选点位列表

**任务4.2：实现3D图点击交互**

- 文件：`app/view/heatmap_view.py`
- 在Plotly 3D图上添加：
- 使用Plotly的`clickData`事件
- 在所有Z层的相同XY坐标添加Scatter3d标记
- 与2D点位列表同步

**任务4.3：Model层添加梯度计算方法**

- 文件：`app/model/heatmap_model.py`
- 新增方法：
- `get_value_at_point(dataset_index, x, y)` - 插值获取指定坐标的应力值
- `calculate_gradients(point_list)` - 计算多个点的梯度数据
- `get_default_analysis_points()` - 返回预选点位：中心(0,0)和四个主轴边缘点
- 梯度公式：`(stress_next - stress_current) / (z_next - z_current)`

**任务4.4：创建梯度分析视图组件**

- 新建文件：`app/view/gradient_view.py`
- 创建`GradientPanel`类（QWidget）
- 包含：
- 点位列表（QListWidget）- 显示所有已选点的坐标
- "删除选中点"按钮
- "清除所有点"按钮
- "加载默认点位"按钮
- 梯度分析表（QTableWidget）：
- 列：点坐标(X,Y) | 0µm应力 | 500µm应力 | 1000µm应力 | ... | 梯度(0-500) | 梯度(500-1000) | ...
- "导出梯度表为CSV"按钮

**任务4.5：集成梯度分析到主窗口**

- 文件：`app/view/heatmap_view.py`
- 在"梯度分析"标签页中实例化`GradientPanel`
- 文件：`app/controller/heatmap_controller.py`
- 添加回调处理：
- `on_point_clicked(x, y)` - 添加分析点
- `on_remove_analysis_point(index)` - 删除点
- `on_load_default_points()` - 加载预设点
- `on_update_gradient_table()` - 刷新梯度表
- `on_export_gradient_csv()` - 导出梯度数据

### 阶段5：集成与优化

**任务5.1：数据加载时自动更新分析（已完成）**

- 文件：`app/controller/heatmap_controller.py`
- 在`on_model_changed('dataset_added')`中：
- 自动刷新统计表
- 更新趋势图数据层选项
- 更新差分云图的数据层选项

**任务5.2：添加工具提示(Tooltips)**

- 文件：各个视图文件
- 为所有新增的高级功能控件添加详细的工具提示
- 解释"差分"、"梯度"等专业概念

**任务5.3：性能验证与优化**

- 测试大数据集（5000点以上）的统计计算性能
- 确保差分计算在2秒内完成
- 确保UI交互流畅（点位选择无延迟）

**任务5.4：错误处理与边界情况**

- 数据层少于2个时禁用趋势图和差分功能
- 未选择分析点时禁用梯度导出
- 添加友好的错误提示消息

## 关键技术点

### 坐标归一化

- 不同数据集可能有不同的坐标范围
- 在点位选择时需要归一化到相对位置（如中心为0,0，半径为1）
- 在梯度计算时需要精确匹配坐标

### 差分云图色标

- 使用`LinearSegmentedColormap.from_list('diff', ['blue', 'white', 'red'])`
- 确保差分值=0时对应白色
- vmin和vmax需要对称（如-100到+100）

### 点位标记同步

- 维护全局点位列表：`[(x, y), ...]`
- 2D/3D/梯度表之间实时同步
- 使用观察者模式通知各组件更新

## 文件清单

### 新增文件

- `app/view/statistics_view.py` - 统计分析面板
- `app/view/trend_view.py` - 趋势对比面板
- `app/view/gradient_view.py` - 梯度分析面板
- `app/view/difference_window.py` - 差分云图窗口

### 修改文件

- `app/view/heatmap_view.py` - 添加标签页系统和点击交互
- `app/model/heatmap_model.py` - 添加分析计算方法
- `app/controller/heatmap_controller.py` - 添加分析功能回调

## 测试重点

1. **功能测试**

- 统计表数值准确性（与numpy手动计算对比）
- 直方图和KDE曲线正确性
- 差分云图数值和色标正确性
- 梯度计算公式验证

2. **交互测试**

- 2D图点击准确定位
- 3D图点击准确定位
- 点位在不同视图间同步显示
- 标签页切换流畅

3. **性能测试**

- 5000点数据集统计计算<2秒
- 差分计算<2秒
- 点击响应无延迟
- 切换标签页无卡顿

4. **边界测试**

- 单数据集时的功能限制
- 空数据时的错误处理
- 无效坐标点击的处理
- 差分两个相同数据集的结果