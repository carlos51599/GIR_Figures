#!/usr/bin/env python3
"""
Shared Matplotlib Plotting Module - AI-Optimized Monolith
SESRO GIR Geotechnical Data Visualization

Architectural Overview:

Responsibility:
Provides shared Matplotlib plotting utilities for all geotechnical investigation-series plots.
Centralizes common components: marker mappings, color utilities, legend generation,
scatter plotting, axis configuration, and PNG export.
Reduces code duplication across 15+ plotting scripts.

Key Interactions:
- Input: Investigation data, color palettes, test type settings
- Output: Matplotlib Figure objects and PNG files
- Callers: MCvsDepth_simplified, UndrainedShearStrength, PIvsDepth, etc.
- Companion Module: plotly_utils.py (for interactive HTML outputs)
- Shared Module: shared_plotting.py (common utilities for both backends)

Navigation Guide (use VS Code outline Ctrl+Shift+O):
1. CONSTANTS SECTION: Default marker sizes, figure dimensions
2. LEGEND COMPONENTS: Investigation legends, test type shape legends
3. AXIS CONFIGURATION: Depth plot axes setup, scatter plot axes setup
4. SCATTER GENERATION: Add investigation scatter points
5. HIGH-LEVEL GENERATION: Complete depth plot generation
6. EXPORT: Save figure with consistent settings

CONFIGURATION ARCHITECTURE:
- No CONFIG access in this module - all functions accept explicit primitives
- Caller scripts extract config and pass as parameters
- 100% testable without config mocking
"""

# Standard library imports
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set, Literal

# Third-party imports
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
import pandas as pd
import numpy as np

# Local imports - shared plotting utilities
from .shared_plotting_utils import (
    hex_to_rgb,
    create_investigation_color_mapping,
    sanitize_filename,
    get_matplotlib_figure_size,
)

# Logging Configuration
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# 📋 CONSTANTS SECTION
# ═══════════════════════════════════════════════════════════════════════════

# MODIFICATION POINT: Default figure dimensions
DEFAULT_FIGURE_WIDTH: float = 8.67
DEFAULT_FIGURE_HEIGHT: float = 12.0
DEFAULT_DPI: int = 300

# MODIFICATION POINT: Default marker settings
DEFAULT_MARKER_EDGECOLORS: str = "black"
DEFAULT_MARKER_LINEWIDTHS: float = 0.3
DEFAULT_MARKER_SIZE: int = 50

# MODIFICATION POINT: Default legend settings
DEFAULT_LEGEND_FONTSIZE: int = 8
DEFAULT_LEGEND_NCOL: int = 3
DEFAULT_LEGEND_FRAMEALPHA: float = 0.9
DEFAULT_LEGEND_EDGECOLOR: str = "black"

# MODIFICATION POINT: Default axis settings
DEFAULT_GRID_ALPHA: float = 0.3
DEFAULT_GRID_COLOR: str = "gray"
DEFAULT_GRID_STYLE: str = "-"
DEFAULT_GRID_WIDTH: float = 0.5


# ═══════════════════════════════════════════════════════════════════════════
# 📈 CPT DENSITY LINE SECTION
# Density line tracing for CPT data visualization in matplotlib plots
# ═══════════════════════════════════════════════════════════════════════════


def detect_segments(
    depth_array: np.ndarray,
    gap_threshold: float = 0.5,
    min_length: float = 0.20,
) -> List[Tuple[int, int]]:
    """
    Detect continuous segments in sorted depth data.

    Args:
        depth_array: Sorted array of depth values
        gap_threshold: Maximum gap (m) before starting new segment
        min_length: Minimum segment depth range (m) to include

    Returns:
        List of (start_idx, end_idx) tuples for valid segments
    """
    if len(depth_array) < 5:
        return []

    depth_diffs = np.diff(depth_array)
    gap_indices = np.where(depth_diffs > gap_threshold)[0]

    segment_starts = [0] + list(gap_indices + 1)
    segment_ends = list(gap_indices + 1) + [len(depth_array)]

    segments = []
    for start, end in zip(segment_starts, segment_ends):
        segment_depth_range = depth_array[end - 1] - depth_array[start]
        if segment_depth_range >= min_length:
            segments.append((start, end))

    return segments


def calculate_mode_histogram(
    data: np.ndarray, bin_strategy: str = "fd", fallback_bins: int = 30
) -> float:
    """
    Calculate mode using histogram with robust binning.

    Args:
        data: Array of values
        bin_strategy: Binning strategy ('fd' for Freedman-Diaconis)
        fallback_bins: Number of bins if strategy fails

    Returns:
        Mode value
    """
    if len(data) < 10:
        return float(np.median(data))

    try:
        counts, bin_edges = np.histogram(data, bins=bin_strategy)
    except Exception:
        counts, bin_edges = np.histogram(data, bins=fallback_bins)

    if np.sum(counts) == 0:
        return float(np.median(data))

    modal_bin_idx = np.argmax(counts)
    mode_value = (bin_edges[modal_bin_idx] + bin_edges[modal_bin_idx + 1]) / 2

    return float(mode_value)


def estimate_local_cv(
    depth: np.ndarray, strength: np.ndarray, center_depth: float, window: float = 1.0
) -> float:
    """
    Estimate coefficient of variation in a local depth window.

    Args:
        depth: Array of depth values
        strength: Array of strength values
        center_depth: Center of window
        window: Window size (m)

    Returns:
        CV percentage
    """
    mask = np.abs(depth - center_depth) <= window / 2
    local_strength = strength[mask]

    if len(local_strength) < 10:
        return 30.0

    cv = (np.std(local_strength) / np.mean(local_strength)) * 100
    return float(cv)


def adaptive_window_size(
    center_depth: float,
    depth_array: np.ndarray,
    strength_array: np.ndarray,
    base_window: float = 0.6,
    sensitivity: float = 0.5,
    cv_min: float = 18.0,
    cv_max: float = 58.0,
) -> float:
    """
    Calculate adaptive window size based on local variability.

    Args:
        center_depth: Center depth for window
        depth_array: Array of all depth values
        strength_array: Array of all parameter values
        base_window: Base window size in meters
        sensitivity: Sensitivity factor for CV adjustment
        cv_min: Minimum CV threshold
        cv_max: Maximum CV threshold

    Returns:
        Adaptive window size in meters
    """
    cv_local = estimate_local_cv(depth_array, strength_array, center_depth)

    if cv_local <= cv_min:
        return base_window * 1.5
    elif cv_local >= cv_max:
        return base_window * 0.6
    else:
        cv_ratio = (cv_local - cv_min) / (cv_max - cv_min)
        adjustment = (1 + sensitivity * cv_ratio) ** (-1)
        return base_window * adjustment


