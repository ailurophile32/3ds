"""
趋势对比控制器模块

协调趋势模型和视图，处理趋势对比相关的用户交互
"""

from typing import List, Tuple
import numpy as np
from matplotlib.figure import Figure
from PySide6.QtWidgets import QMessageBox

from app.model.trend_model import TrendModel
from app.view.trend_view import TrendView


class TrendController:
    """趋势对比控制器"""
    
    def __init__(self, model: TrendModel, view: TrendView):
        """初始化趋势控制器
        
        Args:
            model: 趋势模型
            view: 趋势视图
        """
        self.model = model
        self.view = view
        
        # 绑定视图回调
        self.view.on_compare_layers = self.on_compare_layers
        self.view.on_refresh_trend = self.on_refresh_trend
    
    def set_data_sets(self, data_sets: List[Tuple]):
        """设置数据集
        
        Args:
            data_sets: 数据集列表 [(data, z_depth, file_name), ...]
        """
        self.model.set_data_sets(data_sets)
        self.view.update_layer_list(data_sets)
        
        # 自动刷新趋势分析
        if len(data_sets) > 0:
            self.refresh_trend_analysis()
    
    def on_compare_layers(self, indices: List[int]):
        """处理层对比请求（支持多层）
        
        Args:
            indices: 层索引列表
        """
        try:
            # 只清理选择栏下方的对比结果，保留上方趋势图
            self.view.clear_comparison_results()
            
            if len(indices) == 2:
                # 双层对比：使用原有逻辑
                comparison = self.model.calculate_layer_comparison(indices[0], indices[1])
                
                if not comparison:
                    QMessageBox.warning(self.view, "错误", "无法计算层间对比数据")
                    return
                
                # 显示对比表格（选择栏下方）
                self.view.add_comparison_table(comparison)
                
                # 生成对比图表
                self._generate_comparison_charts(indices[0], indices[1], comparison)
                
            else:
                # 多层对比：使用新逻辑
                comparison = self.model.calculate_multi_layer_comparison(indices)
                
                if not comparison:
                    QMessageBox.warning(self.view, "错误", "无法计算多层对比数据")
                    return
                
                # 显示对比表格（选择栏下方）
                self.view.add_comparison_table(comparison)
                
                # 生成多层对比图表
                self._generate_multi_layer_comparison_charts(indices, comparison)
            
        except Exception as e:
            print(f"层对比错误: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self.view, "错误", f"层对比失败: {str(e)}")
    
    def on_refresh_trend(self):
        """刷新趋势分析"""
        self.refresh_trend_analysis()
    
    def refresh_trend_analysis(self):
        """刷新整体趋势分析"""
        try:
            self.view.clear_content()
            
            # 获取趋势数据
            trend_data = self.model.get_z_trend_data()
            
            if not trend_data or trend_data.get('layer_count', 0) == 0:
                return
            
            # 生成趋势图表
            self._generate_trend_charts(trend_data)
            
            # 检测异常层
            anomalies = self.model.detect_anomalous_layers(threshold=2.0)
            if anomalies:
                self.view.add_anomaly_table(anomalies)
            
        except Exception as e:
            print(f"趋势分析错误: {e}")
            QMessageBox.warning(self.view, "错误", f"趋势分析失败: {str(e)}")
    
    def _generate_trend_charts(self, trend_data: dict):
        """生成趋势图表
        
        Args:
            trend_data: 趋势数据
        """
        # 1. Z轴趋势图（均值、中位数）
        fig1 = self._create_z_trend_chart(trend_data)
        self.view.add_chart(fig1, "Z轴应力趋势分析")
        
        # 2. 标准差趋势图
        fig2 = self._create_std_trend_chart(trend_data)
        self.view.add_chart(fig2, "Z轴标准差趋势")
        
        # 3. 极值趋势图
        fig3 = self._create_minmax_trend_chart(trend_data)
        self.view.add_chart(fig3, "Z轴极值趋势")
        
        # 4. 梯度分析图
        gradient_data = self.model.calculate_gradient()
        if gradient_data:
            fig4 = self._create_gradient_chart(gradient_data)
            self.view.add_chart(fig4, "Z轴应力梯度分析")
    
    def _create_z_trend_chart(self, trend_data: dict) -> Figure:
        """创建Z轴趋势图
        
        Args:
            trend_data: 趋势数据
            
        Returns:
            Figure: matplotlib图形对象
        """
        fig = Figure(figsize=(10, 6))
        ax = fig.add_subplot(111)
        
        z_depths = trend_data['z_depths']
        mean_values = trend_data['mean_values']
        median_values = trend_data['median_values']
        
        # 绘制均值和中位数
        ax.plot(z_depths, mean_values, 'o-', linewidth=2, markersize=8, 
               label='均值', color='steelblue')
        ax.plot(z_depths, median_values, 's--', linewidth=2, markersize=6, 
               label='中位数', color='orange', alpha=0.7)
        
        # 填充区域
        ax.fill_between(z_depths, mean_values, median_values, alpha=0.2, color='gray')
        
        ax.set_xlabel('Z轴深度 (μm)', fontsize=11)
        ax.set_ylabel('应力 (MPa)', fontsize=11)
        ax.set_title('应力沿Z轴的变化趋势', fontsize=12, fontweight='bold')
        ax.legend(loc='best', fontsize=10)
        ax.grid(True, alpha=0.3)
        
        fig.tight_layout()
        return fig
    
    def _create_std_trend_chart(self, trend_data: dict) -> Figure:
        """创建标准差趋势图
        
        Args:
            trend_data: 趋势数据
            
        Returns:
            Figure: matplotlib图形对象
        """
        fig = Figure(figsize=(10, 6))
        ax = fig.add_subplot(111)
        
        z_depths = trend_data['z_depths']
        std_values = trend_data['std_values']
        mean_values = trend_data['mean_values']
        
        # 绘制标准差
        ax.plot(z_depths, std_values, 'o-', linewidth=2, markersize=8, 
               color='crimson', label='标准差')
        
        # 计算变异系数
        cv_values = [(std/mean*100) if mean != 0 else 0 
                    for std, mean in zip(std_values, mean_values)]
        
        # 创建第二个Y轴显示变异系数
        ax2 = ax.twinx()
        ax2.plot(z_depths, cv_values, 's--', linewidth=2, markersize=6, 
                color='purple', alpha=0.6, label='变异系数')
        
        ax.set_xlabel('Z轴深度 (μm)', fontsize=11)
        ax.set_ylabel('标准差 (MPa)', fontsize=11, color='crimson')
        ax2.set_ylabel('变异系数 (%)', fontsize=11, color='purple')
        ax.set_title('应力离散程度沿Z轴的变化', fontsize=12, fontweight='bold')
        
        # 合并图例
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='best', fontsize=10)
        
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='y', labelcolor='crimson')
        ax2.tick_params(axis='y', labelcolor='purple')
        
        fig.tight_layout()
        return fig
    
    def _create_minmax_trend_chart(self, trend_data: dict) -> Figure:
        """创建极值趋势图
        
        Args:
            trend_data: 趋势数据
            
        Returns:
            Figure: matplotlib图形对象
        """
        fig = Figure(figsize=(10, 6))
        ax = fig.add_subplot(111)
        
        z_depths = trend_data['z_depths']
        min_values = trend_data['min_values']
        max_values = trend_data['max_values']
        mean_values = trend_data['mean_values']
        
        # 绘制极值和均值
        ax.plot(z_depths, max_values, '^-', linewidth=2, markersize=8, 
               label='最大值', color='red')
        ax.plot(z_depths, mean_values, 'o-', linewidth=2, markersize=6, 
               label='均值', color='green')
        ax.plot(z_depths, min_values, 'v-', linewidth=2, markersize=8, 
               label='最小值', color='blue')
        
        # 填充极值区域
        ax.fill_between(z_depths, min_values, max_values, alpha=0.15, color='gray')
        
        ax.set_xlabel('Z轴深度 (μm)', fontsize=11)
        ax.set_ylabel('应力 (MPa)', fontsize=11)
        ax.set_title('应力极值沿Z轴的变化', fontsize=12, fontweight='bold')
        ax.legend(loc='best', fontsize=10)
        ax.grid(True, alpha=0.3)
        
        fig.tight_layout()
        return fig
    
    def _create_gradient_chart(self, gradient_data: dict) -> Figure:
        """创建梯度分析图
        
        Args:
            gradient_data: 梯度数据
            
        Returns:
            Figure: matplotlib图形对象
        """
        fig = Figure(figsize=(10, 6))
        ax = fig.add_subplot(111)
        
        z_depths = gradient_data['z_depths']
        mean_values = gradient_data['mean_values']
        gradients = gradient_data['gradients']
        slope = gradient_data['slope']
        intercept = gradient_data['intercept']
        r_squared = gradient_data['r_squared']
        
        # 绘制实际值和线性拟合
        ax.plot(z_depths, mean_values, 'o', markersize=8, 
               label='实际均值', color='steelblue')
        
        # 绘制拟合线
        fit_line = [slope * z + intercept for z in z_depths]
        ax.plot(z_depths, fit_line, '--', linewidth=2, 
               label=f'线性拟合 (R²={r_squared:.3f})', color='red')
        
        # 添加斜率信息
        slope_text = f'斜率: {slope:.4f} MPa/μm'
        ax.text(0.05, 0.95, slope_text, transform=ax.transAxes, 
               fontsize=10, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        ax.set_xlabel('Z轴深度 (μm)', fontsize=11)
        ax.set_ylabel('应力均值 (MPa)', fontsize=11)
        ax.set_title('应力梯度线性拟合', fontsize=12, fontweight='bold')
        ax.legend(loc='best', fontsize=10)
        ax.grid(True, alpha=0.3)
        
        fig.tight_layout()
        return fig
    
    def _generate_multi_layer_comparison_charts(self, indices: List[int], comparison: dict):
        """生成多层对比图表
        
        Args:
            indices: 层索引列表
            comparison: 多层对比数据
        """
        # 1. 多层统计指标对比图（柱状图）
        fig1 = self._create_multi_layer_bar_chart(comparison)
        self.view.add_chart_below_selector(fig1, f"多层统计指标对比 ({len(indices)}层)")
        
        # 2. 多层分布对比（箱线图）
        fig2 = self._create_multi_layer_boxplot(indices, comparison)
        self.view.add_chart_below_selector(fig2, "多层应力分布对比")
        
        # 3. 多层分布对比（叠加直方图）
        if len(indices) <= 5:  # 只在层数不太多时显示
            fig3 = self._create_multi_layer_histogram(indices, comparison)
            self.view.add_chart_below_selector(fig3, "多层应力分布直方图")
        
        # 4. ANOVA分析结果表格（如果有）
        if comparison.get('anova_significant', False):
            self._show_anova_results(comparison)
    
    def _create_multi_layer_bar_chart(self, comparison: dict) -> Figure:
        """创建多层柱状对比图
        
        Args:
            comparison: 多层对比数据
            
        Returns:
            Figure: matplotlib图形对象
        """
        fig = Figure(figsize=(12, 7))
        
        layers_stats = comparison['layers_stats']
        layer_names = [f"{s['file_name'][:15]}..." if len(s['file_name']) > 15 
                       else s['file_name'] for s in layers_stats]
        
        # 创建2x2子图
        axes = [fig.add_subplot(2, 2, i+1) for i in range(4)]
        
        # 1. 均值对比
        means = [s['mean'] for s in layers_stats]
        axes[0].bar(range(len(means)), means, color='steelblue', alpha=0.7)
        axes[0].set_title('均值对比', fontweight='bold')
        axes[0].set_ylabel('应力 (MPa)')
        axes[0].set_xticks(range(len(layer_names)))
        axes[0].set_xticklabels(layer_names, rotation=45, ha='right')
        axes[0].grid(True, alpha=0.3, axis='y')
        
        # 2. 标准差对比
        stds = [s['std'] for s in layers_stats]
        axes[1].bar(range(len(stds)), stds, color='coral', alpha=0.7)
        axes[1].set_title('标准差对比', fontweight='bold')
        axes[1].set_ylabel('标准差 (MPa)')
        axes[1].set_xticks(range(len(layer_names)))
        axes[1].set_xticklabels(layer_names, rotation=45, ha='right')
        axes[1].grid(True, alpha=0.3, axis='y')
        
        # 3. 变异系数对比
        cvs = [s['cv'] for s in layers_stats]
        axes[2].bar(range(len(cvs)), cvs, color='mediumseagreen', alpha=0.7)
        axes[2].set_title('变异系数对比', fontweight='bold')
        axes[2].set_ylabel('变异系数 (%)')
        axes[2].set_xticks(range(len(layer_names)))
        axes[2].set_xticklabels(layer_names, rotation=45, ha='right')
        axes[2].grid(True, alpha=0.3, axis='y')
        
        # 4. 极值范围对比
        ranges = [s['max'] - s['min'] for s in layers_stats]
        axes[3].bar(range(len(ranges)), ranges, color='orchid', alpha=0.7)
        axes[3].set_title('极值范围对比', fontweight='bold')
        axes[3].set_ylabel('极值范围 (MPa)')
        axes[3].set_xticks(range(len(layer_names)))
        axes[3].set_xticklabels(layer_names, rotation=45, ha='right')
        axes[3].grid(True, alpha=0.3, axis='y')
        
        fig.tight_layout()
        return fig
    
    def _create_multi_layer_boxplot(self, indices: List[int], comparison: dict) -> Figure:
        """创建多层箱线图
        
        Args:
            indices: 层索引列表
            comparison: 多层对比数据
            
        Returns:
            Figure: matplotlib图形对象
        """
        fig = Figure(figsize=(12, 6))
        ax = fig.add_subplot(111)
        
        # 提取各层数据
        data_list = []
        labels = []
        for idx in indices:
            data, _, file_name = self.model.data_sets[idx]
            if 'Value' in data.columns:
                stress = data['Value'].values
                valid_stress = stress[~np.isnan(stress)]
                data_list.append(valid_stress)
                # 缩短标签名
                short_name = file_name[:20] + '...' if len(file_name) > 20 else file_name
                labels.append(short_name)
        
        # 绘制箱线图
        bp = ax.boxplot(data_list, labels=labels, patch_artist=True)
        
        # 美化箱线图
        colors = ['lightblue', 'lightcoral', 'lightgreen', 'lightyellow', 'lightpink', 'lightgray']
        for patch, color in zip(bp['boxes'], colors * (len(data_list) // len(colors) + 1)):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        
        # 添加ANOVA显著性标注
        if comparison.get('anova_significant', False):
            y_max = max([max(d) for d in data_list])
            ax.text(len(data_list)/2, y_max * 1.05, 
                   f'ANOVA: F={comparison["anova_f_statistic"]:.2f}, p={comparison["anova_p_value"]:.4f} ***',
                   ha='center', fontsize=10, color='red', fontweight='bold',
                   bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.3))
        
        ax.set_ylabel('应力 (MPa)', fontsize=11)
        ax.set_title('多层应力分布箱线图', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        # 旋转X轴标签
        for label in ax.get_xticklabels():
            label.set_rotation(45)
            label.set_ha('right')
        
        fig.tight_layout()
        return fig
    
    def _create_multi_layer_histogram(self, indices: List[int], comparison: dict) -> Figure:
        """创建多层分布直方图
        
        Args:
            indices: 层索引列表
            comparison: 多层对比数据
            
        Returns:
            Figure: matplotlib图形对象
        """
        fig = Figure(figsize=(12, 6))
        ax = fig.add_subplot(111)
        
        colors = ['steelblue', 'orange', 'green', 'red', 'purple']
        
        for i, idx in enumerate(indices):
            data, z_depth, file_name = self.model.data_sets[idx]
            if 'Value' in data.columns:
                stress = data['Value'].values
                valid_stress = stress[~np.isnan(stress)]
                
                # 缩短标签
                short_name = file_name[:15] + '...' if len(file_name) > 15 else file_name
                
                ax.hist(valid_stress, bins=30, alpha=0.5, 
                       label=f"{short_name} (Z={z_depth}μm)",
                       color=colors[i % len(colors)], density=True)
        
        ax.set_xlabel('应力 (MPa)', fontsize=11)
        ax.set_ylabel('概率密度', fontsize=11)
        ax.set_title('多层应力分布叠加直方图', fontsize=12, fontweight='bold')
        ax.legend(loc='best', fontsize=9)
        ax.grid(True, alpha=0.3)
        
        fig.tight_layout()
        return fig
    
    def _show_anova_results(self, comparison: dict):
        """显示ANOVA分析结果
        
        Args:
            comparison: 多层对比数据
        """
        # 可以在这里添加一个专门的ANOVA结果表格
        # 暂时先跳过，已经在箱线图上标注了
        pass
    
    def _generate_comparison_charts(self, index1: int, index2: int, comparison: dict):
        """生成层对比图表
        
        Args:
            index1: 第一层索引
            index2: 第二层索引
            comparison: 对比数据
        """
        # 获取两层的原始数据
        data1, _, _ = self.model.data_sets[index1]
        data2, _, _ = self.model.data_sets[index2]
        
        if 'Value' not in data1.columns or 'Value' not in data2.columns:
            return
        
        stress1 = data1['Value'].values
        stress2 = data2['Value'].values
        
        valid_stress1 = stress1[~np.isnan(stress1)]
        valid_stress2 = stress2[~np.isnan(stress2)]
        
        # 1. 分布对比直方图
        fig1 = self._create_distribution_comparison(valid_stress1, valid_stress2, comparison)
        self.view.add_chart_below_selector(fig1, "应力分布对比")
        
        # 2. 箱线图对比
        fig2 = self._create_boxplot_comparison(valid_stress1, valid_stress2, comparison)
        self.view.add_chart_below_selector(fig2, "统计特征对比")
    
    def _create_distribution_comparison(self, stress1: np.ndarray, 
                                       stress2: np.ndarray, comparison: dict) -> Figure:
        """创建分布对比图
        
        Args:
            stress1: 第一层应力值
            stress2: 第二层应力值
            comparison: 对比数据
            
        Returns:
            Figure: matplotlib图形对象
        """
        fig = Figure(figsize=(10, 6))
        ax = fig.add_subplot(111)
        
        # 绘制直方图
        ax.hist(stress1, bins=30, alpha=0.6, label=comparison['layer1_name'], 
               color='steelblue', density=True)
        ax.hist(stress2, bins=30, alpha=0.6, label=comparison['layer2_name'], 
               color='orange', density=True)
        
        # 标注均值
        ax.axvline(comparison['layer1_mean'], color='steelblue', 
                  linestyle='--', linewidth=2, 
                  label=f"均值1: {comparison['layer1_mean']:.2f}")
        ax.axvline(comparison['layer2_mean'], color='orange', 
                  linestyle='--', linewidth=2, 
                  label=f"均值2: {comparison['layer2_mean']:.2f}")
        
        ax.set_xlabel('应力 (MPa)', fontsize=11)
        ax.set_ylabel('概率密度', fontsize=11)
        ax.set_title('两层应力分布对比', fontsize=12, fontweight='bold')
        ax.legend(loc='best', fontsize=9)
        ax.grid(True, alpha=0.3)
        
        fig.tight_layout()
        return fig
    
    def _create_boxplot_comparison(self, stress1: np.ndarray, 
                                   stress2: np.ndarray, comparison: dict) -> Figure:
        """创建箱线图对比
        
        Args:
            stress1: 第一层应力值
            stress2: 第二层应力值
            comparison: 对比数据
            
        Returns:
            Figure: matplotlib图形对象
        """
        fig = Figure(figsize=(10, 6))
        ax = fig.add_subplot(111)
        
        # 绘制箱线图
        bp = ax.boxplot([stress1, stress2], 
                        labels=[comparison['layer1_name'], comparison['layer2_name']],
                        patch_artist=True)
        
        # 美化箱线图
        colors = ['lightblue', 'lightcoral']
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        
        # 标注显著性
        if comparison['significant']:
            y_max = max(np.max(stress1), np.max(stress2))
            ax.text(1.5, y_max * 1.05, f'p={comparison["p_value"]:.4f} *', 
                   ha='center', fontsize=10, color='red', fontweight='bold')
        
        ax.set_ylabel('应力 (MPa)', fontsize=11)
        ax.set_title('两层应力统计特征对比', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        
        fig.tight_layout()
        return fig

