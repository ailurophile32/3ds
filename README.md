# SiC晶圆应力分析工具



一款专业的SiC（碳化硅）晶圆应力分析与可视化工具，支持多层应力数据的2D/3D可视化、统计分析和差分对比。采用现代化的MVC架构设计，提供流畅的交互体验和高性能的图形渲染。

## ✨ 核心特性

### 📊 数据可视化
- **2D圆形热力图**: 高质量的圆形应力分布图，支持多种色标方案
- **3D多层可视化**: 基于 Plotly + WebGL 的交互式3D热力图，支持旋转、缩放、平移
- **实时交互**: 流畅的用户交互体验，支持拖拽文件、实时预览

### 📈 数据分析
- **统计分析**: 均值、中位数、标准差、偏度、峰度等多维度统计
- **趋势分析**: 应力随深度变化的趋势图，支持多指标对比
- **差分分析**: 层间应力差分云图，凸显应力演变特征
- **梯度分析**: Z轴方向应力梯度的逐点计算与可视化

### 🎨 可视化配置
- **多色标方案**: coolwarm、RdYlBu_r、Spectral、jet 等科学色标
- **智能色标范围**: 自动去除异常值，优化色标映射效果
- **插值算法**: 支持 RBF 和 Griddata 两种高精度插值方法
- **X轴翻转**: 适配不同的坐标系统需求

### ⚡ 性能优化
- **GPU加速**: WebGL 硬件加速渲染，提升 3D 性能
- **数据降采样**: 智能采样策略，平衡质量与性能
- **内存管理**: 优化大数据集处理，防止内存溢出
- **可调参数**: 灵活的性能参数配置，适应不同硬件环境

### 💾 数据管理
- **多文件批量导入**: 支持同时加载多个 CSV 数据文件
- **Z深度设置**: 为每层数据灵活设置深度值
- **拖拽上传**: 支持文件拖拽，简化操作流程
- **多格式导出**: PNG、PDF、SVG、HTML 多种导出格式

## 🛠 技术栈

| 技术 | 用途 | 版本要求 |
|------|------|----------|
| Python | 核心语言 | 3.12+ |
| PySide6 | GUI框架 | 6.5.0+ |
| Matplotlib | 2D绘图引擎 | 3.7.0+ |
| Plotly | 3D可视化 | 5.0.0+ |
| Pandas | 数据处理 | 2.0.0+ |
| NumPy | 数值计算 | 1.24.0+ |
| SciPy | 科学计算/插值 | 1.10.0+ |
| Kaleido | 图像导出 | 0.1.0+ |
| OpenPyXL/xlrd | Excel支持 | 最新版 |
| uv | 包管理工具 | 最新版 |

## 📁 项目结构

项目采用经典的 MVC 架构设计，职责清晰，易于维护和扩展：

```
3ds/
├── app/                      # 应用核心代码
│   ├── controller/           # 控制器层 - 业务逻辑协调
│   │   ├── base_controller.py
│   │   ├── heatmap_controller.py
│   │   ├── statistics_controller.py
│   │   ├── trend_controller.py
│   │   └── difference_controller.py
│   ├── model/                # 模型层 - 数据处理与计算
│   │   ├── base_model.py
│   │   ├── heatmap_model.py
│   │   ├── statistics_model.py
│   │   └── trend_model.py
│   ├── view/                 # 视图层 - 用户界面
│   │   ├── base_view.py
│   │   ├── heatmap_view.py
│   │   ├── statistics_view.py
│   │   ├── trend_view.py
│   │   ├── difference_view.py
│   │   └── difference_window.py
│   └── utils/                # 工具模块
│       ├── config.py         # 配置常量
│       ├── config_loader.py  # 配置加载
│       ├── config_migration.py  # 配置迁移
│       ├── message_handler.py   # 消息处理
│       └── widgets.py        # 自定义UI组件
├── doc/                      # 项目文档
│   ├── ARCHITECTURE.md       # 架构设计文档
│   ├── API.md                # API文档
│   ├── CHANGELOG.md          # 变更日志
│   ├── DEVELOPMENT.md        # 开发指南
│   └── PRD*.md               # 产品需求文档
├── sample/                   # 示例数据
├── main.py                   # 应用入口
├── pyproject.toml            # 项目配置
├── uv.lock                   # 依赖锁定文件
└── README.md                 # 项目说明（本文件）
```

## 🚀 快速开始

### 环境要求

- **操作系统**: Windows 10+, macOS 10.15+, Linux
- **Python**: 3.12 或更高版本
- **内存**: 建议 4GB 以上
- **显卡**: 支持 OpenGL 3.3+ 或 WebGL（用于 3D 渲染加速）

### 安装步骤

#### 方法一：使用 uv（推荐）

