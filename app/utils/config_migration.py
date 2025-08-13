"""配置迁移模块

提供配置文件的版本迁移和用户体验过渡功能
"""
import logging
from typing import Dict, Any, Tuple, List
from datetime import datetime

logger = logging.getLogger(__name__)


class ConfigMigration:
    """配置迁移工具类"""
    
    # 版本定义
    LEGACY_VERSION = "1.0"
    CURRENT_VERSION = "2.0"
    
    def __init__(self):
        """初始化配置迁移工具"""
        self.migration_log = []
    
    def detect_legacy_config(self, config_data: Dict[str, Any]) -> bool:
        """检测是否为旧版本配置
        
        Args:
            config_data: 配置数据
            
        Returns:
            bool: 是否为旧版本配置
        """
        # 检查版本号
        version = config_data.get('version')
        if version is None or version == self.LEGACY_VERSION:
            return True
        
        # 检查是否存在旧的配置字段
        if 'colorbar_settings' in config_data:
            colorbar_settings = config_data['colorbar_settings']
            if 'auto_range' in colorbar_settings:
                return True
        
        return False
    
    def migrate_config_data(self, config_data: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        """迁移配置数据
        
        Args:
            config_data: 原始配置数据
            
        Returns:
            Tuple[Dict[str, Any], bool]: (迁移后的配置数据, 是否发生了迁移)
        """
        migrated_data = config_data.copy()
        migration_occurred = False
        
        # 清空迁移日志
        self.migration_log.clear()
        
        # 迁移色标设置
        if 'colorbar_settings' in migrated_data:
            colorbar_settings = migrated_data['colorbar_settings']
            
            # 迁移 auto_range 到 smart_range
            if 'auto_range' in colorbar_settings:
                auto_range = colorbar_settings.pop('auto_range')
                
                if not auto_range:
                    # 之前是手动模式，禁用智能范围计算
                    colorbar_settings['smart_range'] = False
                    self.migration_log.append("检测到手动色标范围模式，已禁用智能范围计算")
                else:
                    # 之前是自动模式，保持smart_range设置不变
                    if 'smart_range' not in colorbar_settings:
                        colorbar_settings['smart_range'] = False
                    self.migration_log.append("检测到自动色标范围模式，已保持智能范围计算设置")
                
                migration_occurred = True
                self.migration_log.append(f"已移除auto_range字段，当前smart_range={colorbar_settings.get('smart_range', False)}")
        
        # 更新版本号
        if migration_occurred:
            migrated_data['version'] = self.CURRENT_VERSION
            migrated_data['migrated_at'] = datetime.now().isoformat()
        
        return migrated_data, migration_occurred


class UserExperienceTransition:
    """用户体验过渡工具类"""
    
    def __init__(self):
        """初始化用户体验过渡工具"""
        pass
    
    def show_migration_notice(self, migration_occurred: bool, migration_log: List[str]) -> None:
        """显示迁移通知
        
        Args:
            migration_occurred: 是否发生了迁移
            migration_log: 迁移日志
        """
        if migration_occurred:
            logger.info("配置迁移完成")
            for log_entry in migration_log:
                logger.info(f"迁移: {log_entry}")
        else:
            logger.debug("无需配置迁移")
    
    def show_feature_introduction(self, feature_name: str, description: str) -> None:
        """显示新功能介绍
        
        Args:
            feature_name: 功能名称
            description: 功能描述
        """
        logger.info(f"新功能介绍: {feature_name} - {description}")
    
    def show_deprecation_warning(self, deprecated_feature: str, replacement: str) -> None:
        """显示弃用警告
        
        Args:
            deprecated_feature: 被弃用的功能
            replacement: 替代功能
        """
        logger.warning(f"弃用警告: {deprecated_feature} 已被弃用，请使用 {replacement} 替代")