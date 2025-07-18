"""
SiC应力可视化应用 - MVC模式实现

该应用用于可视化半导体材料SiC（碳化硅）的应力分布，
支持2D圆形热力图和3D多层热力图的生成与交互。
"""
import sys
import locale
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app import __version__
from app.controller.heatmap_controller import HeatmapController
from app.model.heatmap_model import HeatmapModel
from app.view.heatmap_view import HeatmapView


def setup_encoding():
    """设置输出编码以确保正确显示中文"""
    # 强制设置stdout和stderr编码为UTF-8 (Python 3.7+)
    if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding != 'utf-8':
        try:
            # 使用 getattr 和 type: ignore 来避免类型检查器警告
            reconfigure_method = getattr(sys.stdout, 'reconfigure', None)
            if reconfigure_method:
                reconfigure_method(encoding='utf-8')
        except Exception:
            pass
            
    if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding != 'utf-8':
        try:
            # 使用 getattr 和 type: ignore 来避免类型检查器警告
            reconfigure_method = getattr(sys.stderr, 'reconfigure', None)
            if reconfigure_method:
                reconfigure_method(encoding='utf-8')
        except Exception:
            pass

    # 设置控制台输出编码
    if sys.platform.startswith('win'):
        try:
            # 尝试设置UTF-8编码
            locale.setlocale(locale.LC_ALL, 'zh_CN.UTF-8')
        except locale.Error:
            try:
                # 如果UTF-8失败，使用系统默认编码
                locale.setlocale(locale.LC_ALL, '')
            except locale.Error:
                pass


def run_command_line_mode(args):
    """命令行模式处理函数"""
    model = HeatmapModel()
    
    # 处理所有传入的CSV文件
    csv_files = args
    for i, csv_file in enumerate(csv_files):
        if Path(csv_file).exists():
            # 为每个CSV文件设置不同的Z深度
            z_depth = float(input(f"请为 {Path(csv_file).name} 输入Z轴深度值 (μm): ") or f"{i*10}.0")
            if model.load_csv(csv_file, z_depth):
                print(f"成功加载 {Path(csv_file).name}, Z轴深度: {z_depth}μm")
            else:
                print(f"加载 {Path(csv_file).name} 失败")
        else:
            print(f"文件不存在: {csv_file}")
    
    # 检查是否成功加载了至少一个文件
    if model.get_dataset_count() > 0:
        # 为每个CSV生成单独的2D图
        for i in range(model.get_dataset_count()):
            data, z_depth, file_name = model.data_sets[i]
            fig_2d = model.create_circular_heatmap_2d(i)
            output_2d = f"{file_name.replace('.csv', '')}_2d_z{z_depth}.png"
            model.save_heatmap(output_2d, '2d')
            print(f"{file_name}的2D热力图已生成并保存为: {output_2d}")
        
        # 生成包含所有层的3D图
        if model.get_dataset_count() > 1:
            fig_3d = model.create_plotly_3d_heatmap()
            output_3d = "multi_layer_3d_heatmap.html"
            model.save_heatmap(output_3d, 'plotly')
            print(f"多层3D热力图已生成并保存为: {output_3d}")
        else:
            # 单层也生成3D图
            fig_3d = model.create_plotly_3d_heatmap()
            data, z_depth, file_name = model.data_sets[0]
            output_3d = f"{file_name.replace('.csv', '')}_3d_z{z_depth}.html"
            model.save_heatmap(output_3d, 'plotly')
            print(f"{file_name}的3D热力图已生成并保存为: {output_3d}")
    else:
        print("未成功加载任何CSV文件")


def run_gui_mode():
    """GUI模式处理函数"""
    app = QApplication(sys.argv)
    
    # 设置应用程序字体
    font = app.font()
    font.setFamily('Microsoft YaHei')
    app.setFont(font)
    
    # 显示欢迎信息
    print("\n===== SiC应力圆形热力图生成器 - 多层3D可视化 =====")
    print(f"版本: {__version__}")
    print("使用Plotly+WebGL高性能渲染引擎")
    print("支持交互式3D可视化，鼠标左键旋转，右键平移，滚轮缩放")
    print("=============================================\n")
    
    # 创建MVC组件
    model = HeatmapModel()
    view = HeatmapView()
    controller = HeatmapController(model, view)
    
    # 显示视图并运行应用
    view.show()
    return app.exec()


def main():
    """主函数"""
    # 设置编码
    setup_encoding()
    
    # 检查是否有命令行参数指定CSV文件
    if len(sys.argv) > 1:
        # 命令行模式：直接生成热力图
        run_command_line_mode(sys.argv[1:])
    else:
        # GUI模式
        return run_gui_mode()


if __name__ == "__main__":
    sys.exit(main()) 