[uv](https://github.com/astral-sh/uv) 是一个超快的 Python 包管理工具，可以显著提升安装速度。

1. **安装 uv**

```bash
# Windows (PowerShell)
irm https://astral.sh/uv/install.ps1 | iex

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. **克隆项目并安装依赖**

```bash
# 克隆仓库
git clone <repository-url>
cd 3ds

# 创建虚拟环境
uv venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 同步依赖（根据 uv.lock 和 pyproject.toml）
uv sync

# 或手动安装项目
uv pip install -e .
```

#### 方法二：使用传统 pip

```bash
# 克隆仓库
git clone <repository-url>
cd 3ds

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖
pip install -e .
```

### 运行应用

#### GUI 模式（推荐）

```bash
# 激活虚拟环境后直接运行
python main.py
```

#### 命令行模式

适用于批量处理和自动化脚本：

```bash
# 处理单个文件
python main.py data.csv

# 处理多个文件
python main.py 0um.csv 500um.csv 1000um.csv
```

命令行模式会为每个文件生成 2D 热力图，并自动生成包含所有层的 3D 热力图。

## 📖 使用指南

### 基础工作流程

1. **启动应用**: 运行 `python main.py` 启动 GUI 界面
2. **导入数据**: 
   - 点击"添加CSV"按钮选择文件
   - 或直接拖拽 CSV 文件到窗口
3. **设置深度**: 为每个数据层设置对应的 Z 轴深度值（单位：μm）
4. **生成图表**:
   - "生成2D热力图"：为当前选中的数据层生成 2D 热力图
   - "生成3D多层热力图"：生成包含所有层的交互式 3D 可视化
5. **调整参数**:
   - 选择色标方案（coolwarm、RdYlBu_r、Spectral、jet）
   - 选择插值方法（RBF、Griddata）
   - 调整 Z 轴缩放比例
   - 配置性能参数（分辨率、采样率等）
6. **保存结果**: 点击"保存当前图像"，选择格式（PNG、PDF、SVG、HTML）

### CSV 数据格式要求

程序接受以下格式的 CSV 文件（带表头）：

```csv
X,Y,Value
100.5,200.3,35.6
101.2,205.7,42.1
102.8,198.4,38.3
...
```

**列说明**：
- `X`: X坐标（单位：μm）
- `Y`: Y坐标（单位：μm）
- `Value`: 应力值（单位：MPa）

**数据要求**：
- 支持不规则分布的数据点
- 自动处理 NaN 和缺失值
- 建议每层数据点数量 > 100 以获得较好的插值效果

### 高级功能

#### 统计分析
- 查看每层数据的统计摘要（均值、标准差、偏度、峰度等）
- 生成应力分布直方图和核密度估计曲线
- 导出统计结果为 CSV

#### 趋势分析
- 绘制关键指标随深度变化的趋势图
- 分析应力均匀性演变
- 识别工艺优化方向

#### 差分分析
- 计算任意两层之间的应力差分
- 使用发散型色标（蓝-白-红）凸显变化
- 滤除共同特征，聚焦体应力演变

#### 梯度分析
- 在热力图上选择关键分析点
- 查看各点的 Z 轴应力剖面
- 计算并导出应力梯度数据

### 性能优化建议

处理大数据集或在性能较弱的硬件上运行时：

1. **调整分辨率**: 在"3D性能设置"中降低网格分辨率（默认300，可降至150-200）
2. **增加采样率**: 对大数据集使用数据降采样（如 0.5 表示采样50%的点）
3. **关闭实时预览**: 生成图表后再显示，避免实时更新的性能开销
4. **使用 Griddata**: 相比 RBF，Griddata 插值速度更快（但精度略低）

## 🔧 配置说明

### 配置文件

应用的配置文件位于：
- **Windows**: `C:\Users\<用户名>\.sic_visualizer\config.json`
- **macOS/Linux**: `~/.sic_visualizer/config.json`

### 配置项说明

```json
{
    "version": "1.1.0",
    "performance_settings": {
        "resolution": 300,           // 网格分辨率 (100-500)
        "sampling_rate": 1.0,        // 数据采样率 (0.1-1.0)
        "max_memory_mb": 1024,       // 最大内存限制 (MB)
        "enable_gpu": true           // 启用GPU加速
    },
    "colorbar_settings": {
        "smart_range": false,        // 智能色标范围
        "vmin": null,                // 手动最小值
        "vmax": null,                // 手动最大值
        "symmetric": false           // 对称色标
    },
    "ui_settings": {
        "current_colormap": "coolwarm",      // 当前色标
        "current_interpolation": "rbf",      // 插值方法
        "x_axis_flipped": false,             // X轴翻转
        "window_geometry": [100, 100, 1400, 900]  // 窗口位置和大小
    }
}
```

配置会在应用退出时自动保存，下次启动时自动加载。

## 📚 文档导航

- **[架构文档](doc/ARCHITECTURE.md)**: 深入了解系统设计和技术实现
- **[变更日志](doc/CHANGELOG.md)**: 查看版本历史和更新记录
- **[开发指南](doc/DEVELOPMENT.md)**: 参与项目开发的指引
- **[贡献指南](doc/CONTRIBUTING.md)**: 如何为项目做贡献
- **[API文档](doc/API.md)**: 核心模块和接口说明
- **[产品需求](doc/)**: V1.1及后续版本的规划

### 开发规范

- 遵循 PEP 8 Python 代码规范
- 保持代码简洁（KISS原则）
- 避免过度设计（YAGNI原则）
- 消除代码重复（DRY原则）
- 遵循 SOLID 面向对象设计原则
- 所有代码和注释使用 UTF-8 编码（无BOM）

详见 [CONTRIBUTING.md](doc/CONTRIBUTING.md)

## 🙏 致谢

本项目使用了以下优秀的开源项目：

- [PySide6](https://www.qt.io/qt-for-python) - Qt for Python GUI框架
- [Plotly](https://plotly.com/python/) - 交互式图表库
- [Matplotlib](https://matplotlib.org/) - Python 绘图库
- [SciPy](https://scipy.org/) - 科学计算库
- [Pandas](https://pandas.pydata.org/) - 数据分析库
- [NumPy](https://numpy.org/) - 数值计算库

## 📊 项目状态

- **当前版本**: 1.0.0
- **开发状态**: 稳定版本 ✅
- **下一版本**: V1.1（高级数据分析模块）规划中 🚧
- **Python支持**: 3.12+
- **维护状态**: 活跃维护中

**最后更新**: 2025-10-16
