"""
趋势对比模型模块

提供多层数据的趋势分析和对比功能
"""

from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pandas as pd
from scipy import stats
from scipy.interpolate import interp1d


class TrendModel:
    """趋势对比模型，负责多层数据的趋势分析"""
    
    def __init__(self):
        """初始化趋势模型"""
        self.data_sets: List[Tuple] = []  # 数据集列表 [(data, z_depth, file_name), ...]
    
    def set_data_sets(self, data_sets: List[Tuple]) -> None:
        """设置数据集
        
        Args:
            data_sets: 数据集列表 [(data, z_depth, file_name), ...]
        """
        self.data_sets = data_sets
    
    def get_z_trend_data(self) -> Dict[str, Any]:
        """获取Z轴趋势数据
        
        Returns:
            Dict: Z轴趋势数据
        """
        if len(self.data_sets) == 0:
            return {}
        
        # 按Z轴深度排序
        sorted_datasets = sorted(self.data_sets, key=lambda x: x[1])
        
        z_depths = []
        mean_values = []
        median_values = []
        std_values = []
        min_values = []
        max_values = []
        
        for data, z_depth, file_name in sorted_datasets:
            if 'Value' not in data.columns:
                continue
            
            stress_values = data['Value'].values
            valid_stress = stress_values[~np.isnan(stress_values)]
            
            if len(valid_stress) == 0:
                continue
            
            z_depths.append(z_depth)
            mean_values.append(np.mean(valid_stress))
            median_values.append(np.median(valid_stress))
            std_values.append(np.std(valid_stress))
            min_values.append(np.min(valid_stress))
            max_values.append(np.max(valid_stress))
        
        return {
            'z_depths': z_depths,
            'mean_values': mean_values,
            'median_values': median_values,
            'std_values': std_values,
            'min_values': min_values,
            'max_values': max_values,
            'layer_count': len(z_depths)
        }
    
    def calculate_layer_comparison(self, index1: int, index2: int) -> Dict[str, Any]:
        """计算两层之间的对比数据（兼容旧接口）
        
        Args:
            index1: 第一层索引
            index2: 第二层索引
            
        Returns:
            Dict: 对比数据
        """
        if index1 < 0 or index1 >= len(self.data_sets):
            return {}
        if index2 < 0 or index2 >= len(self.data_sets):
            return {}
        
        data1, z1, name1 = self.data_sets[index1]
        data2, z2, name2 = self.data_sets[index2]
        
        if 'Value' not in data1.columns or 'Value' not in data2.columns:
            return {}
        
        stress1 = data1['Value'].values
        stress2 = data2['Value'].values
        
        valid_stress1 = stress1[~np.isnan(stress1)]
        valid_stress2 = stress2[~np.isnan(stress2)]
        
        if len(valid_stress1) == 0 or len(valid_stress2) == 0:
            return {}
        
        # 基本统计对比
        mean_diff = np.mean(valid_stress2) - np.mean(valid_stress1)
        median_diff = np.median(valid_stress2) - np.median(valid_stress1)
        std_diff = np.std(valid_stress2) - np.std(valid_stress1)
        
        # 统计检验（t检验）
        t_stat, p_value = stats.ttest_ind(valid_stress1, valid_stress2)
        
        # 效应量（Cohen's d）
        pooled_std = np.sqrt((np.std(valid_stress1)**2 + np.std(valid_stress2)**2) / 2)
        cohens_d = (np.mean(valid_stress2) - np.mean(valid_stress1)) / pooled_std if pooled_std > 0 else 0
        
        return {
            'layer1_name': name1,
            'layer1_z': z1,
            'layer1_mean': float(np.mean(valid_stress1)),
            'layer1_std': float(np.std(valid_stress1)),
            'layer2_name': name2,
            'layer2_z': z2,
            'layer2_mean': float(np.mean(valid_stress2)),
            'layer2_std': float(np.std(valid_stress2)),
            'mean_diff': float(mean_diff),
            'median_diff': float(median_diff),
            'std_diff': float(std_diff),
            't_statistic': float(t_stat),
            'p_value': float(p_value),
            'cohens_d': float(cohens_d),
            'significant': bool(p_value < 0.05)
        }
    
    def calculate_multi_layer_comparison(self, indices: List[int]) -> Dict[str, Any]:
        """计算多层对比数据
        
        Args:
            indices: 层索引列表（至少2个）
            
        Returns:
            Dict: 多层对比数据
        """
        if len(indices) < 2:
            return {}
        
        layers_stats = []
        all_stress_values = []
        
        for idx in indices:
            if idx < 0 or idx >= len(self.data_sets):
                continue
            
            data, z_depth, file_name = self.data_sets[idx]
            
            if 'Value' not in data.columns:
                continue
            
            stress_values = data['Value'].values
            valid_stress = stress_values[~np.isnan(stress_values)]
            
            if len(valid_stress) == 0:
                continue
            
            # 计算统计指标
            mean_val = np.mean(valid_stress)
            median_val = np.median(valid_stress)
            std_val = np.std(valid_stress)
            min_val = np.min(valid_stress)
            max_val = np.max(valid_stress)
            cv = (std_val / mean_val * 100) if mean_val != 0 else 0
            
            layer_stat = {
                'index': idx,
                'file_name': file_name,
                'z_depth': float(z_depth),
                'mean': float(mean_val),
                'median': float(median_val),
                'std': float(std_val),
                'min': float(min_val),
                'max': float(max_val),
                'cv': float(cv),
                'count': len(valid_stress)
            }
            
            layers_stats.append(layer_stat)
            all_stress_values.append(valid_stress)
        
        if len(layers_stats) < 2:
            return {}
        
        # 计算层间方差分析（ANOVA）
        f_stat, p_value = stats.f_oneway(*all_stress_values) if len(all_stress_values) >= 2 else (0.0, 1.0)
        
        # 计算成对t检验
        pairwise_comparisons = []
        for i in range(len(layers_stats)):
            for j in range(i + 1, len(layers_stats)):
                t_stat, p_val = stats.ttest_ind(all_stress_values[i], all_stress_values[j])
                pairwise_comparisons.append({
                    'layer1': layers_stats[i]['file_name'],
                    'layer2': layers_stats[j]['file_name'],
                    't_statistic': float(t_stat),
                    'p_value': float(p_val),
                    'significant': bool(p_val < 0.05)
                })
        
        return {
            'layer_count': len(layers_stats),
            'layers_stats': layers_stats,
            'anova_f_statistic': float(f_stat),
            'anova_p_value': float(p_value),
            'anova_significant': bool(p_value < 0.05),
            'pairwise_comparisons': pairwise_comparisons
        }
    
    def calculate_gradient(self) -> Dict[str, Any]:
        """计算Z轴应力梯度
        
        Returns:
            Dict: 梯度数据
        """
        trend_data = self.get_z_trend_data()
        
        if not trend_data or len(trend_data['z_depths']) < 2:
            return {}
        
        z_depths = np.array(trend_data['z_depths'])
        mean_values = np.array(trend_data['mean_values'])
        
        # 计算梯度（应力变化率）
        gradients = np.gradient(mean_values, z_depths)
        
        # 线性拟合
        slope, intercept, r_value, p_value, std_err = stats.linregress(z_depths, mean_values)
        
        return {
            'z_depths': z_depths.tolist(),
            'mean_values': mean_values.tolist(),
            'gradients': gradients.tolist(),
            'slope': float(slope),
            'intercept': float(intercept),
            'r_squared': float(r_value**2),
            'p_value': float(p_value),
            'std_error': float(std_err)
        }
    
    def get_spatial_distribution_comparison(self) -> Dict[str, Any]:
        """获取空间分布对比数据（用于热力图对比）
        
        Returns:
            Dict: 空间分布数据
        """
        if len(self.data_sets) == 0:
            return {}
        
        layers_data = []
        
        for i, (data, z_depth, file_name) in enumerate(self.data_sets):
            if 'X' not in data.columns or 'Y' not in data.columns or 'Value' not in data.columns:
                continue
            
            layer_info = {
                'index': i,
                'z_depth': z_depth,
                'file_name': file_name,
                'x': data['X'].values.tolist(),
                'y': data['Y'].values.tolist(),
                'values': data['Value'].values.tolist()
            }
            layers_data.append(layer_info)
        
        return {
            'layers': layers_data,
            'layer_count': len(layers_data)
        }
    
    def calculate_correlation_between_layers(self) -> Dict[str, Any]:
        """计算层间相关性矩阵
        
        Returns:
            Dict: 相关性数据
        """
        if len(self.data_sets) < 2:
            return {}
        
        layer_count = len(self.data_sets)
        correlation_matrix = np.zeros((layer_count, layer_count))
        
        # 提取所有层的应力值
        all_stress_values = []
        for data, _, _ in self.data_sets:
            if 'Value' in data.columns:
                stress = data['Value'].values
                valid_stress = stress[~np.isnan(stress)]
                all_stress_values.append(valid_stress)
            else:
                all_stress_values.append(np.array([]))
        
        # 计算相关系数
        for i in range(layer_count):
            for j in range(layer_count):
                if len(all_stress_values[i]) > 0 and len(all_stress_values[j]) > 0:
                    # 使用较短的长度进行相关性计算
                    min_len = min(len(all_stress_values[i]), len(all_stress_values[j]))
                    if min_len > 1:
                        corr, _ = stats.pearsonr(
                            all_stress_values[i][:min_len], 
                            all_stress_values[j][:min_len]
                        )
                        correlation_matrix[i, j] = corr
                    else:
                        correlation_matrix[i, j] = 0
                else:
                    correlation_matrix[i, j] = 0
        
        # 获取层名称
        layer_names = [f"{name} (Z={z}μm)" for _, z, name in self.data_sets]
        
        return {
            'correlation_matrix': correlation_matrix.tolist(),
            'layer_names': layer_names,
            'layer_count': layer_count
        }
    
    def detect_anomalous_layers(self, threshold: float = 2.0) -> List[Dict[str, Any]]:
        """检测异常层（与整体趋势偏差较大的层）
        
        Args:
            threshold: 偏差阈值（标准差倍数）
            
        Returns:
            List[Dict]: 异常层列表
        """
        trend_data = self.get_z_trend_data()
        
        if not trend_data or len(trend_data['z_depths']) < 3:
            return []
        
        mean_values = np.array(trend_data['mean_values'])
        z_depths = np.array(trend_data['z_depths'])
        
        # 计算整体均值和标准差
        global_mean = np.mean(mean_values)
        global_std = np.std(mean_values)
        
        # 检测异常值
        anomalies = []
        for i, (mean_val, z_depth) in enumerate(zip(mean_values, z_depths)):
            z_score = abs(mean_val - global_mean) / global_std if global_std > 0 else 0
            
            if z_score > threshold:
                _, _, file_name = self.data_sets[i]
                anomalies.append({
                    'index': i,
                    'z_depth': float(z_depth),
                    'file_name': file_name,
                    'mean_value': float(mean_val),
                    'z_score': float(z_score),
                    'deviation': float(mean_val - global_mean)
                })
        
        return anomalies
    
    def calculate_uniformity_metrics(self) -> Dict[str, Any]:
        """计算均匀性指标
        
        Returns:
            Dict: 均匀性指标
        """
        if len(self.data_sets) == 0:
            return {}
        
        uniformity_metrics = []
        
        for i, (data, z_depth, file_name) in enumerate(self.data_sets):
            if 'Value' not in data.columns:
                continue
            
            stress_values = data['Value'].values
            valid_stress = stress_values[~np.isnan(stress_values)]
            
            if len(valid_stress) == 0:
                continue
            
            # 变异系数（CV）
            mean_val = np.mean(valid_stress)
            std_val = np.std(valid_stress)
            cv = (std_val / mean_val * 100) if mean_val != 0 else 0
            
            # 极差比
            range_val = np.max(valid_stress) - np.min(valid_stress)
            range_ratio = (range_val / mean_val * 100) if mean_val != 0 else 0
            
            uniformity_metrics.append({
                'index': i,
                'z_depth': z_depth,
                'file_name': file_name,
                'cv': float(cv),
                'range_ratio': float(range_ratio),
                'std': float(std_val),
                'mean': float(mean_val)
            })
        
        return {
            'layers': uniformity_metrics,
            'layer_count': len(uniformity_metrics)
        }

