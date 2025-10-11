"""
统计分析模型模块

提供应力数据的统计分析功能，包括描述性统计、分布分析和异常值检测
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from scipy import stats


class StatisticsModel:
    """统计分析模型，负责计算各类统计指标"""
    
    def __init__(self):
        """初始化统计模型"""
        self.data_sets: List[Tuple] = []  # 数据集列表 [(data, z_depth, file_name), ...]
        self.cached_statistics: Dict[int, Dict[str, Any]] = {}  # 缓存计算结果
    
    def set_data_sets(self, data_sets: List[Tuple]) -> None:
        """设置数据集
        
        Args:
            data_sets: 数据集列表 [(data, z_depth, file_name), ...]
        """
        self.data_sets = data_sets
        self.cached_statistics.clear()  # 清除缓存
    
    def calculate_basic_statistics(self, dataset_index: int) -> Dict[str, float]:
        """计算基础统计指标
        
        Args:
            dataset_index: 数据集索引
            
        Returns:
            Dict: 包含各类统计指标的字典
        """
        if dataset_index < 0 or dataset_index >= len(self.data_sets):
            return {}
        
        # 检查缓存
        if dataset_index in self.cached_statistics:
            return self.cached_statistics[dataset_index]
        
        data, z_depth, file_name = self.data_sets[dataset_index]
        
        # 提取应力值（DataFrame的'Value'列）
        if 'Value' not in data.columns:
            return {}
        
        stress_values = data['Value'].values
        
        # 过滤掉NaN值
        valid_stress = stress_values[~np.isnan(stress_values)]
        
        if len(valid_stress) == 0:
            return {}
        
        # 计算统计指标
        statistics = {
            # 集中趋势
            'mean': float(np.mean(valid_stress)),
            'median': float(np.median(valid_stress)),
            'mode': float(stats.mode(valid_stress, keepdims=True).mode[0]) if len(valid_stress) > 0 else 0,
            
            # 离散程度
            'std': float(np.std(valid_stress, ddof=1)),
            'variance': float(np.var(valid_stress, ddof=1)),
            'range': float(np.ptp(valid_stress)),
            'iqr': float(np.percentile(valid_stress, 75) - np.percentile(valid_stress, 25)),
            'cv': float(np.std(valid_stress, ddof=1) / np.mean(valid_stress) * 100) if np.mean(valid_stress) != 0 else 0,
            
            # 极值
            'min': float(np.min(valid_stress)),
            'max': float(np.max(valid_stress)),
            
            # 分位数
            'q25': float(np.percentile(valid_stress, 25)),
            'q50': float(np.percentile(valid_stress, 50)),
            'q75': float(np.percentile(valid_stress, 75)),
            
            # 形态特征
            'skewness': float(stats.skew(valid_stress)),
            'kurtosis': float(stats.kurtosis(valid_stress)),
            
            # 数据质量
            'count': int(len(valid_stress)),
            'missing': int(len(stress_values) - len(valid_stress)),
            'missing_ratio': float((len(stress_values) - len(valid_stress)) / len(stress_values) * 100),
            
            # 元数据
            'z_depth': float(z_depth),
            'file_name': file_name,
        }
        
        # 缓存结果
        self.cached_statistics[dataset_index] = statistics
        
        return statistics
    
    def calculate_distribution_analysis(self, dataset_index: int) -> Dict[str, Any]:
        """计算分布特征分析
        
        Args:
            dataset_index: 数据集索引
            
        Returns:
            Dict: 分布特征数据
        """
        if dataset_index < 0 or dataset_index >= len(self.data_sets):
            return {}
        
        data, z_depth, file_name = self.data_sets[dataset_index]
        
        if 'Value' not in data.columns:
            return {}
        
        stress_values = data['Value'].values
        valid_stress = stress_values[~np.isnan(stress_values)]
        
        if len(valid_stress) == 0:
            return {}
        
        # 正态性检验 (Shapiro-Wilk test)
        # 对于大样本（n>5000），使用采样以提高性能
        sample_size = min(5000, len(valid_stress))
        sample_stress = np.random.choice(valid_stress, size=sample_size, replace=False)
        shapiro_stat, shapiro_p = stats.shapiro(sample_stress)
        
        # Kolmogorov-Smirnov检验（与标准正态分布比较）
        ks_stat, ks_p = stats.kstest(
            (valid_stress - np.mean(valid_stress)) / np.std(valid_stress),
            'norm'
        )
        
        # 计算直方图数据
        hist, bin_edges = np.histogram(valid_stress, bins=50)
        
        return {
            'shapiro_stat': float(shapiro_stat),
            'shapiro_p_value': float(shapiro_p),
            'is_normal_shapiro': bool(shapiro_p > 0.05),
            'ks_stat': float(ks_stat),
            'ks_p_value': float(ks_p),
            'is_normal_ks': bool(ks_p > 0.05),
            'histogram_counts': hist.tolist(),
            'histogram_bins': bin_edges.tolist(),
        }
    
    def detect_outliers(self, dataset_index: int, method: str = 'iqr') -> Dict[str, Any]:
        """检测异常值
        
        Args:
            dataset_index: 数据集索引
            method: 检测方法 ('iqr', 'zscore', 'isolation_forest')
            
        Returns:
            Dict: 异常值检测结果
        """
        if dataset_index < 0 or dataset_index >= len(self.data_sets):
            return {}
        
        data, z_depth, file_name = self.data_sets[dataset_index]
        
        if 'Value' not in data.columns:
            return {}
        
        stress_values = data['Value'].values
        valid_stress = stress_values[~np.isnan(stress_values)]
        
        if len(valid_stress) == 0:
            return {}
        
        outliers_mask = np.zeros(len(valid_stress), dtype=bool)
        
        if method == 'iqr':
            # IQR方法
            q25 = np.percentile(valid_stress, 25)
            q75 = np.percentile(valid_stress, 75)
            iqr = q75 - q25
            lower_bound = q25 - 1.5 * iqr
            upper_bound = q75 + 1.5 * iqr
            outliers_mask = (valid_stress < lower_bound) | (valid_stress > upper_bound)
            
        elif method == 'zscore':
            # Z-score方法（3倍标准差）
            z_scores = np.abs(stats.zscore(valid_stress))
            outliers_mask = z_scores > 3
            
        elif method == 'isolation_forest':
            # Isolation Forest方法（需要sklearn）
            try:
                from sklearn.ensemble import IsolationForest
                clf = IsolationForest(contamination=0.1, random_state=42)
                outliers_mask = clf.fit_predict(valid_stress.reshape(-1, 1)) == -1
            except ImportError:
                # 如果sklearn未安装，回退到IQR方法
                return self.detect_outliers(dataset_index, method='iqr')
        
        outlier_indices = np.where(outliers_mask)[0]
        outlier_values = valid_stress[outliers_mask]
        
        return {
            'method': method,
            'outlier_count': int(np.sum(outliers_mask)),
            'outlier_ratio': float(np.sum(outliers_mask) / len(valid_stress) * 100),
            'outlier_indices': outlier_indices.tolist(),
            'outlier_values': outlier_values.tolist(),
            'lower_bound': float(lower_bound) if method == 'iqr' else None,
            'upper_bound': float(upper_bound) if method == 'iqr' else None,
        }
    
    def calculate_multi_layer_statistics(self) -> Dict[str, Any]:
        """计算多层统计对比（用于3D数据）
        
        Returns:
            Dict: 多层统计对比数据
        """
        if len(self.data_sets) == 0:
            return {}
        
        # 收集每层的统计信息
        layers_stats = []
        for i in range(len(self.data_sets)):
            stats = self.calculate_basic_statistics(i)
            if stats:
                layers_stats.append(stats)
        
        if not layers_stats:
            return {}
        
        # 提取各层的关键指标
        z_depths = [s['z_depth'] for s in layers_stats]
        means = [s['mean'] for s in layers_stats]
        stds = [s['std'] for s in layers_stats]
        ranges = [s['range'] for s in layers_stats]
        
        return {
            'layer_count': len(layers_stats),
            'z_depths': z_depths,
            'means': means,
            'stds': stds,
            'ranges': ranges,
            'global_mean': float(np.mean(means)),
            'global_std': float(np.std(means)),
            'max_variation_layer': int(np.argmax(stds)),
            'min_variation_layer': int(np.argmin(stds)),
        }
    
    def calculate_confidence_interval(self, dataset_index: int, confidence_level: float = 0.95) -> Tuple[float, float]:
        """计算置信区间
        
        Args:
            dataset_index: 数据集索引
            confidence_level: 置信水平 (默认95%)
            
        Returns:
            Tuple[float, float]: (下界, 上界)
        """
        if dataset_index < 0 or dataset_index >= len(self.data_sets):
            return (0.0, 0.0)
        
        data, _, _ = self.data_sets[dataset_index]
        
        if 'Value' not in data.columns:
            return (0.0, 0.0)
        
        stress_values = data['Value'].values
        valid_stress = stress_values[~np.isnan(stress_values)]
        
        if len(valid_stress) == 0:
            return (0.0, 0.0)
        
        mean = np.mean(valid_stress)
        sem = stats.sem(valid_stress)
        confidence = stats.t.interval(
            confidence_level,
            len(valid_stress) - 1,
            loc=mean,
            scale=sem
        )
        
        return (float(confidence[0]), float(confidence[1]))

