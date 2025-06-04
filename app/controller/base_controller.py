"""
基础控制器模块

提供所有控制器类的基础功能和接口定义。
"""
from typing import Dict, Any, Callable, Optional

from app.model.base_model import BaseModel
from app.view.base_view import BaseView


class BaseController:
    """控制器基类，提供通用功能和接口"""
    
    def __init__(self, model: BaseModel, view: BaseView):
        """初始化基础控制器
        
        Args:
            model: 模型对象
            view: 视图对象
        """
        self.model = model
        self.view = view
        
        # 注册模型观察者
        self.model.add_observer(self.on_model_changed)
    
    def on_model_changed(self, event_type: str, data: Any) -> None:
        """处理模型变化事件
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        # 子类应该重写此方法以处理特定的模型变化事件
        pass
    
    def init_callbacks(self) -> None:
        """初始化视图回调函数
        
        子类应该重写此方法以注册特定的视图回调
        """
        pass
    
    def handle_exception(self, exception: Exception, context: str = "") -> None:
        """处理异常
        
        Args:
            exception: 异常对象
            context: 异常发生的上下文描述
        """
        error_message = f"{context}错误: {str(exception)}"
        print(f"错误: {error_message}")
        self.view.show_error("操作失败", error_message)
        self.view.update_status(f"操作失败: {str(exception)}")
    
    def save_config(self, config_path: str) -> None:
        """保存配置到文件
        
        Args:
            config_path: 配置文件路径
        """
        try:
            if self.model.save_config(config_path):
                self.view.update_status(f"配置已保存到: {config_path}")
            else:
                self.view.show_warning("保存配置", "保存配置失败")
        except Exception as e:
            self.handle_exception(e, "保存配置")
    
    def load_config(self, config_path: str) -> None:
        """从文件加载配置
        
        Args:
            config_path: 配置文件路径
        """
        try:
            if self.model.load_config(config_path):
                self.view.update_status(f"配置已从 {config_path} 加载")
            else:
                self.view.show_warning("加载配置", "加载配置失败或文件不存在")
        except Exception as e:
            self.handle_exception(e, "加载配置") 