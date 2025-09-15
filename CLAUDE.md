# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a SiC (Silicon Carbide) stress distribution visualization tool that creates 2D and 3D heatmaps from CSV data files. It's built using Python 3.12+ with a Qt-based GUI (PySide6) following the MVC (Model-View-Controller) architecture pattern.

## Development Commands

### Environment Setup
The project uses `uv` as the package manager (preferred) or standard `pip`:

```bash
# Using uv (recommended)
uv venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
uv sync

# Using pip
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
pip install -e .
```

### Running the Application
```bash
# GUI mode
python main.py

# Command line mode with CSV files
python main.py data1.csv data2.csv data3.csv
```

### Testing
There is a `tests/` directory but no specific test runner is configured in pyproject.toml. Check for test files and run appropriately.

## Architecture Overview

### MVC Structure
The application follows a strict MVC pattern:

- **Model** (`app/model/`): Data processing, CSV loading, heatmap generation logic
- **View** (`app/view/`): Qt-based GUI interface, user interactions
- **Controller** (`app/controller/`): Coordinates between model and view, handles events

### Key Components

#### Core Classes
- `HeatmapModel`: Main data model handling CSV processing and visualization generation
- `HeatmapView`: Main GUI window with controls for data loading and visualization
- `HeatmapController`: Orchestrates model-view interactions and user events

#### Utility Modules
- `app/utils/config.py`: Application configuration and default settings
- `app/utils/message_handler.py`: Centralized message handling for user feedback
- `app/utils/widgets.py`: Custom Qt widgets (PlotlyWebView, dialogs, etc.)

### Data Flow
1. CSV files are loaded through the view → controller → model
2. Each dataset gets assigned a Z-axis depth for 3D visualization
3. Model processes data using interpolation methods (RBF, griddata)
4. Generates either 2D circular heatmaps (matplotlib) or 3D multi-layer plots (Plotly)
5. View displays results through embedded matplotlib canvas or web view

### Visualization Features
- **2D Mode**: Circular heatmaps using matplotlib with customizable colormaps
- **3D Mode**: Multi-layer visualization using Plotly with WebGL rendering
- **Data Range Control**: Smart range calculation or manual range setting
- **Performance Settings**: Configurable parameters for handling large datasets
- **Export Options**: Save as PNG, PDF, SVG, or HTML formats

### Configuration System
- Configuration stored in JSON format with automatic migration support
- Settings include: colormap preferences, performance parameters, UI state
- X-axis flipping functionality for coordinate system adjustments

## File Structure Highlights

- `main.py`: Entry point supporting both GUI and CLI modes
- `app/__init__.py`: Module initialization with matplotlib Chinese font configuration
- `sample/`: Contains example CSV files and corresponding PNG visualizations
- `pyproject.toml`: Project dependencies and metadata (no build scripts defined)

## Key Dependencies

- **PySide6**: Qt-based GUI framework
- **matplotlib**: 2D plotting and visualization
- **Plotly**: Interactive 3D visualization with WebGL
- **pandas/numpy**: Data processing and numerical operations
- **scipy**: Scientific computing (interpolation methods)
- **Kaleido**: Plotly image export capabilities

## Development Notes

- The application supports Chinese text and uses specific font configurations
- Both command-line and GUI modes are supported
- 3D visualizations use WebGL for performance with large datasets
- Color mapping system supports both automatic and manual range setting
- The MVC pattern is strictly enforced with event-driven communication between layers

- 始终用中文回答
