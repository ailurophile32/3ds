"""
基础模型模块

提供所有模型类的基础功能和接口定义。
"""
from typing import Dict, Any, List, Optional, Callable
import json
import os
from pathlib import Path


class BaseModel:
    """模型基类，提供通用功能和接口"""
    
    def __init__(self):
        """初始化基础模型"""
        self._observers: List[Callable] = []
        self._config: Dict[str, Any] = {}
    
    def add_observer(self, callback: Callable) -> None:
        """添加观察者回调函数
        
        Args:
            callback: 回调函数，当模型数据变化时会被调用
        """
        if callback not in self._observers:
            self._observers.append(callback)
    
    def remove_observer(self, callback: Callable) -> None:
        """移除观察者回调函数
        
        Args:
            callback: 要移除的回调函数
        """
        if callback in self._observers:
            self._observers.remove(callback)
    
    def notify_observers(self, event_type: str, data: Any = None) -> None:
        """通知所有观察者模型发生了变化
        
        Args:
            event_type: 事件类型
            data: 事件相关数据
        """
        for callback in self._observers:
            callback(event_type, data)
    
    def load_config(self, config_path: str) -> bool:
        """从JSON文件加载配置
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            bool: 加载是否成功
        """
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                
                # 执行配置迁移
                self._migrate_config()
                return True
            return False
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return False
    
    def save_config(self, config_path: str) -> bool:
        """保存配置到JSON文件
        
        Args:
            config_path: 配置文件保存路径
            
        Returns:
            bool: 保存是否成功
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置值
        
        Args:
            key: 配置键名
            default: 默认值，当键不存在时返回
            
        Returns:
            Any: 配置值或默认值
        """
        return self._config.get(key, default)
    
    def set_config(self, key: str, value: Any) -> None:
        """设置配置值
        
        Args:
            key: 配置键名
            value: 配置值
        """
        self._config[key] = value
        # 配置变更时通知观察者
        self.notify_observers('config_changed', {key: value})
    
    def _migrate_config(self) -> None:
        """迁移配置文件，处理版本兼容性问题
        
        处理从旧版本配置到新版本配置的迁移，确保向后兼容性
        """
        # 迁移色标卡设置：移除auto_range字段
        if 'colorbar_settings' in self._config:
            colorbar_settings = self._config['colorbar_settings']
            
            # 如果存在auto_range字段，进行迁移
            if 'auto_range' in colorbar_settings:
                auto_range = colorbar_settings.pop('auto_range')  # 移除auto_range字段
                
                # 迁移逻辑：
                # 1. 如果auto_range为False，说明用户之前使用手动模式
                #    此时应该禁用smart_range，保持手动设置的行为
                # 2. 如果auto_range为True，保持smart_range的当前设置
                if not auto_range:
                    # 之前是手动模式，禁用智能范围计算
                    colorbar_settings['smart_range'] = False
                    print("配置迁移: 检测到手动色标范围模式，已禁用智能范围计算")
                else:
                    # 之前是自动模式，保持smart_range设置不变
                    # 如果smart_range不存在，设置为默认值False
                    if 'smart_range' not in colorbar_settings:
                        colorbar_settings['smart_range'] = False
                    print("配置迁移: 检测到自动色标范围模式，已保持智能范围计算设置")
                
                print(f"配置迁移完成: 已移除auto_range字段，当前smart_range={colorbar_settings.get('smart_range', False)}")
        
        # 可以在这里添加其他配置迁移逻辑