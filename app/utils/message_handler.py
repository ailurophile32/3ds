"""
消息处理工具模块

用于在应用中显示消息、警告和错误对话框，提供统一的用户反馈机制。
"""
from PySide6.QtWidgets import QMessageBox


class MessageHandler:
    """消息处理器类，负责显示各种对话框"""
    
    def __init__(self, parent=None):
        """初始化消息处理器
        
        Args:
            parent: 父窗口对象，用于对话框的模态显示
        """
        self.parent = parent
    
    def show_info(self, title: str, message: str):
        """显示信息对话框
        
        Args:
            title: 对话框标题
            message: 对话框消息内容
        """
        msg_box = QMessageBox(self.parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.exec()
    
    def show_warning(self, title: str, message: str):
        """显示警告对话框
        
        Args:
            title: 对话框标题
            message: 对话框消息内容
        """
        msg_box = QMessageBox(self.parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.exec()
    
    def show_error(self, title: str, message: str):
        """显示错误对话框
        
        Args:
            title: 对话框标题
            message: 对话框消息内容
        """
        msg_box = QMessageBox(self.parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.exec()
    
    def show_question(self, title: str, message: str) -> bool:
        """显示问题对话框
        
        Args:
            title: 对话框标题
            message: 对话框消息内容
            
        Returns:
            bool: 用户是否点击了确认按钮
        """
        reply = QMessageBox.question(
            self.parent, title, message,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        return reply == QMessageBox.Yes 