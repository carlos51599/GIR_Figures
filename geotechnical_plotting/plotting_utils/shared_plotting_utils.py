#!/usr/bin/env python3
"""
Shared Plotting Utilities - AI-Optimized Monolith
SESRO GIR Geotechnical Data Visualization

Architectural Overview:

Responsibility:
Provides shared plotting utilities used by both matplotlib and Plotly modules.
Centralizes common functions to eliminate code duplication and ensure consistency
between different plotting backends.

Key Interactions:
- Input: Investigation names, color palettes, filenames
- Output: Color mappings, sanitized filenames, RGB tuples, figure dimensions
- Callers: matplotlib_utils.py, plotly_utils.py

Navigation Guide (use VS Code outline Ctrl+Shift+O):
1. FIGURE SIZE CONFIGURATION: Centralized dimensions for consistent aspect ratios
2. COLOR UTILITIES: hex_to_rgb, hex_to_rgba, create_investigation_color_mapping
3. FILENAME UTILITIES: sanitize_filename

CONFIGURATION ARCHITECTURE:
- No CONFIG access in this module - all functions accept explicit primitives
- Caller scripts extract config and pass as parameters
- 100% testable without config mocking
"""

# Standard library imports
from typing import Dict, List, Tuple, Any


# ═══════════════════════════════════════════════════════════════════════════
# 📐 FIGURE SIZE CONFIGURATION SECTION
# Centralized dimensions for consistent aspect ratios across backends
# MODIFICATION POINT: Adjust these values to change plot dimensions globally
# ═══════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════
# 🔧 PLOT TYPE HELPERS - Extract axis configuration from plot type
# Unified abstraction to eliminate depth vs XY code duplication
# ═══════════════════════════════════════════════════════════════════════════