def trace_density_line_segment(
    depth: np.ndarray,
    strength: np.ndarray,
    density_config: Dict[str, Any],
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Trace density line through a single continuous segment.

    Args:
        depth: Depth values for segment
        strength: Strength values for segment
        density_config: Configuration dictionary

    Returns:
        Tuple of (mode_depths, mode_strengths)
    """
    min_depth = depth.min()
    max_depth = depth.max()

    base_window = density_config["moving_window"]["base_window_size"]
    step_size = base_window * density_config["moving_window"]["step_size_ratio"]
    min_points = density_config["moving_window"]["min_points_per_window"]

    window_centers = np.arange(
        min_depth + base_window / 2,
        max_depth - base_window / 2 + step_size,
        step_size,
    )

    mode_depths = []
    mode_strengths = []

    cv_min = density_config["cv_zones"]["cv_min"]
    cv_max = density_config["cv_zones"]["cv_max"]

    for center in window_centers:
        window_size = adaptive_window_size(
            center,
            depth,
            strength,
            base_window=base_window,
            sensitivity=density_config["moving_window"]["adaptive_sensitivity"],
            cv_min=cv_min,
            cv_max=cv_max,
        )

        half_window = window_size / 2
        mask = (depth >= center - half_window) & (depth <= center + half_window)
        window_strength = strength[mask]

        if len(window_strength) < min_points:
            continue

        mode_val = calculate_mode_histogram(
            window_strength,
            bin_strategy=density_config["mode_estimation"]["bin_strategy"],
        )

        mode_depths.append(center)
        mode_strengths.append(mode_val)

    if len(mode_depths) == 0:
        return np.array([]), np.array([])

    mode_depths_arr = np.array(mode_depths)
    mode_strengths_arr = np.array(mode_strengths)

    # Return raw mode values without any smoothing
    return mode_depths_arr, mode_strengths_arr


def generate_density_traces(
    depth_array: np.ndarray,
    strength_array: np.ndarray,
    density_config: Dict[str, Any],
) -> List[Tuple[np.ndarray, np.ndarray]]:
    """
    Generate density traces for multi-segment CPT data.

    Args:
        depth_array: Array of all depth values
        strength_array: Array of all strength values
        density_config: Configuration dictionary

    Returns:
        List of (segment_depths, segment_strengths) tuples
    """
    if len(depth_array) == 0 or len(strength_array) == 0:
        return []

    sort_idx = np.argsort(depth_array)
    depth = depth_array[sort_idx]
    strength = strength_array[sort_idx]

    segments = detect_segments(
        depth,
        gap_threshold=density_config["segment_detection"]["gap_threshold"],
        min_length=density_config["segment_detection"]["min_segment_length"],
    )

    if len(segments) == 0:
        return []

    density_traces = []

    for start_idx, end_idx in segments:
        seg_depth = depth[start_idx:end_idx]
        seg_strength = strength[start_idx:end_idx]

        mode_depths, mode_strengths = trace_density_line_segment(
            seg_depth, seg_strength, density_config
        )

        if len(mode_depths) > 0:
            density_traces.append((mode_depths, mode_strengths))

    return density_traces


def add_cpt_density_lines_matplotlib(
    ax: Axes,
    cpt_data: pd.DataFrame,
    param_column: str,
    investigation_color_map: Dict[str, str],
    density_config: Dict[str, Any],
    density_line_settings: Dict[str, Any],
    min_points_threshold: int = 5,
    cpt_auto_plot_threshold: int = 50,
    cpt_auto_plot_disable_density: bool = True,
) -> List[float]:
    """
    Add CPT density lines to a matplotlib axes, one per investigation.

    Args:
        ax: Matplotlib Axes object to add lines to
        cpt_data: DataFrame with CPT data including 'Investigation', 'Top Depth', and param_column
        param_column: Name of the parameter column
        investigation_color_map: Dict mapping investigation names to hex colors
        density_config: Density tracing configuration
        density_line_settings: Settings for density line appearance (linewidth, alpha, etc.)
        min_points_threshold: Minimum CPT points required to generate density line
        cpt_auto_plot_threshold: Threshold for sparse investigation auto-plot (default 50)
        cpt_auto_plot_disable_density: If True, skip density lines for sparse investigations

    Returns:
        List of all parameter values from density traces (for x-axis scaling)
    """
    all_density_values: List[float] = []

    if "Investigation" not in cpt_data.columns:
        logger.warning(
            "⚠️ CPT data missing 'Investigation' column - skipping density lines"
        )
        return all_density_values

    line_width = density_line_settings.get("linewidth", 1.0)
    line_alpha = density_line_settings.get("alpha", 1.0)
    line_style = density_line_settings.get("linestyle", "-")

    for investigation in sorted(cpt_data["Investigation"].unique()):
        inv_cpt = cpt_data[cpt_data["Investigation"] == investigation]

        cpt_param_values = inv_cpt[param_column].values
        cpt_depth_values = inv_cpt["Top Depth"].values

        # Skip if insufficient points for any density line
        if len(cpt_param_values) < min_points_threshold:
            logger.debug(
                f"  ⏭️ {investigation}: Insufficient CPT points for density line "
                f"({len(cpt_param_values)} points < {min_points_threshold})"
            )
            continue

        # === CPT AUTO-PLOT DENSITY DISABLE LOGIC ===
        # Skip density line if investigation is sparse and disable_density is True
        # (sparse investigations get scatter points instead, handled in generate_depth_plot)
        if (
            len(cpt_param_values) < cpt_auto_plot_threshold
            and cpt_auto_plot_disable_density
        ):
            logger.info(
                f"  ⏭️ {investigation}: Density line disabled (auto-plot triggered: "
                f"{len(cpt_param_values)} points < {cpt_auto_plot_threshold} threshold, "
                f"cpt_auto_plot_disable_density=True)"
            )
            continue

        inv_color = investigation_color_map.get(investigation, "#888888")

        # Generate density traces for this investigation
        density_traces = generate_density_traces(
            depth_array=cpt_depth_values,
            strength_array=cpt_param_values,
            density_config=density_config,
        )

        if not density_traces:
            logger.debug(f"  ⚠️ No density traces generated for {investigation}")
            continue

        # Add each segment as a separate line
        for trace_depths, trace_strengths in density_traces:
            if len(trace_depths) > 0:
                ax.plot(
                    trace_strengths,
                    trace_depths,
                    color=inv_color,
                    linewidth=line_width,
                    linestyle=line_style,
                    alpha=line_alpha,
                    label="_nolegend_",  # Don't add to legend
                )

                all_density_values.extend(trace_strengths.tolist())

        logger.info(
            f"  ✅ Added {len(density_traces)} density line segment(s) for {investigation}"
        )

    return all_density_values


# ═══════════════════════════════════════════════════════════════════════════
# 🧪 CLASSIFICATION BOUNDARIES SECTION
# Geotechnical classification lines for specialized plots (A-line, etc.)
# ═══════════════════════════════════════════════════════════════════════════


def add_plasticity_classification_boxes(
    fig: Figure,
    main_ax: Axes,
    ll_low: float = 35,
    ll_intermediate: float = 50,
    ll_high: float = 70,
    ll_very_high: float = 90,
    x_max: float = 120,
) -> None:
    """
    Add plasticity classification boxes above the A-line plot.

    Creates a new axes positioned above the main plot area to draw rectangular
    boxes divided by vertical LL boundaries, with labels indicating plasticity
    levels: Low, Intermediate, High, Very high, Extremely high.

    Args:
        fig: Matplotlib figure object
        main_ax: Main plot axes object (used for positioning)
        ll_low: Liquid limit boundary for low plasticity (35)
        ll_intermediate: Liquid limit boundary for intermediate plasticity (50)
        ll_high: Liquid limit boundary for high plasticity (70)
        ll_very_high: Liquid limit boundary for very high plasticity (90)
        x_max: Maximum x-axis value (120)
    """
    from matplotlib.patches import Rectangle

    # Configuration for box styling
    labels = ["Low", "Intermediate", "High", "Very high", "Extremely high"]
    text_size = 11
    text_weight = "normal"
    text_color = "black"
    box_edgecolor = "black"
    box_linewidth = 1.0
    box_facecolor = "white"
    box_alpha = 0.8

    # Get main axes position
    main_pos = main_ax.get_position()

    # Create new axes above main plot (same width, positioned above)
    # Height relative to figure: 0.05 = 5% of figure height
    # Bottom edge aligned with top of main plot (no gap)
    box_ax = fig.add_axes([main_pos.x0, main_pos.y1, main_pos.width, 0.05])

    # Set limits to match main plot x-axis
    box_ax.set_xlim(0, x_max)
    box_ax.set_ylim(0, 1)  # Normalized y-axis for the box strip

    # Remove all axes decorations
    box_ax.set_xticks([])
    box_ax.set_yticks([])
    box_ax.spines["top"].set_visible(False)
    box_ax.spines["bottom"].set_visible(False)
    box_ax.spines["left"].set_visible(False)
    box_ax.spines["right"].set_visible(False)

    # Define box boundaries (x_min, x_max) for each plasticity zone
    box_boundaries = [
        (0, ll_low),  # Low
        (ll_low, ll_intermediate),  # Intermediate
        (ll_intermediate, ll_high),  # High
        (ll_high, ll_very_high),  # Very high
        (ll_very_high, x_max),  # Extremely high
    ]

    # Draw boxes with labels in the new axes
    for (x_min, x_max_box), label in zip(box_boundaries, labels):
        # Calculate box width and center
        box_width = x_max_box - x_min
        x_center = x_min + (box_width / 2)

        # Draw rectangle filling the full height of box_ax
        rect = Rectangle(
            (x_min, 0),  # Start at bottom of box_ax
            box_width,
            1,  # Fill full height
            linewidth=box_linewidth,
            edgecolor=box_edgecolor,
            facecolor=box_facecolor,
            alpha=box_alpha,
            clip_on=False,
        )
        box_ax.add_patch(rect)

        # Add text label centered in box
        box_ax.text(
            x_center,
            0.5,  # Center vertically in normalized coordinates
            label,
            fontsize=text_size,
            weight=text_weight,
            color=text_color,
            ha="center",
            va="center",
        )


def add_matplotlib_plasticity_chart_boundaries(
    fig: Figure,
    ax: Axes,
    x_range: Tuple[float, float] = (0, 120),
    y_range: Tuple[float, float] = (0, 80),
) -> None:
    """
    Add A-line and U-line geotechnical classification boundaries to a matplotlib figure.

    Standard Atterberg plasticity chart boundaries:
    - A-line: PI = 0.73 * (LL - 20) - separates clays (above) from silts (below)
    - Horizontal line at PI=4 connecting to exact A-line intersection point
    - Vertical boundaries at LL = 35, 50, 70, 90 (plasticity transitions)
    - Soil classification labels (CL, ML, MI, CI, MH, CH, MV, CV, ME, CE)
    - Plasticity classification boxes above plot

    Args:
        fig: Matplotlib Figure object
        ax: Matplotlib Axes object
        x_range: Tuple of (min, max) for x-axis (Liquid Limit range)
        y_range: Tuple of (min, max) for y-axis (Plasticity Index range)
    """
    # === A-LINE BOUNDARY PARAMETERS ===
    a_line_start_ll = 20  # A-line starts at LL=20
    a_line_slope = 0.73  # A-line slope: PI = 0.73(LL-20)
    pi_min = 4  # Minimum PI for classification
    ll_low = 35  # Low liquid limit
    ll_intermediate = 50  # Intermediate liquid limit
    ll_high = 70  # High liquid limit
    ll_very_high = 90  # Very high liquid limit

    # === PLOT GEOTECHNICAL CLASSIFICATION BOUNDARIES ===
    # Define Liquid Limit range for plotting lines with fine resolution
    ll = np.linspace(0, 120, 1201)  # Fine resolution for smooth connection

    # A-line: PI = 0.73(LL - 20)
    a_line = a_line_slope * (ll - a_line_start_ll)

    # Calculate exact connection point where A-line meets PI=4
    pi_min_connection = (pi_min / a_line_slope) + a_line_start_ll

    # Truncate A-line at PI >= pi_min
    a_mask = a_line >= pi_min

    # Plot truncated A-line
    ax.plot(ll[a_mask], a_line[a_mask], "k-", linewidth=1, zorder=2)

    # Horizontal line at PI = 4, between 0 and exact A-line connection point
    ax.plot(
        [0, pi_min_connection],
        [pi_min, pi_min],
        color="k",
        linestyle="-",
        linewidth=1,
        zorder=1,
    )

    # Vertical classification lines
    ax.axvline(x=ll_low, color="k", linestyle="-", linewidth=0.5, zorder=1)
    ax.axvline(x=ll_intermediate, color="k", linestyle="-", linewidth=0.5, zorder=1)
    ax.axvline(x=ll_high, color="k", linestyle="-", linewidth=0.5, zorder=1)
    ax.axvline(x=ll_very_high, color="k", linestyle="-", linewidth=0.5, zorder=1)

    # === ADD SOIL CLASSIFICATION LABELS ===
    # Soil classification labels with positions matching the monolith exactly
    soil_labels = {
        "CL": {"x": 20, "y": 30},
        "ML": {"x": 20, "y": 2},
        "MI": {"x": 42.5, "y": 5},
        "CI": {"x": 42.5, "y": 45},
        "MH": {"x": 60, "y": 10},
        "CH": {"x": 60, "y": 55},
        "MV": {"x": 80, "y": 20},
        "CV": {"x": 80, "y": 61},
        "ME": {"x": 100, "y": 35},
        "CE": {"x": 100, "y": 65},
    }

    label_font = {"weight": "normal", "size": 12}

    # Add all soil classification labels
    for label, config in soil_labels.items():
        if config["x"] is not None:
            ax.text(
                config["x"],
                config["y"],
                label,
                fontdict=label_font,
                ha="center",
                va="center",
            )

    # === ADD PLASTICITY CLASSIFICATION BOXES ===
    add_plasticity_classification_boxes(
        fig=fig,
        main_ax=ax,
        ll_low=ll_low,
        ll_intermediate=ll_intermediate,
        ll_high=ll_high,
        ll_very_high=ll_very_high,
        x_max=x_range[1],
    )


def add_particle_size_classification_legend(
    classification_ax: Axes,
    x_limit_left: float = 0.001,
    x_limit_right: float = 200,
    font_size: float = 9,
    font_weight: str = "bold",
    line_width: float = 0.8,
    line_color: str = "black",
) -> None:
    """
    Add particle size classification legend in a separate subplot.

    Creates a visual classification system showing soil particle size categories
    (CLAY, SILT, SAND, GRAVEL, COBBLES) with their size ranges in mm.
    The classification legend has its own top and bottom boundaries.

    Args:
        classification_ax: Matplotlib Axes object for classification subplot
        x_limit_left: Left limit of x-axis (minimum particle size in mm)
        x_limit_right: Right limit of x-axis (maximum particle size in mm)
        font_size: Font size for category labels
        font_weight: Font weight for category labels
        line_width: Width of boundary lines
        line_color: Color of boundary lines
    """
    # Standard BS EN ISO 14688-1 particle size classification
    categories = [
        {
            "name": "CLAY",
            "size_min": 0.001,
            "size_max": 0.002,
            "subcategories": None,
        },
        {
            "name": "SILT",
            "size_min": 0.002,
            "size_max": 0.063,
            "subcategories": [
                {"name": "Fine", "size_min": 0.002, "size_max": 0.0063},
                {"name": "Medium", "size_min": 0.0063, "size_max": 0.02},
                {"name": "Coarse", "size_min": 0.02, "size_max": 0.063},
            ],
        },
        {
            "name": "SAND",
            "size_min": 0.063,
            "size_max": 2.0,
            "subcategories": [
                {"name": "Fine", "size_min": 0.063, "size_max": 0.2},
                {"name": "Medium", "size_min": 0.2, "size_max": 0.63},
                {"name": "Coarse", "size_min": 0.63, "size_max": 2.0},
            ],
        },
        {
            "name": "GRAVEL",
            "size_min": 2.0,
            "size_max": 63,
            "subcategories": [
                {"name": "Fine", "size_min": 2.0, "size_max": 6.3},
                {"name": "Medium", "size_min": 6.3, "size_max": 20},
                {"name": "Coarse", "size_min": 20, "size_max": 63},
            ],
        },
        {
            "name": "COBBLES",
            "size_min": 63,
            "size_max": 200,
            "subcategories": None,
        },
    ]

    # Set same x-limits and log scale as main plot
    classification_ax.set_xlim(x_limit_left, x_limit_right)
    classification_ax.set_xscale("log")

    # Set y-limits for classification area (0 to 1 for simplicity)
    classification_ax.set_ylim(0, 1)

    # Configure axis spines - show top and bottom boundaries
    classification_ax.spines["top"].set_visible(True)
    classification_ax.spines["top"].set_linewidth(line_width)
    classification_ax.spines["top"].set_color(line_color)

    classification_ax.spines["bottom"].set_visible(True)
    classification_ax.spines["bottom"].set_linewidth(line_width)
    classification_ax.spines["bottom"].set_color(line_color)

    classification_ax.spines["right"].set_visible(False)
    classification_ax.spines["left"].set_visible(False)

    # Remove tick marks but keep axes
    classification_ax.set_xticks([])
    classification_ax.set_yticks([])
    classification_ax.tick_params(axis="x", which="both", bottom=False, top=False)

    # Draw vertical lines for category boundaries and add labels
    for category in categories:
        size_min = category["size_min"]
        size_max = category["size_max"]
        category_name = category["name"]
        subcategories = category["subcategories"]

        # Draw main category boundaries (vertical line spanning full height)
        classification_ax.axvline(
            x=size_min, ymin=0, ymax=1, color=line_color, linewidth=line_width
        )

        if subcategories:
            # Draw subdivisions within this category
            for subcat in subcategories:
                sub_min = subcat["size_min"]
                sub_max = subcat["size_max"]
                sub_name = subcat["name"]

                # Draw subdivision boundary line (thinner, top cell only)
                classification_ax.axvline(
                    x=sub_min,
                    ymin=0.5,
                    ymax=1.0,
                    color=line_color,
                    linewidth=line_width * 0.7,
                )

                # Draw subcategory label at TOP (geometric mean in log space)
                sub_x_center = np.sqrt(sub_min * sub_max)
                classification_ax.text(
                    sub_x_center,
                    0.75,
                    sub_name,
                    ha="center",
                    va="center",
                    fontsize=font_size * 0.8,
                    weight="normal",
                )

            # Draw main category label at BOTTOM (merged cell effect)
            category_x_center = np.sqrt(size_min * size_max)
            classification_ax.text(
                category_x_center,
                0.25,
                category_name,
                ha="center",
                va="center",
                fontsize=font_size * 0.8,
                weight="normal",
            )
        else:
            # Single category without subdivisions - show centered
            category_x_center = np.sqrt(size_min * size_max)
            classification_ax.text(
                category_x_center,
                0.5,
                category_name,
                ha="center",
                va="center",
                fontsize=font_size * 0.8,
                weight="normal",
            )

    # Draw final right boundary
    classification_ax.axvline(
        x=categories[-1]["size_max"],
        ymin=0,
        ymax=1,
        color=line_color,
        linewidth=line_width,
    )

    # Draw horizontal line between subdivisions (top) and main categories (bottom)
    # Only spans from silt start (0.002 mm) to gravel end (63 mm) where subcategories exist
    classification_ax.plot(
        [0.002, 63], [0.5, 0.5], color=line_color, linewidth=line_width
    )


# ═══════════════════════════════════════════════════════════════════════════
# 📊 LEGEND COMPONENTS SECTION
# ═══════════════════════════════════════════════════════════════════════════


def add_investigation_legend_entries(
    ax: Axes,
    plotted_investigations: Set[str],
    investigation_color_map: Dict[str, str],
    marker_size: int = 100,
    marker_alpha: float = 0.8,
    marker_edgecolors: str = DEFAULT_MARKER_EDGECOLORS,
    marker_linewidths: float = DEFAULT_MARKER_LINEWIDTHS,
) -> None:
    """
    Add invisible scatter points to create investigation color legend entries.

    Creates legend entries for each investigation using circle markers in
    the investigation's assigned color. These are invisible on the plot
    but appear in the legend.

    Args:
        ax: Matplotlib axes to add legend entries to
        plotted_investigations: Set of investigation names that have data
        investigation_color_map: Dict mapping investigations to hex colors
        marker_size: Size of legend marker
        marker_alpha: Transparency of legend marker
        marker_edgecolors: Edge color for legend markers
        marker_linewidths: Edge width for legend markers
    """
    for investigation in sorted(plotted_investigations):
        inv_color = investigation_color_map[investigation]
        ax.scatter(
            [],
            [],
            c=inv_color,
            marker="o",  # Use circle marker for investigation colors
            s=marker_size,
            alpha=marker_alpha,
            edgecolors=marker_edgecolors,
            linewidths=marker_linewidths,
            label=f"{investigation}",
        )


def add_test_type_legend_entries(
    ax: Axes,
    csv_source_settings: Dict[str, Dict[str, Any]],
    test_types_in_formation: Set[str],
    marker_edgecolors: str = DEFAULT_MARKER_EDGECOLORS,
    marker_linewidths: float = DEFAULT_MARKER_LINEWIDTHS,
    cpt_points_plotted: bool = False,
    cpt_lines_plotted: bool = False,
) -> None:
    """
    Add invisible scatter points to create test type shape legend entries.

    Creates legend entries for each test type showing the marker shape
    in gray color. These are invisible on the plot but appear in the legend.

    For CPT, creates separate entries for "CPT Line" and "CPT Points" based
    on what was actually plotted in the formation.

    Args:
        ax: Matplotlib axes to add legend entries to
        csv_source_settings: Dict mapping CSV names to marker settings
        test_types_in_formation: Set of CSV names with data in this formation
        marker_edgecolors: Edge color for legend markers
        marker_linewidths: Edge width for legend markers
        cpt_points_plotted: Whether CPT points were plotted (sparse investigations)
        cpt_lines_plotted: Whether CPT density lines were plotted (dense investigations)
    """
    for csv_name in sorted(test_types_in_formation):
        test_type_settings = csv_source_settings.get(csv_name, {})

        if not test_type_settings.get("plotted", True):
            continue

        marker_style = test_type_settings.get("marker", "o")
        marker_size = test_type_settings.get("marker_size", DEFAULT_MARKER_SIZE)
        marker_thickness = test_type_settings.get("marker_thickness", marker_linewidths)

        # Get display name from config, fallback to cleaned CSV name
        clean_test_name = csv_name.replace(" by Geology.csv", "").replace(".csv", "")
        display_test_name = test_type_settings.get(
            "legend_name_points", clean_test_name
        )

        # === CPT SPECIAL HANDLING ===
        # CPT has plot_points=False by default, but may have:
        # - Points plotted (for sparse investigations below threshold)
        # - Lines plotted (density lines for dense investigations above threshold)
        if csv_name == "CPT by Geology.csv":
            # Add CPT Line legend entry if density lines were plotted
            if cpt_lines_plotted:
                density_line_settings = test_type_settings.get("density_line", {})
                line_width = density_line_settings.get("linewidth", 1.0)
                line_style = density_line_settings.get("linestyle", "-")

                ax.plot(
                    [],
                    [],
                    color="gray",
                    linewidth=line_width,
                    linestyle=line_style,
                    alpha=0.7,
                    label=f"{display_test_name} Line (shape)",
                )

            # Add CPT Points legend entry if scatter points were plotted
            if cpt_points_plotted:
                ax.scatter(
                    [],
                    [],
                    c="gray",
                    marker=marker_style,
                    s=marker_size,
                    alpha=0.7,
                    edgecolors=marker_edgecolors,
                    linewidths=marker_thickness,
                    label=f"{display_test_name} Points (shape)",
                )

            continue  # Skip default handling for CPT

        # === DEFAULT HANDLING FOR NON-CPT TEST TYPES ===
        if not test_type_settings.get("plot_points", True):
            continue

        ax.scatter(
            [],
            [],
            c="gray",
            marker=marker_style,
            s=marker_size,
            alpha=0.7,
            edgecolors=marker_edgecolors,
            linewidths=marker_thickness,
            label=f"{display_test_name} (shape)",
        )


def configure_legend(
    ax: Axes,
    fixed_width: bool = True,
    ncol: Optional[int] = None,
    fontsize: int = DEFAULT_LEGEND_FONTSIZE,
    edgecolor: str = DEFAULT_LEGEND_EDGECOLOR,
    framealpha: float = DEFAULT_LEGEND_FRAMEALPHA,
    fig: Optional[Figure] = None,
) -> None:
    """
    Configure and add legend to axes with consistent formatting.

    Creates a legend positioned below the plot area with configurable
    layout options. Can match legend width to axes width when fixed_width=True.

    Args:
        ax: Matplotlib axes to add legend to
        fixed_width: If True, expand legend to match axes width
        ncol: Number of columns (auto-calculated if None)
        fontsize: Font size for legend labels
        edgecolor: Edge color for legend box
        framealpha: Transparency of legend background
        fig: Figure object (required if fixed_width=True for canvas draw)
    """
    handles, labels = ax.get_legend_handles_labels()
    num_entries = len(labels)

    if num_entries == 0:
        return

    # Calculate optimal number of columns
    if ncol is None:
        ncol = min(3, max(1, num_entries // 2))

    if fixed_width and fig is not None:
        # Draw canvas to calculate layout
        fig.canvas.draw()
        bbox_expand = (0, -0.15, 1, 0)

        ax.legend(
            loc="lower left",
            bbox_to_anchor=bbox_expand,
            bbox_transform=ax.transAxes,
            edgecolor=edgecolor,
            framealpha=framealpha,
            ncol=ncol,
            mode="expand",
            borderaxespad=0,
            labelspacing=0.5,
            borderpad=0.5,
            fontsize=fontsize,
            columnspacing=1.0,
        )
    else:
        ax.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, -0.15),
            edgecolor=edgecolor,
            framealpha=framealpha,
            ncol=ncol,
            fontsize=fontsize,
            labelspacing=0.5,
            borderpad=0.5,
        )


# ═══════════════════════════════════════════════════════════════════════════
# ⚙️ AXIS CONFIGURATION SECTION
# ═══════════════════════════════════════════════════════════════════════════


def setup_depth_plot_axes(
    ax: Axes,
    parameter_display_name: str,
    formation_name: str,
    x_max: float,
    y_max: float,
    x_limit_left: float = 0.0,
    y_margin: float = 1.0,
    invert_y: bool = True,
    x_label_position: str = "top",
    x_label_size: int = 14,
    x_label_weight: str = "normal",
    y_label: str = "Depth (m)",
    y_label_size: int = 14,
    y_label_weight: str = "normal",
    title_enabled: bool = True,
    title_fontsize: int = 16,
    title_weight: str = "bold",
    title_pad: int = 20,
    grid_enabled: bool = True,
    grid_which: Literal["major", "minor", "both"] = "both",
    grid_style: str = DEFAULT_GRID_STYLE,
    grid_width: float = DEFAULT_GRID_WIDTH,
    grid_color: str = DEFAULT_GRID_COLOR,
    grid_alpha: float = DEFAULT_GRID_ALPHA,
) -> None:
    """
    Configure axes for depth plot with inverted Y-axis.

    Sets up standard depth plot configuration with:
    - X-axis at top showing parameter values
    - Y-axis inverted (depth increases downward)
    - Configurable labels, grid, and title

    Args:
        ax: Matplotlib axes to configure
        parameter_display_name: Display name for X-axis label
        formation_name: Formation name for plot title
        x_max: Maximum X-axis value (parameter)
        y_max: Maximum Y-axis value (depth)
        x_limit_left: Left limit for X-axis (usually 0)
        y_margin: Additional margin for Y-axis beyond max depth
        invert_y: Whether to invert Y-axis (True for depth plots)
        x_label_position: Position of X-axis label ("top" or "bottom")
        x_label_size: Font size for X-axis label
        x_label_weight: Font weight for X-axis label
        y_label: Label text for Y-axis
        y_label_size: Font size for Y-axis label
        y_label_weight: Font weight for Y-axis label
        title_enabled: Whether to show plot title
        title_fontsize: Font size for title
        title_weight: Font weight for title
        title_pad: Padding between title and plot
        grid_enabled: Whether to show grid
        grid_which: Grid lines to show ("major", "minor", "both")
        grid_style: Line style for grid
        grid_width: Line width for grid
        grid_color: Color for grid lines
        grid_alpha: Transparency for grid lines
    """
    # Set axis limits
    ax.set_xlim(left=x_limit_left, right=x_max * 1.1)

    if invert_y:
        ax.set_ylim(top=0, bottom=y_max + y_margin)
    else:
        ax.set_ylim(bottom=0, top=y_max + y_margin)

    # Set axis labels
    ax.set_xlabel(
        parameter_display_name,
        fontsize=x_label_size,
        weight=x_label_weight,
    )
    ax.set_ylabel(y_label, fontsize=y_label_size, weight=y_label_weight)

    # Position X-axis at top
    if x_label_position == "top":
        ax.xaxis.tick_top()
        ax.xaxis.set_label_position("top")

    # Add plot title
    if title_enabled:
        ax.set_title(
            formation_name,
            fontsize=title_fontsize,
            weight=title_weight,
            pad=title_pad,
        )

    # Configure grid
    if grid_enabled:
        ax.grid(
            which=grid_which,
            linestyle=grid_style,
            linewidth=grid_width,
            color=grid_color,
            alpha=grid_alpha,
        )


def setup_scatter_plot_axes(
    ax: Axes,
    x_display_name: str,
    y_display_name: str,
    formation_name: str,
    x_min: Optional[float] = None,
    x_max: Optional[float] = None,
    y_min: Optional[float] = None,
    y_max: Optional[float] = None,
    x_label_size: int = 14,
    x_label_weight: str = "normal",
    y_label_size: int = 14,
    y_label_weight: str = "normal",
    title_enabled: bool = True,
    title_fontsize: int = 16,
    title_weight: str = "bold",
    title_pad: int = 20,
    grid_enabled: bool = True,
    grid_which: Literal["major", "minor", "both"] = "both",
    grid_style: str = DEFAULT_GRID_STYLE,
    grid_width: float = DEFAULT_GRID_WIDTH,
    grid_color: str = DEFAULT_GRID_COLOR,
    grid_alpha: float = DEFAULT_GRID_ALPHA,
) -> None:
    """
    Configure axes for standard X-Y scatter plot.

    Sets up standard scatter plot configuration with:
    - X-axis at bottom showing first parameter
    - Y-axis showing second parameter (not inverted)
    - Configurable labels, grid, and title

    Args:
        ax: Matplotlib axes to configure
        x_display_name: Display name for X-axis label
        y_display_name: Display name for Y-axis label
        formation_name: Formation name for plot title
        x_min: Minimum X-axis value (auto if None)
        x_max: Maximum X-axis value (auto if None)
        y_min: Minimum Y-axis value (auto if None)
        y_max: Maximum Y-axis value (auto if None)
        x_label_size: Font size for X-axis label
        x_label_weight: Font weight for X-axis label
        y_label_size: Font size for Y-axis label
        y_label_weight: Font weight for Y-axis label
        title_enabled: Whether to show plot title
        title_fontsize: Font size for title
        title_weight: Font weight for title
        title_pad: Padding between title and plot
        grid_enabled: Whether to show grid
        grid_which: Grid lines to show ("major", "minor", "both")
        grid_style: Line style for grid
        grid_width: Line width for grid
        grid_color: Color for grid lines
        grid_alpha: Transparency for grid lines
    """
    # Set axis limits if provided
    if x_min is not None or x_max is not None:
        ax.set_xlim(left=x_min, right=x_max)
    if y_min is not None or y_max is not None:
        ax.set_ylim(bottom=y_min, top=y_max)

    # Set axis labels
    ax.set_xlabel(x_display_name, fontsize=x_label_size, weight=x_label_weight)
    ax.set_ylabel(y_display_name, fontsize=y_label_size, weight=y_label_weight)

    # Add plot title
    if title_enabled:
        ax.set_title(
            formation_name,
            fontsize=title_fontsize,
            weight=title_weight,
            pad=title_pad,
        )

    # Configure grid
    if grid_enabled:
        ax.grid(
            which=grid_which,
            linestyle=grid_style,
            linewidth=grid_width,
            color=grid_color,
            alpha=grid_alpha,
        )


# ═══════════════════════════════════════════════════════════════════════════
# 📈 SCATTER GENERATION SECTION
# ═══════════════════════════════════════════════════════════════════════════


def add_investigation_scatter(
    ax: Axes,
    x_data: np.ndarray,
    y_data: np.ndarray,
    color: str,
    marker: str,
    marker_size: int,
    alpha: float = 1.0,
    edgecolors: str = DEFAULT_MARKER_EDGECOLORS,
    linewidths: float = DEFAULT_MARKER_LINEWIDTHS,
) -> None:
    """
    Add scatter points for a single investigation/test type combination.

    Args:
        ax: Matplotlib axes to add scatter to
        x_data: X-axis values (parameter values or first parameter)
        y_data: Y-axis values (depth or second parameter)
        color: Hex color for points
        marker: Matplotlib marker style
        marker_size: Size of markers
        alpha: Transparency of markers
        edgecolors: Edge color for markers
        linewidths: Edge width for markers
    """
    ax.scatter(
        x_data,
        y_data,
        c=color,
        marker=marker,
        s=marker_size,
        alpha=alpha,
        edgecolors=edgecolors,
        linewidths=linewidths,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 💾 EXPORT SECTION
# ═══════════════════════════════════════════════════════════════════════════


def save_matplotlib_figure(
    fig: Figure,
    output_path: Path,
    dpi: int = DEFAULT_DPI,
    bbox_inches: str = "tight",
) -> None:
    """
    Save matplotlib figure with consistent settings.

    Creates output directory if it doesn't exist and saves the figure.

    Args:
        fig: Matplotlib figure to save
        output_path: Full path including filename for output
        dpi: Resolution in dots per inch
        bbox_inches: How to handle figure bounds ("tight" recommended)
    """
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig.savefig(output_path, dpi=dpi, bbox_inches=bbox_inches)
    plt.close(fig)

    logger.info(f"✅ Saved matplotlib figure: {output_path}")


# ═══════════════════════════════════════════════════════════════════════════
# 🎯 HIGH-LEVEL PLOT GENERATION
# Complete depth plot generation functions for parameter scripts
# ═══════════════════════════════════════════════════════════════════════════


def generate_depth_plot(
    formation_name: str,
    csv_data_with_investigations: Dict[str, Dict[str, Any]],
    parameter_display_name: str,
    output_folder: Path,
    investigation_color_map: Dict[str, str],
    csv_source_settings: Dict[str, Dict[str, Any]],
    filter_column: Optional[str] = None,
    include_manual_additions: bool = False,
    show_test_type_legend: bool = True,
    figure_width: float = DEFAULT_FIGURE_WIDTH,
    figure_height: float = DEFAULT_FIGURE_HEIGHT,
    dpi: int = DEFAULT_DPI,
    marker_edgecolors: str = DEFAULT_MARKER_EDGECOLORS,
    marker_linewidths: float = DEFAULT_MARKER_LINEWIDTHS,
    x_limit_left: float = 0.0,
    y_margin: float = 1.0,
    legend_fixed_width: bool = True,
    density_tracing_config: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Generate complete depth plot with investigation-based coloring.

    High-level function that creates a complete depth plot including:
    - Figure creation and sizing
    - Data plotting by investigation and test type
    - CPT density lines (if enabled)
    - Legend generation (investigation colors + test type shapes)
    - Axis configuration
    - File saving

    Args:
        formation_name: Geological formation name
        csv_data_with_investigations: Dict mapping CSV names to:
            {"df": DataFrame, "param_column": str}
            DataFrame must have "Investigation", "Top Depth", and param_column
        parameter_display_name: Display name for X-axis
        output_folder: Directory to save plot
        investigation_color_map: Dict mapping investigations to hex colors
        csv_source_settings: Dict mapping CSV names to marker settings
        filter_column: Optional column to filter by (e.g., "is_manual_outlier")
        include_manual_additions: Whether to include manually added points
        show_test_type_legend: Whether to show test type shape legend
        figure_width: Figure width in inches
        figure_height: Figure height in inches
        dpi: Resolution for saved figure
        marker_edgecolors: Edge color for markers
        marker_linewidths: Edge width for markers
        x_limit_left: Left limit for X-axis
        y_margin: Margin to add to max depth
        legend_fixed_width: Whether to expand legend to axes width
        density_tracing_config: Configuration for CPT density line tracing
    """
    if not csv_data_with_investigations:
        logger.warning(f"⚠️ No data for formation {formation_name} - skipping plot")
        return

    logger.info(f"🎨 Generating matplotlib depth plot for: {formation_name}")

    # === FIGURE INITIALIZATION ===
    fig, ax = plt.subplots(figsize=(figure_width, figure_height))

    # === DATA COLLECTION ===
    all_x_values: List[float] = []
    all_y_values: List[float] = []
    plotted_investigations: Set[str] = set()
    test_types_in_formation: Set[str] = set()

    # === CPT LEGEND TRACKING ===
    # Track what CPT components are actually plotted for legend entries
    cpt_points_plotted: bool = False
    cpt_lines_plotted: bool = False

    # Sort by test type order
    sorted_items = sorted(
        csv_data_with_investigations.items(),
        key=lambda x: csv_source_settings.get(x[0], {}).get("order", 999),
    )

    # === PLOT DATA POINTS ===
    for csv_name, data_info in sorted_items:
        df = data_info["df"]
        param_column = data_info["param_column"]

        # Get test type settings
        settings = csv_source_settings.get(csv_name, {})
        if not settings.get("plotted", True):
            continue

        # Base plot_points setting (may be overridden per-investigation for CPT)
        base_plot_points = settings.get("plot_points", True)

        # CPT-specific: get auto-plot threshold for sparse investigation handling
        is_cpt = csv_name == "CPT by Geology.csv"
        cpt_auto_plot_threshold = settings.get("cpt_auto_plot_threshold", 50)

        # Apply filter if specified
        if filter_column and filter_column in df.columns:
            df_filtered = df[~df[filter_column]].copy()
        else:
            df_filtered = df.copy()

        # Handle manual additions
        if not include_manual_additions and "is_manual_addition" in df_filtered.columns:
            df_filtered = df_filtered[~df_filtered["is_manual_addition"]]

        if len(df_filtered) == 0:
            continue

        marker = settings.get("marker", "o")
        marker_size = settings.get("marker_size", DEFAULT_MARKER_SIZE)
        alpha = settings.get("alpha", 1.0)
        marker_thickness = settings.get("marker_thickness", marker_linewidths)

        test_types_in_formation.add(csv_name)

        # Plot each investigation
        for investigation in sorted(df_filtered["Investigation"].unique()):
            inv_data = df_filtered[df_filtered["Investigation"] == investigation]

            # ═══════════════════════════════════════════════════════════════════════
            # NOTE: max_kpa filtering (e.g., Vane Tests max_kpa=129) is now handled
            # in the orchestrator Phase 3a (Script-Specific Filtering) BEFORE unified
            # data objects are created. This ensures counts match plotted data.
            # DO NOT add data filtering here - add it to apply_test_type_threshold_filtering()
            # in data_pipeline.py instead. See orchestrator.py Phase 3a docstring.
            # ═══════════════════════════════════════════════════════════════════════

            x_values = inv_data[param_column].values
            y_values = inv_data["Top Depth"].values

            # === CPT AUTO-PLOT OVERRIDE (Per-Investigation Sparse Check) ===
            # If CPT and base_plot_points=False, check if this investigation has sparse data
            # Sparse investigations (< threshold) get points plotted individually
            plot_points = base_plot_points
            if is_cpt and not base_plot_points:
                if len(x_values) < cpt_auto_plot_threshold:
                    plot_points = True
                    logger.info(
                        f"  🔄 CPT Auto-Plot Override ({investigation}): {len(x_values)} points "
                        f"< {cpt_auto_plot_threshold} threshold - plotting enabled"
                    )

            # Skip if plot_points is False (after checking override)
            if not plot_points:
                continue

            # >>> DEBUG LOGGING FOR POINT-TO-POINT COMPARISON <<<
            # Only log for manually_modified plots to match monolith
            if (
                "Kimmeridge" in formation_name
                and "Unweathered" in formation_name
                and "manually_modified" in str(output_folder)
            ):
                for idx, row in inv_data.iterrows():
                    x_val = row.get(param_column, "N/A")
                    y_val = row.get("Top Depth", "N/A")
                    loc_id = row.get("Location ID", row.get("LocationID", "N/A"))
                    logger.info(f"    [m] {loc_id} | Depth={y_val} | X={x_val}")
            # >>> END DEBUG LOGGING <<<

            if len(x_values) == 0:
                continue

            color = investigation_color_map.get(investigation, "#000000")
            plotted_investigations.add(investigation)

            add_investigation_scatter(
                ax=ax,
                x_data=x_values,
                y_data=y_values,
                color=color,
                marker=marker,
                marker_size=marker_size,
                alpha=alpha,
                edgecolors=marker_edgecolors,
                linewidths=marker_thickness,
            )

            # Track CPT points plotted for legend entry
            if is_cpt:
                cpt_points_plotted = True

            all_x_values.extend(x_values)
            all_y_values.extend(y_values)

    # === ADD CPT DENSITY LINES ===
    # Process CPT data to add density lines per investigation
    if density_tracing_config and "CPT by Geology.csv" in csv_data_with_investigations:
        cpt_csv_name = "CPT by Geology.csv"
        cpt_settings = csv_source_settings.get(cpt_csv_name, {})
        density_line_settings = cpt_settings.get("density_line", {})

        # Check if density lines are enabled for CPT
        if density_line_settings.get("enabled", False):
            logger.info("🎨 Processing CPT density lines by investigation")

            cpt_data_info = csv_data_with_investigations[cpt_csv_name]
            cpt_df = cpt_data_info["df"]
            cpt_param_column = cpt_data_info["param_column"]

            # Apply the same filters as for scatter points
            if filter_column and filter_column in cpt_df.columns:
                cpt_df_filtered = cpt_df[~cpt_df[filter_column]].copy()
            else:
                cpt_df_filtered = cpt_df.copy()

            # Get CPT auto-plot settings for sparse investigation handling
            cpt_auto_plot_threshold = cpt_settings.get("cpt_auto_plot_threshold", 50)
            cpt_auto_plot_disable_density = cpt_settings.get(
                "cpt_auto_plot_disable_density", True
            )

            # Add density line traces
            density_values = add_cpt_density_lines_matplotlib(
                ax=ax,
                cpt_data=cpt_df_filtered,
                param_column=cpt_param_column,
                investigation_color_map=investigation_color_map,
                density_config=density_tracing_config,
                density_line_settings=density_line_settings,
                min_points_threshold=density_tracing_config["segment_detection"].get(
                    "min_segment_length", 5
                ),
                cpt_auto_plot_threshold=cpt_auto_plot_threshold,
                cpt_auto_plot_disable_density=cpt_auto_plot_disable_density,
            )

            if density_values:
                cpt_lines_plotted = True  # Track CPT lines plotted for legend entry
                logger.info(
                    f"  📊 Added density lines with {len(density_values)} total points"
                )
                # Include density values in x-axis scaling
                all_x_values.extend(density_values)

    # === ADD LEGEND ENTRIES ===
    add_investigation_legend_entries(
        ax=ax,
        plotted_investigations=plotted_investigations,
        investigation_color_map=investigation_color_map,
        marker_edgecolors=marker_edgecolors,
        marker_linewidths=marker_linewidths,
    )

    if show_test_type_legend:
        add_test_type_legend_entries(
            ax=ax,
            csv_source_settings=csv_source_settings,
            test_types_in_formation=test_types_in_formation,
            marker_edgecolors=marker_edgecolors,
            marker_linewidths=marker_linewidths,
            cpt_points_plotted=cpt_points_plotted,
            cpt_lines_plotted=cpt_lines_plotted,
        )

    # === CONFIGURE AXES ===
    if all_x_values and all_y_values:
        x_max = max(all_x_values)
        y_max = max(all_y_values)

        setup_depth_plot_axes(
            ax=ax,
            parameter_display_name=parameter_display_name,
            formation_name=formation_name,
            x_max=x_max,
            y_max=y_max,
            x_limit_left=x_limit_left,
            y_margin=y_margin,
        )

    # === CONFIGURE LEGEND ===
    configure_legend(
        ax=ax,
        fixed_width=legend_fixed_width,
        fig=fig,
    )

    # === SAVE ===
    sanitized_name = sanitize_filename(formation_name)
    output_path = output_folder / f"{sanitized_name}.png"

    save_matplotlib_figure(fig, output_path, dpi=dpi)
    logger.info(f"✅ Saved matplotlib depth plot: {output_path}")


def generate_xy_plot(
    formation_name: str,
    csv_data_with_investigations: Dict[str, Dict[str, Any]],
    x_display_name: str,
    y_display_name: str,
    output_folder: Path,
    investigation_color_map: Dict[str, str],
    csv_source_settings: Dict[str, Dict[str, Any]],
    filter_column: Optional[str] = None,
    include_manual_additions: bool = False,
    show_test_type_legend: bool = True,
    figure_width: Optional[float] = None,
    figure_height: Optional[float] = None,
    dpi: int = DEFAULT_DPI,
    marker_edgecolors: str = DEFAULT_MARKER_EDGECOLORS,
    marker_linewidths: float = DEFAULT_MARKER_LINEWIDTHS,
    legend_fixed_width: bool = True,
    classification_boundaries: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Generate complete X vs Y scatter plot with investigation-based coloring.

    High-level function that creates a complete X vs Y scatter plot including:
    - Figure creation and sizing
    - Data plotting by investigation and test type
    - Legend generation (investigation colors + test type shapes)
    - Axis configuration
    - Optional classification boundaries (e.g., A-line plasticity chart)
    - File saving

    This is for dual-parameter plots like CV vs Cell Pressure where one
    parameter is plotted against another (not vs depth).

    Args:
        formation_name: Geological formation name
        csv_data_with_investigations: Dict mapping CSV names to:
            {"df": DataFrame, "x_column": str, "y_column": str}
            DataFrame must have "Investigation" and both column names
        x_display_name: Display name for X-axis
        y_display_name: Display name for Y-axis
        output_folder: Directory to save plot
        investigation_color_map: Dict mapping investigations to hex colors
        csv_source_settings: Dict mapping CSV names to marker settings
        filter_column: Optional column to filter by (e.g., "is_manual_outlier")
        include_manual_additions: Whether to include manually added points
        show_test_type_legend: Whether to show test type shape legend
        figure_width: Figure width in inches (defaults to shared config)
        figure_height: Figure height in inches (defaults to shared config)
        dpi: Resolution for saved figure
        marker_edgecolors: Edge color for markers
        marker_linewidths: Edge width for markers
        legend_fixed_width: Whether to expand legend to axes width
        classification_boundaries: Optional dict with classification settings:
            {"plasticity_chart": True, "x_range": (0, 120), "y_range": (0, 80)}
    """
    if not csv_data_with_investigations:
        logger.warning(f"⚠️ No data for formation {formation_name} - skipping plot")
        return

    logger.info(f"🎨 Generating matplotlib X vs Y plot for: {formation_name}")

    # Get figure size from shared config if not provided
    if figure_width is None or figure_height is None:
        shared_width, shared_height = get_matplotlib_figure_size("xy")
        figure_width = figure_width or shared_width
        figure_height = figure_height or shared_height

    # === FIGURE INITIALIZATION ===
    fig, ax = plt.subplots(figsize=(figure_width, figure_height))

    # === DATA COLLECTION ===
    all_x_values: List[float] = []
    all_y_values: List[float] = []
    plotted_investigations: Set[str] = set()
    test_types_in_formation: Set[str] = set()

    # Sort by test type order
    sorted_items = sorted(
        csv_data_with_investigations.items(),
        key=lambda x: csv_source_settings.get(x[0], {}).get("order", 999),
    )

    # === PLOT DATA POINTS ===
    for csv_name, data_info in sorted_items:
        df = data_info["df"]
        x_column = data_info["x_column"]
        y_column = data_info["y_column"]

        # Get test type settings
        settings = csv_source_settings.get(csv_name, {})
        if not settings.get("plotted", True):
            continue
        if not settings.get("plot_points", True):
            continue

        # Apply filter if specified
        if filter_column and filter_column in df.columns:
            df_filtered = df[~df[filter_column]].copy()
        else:
            df_filtered = df.copy()

        # Handle manual additions
        if not include_manual_additions and "is_manual_addition" in df_filtered.columns:
            df_filtered = df_filtered[~df_filtered["is_manual_addition"]]

        if len(df_filtered) == 0:
            continue

        marker = settings.get("marker", "o")
        marker_size = settings.get("marker_size", DEFAULT_MARKER_SIZE)
        alpha = settings.get("alpha", 1.0)
        marker_thickness = settings.get("marker_thickness", marker_linewidths)

        test_types_in_formation.add(csv_name)

        # Plot each investigation
        for investigation in sorted(df_filtered["Investigation"].unique()):
            inv_data = df_filtered[df_filtered["Investigation"] == investigation]

            x_values = inv_data[x_column].values
            y_values = inv_data[y_column].values

            if len(x_values) == 0:
                continue

            color = investigation_color_map.get(investigation, "#000000")
            plotted_investigations.add(investigation)

            # >>> DEBUG LOGGING FOR POINT-TO-POINT COMPARISON <<<
            # Only log for KC_UW formation in matplotlib plots
            if "Kimmeridge" in formation_name and "Unweathered" in formation_name:
                for idx, row in inv_data.iterrows():
                    x_val = row.get(x_column, "N/A")
                    y_val = row.get(y_column, "N/A")
                    loc_id = row.get("Location ID", row.get("LocationID", "N/A"))
                    logger.info(f"    [m] {loc_id} | Depth={y_val} | X={x_val}")
            # >>> END DEBUG LOGGING <<<

            add_investigation_scatter(
                ax=ax,
                x_data=x_values,
                y_data=y_values,
                color=color,
                marker=marker,
                marker_size=marker_size,
                alpha=alpha,
                edgecolors=marker_edgecolors,
                linewidths=marker_thickness,
            )

            all_x_values.extend(x_values)
            all_y_values.extend(y_values)

    # === ADD LEGEND ENTRIES ===
    add_investigation_legend_entries(
        ax=ax,
        plotted_investigations=plotted_investigations,
        investigation_color_map=investigation_color_map,
        marker_edgecolors=marker_edgecolors,
        marker_linewidths=marker_linewidths,
    )

    if show_test_type_legend:
        add_test_type_legend_entries(
            ax=ax,
            csv_source_settings=csv_source_settings,
            test_types_in_formation=test_types_in_formation,
            marker_edgecolors=marker_edgecolors,
            marker_linewidths=marker_linewidths,
            # XY plots don't track CPT - use defaults (False)
        )

    # === CONFIGURE AXES ===
    # Check if classification boundaries specify fixed axis ranges
    use_fixed_ranges = False
    if classification_boundaries and classification_boundaries.get("plasticity_chart"):
        x_range = classification_boundaries.get("x_range", (0, 120))
        y_range = classification_boundaries.get("y_range", (0, 80))
        use_fixed_ranges = True

    if all_x_values and all_y_values:
        if use_fixed_ranges:
            # Use fixed ranges from classification boundaries
            setup_scatter_plot_axes(
                ax=ax,
                x_display_name=x_display_name,
                y_display_name=y_display_name,
                formation_name=formation_name,
                x_min=x_range[0],
                x_max=x_range[1],
                y_min=y_range[0],
                y_max=y_range[1],
            )
        else:
            # Use data-based ranges with margins
            x_min_val = min(all_x_values)
            x_max_val = max(all_x_values)
            y_min_val = min(all_y_values)
            y_max_val = max(all_y_values)

            setup_scatter_plot_axes(
                ax=ax,
                x_display_name=x_display_name,
                y_display_name=y_display_name,
                formation_name=formation_name,
                x_min=x_min_val * 0.9 if x_min_val > 0 else x_min_val * 1.1,
                x_max=x_max_val * 1.1,
                y_min=y_min_val * 0.9 if y_min_val > 0 else y_min_val * 1.1,
                y_max=y_max_val * 1.1,
            )

    # === ADD CLASSIFICATION BOUNDARIES (if enabled) ===
    if classification_boundaries and classification_boundaries.get("plasticity_chart"):
        x_range = classification_boundaries.get("x_range", (0, 120))
        y_range = classification_boundaries.get("y_range", (0, 80))
        add_matplotlib_plasticity_chart_boundaries(
            fig=fig,
            ax=ax,
            x_range=x_range,
            y_range=y_range,
        )

    # === CONFIGURE LEGEND ===
    configure_legend(
        ax=ax,
        fixed_width=legend_fixed_width,
        fig=fig,
        ncol=None,  # Let configure_legend calculate optimal ncol dynamically
    )

    # === SAVE ===
    sanitized_name = sanitize_filename(formation_name)
    output_path = output_folder / f"{sanitized_name}.png"

    save_matplotlib_figure(fig, output_path, dpi=dpi)
    logger.info(f"✅ Saved matplotlib X vs Y plot: {output_path}")


def generate_psd_plot(
    formation_name: str,
    psd_data: pd.DataFrame,
    output_folder: Path,
    investigation_color_map: Dict[str, str],
    particle_size_column: str = "Particle Size",
    percentage_passing_column: str = "Percentage Passing",
    sample_id_column: str = "Sample_ID",
    average_by_investigation: bool = True,
    show_classification_legend: bool = True,
    figure_width: Optional[float] = None,
    figure_height: Optional[float] = None,
    dpi: int = DEFAULT_DPI,
    x_limit_left: float = 0.001,
    x_limit_right: float = 200,
    y_limit_bottom: float = 0,
    y_limit_top: float = 105,
    linestyle: str = "-",
    linewidth: float = 2,
    alpha_labeled: float = 1.0,
    alpha_unlabeled: float = 0.5,
) -> None:
    """
    Generate particle size distribution plot with line plots.

    Creates PSD line plot with two modes:
    - MODE 1 (average_by_investigation=True): One averaged line per investigation
    - MODE 2 (average_by_investigation=False): One line per sample

    Args:
        formation_name: Geological formation name
        psd_data: DataFrame with Investigation, particle size, and percentage passing
        output_folder: Directory to save plot
        investigation_color_map: Dict mapping investigations to hex colors
        particle_size_column: Column name for particle size values
        percentage_passing_column: Column name for percentage passing values
        sample_id_column: Column name for sample identifiers
        average_by_investigation: If True, average values per investigation
        show_classification_legend: If True, add particle classification subplot
        figure_width: Figure width in inches (defaults to shared config)
        figure_height: Figure height in inches (defaults to shared config)
        dpi: Resolution for saved figure
        x_limit_left: Minimum particle size (mm)
        x_limit_right: Maximum particle size (mm)
        y_limit_bottom: Minimum percentage passing
        y_limit_top: Maximum percentage passing
        linestyle: Line style for plots
        linewidth: Line width for plots
        alpha_labeled: Alpha for labeled (first) lines
        alpha_unlabeled: Alpha for unlabeled (subsequent) lines
    """
    if psd_data.empty:
        logger.warning(f"⚠️ No data for formation {formation_name} - skipping plot")
        return

    logger.info(f"🎨 Generating PSD plot for: {formation_name}")

    # Get figure size from shared config if not provided
    if figure_width is None or figure_height is None:
        shared_width, shared_height = get_matplotlib_figure_size("psd")
        figure_width = figure_width or shared_width
        figure_height = figure_height or shared_height

    # === FIGURE INITIALIZATION ===
    if show_classification_legend:
        # Create figure with GridSpec for main plot + classification legend
        from matplotlib.gridspec import GridSpec

        classification_height_ratio = 0.12
        classification_spacing = 0.08

        fig = plt.figure(figsize=(figure_width, figure_height))
        gs = GridSpec(
            2,
            1,
            figure=fig,
            height_ratios=[1.0, classification_height_ratio],
            hspace=classification_spacing,
        )
        ax = fig.add_subplot(gs[0])
        classification_ax = fig.add_subplot(gs[1])
    else:
        fig, ax = plt.subplots(figsize=(figure_width, figure_height))
        classification_ax = None

    # === COLLECT INVESTIGATIONS ===
    all_investigations = sorted(psd_data["Investigation"].unique())

    # === PLOTTING SECTION ===
    if average_by_investigation:
        # MODE 1: One averaged line per investigation
        for investigation in all_investigations:
            inv_data = psd_data[psd_data["Investigation"] == investigation].copy()

            if inv_data.empty:
                continue

            # Group by particle size and calculate mean percentage passing
            averaged_data = (
                inv_data.groupby(particle_size_column)[percentage_passing_column]
                .mean()
                .reset_index()
            )
            averaged_data = averaged_data.sort_values(by=particle_size_column)

            particle_sizes = averaged_data[particle_size_column].values
            percentage_passing = averaged_data[percentage_passing_column].values

            if len(particle_sizes) == 0:
                continue

            inv_color = investigation_color_map.get(investigation, "#000000")

            ax.plot(
                particle_sizes,
                percentage_passing,
                linestyle=linestyle,
                linewidth=linewidth,
                color=inv_color,
                alpha=alpha_labeled,
                label=investigation,
            )
    else:
        # MODE 2: One line per sample (colored by investigation)
        labeled_investigations: Set[str] = set()

        for investigation in all_investigations:
            inv_data = psd_data[psd_data["Investigation"] == investigation].copy()

            if inv_data.empty:
                continue

            inv_color = investigation_color_map.get(investigation, "#000000")

            # Plot each unique sample within this investigation
            unique_samples = sorted(inv_data[sample_id_column].unique())

            for sample_id in unique_samples:
                sample_data = inv_data[inv_data[sample_id_column] == sample_id].copy()

                if sample_data.empty:
                    continue

                sample_data = sample_data.sort_values(by=particle_size_column)
                particle_sizes = sample_data[particle_size_column].values
                percentage_passing = sample_data[percentage_passing_column].values

                if len(particle_sizes) == 0:
                    continue

                # Label only first sample from each investigation for legend
                if investigation not in labeled_investigations:
                    ax.plot(
                        particle_sizes,
                        percentage_passing,
                        linestyle=linestyle,
                        linewidth=linewidth,
                        color=inv_color,
                        alpha=alpha_labeled,
                        label=investigation,
                    )
                    labeled_investigations.add(investigation)
                else:
                    ax.plot(
                        particle_sizes,
                        percentage_passing,
                        linestyle=linestyle,
                        linewidth=linewidth,
                        color=inv_color,
                        alpha=alpha_unlabeled,
                    )

    # === CONFIGURE AXES ===
    ax.set_xscale("log")
    ax.set_xlim(x_limit_left, x_limit_right)
    ax.set_ylim(y_limit_bottom, y_limit_top)

    ax.set_xlabel("Particle Size (mm)", fontsize=10, fontweight="normal", labelpad=50)
    ax.set_ylabel("Percentage Passing (%)", fontsize=10, fontweight="normal")
    ax.set_title(formation_name, fontsize=11, fontweight="bold")

    ax.grid(True, which="both", linestyle="-", linewidth=0.5, color="gray", alpha=0.5)

    # Set x-axis tick labels
    ax.set_xticks([0.001, 0.01, 0.1, 1, 10, 100])
    ax.get_xaxis().set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:g}"))

    # === ADD CLASSIFICATION LEGEND ===
    if show_classification_legend and classification_ax is not None:
        add_particle_size_classification_legend(
            classification_ax=classification_ax,
            x_limit_left=x_limit_left,
            x_limit_right=x_limit_right,
        )

    # === CONFIGURE LEGEND ===
    # Position legend at bottom with fixed width matching plot area (like monolith)
    # Get legend handles and labels
    handles, labels = ax.get_legend_handles_labels()
    num_entries = len(labels)

    # Calculate optimal number of columns
    optimal_ncol = min(3, max(1, num_entries // 2))
    legend_fontsize = 8

    # Position lower when classification is present
    if show_classification_legend:
        legend_y_position = -0.35
    else:
        legend_y_position = -0.17

    # Make legend match axes width exactly using mode='expand'
    fig.canvas.draw()
    bbox_expand = (0, legend_y_position, 1, 0)

    ax.legend(
        loc="lower left",
        bbox_to_anchor=bbox_expand,
        bbox_transform=ax.transAxes,
        edgecolor=DEFAULT_LEGEND_EDGECOLOR,
        framealpha=0.9,
        ncol=optimal_ncol,
        mode="expand",
        borderaxespad=0,
        labelspacing=0.5,
        borderpad=0.5,
        fontsize=legend_fontsize,
        columnspacing=1.0,
    )

    # === SAVE ===
    sanitized_name = sanitize_filename(formation_name)
    output_path = output_folder / f"{sanitized_name}.png"

    save_matplotlib_figure(fig, output_path, dpi=dpi)
    logger.info(f"✅ Saved matplotlib PSD plot: {output_path}")


def generate_manually_modified_depth_plot(
    formation_name: str,
    csv_data_with_investigations: Dict[str, Dict[str, Any]],
    parameter_display_name: str,
    output_folder: Path,
    investigation_color_map: Dict[str, str],
    csv_source_settings: Dict[str, Dict[str, Any]],
    figure_width: float = DEFAULT_FIGURE_WIDTH,
    figure_height: float = DEFAULT_FIGURE_HEIGHT,
    dpi: int = DEFAULT_DPI,
    marker_edgecolors: str = DEFAULT_MARKER_EDGECOLORS,
    marker_linewidths: float = DEFAULT_MARKER_LINEWIDTHS,
    x_limit_left: float = 0.0,
    y_margin: float = 1.0,
    legend_fixed_width: bool = True,
    show_test_type_legend: bool = True,
    density_tracing_config: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Generate depth plot with manual data modifications applied.

    Creates a plot that:
    - Excludes points marked as is_manual_outlier=True
    - Includes points marked as is_manual_addition=True
    - Adds CPT density lines (if enabled)

    This is a convenience wrapper around generate_depth_plot with the
    appropriate filter settings for manually modified plots.

    Args:
        formation_name: Geological formation name
        csv_data_with_investigations: Dict mapping CSV names to:
            {"df": DataFrame, "param_column": str}
            DataFrame must have "Investigation", "Top Depth", param_column,
            and optionally "is_manual_outlier", "is_manual_addition"
        parameter_display_name: Display name for X-axis
        output_folder: Directory to save plot
        investigation_color_map: Dict mapping investigations to hex colors
        csv_source_settings: Dict mapping CSV names to marker settings
        figure_width: Figure width in inches
        figure_height: Figure height in inches
        dpi: Resolution for saved figure
        marker_edgecolors: Edge color for markers
        marker_linewidths: Edge width for markers
        x_limit_left: Left limit for X-axis
        y_margin: Margin to add to max depth
        legend_fixed_width: Whether to expand legend to axes width
        show_test_type_legend: Whether to show test type shape legend
        density_tracing_config: Configuration for CPT density line tracing
    """
    generate_depth_plot(
        formation_name=formation_name,
        csv_data_with_investigations=csv_data_with_investigations,
        parameter_display_name=parameter_display_name,
        output_folder=output_folder,
        investigation_color_map=investigation_color_map,
        csv_source_settings=csv_source_settings,
        filter_column="is_manual_outlier",
        include_manual_additions=True,
        show_test_type_legend=show_test_type_legend,
        figure_width=figure_width,
        figure_height=figure_height,
        dpi=dpi,
        marker_edgecolors=marker_edgecolors,
        marker_linewidths=marker_linewidths,
        x_limit_left=x_limit_left,
        y_margin=y_margin,
        legend_fixed_width=legend_fixed_width,
        density_tracing_config=density_tracing_config,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 📦 MODULE EXPORTS
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    # Constants
    "DEFAULT_FIGURE_WIDTH",
    "DEFAULT_FIGURE_HEIGHT",
    "DEFAULT_DPI",
    "DEFAULT_MARKER_EDGECOLORS",
    "DEFAULT_MARKER_LINEWIDTHS",
    "DEFAULT_MARKER_SIZE",
    "DEFAULT_LEGEND_FONTSIZE",
    "DEFAULT_LEGEND_NCOL",
    # Color utilities (re-exported from shared_plotting)
    "hex_to_rgb",
    "create_investigation_color_mapping",
    # Legend components
    "add_investigation_legend_entries",
    "add_test_type_legend_entries",
    "configure_legend",
    # Axis configuration
    "setup_depth_plot_axes",
    "setup_scatter_plot_axes",
    # Scatter generation
    "add_investigation_scatter",
    # Export (sanitize_filename re-exported from shared_plotting)
    "sanitize_filename",
    "save_matplotlib_figure",
    # High-level plot generation
    "generate_depth_plot",
    "generate_xy_plot",
    "generate_manually_modified_depth_plot",
]
