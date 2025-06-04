"""
基础视图模块

提供所有视图类的基础功能和接口定义。
"""
from typing import Dict, Any, Callable, Optional

from PySide6.QtWidgets import QMainWindow, QStatusBar, QLabel

from app.utils.message_handler import MessageHandler


class BaseView(QMainWindow):
    """视图基类，提供通用功能和接口"""
    
    def __init__(self, title: str = "应用程序", width: int = 800, height: int = 600):
        """初始化基础视图
        
        Args:
            title: 窗口标题
            width: 窗口宽度
            height: 窗口高度
        """
        super().__init__()
        self.setWindowTitle(title)
        self.setGeometry(100, 100, width, height)
        
        # 设置应用程序字体
        font = self.font()
        font.setFamily('Microsoft YaHei')
        self.setFont(font)
        
        # 创建状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("就绪")
        self.status_bar.addWidget(self.status_label)
        
        # 消息处理器
        self.message_handler = MessageHandler(self)
        
        # 回调函数字典
        self.callbacks: Dict[str, Optional[Callable]] = {}
    
    def register_callback(self, event_name: str, callback: Callable) -> None:
        """注册事件回调函数
        
        Args:
            event_name: 事件名称
            callback: 回调函数
        """
        self.callbacks[event_name] = callback
    
    def trigger_callback(self, event_name: str, *args, **kwargs) -> Any:
        """触发回调函数
        
        Args:
            event_name: 事件名称
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            Any: 回调函数的返回值，如果回调不存在则返回None
        """
        if event_name in self.callbacks and self.callbacks[event_name] is not None:
            return self.callbacks[event_name](*args, **kwargs)
        return None
    
    def update_status(self, message: str) -> None:
        """更新状态栏消息
        
        Args:
            message: 状态消息
        """
        self.status_label.setText(message)
    
    def show_info(self, title: str, message: str) -> None:
        """显示信息对话框
        
        Args:
            title: 对话框标题
            message: 对话框消息
        """
        self.message_handler.show_info(title, message)
    
    def show_warning(self, title: str, message: str) -> None:
        """显示警告对话框
        
        Args:
            title: 对话框标题
            message: 对话框消息
        """
        self.message_handler.show_warning(title, message)
    
    def show_error(self, title: str, message: str) -> None:
        """显示错误对话框
        
        Args:
            title: 对话框标题
            message: 对话框消息
        """
        self.message_handler.show_error(title, message)
    
    def show_question(self, title: str, message: str) -> bool:
        """显示问题对话框
        
        Args:
            title: 对话框标题
            message: 对话框消息
            
        Returns:
            bool: 用户是否点击了确认按钮
        """
        return self.message_handler.show_question(title, message) 