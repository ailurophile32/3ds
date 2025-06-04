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