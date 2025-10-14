"""
统计分析控制器模块

协调统计模型和视图，处理统计分析相关的用户交互
"""

from typing import List, Tuple, Optional
import numpy as np
from matplotlib.figure import Figure
from PySide6.QtWidgets import QFileDialog, QMessageBox

from app.model.statistics_model import StatisticsModel
from app.view.statistics_view import StatisticsView


class StatisticsController:
    """统计分析控制器"""
    
    def __init__(self, model: StatisticsModel, view: StatisticsView):
        """初始化统计控制器
        
        Args:
            model: 统计模型
            view: 统计视图
        """
        self.model = model
        self.view = view
        self.current_dataset_index = 0
        self.current_outlier_method = 'iqr'
        
        # 绑定视图回调
        self.view.on_dataset_changed = self.on_dataset_changed
        self.view.on_outlier_method_changed = self.on_outlier_method_changed
        self.view.on_export_statistics = self.on_export_statistics
    
    def set_data_sets(self, data_sets: List[Tuple]):
        """设置数据集
        
        Args:
            data_sets: 数据集列表 [(data, z_depth, file_name), ...]
        """
        self.model.set_data_sets(data_sets)
        self.view.update_dataset_list(data_sets)
        
        # 如果有数据集，自动显示第一个
        if len(data_sets) > 0:
            self.update_statistics_display(0)
    
    def on_dataset_changed(self, index: int):
        """处理数据集选择变更
        
        Args:
            index: 数据集索引
        """
        self.current_dataset_index = index
        self.update_statistics_display(index)
    
    def on_outlier_method_changed(self, method: str):
        """处理异常值检测方法变更
        
        Args:
            method: 检测方法 ('iqr', 'zscore', 'isolation_forest')
        """
        self.current_outlier_method = method
        self.update_outlier_display(self.current_dataset_index)
    
    def update_statistics_display(self, dataset_index: int):
        """更新统计分析显示
        
        Args:
            dataset_index: 数据集索引
        """
        try:
            # 计算统计数据
            basic_stats = self.model.calculate_basic_statistics(dataset_index)
            distribution = self.model.calculate_distribution_analysis(dataset_index)
            outliers = self.model.detect_outliers(dataset_index, self.current_outlier_method)
            
            # 更新表格显示
            self.view.display_basic_statistics(basic_stats)
            self.view.display_distribution_analysis(distribution)
            self.view.display_outlier_detection(outliers)
            
            # 生成并显示图表
            self.generate_charts(dataset_index, basic_stats, distribution, outliers)
            
        except Exception as e:
            print(f"统计分析更新错误: {e}")
            QMessageBox.warning(self.view, "错误", f"统计分析失败: {str(e)}")
    
    def update_outlier_display(self, dataset_index: int):
        """更新异常值检测显示
        
        Args:
            dataset_index: 数据集索引
        """
        try:
            outliers = self.model.detect_outliers(dataset_index, self.current_outlier_method)
            self.view.display_outlier_detection(outliers)
            
            # 重新生成图表
            basic_stats = self.model.calculate_basic_statistics(dataset_index)
            distribution = self.model.calculate_distribution_analysis(dataset_index)
            self.generate_charts(dataset_index, basic_stats, distribution, outliers)
            
        except Exception as e:
            print(f"异常值检测更新错误: {e}")
    
    def generate_charts(self, dataset_index: int, basic_stats: dict, 
                       distribution: dict, outliers: dict):
        """生成统计图表
        
        Args:
            dataset_index: 数据集索引
            basic_stats: 基础统计数据
            distribution: 分布特征数据
            outliers: 异常值检测数据
        """
        self.view.clear_charts()
        
        if not basic_stats:
            return
        
        # 获取原始数据
        data, z_depth, file_name = self.model.data_sets[dataset_index]
        
        # 数据是DataFrame，需要访问'Value'列
        if 'Value' not in data.columns:
            return
        
        stress_values = data['Value'].values
        valid_stress = stress_values[~np.isnan(stress_values)]
        
        # 1. 直方图 + 核密度估计
        fig1 = self._create_histogram_chart(valid_stress, basic_stats, distribution)
        self.view.add_chart(fig1, "应力分布直方图与核密度估计")
        
        # 2. 箱线图
        fig2 = self._create_boxplot_chart(valid_stress, basic_stats, outliers)
        self.view.add_chart(fig2, "应力箱线图（异常值检测）")
        
        # 3. Q-Q图（正态性检验）
        fig3 = self._create_qq_plot(valid_stress)
        self.view.add_chart(fig3, "Q-Q图（正态性检验）")
        
        # 4. 累积分布图
        fig4 = self._create_cdf_plot(valid_stress, basic_stats)
        self.view.add_chart(fig4, "累积分布函数(CDF)")
    
    def _create_histogram_chart(self, stress_values: np.ndarray, 
                                basic_stats: dict, distribution: dict) -> Figure:
        """创建直方图+核密度估计图
        
        Args:
            stress_values: 应力值数组
            basic_stats: 基础统计数据
            distribution: 分布特征数据
            
        Returns:
            Figure: matplotlib图形对象
        """
        from scipy import stats
        
        fig = Figure(figsize=(8, 5), constrained_layout=True)
        ax = fig.add_subplot(111)
        
        # 绘制直方图
        n, bins, patches = ax.hist(stress_values, bins=50, density=True, 
                                   alpha=0.7, color='steelblue', edgecolor='black')
        
        # 绘制核密度估计
        density = stats.gaussian_kde(stress_values)
        xs = np.linspace(stress_values.min(), stress_values.max(), 200)
        ax.plot(xs, density(xs), 'r-', linewidth=2, label='核密度估计')
        
        # 绘制正态分布拟合
        mean = basic_stats['mean']
        std = basic_stats['std']
        xmin, xmax = ax.get_xlim()
        x = np.linspace(xmin, xmax, 100)
        p = stats.norm.pdf(x, mean, std)
        ax.plot(x, p, 'g--', linewidth=2, label='正态分布拟合')
        
        # 标注均值和中位数
        ax.axvline(mean, color='red', linestyle='--', linewidth=1.5, 
                  label=f'均值: {mean:.2f} MPa')
        ax.axvline(basic_stats['median'], color='orange', linestyle='--', 
                  linewidth=1.5, label=f'中位数: {basic_stats["median"]:.2f} MPa')
        
        ax.set_xlabel('应力 (MPa)', fontsize=11)
        ax.set_ylabel('概率密度', fontsize=11)
        ax.set_title('应力分布特征', fontsize=12, fontweight='bold')
        ax.legend(loc='best', fontsize=9)
        ax.grid(True, alpha=0.3)
        
        
        return fig
    
    def _create_boxplot_chart(self, stress_values: np.ndarray, 
                             basic_stats: dict, outliers: dict) -> Figure:
        """创建箱线图
        
        Args:
            stress_values: 应力值数组
            basic_stats: 基础统计数据
            outliers: 异常值检测数据
            
        Returns:
            Figure: matplotlib图形对象
        """
        fig = Figure(figsize=(8, 5), constrained_layout=True)
        ax = fig.add_subplot(111)
        
        # 绘制箱线图
        bp = ax.boxplot([stress_values], vert=True, patch_artist=True,
                        labels=['应力分布'])
        
        # 美化箱线图
        bp['boxes'][0].set_facecolor('lightblue')
        bp['boxes'][0].set_alpha(0.7)
        bp['medians'][0].set_color('red')
        bp['medians'][0].set_linewidth(2)
        
        # 标注关键统计量
        q25 = basic_stats['q25']
        q50 = basic_stats['q50']
        q75 = basic_stats['q75']
        
        ax.text(1.15, q25, f'Q1: {q25:.2f}', va='center', fontsize=9)
        ax.text(1.15, q50, f'Q2: {q50:.2f}', va='center', fontsize=9, 
               color='red', fontweight='bold')
        ax.text(1.15, q75, f'Q3: {q75:.2f}', va='center', fontsize=9)
        
        # 标注异常值信息
        outlier_count = outliers.get('outlier_count', 0)
        outlier_ratio = outliers.get('outlier_ratio', 0)
        ax.text(0.5, ax.get_ylim()[1] * 0.95, 
               f'异常值: {outlier_count}个 ({outlier_ratio:.2f}%)',
               ha='center', fontsize=10, bbox=dict(boxstyle='round', 
               facecolor='yellow', alpha=0.5))
        
        ax.set_ylabel('应力 (MPa)', fontsize=11)
        ax.set_title('应力分布箱线图', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        
        
        return fig
    
    def _create_qq_plot(self, stress_values: np.ndarray) -> Figure:
        """创建Q-Q图
        
        Args:
            stress_values: 应力值数组
            
        Returns:
            Figure: matplotlib图形对象
        """
        from scipy import stats
        
        fig = Figure(figsize=(8, 5), constrained_layout=True)
        ax = fig.add_subplot(111)
        
        # 生成Q-Q图数据
        stats.probplot(stress_values, dist="norm", plot=ax)
        
        ax.set_title('Q-Q图（正态性检验）', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        # 添加说明文本
        ax.text(0.05, 0.95, '数据点越接近红线，\n分布越接近正态分布',
               transform=ax.transAxes, va='top', fontsize=9,
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        
        return fig
    
    def _create_cdf_plot(self, stress_values: np.ndarray, basic_stats: dict) -> Figure:
        """创建累积分布函数图
        
        Args:
            stress_values: 应力值数组
            basic_stats: 基础统计数据
            
        Returns:
            Figure: matplotlib图形对象
        """
        fig = Figure(figsize=(8, 5), constrained_layout=True)
        ax = fig.add_subplot(111)
        
        # 排序数据
        sorted_data = np.sort(stress_values)
        yvals = np.arange(1, len(sorted_data) + 1) / len(sorted_data)
        
        # 绘制经验累积分布
        ax.plot(sorted_data, yvals, linewidth=2, label='经验CDF')
        
        # 标注关键分位数
        q25 = basic_stats['q25']
        q50 = basic_stats['q50']
        q75 = basic_stats['q75']
        
        ax.axvline(q25, color='green', linestyle='--', alpha=0.7, label=f'Q1: {q25:.2f}')
        ax.axvline(q50, color='orange', linestyle='--', alpha=0.7, label=f'Q2: {q50:.2f}')
        ax.axvline(q75, color='red', linestyle='--', alpha=0.7, label=f'Q3: {q75:.2f}')
        
        ax.set_xlabel('应力 (MPa)', fontsize=11)
        ax.set_ylabel('累积概率', fontsize=11)
        ax.set_title('累积分布函数', fontsize=12, fontweight='bold')
        ax.legend(loc='best', fontsize=9)
        ax.grid(True, alpha=0.3)
        
        
        return fig
    
    def on_export_statistics(self):
        """导出统计报告"""
        try:
            # 弹出文件保存对话框
            file_path, _ = QFileDialog.getSaveFileName(
                self.view, "导出统计报告", "", 
                "CSV文件 (*.csv);;文本文件 (*.txt);;所有文件 (*)"
            )
            
            if not file_path:
                return
            
            # 获取当前数据集的统计信息
            basic_stats = self.model.calculate_basic_statistics(self.current_dataset_index)
            distribution = self.model.calculate_distribution_analysis(self.current_dataset_index)
            outliers = self.model.detect_outliers(self.current_dataset_index, 
                                                  self.current_outlier_method)
            
            # 生成报告内容
            report_lines = []
            report_lines.append("=" * 60)
            report_lines.append("SiC晶圆应力分析工具 - 统计分析报告")
            report_lines.append("=" * 60)
            report_lines.append("")
            
            # 数据集信息
            report_lines.append(f"数据集: {basic_stats.get('file_name', 'Unknown')}")
            report_lines.append(f"Z轴深度: {basic_stats.get('z_depth', 0)} μm")
            report_lines.append("")
            
            # 基础统计
            report_lines.append("【描述性统计】")
            report_lines.append(f"样本数量: {basic_stats.get('count', 0)}")
            report_lines.append(f"平均值: {basic_stats.get('mean', 0):.4f} MPa")
            report_lines.append(f"中位数: {basic_stats.get('median', 0):.4f} MPa")
            report_lines.append(f"标准差: {basic_stats.get('std', 0):.4f} MPa")
            report_lines.append(f"变异系数: {basic_stats.get('cv', 0):.2f}%")
            report_lines.append(f"最小值: {basic_stats.get('min', 0):.4f} MPa")
            report_lines.append(f"最大值: {basic_stats.get('max', 0):.4f} MPa")
            report_lines.append(f"极差: {basic_stats.get('range', 0):.4f} MPa")
            report_lines.append("")
            
            # 分布特征
            report_lines.append("【分布特征】")
            report_lines.append(f"偏度: {basic_stats.get('skewness', 0):.4f}")
            report_lines.append(f"峰度: {basic_stats.get('kurtosis', 0):.4f}")
            report_lines.append(f"Shapiro-Wilk检验 p值: {distribution.get('shapiro_p_value', 0):.6f}")
            report_lines.append(f"正态性(Shapiro): {'是' if distribution.get('is_normal_shapiro') else '否'}")
            report_lines.append("")
            
            # 异常值检测
            report_lines.append("【异常值检测】")
            report_lines.append(f"检测方法: {outliers.get('method', 'Unknown')}")
            report_lines.append(f"异常值数量: {outliers.get('outlier_count', 0)}")
            report_lines.append(f"异常值比例: {outliers.get('outlier_ratio', 0):.2f}%")
            report_lines.append("")
            
            report_lines.append("=" * 60)
            
            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report_lines))
            
            QMessageBox.information(self.view, "成功", f"统计报告已导出到:\n{file_path}")
            
        except Exception as e:
            print(f"导出统计报告错误: {e}")
            QMessageBox.warning(self.view, "错误", f"导出失败: {str(e)}")