def get_axis_parameters(plot_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract axis parameters based on plot type.

    This is the core abstraction that unifies depth, XY, and PSD plots.
    All differences between plot types are captured in this single function.

    Args:
        plot_type: One of "depth", "xy", or "psd"
        config: Complete CONFIG dictionary from the plotting script

    Returns:
        Dictionary with keys:
        - x_param: Column name in DataFrame for X-axis data
        - x_display: Display label for X-axis
        - y_param: Column name in DataFrame for Y-axis data
        - y_display: Display label for Y-axis
        - invert_y: Whether Y-axis should be inverted (True for depth plots)
        - log_x: Whether X-axis should use log scale (True for PSD plots)
        - x_side: X-axis position ("top" for depth plots, "bottom" otherwise)
        - output_folder_name: Folder name for output files

    Replaces:
        - Separate config extraction in run_parameter_plotting_pipeline()
        - Separate config extraction in run_dual_parameter_plotting_pipeline()
        - Separate config extraction in run_psd_plotting_pipeline()

    Example:
        >>> axis_params = get_axis_parameters("depth", CONFIG)
        >>> print(axis_params["invert_y"])
        True
        >>> print(axis_params["x_side"])
        "top"

        >>> axis_params = get_axis_parameters("xy", CONFIG)
        >>> print(axis_params["invert_y"])
        False
        >>> print(axis_params["x_display"])
        "Cell Pressure (kPa)"
    """
    if plot_type == "depth":
        # Depth plots: Parameter vs Depth (inverted Y-axis, X at top)
        param_config = config["parameter"]
        return {
            "x_param": param_config["name"],
            "x_display": param_config["display_name"],
            "y_param": "Top Depth",
            "y_display": "Depth (m)",
            "invert_y": True,
            "log_x": False,
            "x_side": "top",
            "output_folder_name": param_config["name"],
            # Source parameter for derived parameters (e.g., Eu uses Cu data)
            "source_param": param_config.get("source_parameter", param_config["name"]),
        }
    elif plot_type == "xy":
        # XY plots: Parameter vs Parameter (standard axes)
        param_config = config["parameter"]
        return {
            "x_param": param_config["x_parameter"],
            "x_display": param_config["x_display_name"],
            "y_param": param_config["y_parameter"],
            "y_display": param_config["y_display_name"],
            "invert_y": False,
            "log_x": False,
            "x_side": "bottom",
            "output_folder_name": param_config["output_folder_name"],
            "source_param": param_config["y_parameter"],  # Y is the primary parameter
        }
    elif plot_type == "psd":
        # PSD plots: Particle Size Distribution (log X-axis)
        param_config = config.get("parameter", {})
        return {
            "x_param": "Particle Size",
            "x_display": "Particle Size (mm)",
            "y_param": "Percentage Passing",
            "y_display": "Percentage Passing (%)",
            "invert_y": False,
            "log_x": True,
            "x_side": "bottom",
            "output_folder_name": param_config.get("name", "PSD"),
            "source_param": "Percentage Passing",
        }
    else:
        raise ValueError(
            f"Unknown plot_type: '{plot_type}'. " f"Valid options: 'depth', 'xy', 'psd'"
        )


def resolve_manual_data_paths(config: Dict[str, Any]) -> Tuple[str, str]:
    """
    Resolve manual data file paths relative to workspace root.

    Extracts path resolution logic that was duplicated in:
    - _execute_phase3c_manual_data_control() (depth pipeline)
    - _execute_dual_phase3c_manual_data_control() (XY pipeline)

    The workspace root is determined as the parent of csv_source_folder.

    Args:
        config: Complete CONFIG dictionary containing:
            - parameter.csv_source_folder: Path to CSV source folder
            - manual_outlier_exclusion.excel_file: Path to Data to Remove.xlsx
            - manual_outlier_exclusion.data_to_add_file: Path to Data to Add.xlsx

    Returns:
        Tuple of (excel_file_path, data_to_add_file_path) as absolute path strings

    Example:
        >>> excel_file, add_file = resolve_manual_data_paths(CONFIG)
        >>> print(excel_file)
        "C:/path/to/workspace/Data to Remove.xlsx"
    """
    from pathlib import Path as PathLib

    # Determine workspace root from csv_source_folder
    csv_source_folder = config["parameter"]["csv_source_folder"]
    csv_folder_path = PathLib(csv_source_folder)
    workspace_root = csv_folder_path.parent

    manual_config = config.get("manual_outlier_exclusion", {})

    # Resolve excel_file path (Data to Remove.xlsx)
    excel_file_cfg = manual_config.get("excel_file", "Data to Remove.xlsx")
    excel_file_path = PathLib(excel_file_cfg)
    if not excel_file_path.is_absolute():
        excel_file = str(workspace_root / excel_file_cfg)
    else:
        excel_file = str(excel_file_path)

    # Resolve data_to_add_file path (Data to Add.xlsx)
    add_file_cfg = manual_config.get("data_to_add_file", "Data to Add.xlsx")
    add_file_path = PathLib(add_file_cfg)
    if not add_file_path.is_absolute():
        data_to_add_file = str(workspace_root / add_file_cfg)
    else:
        data_to_add_file = str(add_file_path)

    return excel_file, data_to_add_file


# --- Depth Plots (Parameter vs Depth) ---
# Used for: Moisture Content, Undrained Shear Strength, SPT, etc.
# MODIFICATION POINT: Change these to adjust depth plot aspect ratio
DEPTH_PLOT_CONFIG: Dict[str, Any] = {
    # Matplotlib dimensions (inches)
    # Aspect ratio: 12.0 / 12.0 = 1.0:1 (wider depth plots)
    "matplotlib": {
        "figure_width": 12.0,
        "figure_height": 12.0,
    },
    # Plotly dimensions (pixels)
    # CRITICAL: Match matplotlib aspect ratio for visual consistency
    # NOTE: Left margin set to 100px since panels are now in a separate sidebar
    # (previously 450px to accommodate fixed overlaying panels)
    # Plot area = total_width - margin.l - margin.r = 1180 - 100 - 200 = 880 (width)
    # Plot area height = total_height - margin.t - margin.b = 1030 - 100 - 50 = 880 (height)
    # Plot area aspect = 880/880 = 1.0:1 (matches matplotlib 12/12!)
    "plotly": {
        "width": 1180,
        "height": 1030,
        "margin": {"l": 100, "r": 200, "t": 100, "b": 50},
    },
}

# --- XY Plots (Parameter vs Parameter) ---
# Used for: A-line (LL vs PI), CV vs Cell Pressure, MV vs Cell Pressure, etc.
# MODIFICATION POINT: Change these to adjust XY plot aspect ratio
XY_PLOT_CONFIG: Dict[str, Any] = {
    # Matplotlib dimensions (inches)
    # Aspect ratio: 10.0 / 8.0 = 1.25:1
    "matplotlib": {
        "figure_width": 10.0,
        "figure_height": 8.0,
    },
    # Plotly dimensions (pixels)
    # CRITICAL: Match matplotlib aspect ratio for visual consistency
    # NOTE: Left margin set to 100px since panels are now in a separate sidebar
    # (previously 450px to accommodate fixed overlaying panels)
    # Plot area = total_width - margin.l - margin.r = 1110 - 100 - 200 = 810 (width)
    # Plot area height = total_height - margin.t - margin.b = 800 - 100 - 50 = 650 (height)
    # Plot area aspect = 810/650 ≈ 1.25:1 (matches matplotlib!)
    "plotly": {
        "width": 1110,
        "height": 800,
        "margin": {"l": 100, "r": 200, "t": 100, "b": 50},
    },
}

# --- PSD Plots (Particle Size Distribution) ---
# Used for: Grading curves
# MODIFICATION POINT: Change these to adjust PSD plot aspect ratio
PSD_PLOT_CONFIG: Dict[str, Any] = {
    # Matplotlib dimensions (inches)
    "matplotlib": {
        "figure_width": 10.0,
        "figure_height": 8.0,
    },
    # Plotly dimensions (pixels)
    # NOTE: Left margin set to 100px since panels are now in a separate sidebar
    # (previously 450px to accommodate fixed overlaying panels)
    "plotly": {
        "width": 850,
        "height": 800,
        "margin": {"l": 100, "r": 200, "t": 100, "b": 50},
    },
}


def get_matplotlib_figure_size(plot_type: str) -> Tuple[float, float]:
    """
    Get matplotlib figure dimensions for a plot type.

    Args:
        plot_type: One of "depth", "xy", or "psd"

    Returns:
        Tuple of (width, height) in inches
    """
    config_map = {
        "depth": DEPTH_PLOT_CONFIG,
        "xy": XY_PLOT_CONFIG,
        "psd": PSD_PLOT_CONFIG,
    }
    config = config_map.get(plot_type, XY_PLOT_CONFIG)
    return (
        config["matplotlib"]["figure_width"],
        config["matplotlib"]["figure_height"],
    )


def get_plotly_figure_size(plot_type: str) -> Dict[str, Any]:
    """
    Get Plotly figure dimensions and margins for a plot type.

    Args:
        plot_type: One of "depth", "xy", or "psd"

    Returns:
        Dict with "width", "height", and "margin" keys
    """
    config_map = {
        "depth": DEPTH_PLOT_CONFIG,
        "xy": XY_PLOT_CONFIG,
        "psd": PSD_PLOT_CONFIG,
    }
    config = config_map.get(plot_type, XY_PLOT_CONFIG)
    return config["plotly"].copy()


# ═══════════════════════════════════════════════════════════════════════════
# 🎨 COLOR UTILITIES SECTION
# Functions for color manipulation and mapping
# ═══════════════════════════════════════════════════════════════════════════


def hex_to_rgb(hex_color: str) -> Tuple[float, float, float]:
    """
    Convert hex color to RGB tuple (0-1 range for matplotlib).

    Args:
        hex_color: Hex color string (e.g., "#0057B7" or "0057B7")

    Returns:
        Tuple of (R, G, B) values normalized to 0-1 range
    """
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    return (r, g, b)


def hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """
    Convert hex color to rgba() string for Plotly.

    Args:
        hex_color: Hex color string (e.g., "#0057B7")
        alpha: Opacity value from 0.0 (transparent) to 1.0 (opaque)

    Returns:
        RGBA color string (e.g., "rgba(0, 87, 183, 0.8)")
    """
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def create_investigation_color_mapping(
    investigations: List[str], color_palette: List[str]
) -> Dict[str, str]:
    """
    Create color mapping for investigations using rotating color palette.

    Assigns a unique color to each investigation from the provided palette.
    If there are more investigations than colors, the palette rotates.
    Investigations are sorted alphabetically to ensure consistent color
    assignment across both Plotly and matplotlib plots.

    Args:
        investigations: List of unique investigation names
        color_palette: List of hex color codes (e.g., ["#0057B7", "#8B0000"])

    Returns:
        Dictionary mapping investigation names to hex color codes

    Example:
        >>> create_investigation_color_mapping(
        ...     ["Site A", "Site B", "Site C"],
        ...     ["#0057B7", "#8B0000"]
        ... )
        {"Site A": "#0057B7", "Site B": "#8B0000", "Site C": "#0057B7"}
    """
    investigation_colors = {}
    for idx, investigation in enumerate(sorted(investigations)):
        color_idx = idx % len(color_palette)
        investigation_colors[investigation] = color_palette[color_idx]
    return investigation_colors


# ═══════════════════════════════════════════════════════════════════════════
# 📁 FILENAME UTILITIES SECTION
# Functions for file path and name sanitization
# ═══════════════════════════════════════════════════════════════════════════


def sanitize_filename(name: str) -> str:
    """
    Sanitize a string for use as a filename.

    Removes or replaces characters that are invalid in filenames across
    different operating systems.

    Args:
        name: Original name string that may contain invalid characters

    Returns:
        Sanitized string safe for use as filename

    Example:
        >>> sanitize_filename("Gault Clay Formation (Weathered)")
        "Gault_Clay_Formation_Weathered"
    """
    return (
        name.replace(" ", "_")
        .replace("(", "")
        .replace(")", "")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
    )


# ═══════════════════════════════════════════════════════════════════════════
# 📤 MODULE EXPORTS
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    # Plot type helpers (unified abstraction)
    "get_axis_parameters",
    "resolve_manual_data_paths",
    # Figure size configuration
    "DEPTH_PLOT_CONFIG",
    "XY_PLOT_CONFIG",
    "PSD_PLOT_CONFIG",
    "get_matplotlib_figure_size",
    "get_plotly_figure_size",
    # Color utilities
    "hex_to_rgb",
    "hex_to_rgba",
    "create_investigation_color_mapping",
    # Filename utilities
    "sanitize_filename",
]
