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
from app.view.difference_window import DifferenceWindow
from app.model.heatmap_model import HeatmapModel


class TrendController:
    """趋势对比控制器"""
    
    def __init__(self, model: TrendModel, view: TrendView, *, heatmap_model: HeatmapModel | None = None, parent=None):
        """初始化趋势控制器
        
        Args:
            model: 趋势模型
            view: 趋势视图
        """
        self.model = model
        self.view = view
        self._heatmap_model = heatmap_model  # 依赖倒置：仅依赖抽象接口所需部分
        self._parent = parent
        
        # 绑定视图回调
        self.view.on_compare_layers = self.on_compare_layers
        self.view.on_refresh_trend = self.on_refresh_trend
        self.view.on_calculate_difference = self.on_calculate_difference
    
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

    def on_calculate_difference(self, minuend_index: int, subtrahend_index: int):
        """计算两层差分并在新窗口显示"""
        try:
            if self._heatmap_model is None:
                QMessageBox.warning(self.view, "错误", "模型未就绪，无法计算差分")
                return
            xi, yi, diff = self._heatmap_model.calculate_difference_map(minuend_index, subtrahend_index)
            # 打开差分窗口
            win = DifferenceWindow(
                parent=self.view,
                xi_grid=xi,
                yi_grid=yi,
                diff_values=diff,
                title="差分云图 (被减数 - 减数)"
            )
            win.show()
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self.view, "错误", f"计算差分失败: {str(e)}")
    
    def _generate_trend_charts(self, trend_data: dict):
        """生成趋势图表
        
        Args:
            trend_data: 趋势数据
        """
        # 1. Z轴趋势图（均值、中位数）
        fig1 = self._create_z_trend_chart(trend_data)
        info1 = (
            "展示不同Z深度的应力均值与中位数的变化趋势，"
            "用于观察整体水平随深度的上升/下降及均值-中位数差异。"
        )
        summary1 = self._build_z_trend_summary(trend_data)
        self.view.add_chart(fig1, "Z轴应力趋势分析", info1, summary1)
        
        # 2. 标准差趋势图
        fig2 = self._create_std_trend_chart(trend_data)
        info2 = (
            "标准差反映离散程度；变异系数(标准差/均值)用于跨层对比相对波动，"
            "两轴合并便于同时评估绝对波动与相对波动。"
        )
        summary2 = self._build_std_trend_summary(trend_data)
        self.view.add_chart(fig2, "Z轴标准差趋势", info2, summary2)
        
        # 3. 极值趋势图
        fig3 = self._create_minmax_trend_chart(trend_data)
        info3 = (
            "显示各层最小/最大值与均值，灰色区域为极差；"
            "用于识别是否存在异常层或极端值随深度的系统性变化。"
        )
        summary3 = self._build_minmax_summary(trend_data)
        self.view.add_chart(fig3, "Z轴极值趋势", info3, summary3)
        
        # 4. 梯度分析图
        gradient_data = self.model.calculate_gradient()
        if gradient_data:
            fig4 = self._create_gradient_chart(gradient_data)
            info4 = (
                "对均值-深度进行线性拟合得到斜率与R²；斜率表示梯度强弱，"
                "R²表示线性解释度，用于判断是否存在线性梯度与其显著性。"
            )
            summary4 = self._build_gradient_summary(gradient_data)
            self.view.add_chart(fig4, "Z轴应力梯度分析", info4, summary4)
    
    def _create_z_trend_chart(self, trend_data: dict) -> Figure:
        """创建Z轴趋势图
        
        Args:
            trend_data: 趋势数据
            
        Returns:
            Figure: matplotlib图形对象
        """
        fig = Figure(figsize=(10, 6), constrained_layout=True)
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
        
        
        return fig
    
    def _create_std_trend_chart(self, trend_data: dict) -> Figure:
        """创建标准差趋势图
        
        Args:
            trend_data: 趋势数据
            
        Returns:
            Figure: matplotlib图形对象
        """
        fig = Figure(figsize=(10, 6), constrained_layout=True)
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
        
        
        return fig
    
    def _create_minmax_trend_chart(self, trend_data: dict) -> Figure:
        """创建极值趋势图
        
        Args:
            trend_data: 趋势数据
            
        Returns:
            Figure: matplotlib图形对象
        """
        fig = Figure(figsize=(10, 6), constrained_layout=True)
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
        
        
        return fig
    
    def _create_gradient_chart(self, gradient_data: dict) -> Figure:
        """创建梯度分析图
        
        Args:
            gradient_data: 梯度数据
            
        Returns:
            Figure: matplotlib图形对象
        """
        fig = Figure(figsize=(10, 6), constrained_layout=True)
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
        
        
        return fig

    # --------- 结论生成（趋势） ---------
    def _build_z_trend_summary(self, trend_data: dict) -> str:
        try:
            z = trend_data['z_depths']
            means = trend_data['mean_values']
            medians = trend_data['median_values']
            if len(z) >= 2:
                # 简单线性拟合评估趋势方向
                import numpy as np
                slope = float(np.polyfit(z, means, 1)[0])
            else:
                slope = 0.0
            diff_mean_median = float(np.mean(np.array(means) - np.array(medians)))
            direction = "上升" if slope>0 else ("下降" if slope<0 else "基本平稳")
            bias = "均值高于中位数（右偏）" if diff_mean_median>0 else ("均值低于中位数（左偏）" if diff_mean_median<0 else "均值≈中位数（对称）")
            return (
                f"结论：均值随深度{direction}，均值-中位数平均差 {diff_mean_median:.2f} MPa（{bias}）。"
                f"若方向明显且需求敏感，建议结合梯度图与R²综合判断。"
            )
        except Exception:
            return "结论生成失败：输入数据异常。"

    def _build_std_trend_summary(self, trend_data: dict) -> str:
        try:
            import numpy as np
            z = trend_data['z_depths']
            stds = trend_data['std_values']
            means = trend_data['mean_values']
            cvs = [(s/m*100) if m!=0 else 0 for s,m in zip(stds,means)]
            cv_mean = float(np.mean(cvs)) if cvs else 0.0
            # 判断离散是否随深度增大
            slope = float(np.polyfit(z, stds, 1)[0]) if len(z)>=2 else 0.0
            direction = "增大" if slope>0 else ("减小" if slope<0 else "基本稳定")
            level = "低波动" if cv_mean<10 else ("中等波动" if cv_mean<20 else "高波动")
            return (
                f"结论：标准差随深度{direction}；平均变异系数约 {cv_mean:.1f}%（{level}）。"
                f"如需控制制程波动，建议关注CV较高的层。"
            )
        except Exception:
            return "结论生成失败：输入数据异常。"

    def _build_minmax_summary(self, trend_data: dict) -> str:
        try:
            import numpy as np
            mins = trend_data['min_values']
            maxs = trend_data['max_values']
            means = trend_data['mean_values']
            ranges = np.array(maxs) - np.array(mins)
            range_mean = float(np.mean(ranges))
            mean_band = f"均值带宽约 {range_mean:.2f} MPa"
            risk = "极差较大，可能存在局部缺陷或应力集中" if range_mean>abs(np.mean(means))*0.8 else "极差适中"
            return f"结论：{mean_band}；{risk}。"
        except Exception:
            return "结论生成失败：输入数据异常。"

    def _build_gradient_summary(self, gradient_data: dict) -> str:
        """根据拟合结果生成专业结论文本（用于图表下方）。
        
        规则：
        - 梯度强度按 |slope| 分类：<0.01 极弱；0.01~0.05 中等；>=0.05 明显。
        - 线性度按 R²：<0.3 较差；0.3~0.6 一般；>=0.6 良好。
        - 显著性按 p 值：<0.05 显著；>=0.05 不显著。
        - 同时报告全深度范围的趋势幅度 Δ= slope * (maxZ-minZ)。
        """
        try:
            slope = float(gradient_data.get('slope', 0.0))
            r2 = float(gradient_data.get('r_squared', 0.0))
            p_val = float(gradient_data.get('p_value', 1.0))
            std_err = float(gradient_data.get('std_error', 0.0))
            z_depths = gradient_data.get('z_depths', []) or []
            if len(z_depths) >= 2:
                z_min, z_max = float(min(z_depths)), float(max(z_depths))
                delta = slope * (z_max - z_min)
            else:
                z_min, z_max, delta = 0.0, 0.0, 0.0
            # 强度等级
            abs_slope = abs(slope)
            if abs_slope < 0.01:
                slope_level = "极弱"
            elif abs_slope < 0.05:
                slope_level = "中等"
            else:
                slope_level = "明显"
            # 线性度等级
            if r2 < 0.3:
                linear_level = "较差"
            elif r2 < 0.6:
                linear_level = "一般"
            else:
                linear_level = "良好"
            # 显著性
            sig_text = "显著" if p_val < 0.05 else "不显著"
            direction = "随深度上升" if slope > 0 else ("随深度下降" if slope < 0 else "与深度无关")
            advice_parts = []
            if p_val < 0.05 and abs_slope >= 0.05 and r2 >= 0.6:
                advice_parts.append("存在显著且线性良好的垂向梯度，建议复核工艺/应力释放步骤")
            if r2 < 0.3:
                advice_parts.append("线性解释度较低，建议尝试二次/分段拟合或增加采样层数")
            if p_val >= 0.05 and abs_slope < 0.01:
                advice_parts.append("整体应力沿Z轴基本稳定，可作为厚度方向均匀性参考")
            advice = "；".join(advice_parts) if advice_parts else ""
            # 组织文本
            lines = [
                f"结论：应力均值{direction}（斜率 {slope:.4f} MPa/μm，{slope_level}），",
                f"线性度 R²={r2:.3f}（{linear_level}），显著性 p={p_val:.4f}（{sig_text}）。",
                f"在 {z_min:.0f}~{z_max:.0f} μm 范围内，预测总体变化幅度约 Δ={delta:.2f} MPa。",
            ]
            if std_err and std_err > 0:
                lines.append(f"斜率标准误 {std_err:.4f} MPa/μm（拟合不确定性参考）。")
            if advice:
                lines.append(f"建议：{advice}。")
            return "".join(lines)
        except Exception:
            return "结论生成失败：输入数据异常。"
    
    def _generate_multi_layer_comparison_charts(self, indices: List[int], comparison: dict):
        """生成多层对比图表
        
        Args:
            indices: 层索引列表
            comparison: 多层对比数据
        """
        # 1. 多层统计指标对比图（柱状图）
        fig1 = self._create_multi_layer_bar_chart(comparison)
        self.view.add_chart_below_selector(
            fig1, f"多层统计指标对比 ({len(indices)}层)",
            "分别对比各层的均值、标准差、变异系数与极值范围，定位差异显著的层。"
        )
        
        # 2. 多层分布对比（箱线图）
        fig2 = self._create_multi_layer_boxplot(indices, comparison)
        self.view.add_chart_below_selector(
            fig2, "多层应力分布对比",
            "多层箱线图并列显示，观察多层的分布、离群点与中位数差异。"
        )
        
        # 3. 多层分布对比（叠加直方图）
        if len(indices) <= 5:  # 只在层数不太多时显示
            fig3 = self._create_multi_layer_histogram(indices, comparison)
            self.view.add_chart_below_selector(
                fig3, "多层应力分布直方图",
                "各层直方图以不同颜色叠加，便于比较整体分布形状与位置差异。"
            )
        
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
        fig = Figure(figsize=(12, 7), constrained_layout=True)
        
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
        
        
        return fig
    
    def _create_multi_layer_boxplot(self, indices: List[int], comparison: dict) -> Figure:
        """创建多层箱线图
        
        Args:
            indices: 层索引列表
            comparison: 多层对比数据
            
        Returns:
            Figure: matplotlib图形对象
        """
        fig = Figure(figsize=(12, 6), constrained_layout=True)
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
        
        
        return fig
    
    def _create_multi_layer_histogram(self, indices: List[int], comparison: dict) -> Figure:
        """创建多层分布直方图
        
        Args:
            indices: 层索引列表
            comparison: 多层对比数据
            
        Returns:
            Figure: matplotlib图形对象
        """
        fig = Figure(figsize=(12, 6), constrained_layout=True)
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
        self.view.add_chart_below_selector(
            fig1, "应力分布对比",
            "两层分布直方图叠加，虚线为各自均值；用于直接比较总体分布与均值差异。"
        )
        
        # 2. 箱线图对比
        fig2 = self._create_boxplot_comparison(valid_stress1, valid_stress2, comparison)
        self.view.add_chart_below_selector(
            fig2, "统计特征对比",
            "两层箱线图并列展示Q1/Q2/Q3与异常值，快速比较离散程度与集中趋势。"
        )
    
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
        fig = Figure(figsize=(10, 6), constrained_layout=True)
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
        fig = Figure(figsize=(10, 6), constrained_layout=True)
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
        
        
        return fig

