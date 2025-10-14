"""
统计分析控制器模块

协调统计模型和视图，处理统计分析相关的用户交互
"""

from typing import List, Tuple, Optional
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_pdf import PdfPages
from PySide6.QtWidgets import QFileDialog, QMessageBox
import io
from PIL import Image

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
        
        # 外部上下文（由热力图控制器注入）
        self._heatmap_model = None
        self._trend_controller = None
        self._difference_controller = None

    def set_external_context(self, *, heatmap_model=None, trend_controller=None, difference_controller=None):
        """注入外部上下文，便于生成综合PDF报告。
        
        Args:
            heatmap_model: 提供2D/3D图的模型
            trend_controller: 生成趋势图表的方法提供者
            difference_controller: 生成多层对比/差分图表的方法提供者
        """
        self._heatmap_model = heatmap_model
        self._trend_controller = trend_controller
        self._difference_controller = difference_controller
    
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
        info_hist = (
            "展示应力值的整体分布：蓝色为频次直方图，红线为核密度曲线，"
            "绿色虚线为基于均值与标准差的正态分布拟合；红/橙虚线分别标注均值与中位数。\n"
            "用于判断分布形状（是否近似正态、是否多峰）、偏度（均值与中位数位置差异），"
            "以及是否存在异常尾部。"
        )
        summary_hist = self._build_hist_summary(valid_stress, basic_stats, distribution)
        self.view.add_chart(fig1, "应力分布直方图与核密度估计", info_hist, summary_hist)
        
        # 2. 箱线图
        fig2 = self._create_boxplot_chart(valid_stress, basic_stats, outliers)
        info_box = (
            "箱体上下沿为Q1/Q3，中线为中位数Q2；须线延伸至1.5×IQR内的最远值；"
            "超出须线者视为异常值（同时显示异常数量与比例）。\n"
            "用于快速比较集中趋势与离散程度，并识别离群点。"
        )
        summary_box = self._build_box_summary(valid_stress, basic_stats, outliers)
        self.view.add_chart(fig2, "应力箱线图（异常值检测）", info_box, summary_box)
        
        # 3. Q-Q图（正态性检验）
        fig3 = self._create_qq_plot(valid_stress)
        info_qq = (
            "用于检验应力分布与正态分布的一致性：点越贴近参考直线，越接近正态。\n"
            "系统性的S弯代表偏度或厚/薄尾；尾部明显偏离直线表示重尾/轻尾特征。"
        )
        summary_qq = self._build_qq_summary(valid_stress, distribution)
        self.view.add_chart(fig3, "Q-Q图（正态性检验）", info_qq, summary_qq)
        
        # 4. 累积分布图
        fig4 = self._create_cdf_plot(valid_stress, basic_stats)
        info_cdf = (
            "横轴为应力，纵轴为累计概率P(X≤x)。任意阈值x可直接读取覆盖率；"
            "虚线标注Q1/Q2/Q3定位常用分位点。\n"
            "常用于评估质量阈值（如95%样本应力低于多少MPa）。"
        )
        summary_cdf = self._build_cdf_summary(valid_stress, basic_stats)
        self.view.add_chart(fig4, "累积分布函数(CDF)", info_cdf, summary_cdf)

    # --------- 结论生成（统计） ---------
    def _build_hist_summary(self, values: np.ndarray, basic_stats: dict, distribution: dict) -> str:
        try:
            mean = float(basic_stats.get('mean', 0.0))
            median = float(basic_stats.get('median', 0.0))
            std = float(basic_stats.get('std', 0.0))
            skew = float(basic_stats.get('skewness', 0.0))
            kurt = float(basic_stats.get('kurtosis', 0.0))
            shapiro_p = float(distribution.get('shapiro_p_value', 1.0))
            normal_flag = distribution.get('is_normal_shapiro', False)
            shape = "近似正态" if normal_flag else ("右偏" if skew>0 else ("左偏" if skew<0 else "对称"))
            risk = "尾部厚重，需关注极端值" if kurt>3 else "尾部正常"
            return (
                f"结论：分布{shape}（均值 {mean:.2f} MPa，中位数 {median:.2f} MPa，"
                f"σ={std:.2f} MPa，偏度 {skew:.2f}，峰度 {kurt:.2f}）。"
                f"正态性检验 p={shapiro_p:.4f}，{ '未拒绝正态' if normal_flag else '拒绝正态' }；{risk}。"
            )
        except Exception:
            return "结论生成失败：输入数据异常。"

    def _build_box_summary(self, values: np.ndarray, basic_stats: dict, outliers: dict) -> str:
        try:
            q1 = float(basic_stats.get('q25', 0.0))
            q2 = float(basic_stats.get('q50', 0.0))
            q3 = float(basic_stats.get('q75', 0.0))
            iqr = float(basic_stats.get('iqr', 0.0))
            out_cnt = int(outliers.get('outlier_count', 0))
            out_ratio = float(outliers.get('outlier_ratio', 0.0))
            dispersion = "离散较小" if iqr < 0.2*max(abs(q2),1e-6) else ("离散中等" if iqr < 0.5*max(abs(q2),1e-6) else "离散较大")
            return (
                f"结论：中位数 {q2:.2f} MPa；IQR={iqr:.2f} MPa（{dispersion}）。"
                f"检测到异常值 {out_cnt} 个（{out_ratio:.2f}%）。"
            )
        except Exception:
            return "结论生成失败：输入数据异常。"

    def _build_qq_summary(self, values: np.ndarray, distribution: dict) -> str:
        try:
            shapiro_p = float(distribution.get('shapiro_p_value', 1.0))
            ks_p = float(distribution.get('ks_p_value', 1.0))
            normal = (shapiro_p > 0.05) and (ks_p > 0.05)
            return (
                f"结论：与正态分布{ '一致' if normal else '存在偏离' }（Shapiro p={shapiro_p:.4f}，K-S p={ks_p:.4f}）。"
                f"若偏离明显，建议采用非参数方法或进行稳健统计。"
            )
        except Exception:
            return "结论生成失败：输入数据异常。"

    def _build_cdf_summary(self, values: np.ndarray, basic_stats: dict) -> str:
        try:
            q1 = float(basic_stats.get('q25', 0.0))
            q2 = float(basic_stats.get('q50', 0.0))
            q3 = float(basic_stats.get('q75', 0.0))
            p95 = float(np.percentile(values, 95)) if len(values)>0 else 0.0
            return (
                f"结论：50%样本≤{q2:.2f} MPa，75%样本≤{q3:.2f} MPa，95%样本≤{p95:.2f} MPa。"
                f"如需质量门限评估，可将目标阈值与CDF读取的覆盖率对比。"
            )
        except Exception:
            return "结论生成失败：输入数据异常。"
    
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
        """生成PDF综合报告：包含2D热力图、3D图、统计/趋势/对比图表与结论"""
        try:
            # 选择保存路径
            file_path, _ = QFileDialog.getSaveFileName(
                self.view, "生成报告", "SiC_应力分析报告.pdf", "PDF 文件 (*.pdf)"
            )
            if not file_path:
                return

            # 当前数据集统计
            basic_stats = self.model.calculate_basic_statistics(self.current_dataset_index)
            distribution = self.model.calculate_distribution_analysis(self.current_dataset_index)
            outliers = self.model.detect_outliers(self.current_dataset_index, self.current_outlier_method)

            figures: List[Figure] = []

            # 统计页四张图
            data, _z, _name = self.model.data_sets[self.current_dataset_index]
            if 'Value' in data.columns:
                vals = data['Value'].values
                vals = vals[~np.isnan(vals)]
                figures.append(self._create_histogram_chart(vals, basic_stats, distribution))
                figures.append(self._create_boxplot_chart(vals, basic_stats, outliers))
                figures.append(self._create_qq_plot(vals))
                figures.append(self._create_cdf_plot(vals, basic_stats))

            # 所有2D热力图
            try:
                if self._heatmap_model and self._heatmap_model.get_dataset_count() > 0:
                    for i in range(self._heatmap_model.get_dataset_count()):
                        figures.append(self._heatmap_model.create_circular_heatmap_2d(i))
            except Exception:
                pass

            # 3D图（转为PNG嵌入）
            try:
                if self._heatmap_model:
                    import plotly.io as pio
                    fig3d = self._heatmap_model.create_plotly_3d_heatmap()
                    if fig3d is not None:
                        png = pio.to_image(fig3d, format='png', width=1600, height=1000, scale=2)
                        image = Image.open(io.BytesIO(png))
                        holder = Figure(figsize=(11, 7))
                        ax = holder.add_subplot(111)
                        ax.axis('off')
                        ax.imshow(image)
                        figures.append(holder)
            except Exception:
                pass

            # 趋势图
            try:
                if self._trend_controller:
                    trend_data = self._trend_controller.model.get_z_trend_data()
                    if trend_data and trend_data.get('layer_count', 0) > 0:
                        figures.append(self._trend_controller._create_z_trend_chart(trend_data))
                        figures.append(self._trend_controller._create_std_trend_chart(trend_data))
                        figures.append(self._trend_controller._create_minmax_trend_chart(trend_data))
                        gradient = self._trend_controller.model.calculate_gradient()
                        if gradient:
                            figures.append(self._trend_controller._create_gradient_chart(gradient))
            except Exception:
                pass

            # 多层对比/差分图
            try:
                if self._difference_controller and len(self._difference_controller.model.data_sets) >= 2:
                    indices = list(range(min(5, len(self._difference_controller.model.data_sets))))
                    comp = self._difference_controller.model.calculate_multi_layer_comparison(indices)
                    figures.append(self._difference_controller._create_multi_layer_bar_chart(comp))
                    figures.append(self._difference_controller._create_multi_layer_boxplot(indices))
                    if len(indices) <= 5:
                        figures.append(self._difference_controller._create_multi_layer_histogram(indices))
            except Exception:
                pass

            # 输出PDF
            with PdfPages(file_path) as pdf:
                # 封面
                cover = Figure(figsize=(11.69, 8.27))
                ax = cover.add_subplot(111)
                ax.axis('off')
                title = "SiC晶圆应力分析报告"
                subtitle = f"数据集: {basic_stats.get('file_name','')}  |  Z={basic_stats.get('z_depth',0)} μm"
                ax.text(0.5, 0.65, title, fontsize=24, fontweight='bold', ha='center')
                ax.text(0.5, 0.55, subtitle, fontsize=12, ha='center')
                summary = (
                    f"样本数: {basic_stats.get('count',0)} | 均值: {basic_stats.get('mean',0):.2f} MPa | "
                    f"中位数: {basic_stats.get('median',0):.2f} MPa | σ: {basic_stats.get('std',0):.2f} MPa\n"
                    f"偏度: {basic_stats.get('skewness',0):.2f} | 峰度: {basic_stats.get('kurtosis',0):.2f} | "
                    f"异常值: {outliers.get('outlier_count',0)} ({outliers.get('outlier_ratio',0):.2f}%)"
                )
                ax.text(0.5, 0.40, summary, fontsize=11, ha='center')
                pdf.savefig(cover, bbox_inches='tight')

                # 简单目录
                toc = Figure(figsize=(11.69, 8.27))
                ax = toc.add_subplot(111)
                ax.axis('off')
                items = ["目录", "1. 统计分析", "2. 2D热力图", "3. 3D可视化", "4. 趋势分析", "5. 多层对比/差分"]
                for i, line in enumerate(items):
                    ax.text(0.1, 0.9 - 0.07*i, line, fontsize=13)
                pdf.savefig(toc, bbox_inches='tight')

                # 所有图表
                for fig in figures:
                    pdf.savefig(fig, bbox_inches='tight')

            QMessageBox.information(self.view, "成功", f"报告已生成:\n{file_path}")
        except Exception as e:
            print(f"生成报告错误: {e}")
            QMessageBox.warning(self.view, "错误", f"生成失败: {str(e)}")

