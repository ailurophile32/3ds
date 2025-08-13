"""
消息处理工具模块 - 增强版本

用于在应用中显示消息、警告和错误对话框，提供统一的用户反馈机制。
增强功能包括性能信息显示、详细错误报告和用户提示。
"""
from typing import List, Dict, Any
from PySide6.QtWidgets import QMessageBox, QTextEdit, QVBoxLayout, QWidget, QLabel, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt


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
    
    def show_detailed_error(self, title: str, message: str, details: str = None, 
                          suggestions: List[str] = None):
        """显示详细错误对话框，包含错误详情和解决建议
        
        Args:
            title: 对话框标题
            message: 主要错误消息
            details: 详细错误信息（可选）
            suggestions: 解决建议列表（可选）
        """
        msg_box = QMessageBox(self.parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Critical)
        
        # 构建详细信息
        detailed_text = ""
        if details:
            detailed_text += f"详细信息:\n{details}\n\n"
        
        if suggestions:
            detailed_text += "建议解决方案:\n"
            for i, suggestion in enumerate(suggestions, 1):
                detailed_text += f"{i}. {suggestion}\n"
        
        if detailed_text:
            msg_box.setDetailedText(detailed_text)
        
        msg_box.exec()
    
    def show_memory_error(self, message: str, suggestions: List[str] = None):
        """显示内存不足错误对话框，提供具体的解决建议
        
        Args:
            message: 错误消息
            suggestions: 解决建议列表
        """
        default_suggestions = [
            "关闭其他应用程序释放内存",
            "降低数据处理分辨率",
            "减少同时加载的数据集数量",
            "重启应用程序清理内存",
            "考虑升级系统内存"
        ]
        
        all_suggestions = (suggestions or []) + default_suggestions
        
        self.show_detailed_error(
            "内存不足",
            message,
            "系统内存不足以完成当前操作。这通常发生在处理大数据集或高分辨率图像时。",
            all_suggestions
        )
    
    def show_performance_info(self, title: str, stats: Dict[str, Any]):
        """显示性能统计信息对话框
        
        Args:
            title: 对话框标题
            stats: 性能统计数据
        """
        msg_box = QMessageBox(self.parent)
        msg_box.setWindowTitle(title)
        msg_box.setIcon(QMessageBox.Information)
        
        # 构建性能信息文本
        info_text = "性能统计信息:\n\n"
        
        if 'interpolation_summary' in stats:
            summary = stats['interpolation_summary']
            info_text += f"插值操作统计:\n"
            info_text += f"  总次数: {summary['count']}\n"
            info_text += f"  平均耗时: {summary['avg_duration']:.3f}秒\n"
            info_text += f"  最大耗时: {summary['max_duration']:.3f}秒\n"
            info_text += f"  最小耗时: {summary['min_duration']:.3f}秒\n\n"
        
        if 'memory_summary' in stats:
            summary = stats['memory_summary']
            info_text += f"内存使用统计:\n"
            info_text += f"  当前使用: {summary['current_mb']:.1f}MB\n"
            info_text += f"  最大使用: {summary['max_mb']:.1f}MB\n"
            info_text += f"  平均使用: {summary['avg_mb']:.1f}MB\n"
        
        msg_box.setText(info_text)
        msg_box.exec()
    
    def show_operation_logs(self, title: str, logs: List[str], max_lines: int = 100):
        """显示操作日志对话框
        
        Args:
            title: 对话框标题
            logs: 日志条目列表
            max_lines: 最大显示行数
        """
        # 创建自定义对话框
        dialog = QMessageBox(self.parent)
        dialog.setWindowTitle(title)
        dialog.setIcon(QMessageBox.Information)
        
        # 限制显示的日志行数
        display_logs = logs[-max_lines:] if len(logs) > max_lines else logs
        
        if len(logs) > max_lines:
            log_text = f"显示最近 {max_lines} 条日志（共 {len(logs)} 条）:\n\n"
        else:
            log_text = f"操作日志（共 {len(logs)} 条）:\n\n"
        
        log_text += "\n".join(display_logs)
        
        dialog.setDetailedText(log_text)
        dialog.setText("点击 'Show Details' 查看详细日志")
        dialog.exec()
    
    def show_data_validation_warning(self, file_name: str, issues: List[str]):
        """显示数据验证警告对话框
        
        Args:
            file_name: 文件名
            issues: 发现的问题列表
        """
        message = f"文件 '{file_name}' 存在数据质量问题，但已尝试自动修复："
        
        details = "发现的问题:\n"
        for i, issue in enumerate(issues, 1):
            details += f"{i}. {issue}\n"
        
        details += "\n建议:\n"
        details += "• 检查原始数据文件的完整性\n"
        details += "• 确认数据格式符合要求（X, Y, Value列）\n"
        details += "• 如果问题持续存在，请联系技术支持"
        
        self.show_detailed_error("数据质量警告", message, details) 