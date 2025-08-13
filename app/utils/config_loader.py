"""
配置加载器模块

提供配置文件的加载、保存和迁移功能，确保向后兼容性
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

from app.utils.config import DefaultSettings
from app.utils.config_migration import ConfigMigration, UserExperienceTransition

logger = logging.getLogger(__name__)


class ConfigLoader:
    """配置加载器类，处理配置文件的加载、保存和迁移"""
    
    def __init__(self, config_dir: str = None):
        """初始化配置加载器
        
        Args:
            config_dir: 配置目录路径，如果为None则使用默认路径
        """
        if config_dir is None:
            # 使用用户主目录下的配置目录
            self.config_dir = Path.home() / ".sic_stress_visualizer"
        else:
            self.config_dir = Path(config_dir)
        
        # 确保配置目录存在
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # 主配置文件路径
        self.config_file = self.config_dir / "config.json"
        
        # 初始化迁移工具
        self.migration_tool = ConfigMigration()
        self.transition_tool = UserExperienceTransition()
        
        # 缓存的配置数据
        self._cached_config = None
        self._config_loaded = False
    
    def load_config(self, force_reload: bool = False) -> Dict[str, Any]:
        """加载配置文件，自动处理迁移
        
        Args:
            force_reload: 是否强制重新加载
            
        Returns:
            Dict[str, Any]: 配置数据
        """
        # 如果已缓存且不强制重新加载，返回缓存的配置
        if self._cached_config is not None and not force_reload:
            return self._cached_config
        
        try:
            # 检查配置文件是否存在
            if not self.config_file.exists():
                logger.info("配置文件不存在，创建默认配置")
                config_data = self._create_default_config()
            else:
                # 加载现有配置文件
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # 检查是否需要迁移
                if self.migration_tool.detect_legacy_config(config_data):
                    logger.info("检测到旧版本配置，开始迁移")
                    config_data = self._migrate_config(config_data)
                else:
                    logger.info("配置文件已是最新版本")
            
            # 验证配置完整性
            config_data = self._ensure_config_completeness(config_data)
            
            # 缓存配置
            self._cached_config = config_data
            self._config_loaded = True
            
            return config_data
            
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            # 返回默认配置作为回退
            return self._create_default_config()
    
    def save_config(self, config_data: Dict[str, Any]) -> bool:
        """保存配置文件
        
        Args:
            config_data: 要保存的配置数据
            
        Returns:
            bool: 是否保存成功
        """
        try:
            # 确保配置目录存在
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            # 添加版本信息
            config_data = config_data.copy()
            config_data['version'] = self.migration_tool.CURRENT_VERSION
            config_data['last_updated'] = self._get_current_timestamp()
            
            # 写入配置文件
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            # 更新缓存
            self._cached_config = config_data
            
            logger.info(f"配置已保存到: {self.config_file}")
            return True
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False
    
    def get_colorbar_settings(self) -> Dict[str, Any]:
        """获取色标卡设置
        
        Returns:
            Dict[str, Any]: 色标卡设置
        """
        config = self.load_config()
        return config.get('colorbar_settings', DefaultSettings.get_colorbar_settings())
    
    def update_colorbar_settings(self, settings: Dict[str, Any]) -> bool:
        """更新色标卡设置
        
        Args:
            settings: 新的色标卡设置
            
        Returns:
            bool: 是否更新成功
        """
        try:
            config = self.load_config()
            
            # 更新色标卡设置
            if 'colorbar_settings' not in config:
                config['colorbar_settings'] = DefaultSettings.get_colorbar_settings()
            
            config['colorbar_settings'].update(settings)
            
            # 保存配置
            return self.save_config(config)
            
        except Exception as e:
            logger.error(f"更新色标卡设置失败: {e}")
            return False
    
    def get_performance_settings(self) -> Dict[str, Any]:
        """获取性能设置
        
        Returns:
            Dict[str, Any]: 性能设置
        """
        config = self.load_config()
        return config.get('performance_settings', DefaultSettings.get_performance_settings())
    
    def update_performance_settings(self, settings: Dict[str, Any]) -> bool:
        """更新性能设置
        
        Args:
            settings: 新的性能设置
            
        Returns:
            bool: 是否更新成功
        """
        try:
            config = self.load_config()
            
            # 更新性能设置
            if 'performance_settings' not in config:
                config['performance_settings'] = DefaultSettings.get_performance_settings()
            
            config['performance_settings'].update(settings)
            
            # 保存配置
            return self.save_config(config)
            
        except Exception as e:
            logger.error(f"更新性能设置失败: {e}")
            return False
    
    def _create_default_config(self) -> Dict[str, Any]:
        """创建默认配置
        
        Returns:
            Dict[str, Any]: 默认配置数据
        """
        default_config = {
            'version': self.migration_tool.CURRENT_VERSION,
            'created_at': self._get_current_timestamp(),
            'colorbar_settings': DefaultSettings.get_colorbar_settings(),
            'performance_settings': DefaultSettings.get_performance_settings(),
            'ui_settings': {
                'current_colormap': 'coolwarm',
                'current_interpolation': 'rbf',
                'x_axis_flipped': False
            },
            'recent_files': [],
            'window_geometry': None
        }
        
        # 保存默认配置
        self.save_config(default_config)
        
        logger.info("已创建默认配置")
        return default_config
    
    def _migrate_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """迁移配置数据
        
        Args:
            config_data: 原始配置数据
            
        Returns:
            Dict[str, Any]: 迁移后的配置数据
        """
        try:
            # 备份原始配置
            backup_path = f"{self.config_file}.backup"
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            logger.info(f"已备份原始配置到: {backup_path}")
            
            # 执行迁移
            migrated_data, migration_occurred = self.migration_tool.migrate_config_data(config_data)
            
            if migration_occurred:
                # 添加迁移信息
                migrated_data['migration_info'] = {
                    'migrated_at': self._get_current_timestamp(),
                    'from_version': self.migration_tool.LEGACY_VERSION,
                    'to_version': self.migration_tool.CURRENT_VERSION,
                    'migration_log': self.migration_tool.migration_log.copy()
                }
                
                # 保存迁移后的配置
                self.save_config(migrated_data)
                
                # 显示迁移通知
                self.transition_tool.show_migration_notice(
                    migration_occurred, 
                    self.migration_tool.migration_log
                )
                
                logger.info("配置迁移完成")
            
            return migrated_data
            
        except Exception as e:
            logger.error(f"配置迁移失败: {e}")
            # 返回原始配置作为回退
            return config_data
    
    def _ensure_config_completeness(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """确保配置完整性，补充缺失的字段
        
        Args:
            config_data: 配置数据
            
        Returns:
            Dict[str, Any]: 完整的配置数据
        """
        complete_config = config_data.copy()
        
        # 确保色标卡设置完整
        if 'colorbar_settings' not in complete_config:
            complete_config['colorbar_settings'] = DefaultSettings.get_colorbar_settings()
        else:
            default_colorbar = DefaultSettings.get_colorbar_settings()
            for key, value in default_colorbar.items():
                if key not in complete_config['colorbar_settings']:
                    complete_config['colorbar_settings'][key] = value
        
        # 确保性能设置完整
        if 'performance_settings' not in complete_config:
            complete_config['performance_settings'] = DefaultSettings.get_performance_settings()
        else:
            default_performance = DefaultSettings.get_performance_settings()
            for key, value in default_performance.items():
                if key not in complete_config['performance_settings']:
                    complete_config['performance_settings'][key] = value
        
        # 确保UI设置完整
        if 'ui_settings' not in complete_config:
            complete_config['ui_settings'] = {
                'current_colormap': 'coolwarm',
                'current_interpolation': 'rbf',
                'x_axis_flipped': False
            }
        
        # 确保版本信息
        if 'version' not in complete_config:
            complete_config['version'] = self.migration_tool.CURRENT_VERSION
        
        return complete_config
    
    def _get_current_timestamp(self) -> str:
        """获取当前时间戳
        
        Returns:
            str: ISO格式的时间戳
        """
        from datetime import datetime
        return datetime.now().isoformat()
    
    def reset_to_defaults(self) -> bool:
        """重置配置为默认值
        
        Returns:
            bool: 是否重置成功
        """
        try:
            # 备份当前配置
            if self.config_file.exists():
                backup_path = f"{self.config_file}.reset_backup"
                with open(self.config_file, 'r', encoding='utf-8') as src:
                    with open(backup_path, 'w', encoding='utf-8') as dst:
                        dst.write(src.read())
                logger.info(f"已备份当前配置到: {backup_path}")
            
            # 创建默认配置
            default_config = self._create_default_config()
            
            # 清除缓存
            self._cached_config = None
            self._config_loaded = False
            
            logger.info("配置已重置为默认值")
            return True
            
        except Exception as e:
            logger.error(f"重置配置失败: {e}")
            return False
    
    def export_config(self, export_path: str) -> bool:
        """导出配置到指定路径
        
        Args:
            export_path: 导出路径
            
        Returns:
            bool: 是否导出成功
        """
        try:
            config = self.load_config()
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"配置已导出到: {export_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出配置失败: {e}")
            return False
    
    def import_config(self, import_path: str) -> bool:
        """从指定路径导入配置
        
        Args:
            import_path: 导入路径
            
        Returns:
            bool: 是否导入成功
        """
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                imported_config = json.load(f)
            
            # 检查是否需要迁移
            if self.migration_tool.detect_legacy_config(imported_config):
                logger.info("导入的配置需要迁移")
                imported_config = self._migrate_config(imported_config)
            
            # 确保配置完整性
            imported_config = self._ensure_config_completeness(imported_config)
            
            # 保存导入的配置
            success = self.save_config(imported_config)
            
            if success:
                logger.info(f"配置已从 {import_path} 导入")
            
            return success
            
        except Exception as e:
            logger.error(f"导入配置失败: {e}")
            return False
    
    def get_config_info(self) -> Dict[str, Any]:
        """获取配置信息
        
        Returns:
            Dict[str, Any]: 配置信息
        """
        config = self.load_config()
        
        return {
            'config_file': str(self.config_file),
            'config_dir': str(self.config_dir),
            'version': config.get('version', 'unknown'),
            'created_at': config.get('created_at', 'unknown'),
            'last_updated': config.get('last_updated', 'unknown'),
            'migration_info': config.get('migration_info'),
            'file_exists': self.config_file.exists(),
            'file_size': self.config_file.stat().st_size if self.config_file.exists() else 0
        }


# 全局配置加载器实例
_global_config_loader = None


def get_config_loader(config_dir: str = None) -> ConfigLoader:
    """获取全局配置加载器实例
    
    Args:
        config_dir: 配置目录路径
        
    Returns:
        ConfigLoader: 配置加载器实例
    """
    global _global_config_loader
    
    if _global_config_loader is None:
        _global_config_loader = ConfigLoader(config_dir)
    
    return _global_config_loader


def load_application_config() -> Dict[str, Any]:
    """加载应用程序配置的便捷函数
    
    Returns:
        Dict[str, Any]: 应用程序配置
    """
    loader = get_config_loader()
    return loader.load_config()


def save_application_config(config_data: Dict[str, Any]) -> bool:
    """保存应用程序配置的便捷函数
    
    Args:
        config_data: 配置数据
        
    Returns:
        bool: 是否保存成功
    """
    loader = get_config_loader()
    return loader.save_config(config_data)


if __name__ == "__main__":
    # 测试配置加载器
    import tempfile
    import shutil
    
    # 创建临时配置目录
    temp_dir = tempfile.mkdtemp()
    
    try:
        # 创建测试用的旧配置文件
        old_config = {
            "colorbar_settings": {
                "auto_range": True,
                "smart_range": False,
                "vmin": -50,
                "vmax": 50
            },
            "performance_settings": {
                "resolution": 150
            }
        }
        
        config_file = Path(temp_dir) / "config.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(old_config, f, indent=2)
        
        print(f"创建测试配置文件: {config_file}")
        print("原始配置:")
        print(json.dumps(old_config, indent=2, ensure_ascii=False))
        
        # 测试配置加载器
        loader = ConfigLoader(temp_dir)
        
        print("\n加载配置...")
        loaded_config = loader.load_config()
        
        print("\n加载后的配置:")
        print(json.dumps(loaded_config, indent=2, ensure_ascii=False))
        
        print("\n配置信息:")
        config_info = loader.get_config_info()
        for key, value in config_info.items():
            print(f"{key}: {value}")
        
    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir)
        print(f"\n已清理临时目录: {temp_dir}")