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
        """导出PDF报告（A4纵向），内容为2D热力图，4图/页固定布局，从第一页开始展示数据。"""
        try:
            # 选择保存路径
            file_path, _ = QFileDialog.getSaveFileName(
                self.view, "导出2D热力图PDF", "SiC_2D热力图报告.pdf", "PDF 文件 (*.pdf)"
            )
            if not file_path:
                return

            # 必须存在热力图模型且有数据
            if not self._heatmap_model or self._heatmap_model.get_dataset_count() == 0:
                QMessageBox.warning(self.view, "提示", "暂无可导出的2D热力图数据。")
                return

            # 计算当前数据集统计（用于智能结论）
            basic_stats = None
            distribution = None
            outliers = None
            try:
                basic_stats = self.model.calculate_basic_statistics(self.current_dataset_index)
                distribution = self.model.calculate_distribution_analysis(self.current_dataset_index)
                outliers = self.model.detect_outliers(self.current_dataset_index, self.current_outlier_method)
            except Exception:
                pass

            dataset_count = self._heatmap_model.get_dataset_count()

            # A4 纵向: 8.27 x 11.69 英寸；每页2x2固定占位
            with PdfPages(file_path) as pdf:
                idx = 0
                while idx < dataset_count:
                    page = Figure(figsize=(8.27, 11.69))
                    page.suptitle("2D热力图", fontsize=14, fontweight='bold')
                    axs = page.subplots(2, 2)

                    # 保证axs为二维数组
                    axes_grid = axs if isinstance(axs, (list, tuple, np.ndarray)) else [[axs]]

                    for r in range(2):
                        for c in range(2):
                            ax = axes_grid[r][c]
                            ax.axis('off')
                            if idx < dataset_count:
                                try:
                                    # 生成单个2D热力图，并转为PNG嵌入
                                    fig_2d = self._heatmap_model.create_circular_heatmap_2d(idx)
                                    buf = io.BytesIO()
                                    # 提高导出位图的DPI以提升清晰度
                                    fig_2d.savefig(buf, format='png', dpi=600, bbox_inches='tight')
                                    buf.seek(0)
                                    img = Image.open(buf)
                                    # 禁用插值，保持像素清晰
                                    ax.imshow(img, interpolation='nearest')
                                    # 标题（文件名 + Z 深度）
                                    try:
                                        data, z_depth, file_name = self._heatmap_model.data_sets[idx]
                                        ax.set_title(f"{file_name} | Z={z_depth} μm", fontsize=9)
                                    except Exception:
                                        pass
                                except Exception:
                                    pass
                                finally:
                                    idx += 1
                            else:
                                # 空占位（固定布局）
                                pass

                    page.tight_layout(pad=0.6, rect=[0, 0, 1, 0.96])
                    # 将整页以更高DPI写入PDF
                    pdf.savefig(page, dpi=300)

                # 追加一页：上半页 3D切片热力图（Plotly导出PNG），下半页 智能数据分析结论
                try:
                    page3 = Figure(figsize=(8.27, 11.69))
                    page3.suptitle("3D切片热力图", fontsize=14, fontweight='bold')
                    gs = page3.add_gridspec(2, 1, height_ratios=[1.2, 1.0])
                    ax_top = page3.add_subplot(gs[0])
                    ax_bot = page3.add_subplot(gs[1])

                    # 3D热力图（切片/体渲染）转PNG嵌入
                    try:
                        import plotly.io as pio
                        fig3d = self._heatmap_model.create_plotly_3d_heatmap()
                        if fig3d is not None:
                            png = pio.to_image(fig3d, format='png', width=1600, height=1000, scale=2)
                            img3d = Image.open(io.BytesIO(png))
                            ax_top.imshow(img3d, interpolation='nearest')
                            ax_top.set_title("3D切片热力图", fontsize=12)
                        else:
                            ax_top.text(0.5, 0.5, "3D热力图不可用", ha='center', va='center')
                    except Exception:
                        ax_top.text(0.5, 0.5, "3D热力图生成失败", ha='center', va='center')
                    finally:
                        ax_top.axis('off')

                    # 智能数据分析结论（基于统计/分布/异常）
                    ax_bot.axis('off')
                    try:
                        if basic_stats is not None and distribution is not None:
                            # 构造结论摘要
                            # 使用已有的结论构建方法
                            # 注意：这里使用当前数据集值集作为统计输入，如果无法获取则仅输出基础指标
                            data_df, _z, file_name = self.model.data_sets[self.current_dataset_index]
                            if 'Value' in data_df.columns:
                                values = data_df['Value'].values
                                values = values[~np.isnan(values)]
                                text_lines = []
                                try:
                                    text_lines.append(self._build_hist_summary(values, basic_stats, distribution))
                                except Exception:
                                    pass
                                try:
                                    text_lines.append(self._build_box_summary(values, basic_stats, outliers or {}))
                                except Exception:
                                    pass
                                try:
                                    text_lines.append(self._build_qq_summary(values, distribution))
                                except Exception:
                                    pass
                                try:
                                    text_lines.append(self._build_cdf_summary(values, basic_stats))
                                except Exception:
                                    pass
                                summary_text = "\n\n".join([t for t in text_lines if t])
                            else:
                                summary_text = "统计结论不可用：缺少 Value 列。"
                        else:
                            summary_text = "统计结论不可用：统计数据计算失败。"
                    except Exception:
                        summary_text = "统计结论生成异常。"

                    ax_bot.text(0.02, 0.98, summary_text, va='top', ha='left', fontsize=10, wrap=True)
                    page3.tight_layout(pad=0.8, rect=[0, 0, 1, 0.96])
                    pdf.savefig(page3, dpi=300)
                except Exception:
                    # 忽略附加页失败不影响2D导出
                    pass

                # 追加：统计分析页（2x1，每页最多2张；每格“图+结论”上下排布）
                try:
                    data_df, _z, _name = self.model.data_sets[self.current_dataset_index]
                    if 'Value' in data_df.columns and basic_stats and distribution is not None:
                        values = data_df['Value'].values
                        values = values[~np.isnan(values)]

                        figs_stats: List[Tuple[Figure, str]] = []
                        try:
                            f1 = self._create_histogram_chart(values, basic_stats, distribution)
                            s1 = self._build_hist_summary(values, basic_stats, distribution)
                            figs_stats.append((f1, s1))
                        except Exception:
                            pass
                        try:
                            f2 = self._create_boxplot_chart(values, basic_stats, outliers or {})
                            s2 = self._build_box_summary(values, basic_stats, outliers or {})
                            figs_stats.append((f2, s2))
                        except Exception:
                            pass
                        try:
                            f3 = self._create_qq_plot(values)
                            s3 = self._build_qq_summary(values, distribution)
                            figs_stats.append((f3, s3))
                        except Exception:
                            pass
                        try:
                            f4 = self._create_cdf_plot(values, basic_stats)
                            s4 = self._build_cdf_summary(values, basic_stats)
                            figs_stats.append((f4, s4))
                        except Exception:
                            pass
                        # 渲染到若干页，每页2行1列，每格上图下结论
                        if figs_stats:
                            i = 0
                            while i < len(figs_stats):
                                page_stats = Figure(figsize=(8.27, 11.69))
                                page_stats.suptitle("统计分析", fontsize=14, fontweight='bold')
                                grid = page_stats.add_gridspec(2, 1, height_ratios=[1, 1])
                                for r in range(2):
                                    if i >= len(figs_stats):
                                        break
                                    fig_src, summary_txt = figs_stats[i]
                                    cell = page_stats.add_subplot(grid[r, 0])
                                    cell.axis('off')
                                    buf = io.BytesIO()
                                    fig_src.savefig(buf, format='png', dpi=600, bbox_inches='tight')
                                    buf.seek(0)
                                    img = Image.open(buf)
                                    # 调整区域：上方图像，下方文本
                                    pos = cell.get_position(page_stats)
                                    x0, y0, w, h = pos.x0, pos.y0, pos.width, pos.height
                                    text_h = h * 0.18
                                    img_ax = page_stats.add_axes([x0, y0 + text_h, w, h - text_h])
                                    img_ax.axis('off')
                                    img_ax.imshow(img, interpolation='nearest')
                                    text_ax = page_stats.add_axes([x0, y0, w, text_h])
                                    text_ax.axis('off')
                                    text_ax.text(0.01, 0.98, summary_txt or "", va='top', ha='left', fontsize=9, wrap=True)
                                    i += 1
                                page_stats.tight_layout(pad=0.6, rect=[0, 0, 1, 0.96])
                                pdf.savefig(page_stats, dpi=300)
                except Exception:
                    pass

                # 追加：趋势分析页（2x1分页：均值趋势、标准差趋势、极值趋势、梯度图；每格含结论）
                try:
                    if self._trend_controller:
                        trend_data = self._trend_controller.model.get_z_trend_data()
                        figs_trend: List[Tuple[Figure, str]] = []
                        if trend_data and trend_data.get('layer_count', 0) > 0:
                            try:
                                ft1 = self._trend_controller._create_z_trend_chart(trend_data)
                                st1 = self._trend_controller._build_z_trend_summary(trend_data)
                                figs_trend.append((ft1, st1))
                            except Exception:
                                pass
                            try:
                                ft2 = self._trend_controller._create_std_trend_chart(trend_data)
                                st2 = self._trend_controller._build_std_trend_summary(trend_data)
                                figs_trend.append((ft2, st2))
                            except Exception:
                                pass
                            try:
                                ft3 = self._trend_controller._create_minmax_trend_chart(trend_data)
                                st3 = self._trend_controller._build_minmax_summary(trend_data)
                                figs_trend.append((ft3, st3))
                            except Exception:
                                pass
                            try:
                                gradient = self._trend_controller.model.calculate_gradient()
                                if gradient:
                                    ft4 = self._trend_controller._create_gradient_chart(gradient)
                                    st4 = self._trend_controller._build_gradient_summary(gradient)
                                    figs_trend.append((ft4, st4))
                            except Exception:
                                pass
                        if figs_trend:
                            i = 0
                            while i < len(figs_trend):
                                page_trend = Figure(figsize=(8.27, 11.69))
                                page_trend.suptitle("趋势分析", fontsize=14, fontweight='bold')
                                grid = page_trend.add_gridspec(2, 1, height_ratios=[1, 1])
                                for r in range(2):
                                    if i >= len(figs_trend):
                                        break
                                    fig_src, summary_txt = figs_trend[i]
                                    cell = page_trend.add_subplot(grid[r, 0])
                                    cell.axis('off')
                                    buf = io.BytesIO()
                                    fig_src.savefig(buf, format='png', dpi=600, bbox_inches='tight')
                                    buf.seek(0)
                                    img = Image.open(buf)
                                    pos = cell.get_position(page_trend)
                                    x0, y0, w, h = pos.x0, pos.y0, pos.width, pos.height
                                    text_h = h * 0.18
                                    img_ax = page_trend.add_axes([x0, y0 + text_h, w, h - text_h])
                                    img_ax.axis('off')
                                    img_ax.imshow(img, interpolation='nearest')
                                    text_ax = page_trend.add_axes([x0, y0, w, text_h])
                                    text_ax.axis('off')
                                    text_ax.text(0.01, 0.98, summary_txt or "", va='top', ha='left', fontsize=9, wrap=True)
                                    i += 1
                                page_trend.tight_layout(pad=0.6, rect=[0, 0, 1, 0.96])
                                pdf.savefig(page_trend, dpi=300)
                except Exception:
                    pass

                # 追加：差分/多层对比页（2x1分页：柱状、箱线、叠加直方图；每格含简述）
                try:
                    if self._difference_controller and len(self._difference_controller.model.data_sets) >= 2:
                        # 取最多5层做多层对比
                        indices = list(range(min(5, len(self._difference_controller.model.data_sets))))
                        comparison = self._difference_controller.model.calculate_multi_layer_comparison(indices)
                        figs_diff: List[Tuple[Figure, str]] = []
                        try:
                            f1 = self._difference_controller._create_multi_layer_bar_chart(comparison)
                            s1 = "对比各层的均值、标准差、CV与极值范围，定位差异显著层。"
                            figs_diff.append((f1, s1))
                        except Exception:
                            pass
                        try:
                            f2 = self._difference_controller._create_multi_layer_boxplot(indices, comparison)
                            s2 = "多层箱线图观察分布、离群点与中位数差异。"
                            figs_diff.append((f2, s2))
                        except Exception:
                            pass
                        try:
                            if len(indices) <= 5:
                                f3 = self._difference_controller._create_multi_layer_histogram(indices, comparison)
                                s3 = "叠加直方图比较整体分布形状与位置差异。"
                                figs_diff.append((f3, s3))
                        except Exception:
                            pass
                        if figs_diff:
                            i = 0
                            while i < len(figs_diff):
                                page_diff = Figure(figsize=(8.27, 11.69))
                                page_diff.suptitle("差分对比", fontsize=14, fontweight='bold')
                                grid = page_diff.add_gridspec(2, 1, height_ratios=[1, 1])
                                for r in range(2):
                                    if i >= len(figs_diff):
                                        break
                                    fig_src, summary_txt = figs_diff[i]
                                    cell = page_diff.add_subplot(grid[r, 0])
                                    cell.axis('off')
                                    buf = io.BytesIO()
                                    fig_src.savefig(buf, format='png', dpi=600, bbox_inches='tight')
                                    buf.seek(0)
                                    img = Image.open(buf)
                                    pos = cell.get_position(page_diff)
                                    x0, y0, w, h = pos.x0, pos.y0, pos.width, pos.height
                                    text_h = h * 0.18
                                    img_ax = page_diff.add_axes([x0, y0 + text_h, w, h - text_h])
                                    img_ax.axis('off')
                                    img_ax.imshow(img, interpolation='nearest')
                                    text_ax = page_diff.add_axes([x0, y0, w, text_h])
                                    text_ax.axis('off')
                                    text_ax.text(0.01, 0.98, summary_txt or "", va='top', ha='left', fontsize=9, wrap=True)
                                    i += 1
                                page_diff.tight_layout(pad=0.6, rect=[0, 0, 1, 0.96])
                                pdf.savefig(page_diff, dpi=300)
                except Exception:
                    pass

                # 追加：差分云图页（2x1分页；相邻层成对差分：i - i+1；每格含结论）
                try:
                    if self._difference_controller and self._heatmap_model and self._heatmap_model.get_dataset_count() >= 2:
                        pair_figs: List[Tuple[Figure, str]] = []
                        try:
                            total = self._heatmap_model.get_dataset_count()
                            for i_pair in range(total - 1):
                                try:
                                    xi, yi, diff = self._heatmap_model.calculate_difference_map(i_pair, i_pair + 1)
                                    fig_dm = self._difference_controller._create_difference_heatmap(xi, yi, diff)
                                    summary_dm = self._difference_controller._build_diff_summary(diff)
                                    # 组装对比标题
                                    try:
                                        name1 = self._heatmap_model.data_sets[i_pair][2]
                                        name2 = self._heatmap_model.data_sets[i_pair + 1][2]
                                        summary_full = f"对比：{name1} - {name2}\n" + (summary_dm or "")
                                    except Exception:
                                        summary_full = summary_dm or ""
                                    pair_figs.append((fig_dm, summary_full))
                                except Exception:
                                    continue
                        except Exception:
                            pair_figs = []

                        if pair_figs:
                            i = 0
                            while i < len(pair_figs):
                                page_pair = Figure(figsize=(8.27, 11.69))
                                page_pair.suptitle("差分云图", fontsize=14, fontweight='bold')
                                grid = page_pair.add_gridspec(2, 1, height_ratios=[1, 1])
                                for r in range(2):
                                    if i >= len(pair_figs):
                                        break
                                    fig_src, summary_txt = pair_figs[i]
                                    cell = page_pair.add_subplot(grid[r, 0])
                                    cell.axis('off')
                                    buf = io.BytesIO()
                                    fig_src.savefig(buf, format='png', dpi=600, bbox_inches='tight')
                                    buf.seek(0)
                                    img = Image.open(buf)
                                    # 上图下文
                                    pos = cell.get_position(page_pair)
                                    x0, y0, w, h = pos.x0, pos.y0, pos.width, pos.height
                                    text_h = h * 0.18
                                    img_ax = page_pair.add_axes([x0, y0 + text_h, w, h - text_h])
                                    img_ax.axis('off')
                                    img_ax.imshow(img, interpolation='nearest')
                                    text_ax = page_pair.add_axes([x0, y0, w, text_h])
                                    text_ax.axis('off')
                                    text_ax.text(0.01, 0.98, summary_txt or "", va='top', ha='left', fontsize=9, wrap=True)
                                    i += 1
                                page_pair.tight_layout(pad=0.6, rect=[0, 0, 1, 0.96])
                                pdf.savefig(page_pair, dpi=300)
                except Exception:
                    pass

            QMessageBox.information(self.view, "成功", f"PDF已导出:\n{file_path}")
        except Exception as e:
            print(f"生成报告错误: {e}")
            QMessageBox.warning(self.view, "错误", f"生成失败: {str(e)}")

