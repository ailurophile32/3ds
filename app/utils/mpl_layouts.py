"""
Matplotlib 布局工具

提供通用的 "主图轴 + 独立色标轴" 创建函数，保持不同模块一致的图面布局。
"""
from typing import Tuple

from matplotlib.figure import Figure


def create_main_and_colorbar_axes(
    figsize: Tuple[int, int] = (10, 6),
    width_ratio_main: int = 20,
    width_ratio_cbar: int = 1,
    wspace: float = 0.05,
) -> Tuple[Figure, object, object]:
    """创建包含主图轴与独立色标轴的 Figure 与 Axes。

    Args:
        figsize: 图尺寸 (width, height)。
        width_ratio_main: 主图列宽权重。
        width_ratio_cbar: 色标列宽权重。
        wspace: 子图间水平间距。

    Returns:
        (fig, ax, cax)
    """
    from matplotlib import gridspec

    fig = Figure(figsize=figsize, facecolor="white", constrained_layout=False)
    gs = gridspec.GridSpec(
        1, 2, width_ratios=[width_ratio_main, width_ratio_cbar], wspace=wspace, figure=fig
    )
    ax = fig.add_subplot(gs[0, 0])
    cax = fig.add_subplot(gs[0, 1])
    return fig, ax, cax


