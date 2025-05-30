# SiC应力分布可视化工具

一款专为SiC（碳化硅）应力分布数据创建2D和3D热力图的可视化工具。支持多层数据的3D可视化，具有GPU加速功能。

## 主要功能

- 导入CSV格式的应力数据
- 生成漂亮的2D圆形热力图
- 创建多层3D热力图，支持交互式旋转
- 使用WebGL技术进行高性能3D渲染
- 可调节的性能参数，适应不同级别的硬件
- 支持数据降采样以提高性能
- 可保存高质量的PNG、PDF或SVG图像

## 安装方法

### 使用uv（推荐）

[uv](https://github.com/astral-sh/uv) 是一个超快的Python包安装器和解析器。首先安装uv:

```bash
# 在Windows上安装uv
curl -sSf https://astral.sh/uv/install.ps1 | powershell

# 在macOS/Linux上安装uv
curl -sSf https://astral.sh/uv/install.sh | bash
```

然后使用uv创建虚拟环境并安装依赖:

```bash
# 创建虚拟环境
uv venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 安装依赖
uv pip install -r requirements.txt
# 或者使用pyproject.toml
uv pip install -e .
```

### 使用传统的pip

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

## 运行方法

```bash
# 直接运行
python main.py

# 或者如果已经安装为包
sic-visualizer
```

## 使用方法

1. 点击"添加CSV"按钮导入数据文件
2. 为每个数据层设置Z轴深度值
3. 使用"生成2D热力图"或"生成3D多层热力图"按钮创建可视化
4. 通过"3D性能设置"调整性能参数
5. 使用"保存当前图像"保存结果

## CSV文件格式

程序接受以下格式的CSV文件:

```
X,Y,Value
100.5,200.3,35.6
101.2,205.7,42.1
...
```

其中：
- `X`、`Y`：数据点的坐标（单位：μm）
- `Value`：应力值（单位：MPa）

## 性能优化

如需获得最佳性能，特别是对于3D可视化：

1. 在"3D性能设置"中根据您的硬件调整参数
3. 对于大型数据集，增加数据抽样率
4. 减小分辨率值可提高旋转流畅度

## 命令行用法

除了GUI界面，该工具还支持命令行操作：

```bash
python main.py data1.csv data2.csv data3.csv
```

将为每个CSV文件创建单独的2D和3D可视化图像。

## 系统需求

- Python 3.9+
- 支持WebGL的现代浏览器内核可实现更好的3D性能

## 许可证

MIT

