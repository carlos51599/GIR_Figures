#!/usr/bin/env python3
"""
Shared Plotly Plotting Module - AI-Optimized Monolith
SESRO GIR Geotechnical Data Visualization

Architectural Overview:

Responsibility:
Provides shared Plotly plotting utilities for all geotechnical investigation-series plots.
Centralizes common components: marker mappings, color utilities, legend generation,
trace generation, hover text, classification lines, test type checkboxes, and HTML export.
Reduces code duplication across 15+ plotting scripts (~5,250 lines saved).

Key Interactions:
- Input: Investigation data, color palettes, test type settings
- Output: Plotly figure components and HTML files
- Callers: UndrainedShearStrength, MCvsDepth, A_line, CVvsCellPressure, PSD, etc.
- Shared Module: shared_plotting.py (common utilities for both backends)

Navigation Guide (use VS Code outline Ctrl+Shift+O):
1. CONSTANTS SECTION: Marker symbols, Unicode mappings
2. LEGEND COMPONENTS: Counts, dummy circles, total count
3. TRACE GENERATION: Data scatter traces, outlier traces
4. HOVER TEXT GENERATION: Depth plots, X-Y plots
5. AXIS PRESETS: Depth plots, X-Y plots
6. TEST TYPE UTILITIES: Symbol mapping builder
7. CHECKBOX GENERATION: Test type filter HTML/JS
8. LIVE COUNT PANELS: Non-interactive count displays with dynamic updates
9. HTML EXPORT: Save with config and injection

CONFIGURATION ARCHITECTURE:
- No CONFIG access in this module - all functions accept explicit primitives
- Caller scripts extract config and pass as parameters
- 100% testable without config mocking
"""

# Standard library imports
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set, Union

# Third-party imports
import numpy as np
import pandas as pd
import plotly.graph_objects as go

# Local imports - shared plotting utilities
from .shared_plotting_utils import (
    hex_to_rgba,
    create_investigation_color_mapping,
    sanitize_filename,
    get_plotly_figure_size,
)

# Logging Configuration
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# 📋 CONSTANTS SECTION
# ═══════════════════════════════════════════════════════════════════════════

# MODIFICATION POINT: Matplotlib to Plotly marker symbol mapping
MARKER_SYMBOL_MAP: Dict[str, str] = {
    "o": "circle",
    "s": "square",
    "^": "triangle-up",
    "v": "triangle-down",
    "d": "diamond",
    "D": "diamond",
    "p": "pentagon",
    "*": "star",
    "x": "x",
    "+": "cross",
    "h": "hexagon",
    ">": "triangle-right",
    "<": "triangle-left",
}

# MODIFICATION POINT: Unicode symbol representations for checkboxes
UNICODE_SYMBOL_MAP: Dict[str, str] = {
    "circle": "●",
    "square": "■",
    "triangle-up": "▲",
    "triangle-down": "▼",
    "diamond": "◆",
    "pentagon": "⬟",
    "star": "★",
    "x": "✕",
    "cross": "+",
    "hexagon": "⬡",
    "triangle-right": "▶",
    "triangle-left": "◀",
}

# MODIFICATION POINT: Centralized font configuration for all HTML panels
# Larger font for live count panels, matches legend font family
PANEL_FONT_CONFIG: Dict[str, str] = {
    "family": "Arial, sans-serif",
    "size_item": "12px",
    "size_header": "13px",
    "color": "rgb(42, 63, 95)",
}

# MODIFICATION POINT: Centralized layout configuration for all HTML panels
# All panels share the same width, left position, and vertical spacing
# Panels are EMBEDDED in the page (scroll with content) using position: absolute
# within a relative container, not position: fixed (which would stay on screen)
PANEL_LAYOUT_CONFIG: Dict[str, int] = {
    "width": 330,  # Fixed width in pixels for all panels (increased for 3-column layout)
    "left": 20,  # Left position within container in pixels
    "vertical_gap": 4,  # Gap between stacked panels in pixels (minimal spacing for compact layout)
    "top_offset": 80,  # Top offset to align with Plotly legend (matches plot margin.t)
}

# MODIFICATION POINT: Liquid Glass styling configuration
# Modern frosted glass aesthetic with translucent backgrounds and soft shadows
LIQUID_GLASS_CONFIG: Dict[str, str] = {
    # Base glass effect - translucent white with frosted blur
    "background": "rgba(255, 255, 255, 0.75)",
    "backdrop_filter": "blur(12px) saturate(180%)",
    "webkit_backdrop_filter": "blur(12px) saturate(180%)",
    # Border with subtle gradient glow
    "border": "1px solid rgba(255, 255, 255, 0.4)",
    "border_radius": "16px",
    # Soft shadow for depth
    "box_shadow": "0 8px 32px rgba(0, 0, 0, 0.1), inset 0 1px 1px rgba(255, 255, 255, 0.6)",
    # Panel padding
    "padding": "12px 16px",
}

# Pre-built CSS style strings for convenience
PANEL_STYLE_ITEM = f"font-family: {PANEL_FONT_CONFIG['family']}; font-size: {PANEL_FONT_CONFIG['size_item']}; color: {PANEL_FONT_CONFIG['color']};"
PANEL_STYLE_HEADER = f"font-family: {PANEL_FONT_CONFIG['family']}; font-size: {PANEL_FONT_CONFIG['size_header']}; font-weight: bold; color: {PANEL_FONT_CONFIG['color']};"

# Liquid glass panel base style - reusable CSS for all panels
LIQUID_GLASS_STYLE = (
    f"background: {LIQUID_GLASS_CONFIG['background']}; "
    f"backdrop-filter: {LIQUID_GLASS_CONFIG['backdrop_filter']}; "
    f"-webkit-backdrop-filter: {LIQUID_GLASS_CONFIG['webkit_backdrop_filter']}; "
    f"border: {LIQUID_GLASS_CONFIG['border']}; "
    f"border-radius: {LIQUID_GLASS_CONFIG['border_radius']}; "
    f"box-shadow: {LIQUID_GLASS_CONFIG['box_shadow']}; "
    f"padding: {LIQUID_GLASS_CONFIG['padding']};"
)

# JavaScript to round the SVG legend corners and add shadow (matching liquid glass panels)
# SVG rect elements use rx/ry attributes instead of CSS border-radius
# SVG uses filter elements for shadows instead of CSS box-shadow
LEGEND_ROUNDING_SCRIPT = """
<script>
    // Track if legend title has already been shifted (to prevent cumulative shifts)
    let legendTitleShifted = false;
    
    // Round legend corners, add shadow filter, expand dimensions, and shift position after Plotly renders
    function styleLegend() {
        const legendBg = document.querySelector('.legend .bg');
        const legendGroup = document.querySelector('.legend');
        if (legendBg) {
            // Add rounded corners
            legendBg.setAttribute('rx', '12');
            legendBg.setAttribute('ry', '12');
            
            // Expand legend box dimensions: +2px width, +10px height for title space
            // Only expand if not already expanded (check for marker attribute)
            if (!legendBg.hasAttribute('data-expanded')) {
                const currentWidth = parseFloat(legendBg.getAttribute('width')) || 0;
                const currentHeight = parseFloat(legendBg.getAttribute('height')) || 0;
                if (currentWidth > 0) {
                    legendBg.setAttribute('width', currentWidth + 2);
                }
                if (currentHeight > 0) {
                    legendBg.setAttribute('height', currentHeight + 2);
                }
                legendBg.setAttribute('data-expanded', 'true');
            }
            
            // Move the entire legend group to align with Test Types box (top: 100px)
            // Calculate the offset needed to position legend top at y=100px in SVG coordinates
            if (legendGroup) {
                const currentTransform = legendGroup.getAttribute('transform') || '';
                const translateMatch = currentTransform.match(/translate\\(([^,]+),\\s*([^)]+)\\)/);
                if (translateMatch) {
                    const x = parseFloat(translateMatch[1]);
                    // Set y to 85 to align with Test Types panel top
                    legendGroup.setAttribute('transform', `translate(${x}, 85)`);
                }
            }
            
            // Move legend title text 10px to the right (only once)
            const legendTitle = legendGroup ? legendGroup.querySelector('.legendtitletext') : null;
            if (legendTitle && !legendTitleShifted) {
                const titleX = parseFloat(legendTitle.getAttribute('x')) || 0;
                legendTitle.setAttribute('x', titleX + 10);
                legendTitleShifted = true;
            }
            
            // Create SVG shadow filter if not exists
            const svgElement = document.querySelector('.main-svg');
            if (svgElement && !document.getElementById('legendShadowFilter')) {
                const defs = svgElement.querySelector('defs') || document.createElementNS('http://www.w3.org/2000/svg', 'defs');
                if (!svgElement.querySelector('defs')) {
                    svgElement.insertBefore(defs, svgElement.firstChild);
                }
                const filter = document.createElementNS('http://www.w3.org/2000/svg', 'filter');
                filter.setAttribute('id', 'legendShadowFilter');
                filter.setAttribute('x', '-50%');
                filter.setAttribute('y', '-50%');
                filter.setAttribute('width', '200%');
                filter.setAttribute('height', '200%');
                
                // Create shadow effect matching liquid glass: 0 8px 32px rgba(0, 0, 0, 0.1)
                const shadow = document.createElementNS('http://www.w3.org/2000/svg', 'feDropShadow');
                shadow.setAttribute('dx', '0');
                shadow.setAttribute('dy', '4');
                shadow.setAttribute('stdDeviation', '8');
                shadow.setAttribute('flood-color', 'rgba(0, 0, 0, 0.15)');
                
                filter.appendChild(shadow);
                defs.appendChild(filter);
            }
            
            // Apply the shadow filter to legend background
            legendBg.setAttribute('filter', 'url(#legendShadowFilter)');
        }
    }
    
    // Re-apply legend styling after Plotly restyle events (legend clicks cause re-renders)
    function setupLegendStyleObserver() {
        const plotDiv = document.querySelector('.plotly-graph-div');
        if (plotDiv) {
            // Re-apply styling after any Plotly event that might reset the legend
            plotDiv.on('plotly_restyle', function() {
                // Use requestAnimationFrame to ensure DOM has updated
                requestAnimationFrame(styleLegend);
            });
            plotDiv.on('plotly_relayout', function() {
                requestAnimationFrame(styleLegend);
            });
            plotDiv.on('plotly_legendclick', function() {
                // Delay to allow Plotly to finish its internal updates
                setTimeout(styleLegend, 50);
            });
            plotDiv.on('plotly_legenddoubleclick', function() {
                setTimeout(styleLegend, 50);
            });
        }
    }
    
    // Run immediately and also observe for dynamic changes
    document.addEventListener('DOMContentLoaded', function() {
        styleLegend();
        setupLegendStyleObserver();
    });
    setTimeout(styleLegend, 100);
    setTimeout(styleLegend, 500);
    // Also try to setup observer if DOM already loaded
    if (document.readyState === 'complete') {
        setTimeout(setupLegendStyleObserver, 600);
    }
</script>
"""


# ═══════════════════════════════════════════════════════════════════════════
# 🧪 CLASSIFICATION BOUNDARIES SECTION
# Geotechnical classification lines for specialized plots (A-line, etc.)
# ═══════════════════════════════════════════════════════════════════════════


def add_plasticity_chart_boundaries(
    fig: go.Figure,
    x_range: Tuple[float, float] = (0, 120),
    y_range: Tuple[float, float] = (0, 80),
) -> List[Dict[str, Any]]:
    """
    Add A-line and U-line geotechnical classification boundaries to a Plotly figure.

    Standard Atterberg plasticity chart boundaries:
    - A-line: PI = 0.73 * (LL - 20) - separates clays (above) from silts (below)
    - U-line: PI = 0.9 * (LL - 8) - upper limit for natural soils
    - Vertical boundaries at LL = 35, 50, 70, 90 (plasticity transitions)
    - Horizontal boundaries at PI = 4, 7 (low plasticity thresholds)

    Args:
        fig: Plotly Figure to add traces and layout elements to
        x_range: Tuple of (min, max) for x-axis (Liquid Limit range)
        y_range: Tuple of (min, max) for y-axis (Plasticity Index range)

    Returns:
        List of annotation dictionaries for soil classification labels
    """
    # Generate x values for lines
    ll_range = np.linspace(x_range[0], x_range[1], 200)

    # A-line: PI = 0.73 * (LL - 20)
    a_line = 0.73 * (ll_range - 20)
    fig.add_trace(
        go.Scatter(
            x=ll_range,
            y=a_line,
            mode="lines",
            line=dict(color="black", width=2, dash="solid"),
            name="A-line",
            legendgroup="classification",
            showlegend=False,
            hoverinfo="skip",
        )
    )

    # U-line: PI = 0.9 * (LL - 8)
    u_line = 0.9 * (ll_range - 8)
    fig.add_trace(
        go.Scatter(
            x=ll_range,
            y=u_line,
            mode="lines",
            line=dict(color="gray", width=1.5, dash="dash"),
            name="U-line",
            legendgroup="classification",
            showlegend=False,
            hoverinfo="skip",
        )
    )

    # Vertical boundaries at LL = 35, 50, 70, 90
    for ll_val in [35, 50, 70, 90]:
        fig.add_vline(
            x=ll_val,
            line=dict(color="lightgray", width=1, dash="dot"),
            layer="below",
        )

    # Horizontal boundaries at PI = 4, 7
    for pi_val in [4, 7]:
        fig.add_hline(
            y=pi_val,
            line=dict(color="lightgray", width=1, dash="dot"),
            layer="below",
        )

    # Soil classification label annotations
    annotations = [
        dict(
            x=17.5, y=2, text="ML/OL", showarrow=False, font=dict(size=10, color="gray")
        ),
        dict(
            x=17.5,
            y=5.5,
            text="CL/OL",
            showarrow=False,
            font=dict(size=10, color="gray"),
        ),
        dict(x=42.5, y=2, text="MI", showarrow=False, font=dict(size=10, color="gray")),
        dict(
            x=42.5, y=12, text="CI", showarrow=False, font=dict(size=10, color="gray")
        ),
        dict(x=60, y=2, text="MI", showarrow=False, font=dict(size=10, color="gray")),
        dict(x=60, y=30, text="CI", showarrow=False, font=dict(size=10, color="gray")),
        dict(
            x=80, y=2, text="MH/OH", showarrow=False, font=dict(size=10, color="gray")
        ),
        dict(
            x=80, y=45, text="CH/OH", showarrow=False, font=dict(size=10, color="gray")
        ),
        dict(
            x=105, y=2, text="MH/OH", showarrow=False, font=dict(size=10, color="gray")
        ),
        dict(
            x=105, y=65, text="CH/OH", showarrow=False, font=dict(size=10, color="gray")
        ),
    ]

    return annotations


# ═══════════════════════════════════════════════════════════════════════════
# 📊 LEGEND COMPONENTS SECTION
# ═══════════════════════════════════════════════════════════════════════════


def calculate_investigation_counts(
    csv_data_with_investigations: Dict[str, Dict[str, Any]],
) -> Dict[str, int]:
    """
    Calculate data point counts per investigation across all CSV sources.

    Args:
        csv_data_with_investigations: Dict mapping CSV names to dicts with:
            - "df": DataFrame with "Investigation" column
            - "param_column": Parameter column name

    Returns:
        Dictionary mapping investigation names to total point counts
    """
    investigation_counts: Dict[str, int] = {}
    for csv_name, data_info in csv_data_with_investigations.items():
        df_with_inv = data_info["df"]
        for investigation in df_with_inv["Investigation"].unique():
            if investigation not in investigation_counts:
                investigation_counts[investigation] = 0
            investigation_counts[investigation] += len(
                df_with_inv[df_with_inv["Investigation"] == investigation]
            )
    return investigation_counts


def calculate_test_type_counts(
    csv_data_with_investigations: Dict[str, Dict[str, Any]],
    csv_source_settings: Optional[Dict[str, Dict[str, Any]]] = None,
    default_source_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, int]:
    """
    Calculate data point counts per test type (CSV source) across all data.

    Args:
        csv_data_with_investigations: Dict mapping CSV names to dicts with:
            - "df": DataFrame with data
            - "param_column": Parameter column name
        csv_source_settings: Optional dict of per-CSV settings (for display name lookup)
        default_source_settings: Optional default settings fallback

    Returns:
        Dictionary mapping display test type names to total point counts
    """
    test_type_counts: Dict[str, int] = {}
    for csv_name, data_info in csv_data_with_investigations.items():
        # Use display name if settings are provided, otherwise fallback to clean name
        if csv_source_settings is not None and default_source_settings is not None:
            test_name = get_test_type_display_name(
                csv_name, csv_source_settings, default_source_settings
            )
        else:
            test_name = csv_name.replace(" by Geology.csv", "").replace(".csv", "")
        df = data_info["df"]
        test_type_counts[test_name] = len(df)
    return test_type_counts


def get_test_type_display_name(
    csv_name: str,
    csv_source_settings: Dict[str, Dict[str, Any]],
    default_source_settings: Dict[str, Any],
) -> str:
    """
    Get display name for a test type from config settings.

    Uses legend_name_points if configured, otherwise cleans CSV filename.
    This ensures consistent display names in hover text and legend.

    Args:
        csv_name: Original CSV filename (e.g., "Shear Box Testing - Data.csv")
        csv_source_settings: Dict of per-CSV settings
        default_source_settings: Default settings fallback

    Returns:
        Display name for the test type (e.g., "Shear Box")
    """
    # Get settings for this CSV
    test_type_settings = csv_source_settings.get(csv_name, default_source_settings)

    # Use legend_name_points if configured, otherwise clean the CSV name
    clean_test_name = csv_name.replace(" by Geology.csv", "").replace(".csv", "")
    display_name = test_type_settings.get("legend_name_points", clean_test_name)

    return display_name


# MODIFICATION POINT: Column variations for sample identification
# Samples are identified by unique Location ID + Top Depth combinations
SAMPLE_LOCATION_COLUMNS: List[str] = [
    "Location ID",
    "LocationID",
    "PointID",
    "BH_ID",
]
SAMPLE_DEPTH_COLUMNS: List[str] = [
    "Top Depth",
    "DepthTop",
    "SampleTop",
    "Test Depth",
    "SPT Top Depth",
    "Depth Top",
    "Depth",
]


def _find_column(df: pd.DataFrame, column_variations: List[str]) -> Optional[str]:
    """
    Find first matching column name from list of variations.

    Args:
        df: DataFrame to search
        column_variations: List of possible column names

    Returns:
        First matching column name, or None if not found
    """
    for col in column_variations:
        if col in df.columns:
            return col
    return None


def _create_sample_id(
    row: pd.Series, loc_col: Optional[str], depth_col: Optional[str]
) -> str:
    """
    Create unique sample identifier from location and depth.

    Combines Location ID and Top Depth to create a unique string identifier
    for each sample. Used for dynamic sample counting in JavaScript.

    Args:
        row: DataFrame row containing location and depth data
        loc_col: Name of location ID column (or None if not found)
        depth_col: Name of depth column (or None if not found)

    Returns:
        Unique sample identifier string (e.g., "BH-01_5.5000")
    """
    loc_id = str(row.get(loc_col, "unknown")) if loc_col else "unknown"
    depth = row.get(depth_col, 0) if depth_col else 0
    if pd.isna(depth):
        depth = 0
    return f"{loc_id}_{float(depth):.4f}"


def _create_sample_ids_vectorized(
    df: pd.DataFrame, loc_col: Optional[str], depth_col: Optional[str]
) -> pd.Series:
    """
    Create unique sample identifiers from location and depth columns (vectorized).

    PERFORMANCE: Vectorized approach is 20-40× faster than row-by-row iteration.
    With 5,000 rows: iterrows ~200ms, vectorized ~5ms.

    Args:
        df: DataFrame with location and depth columns
        loc_col: Name of location ID column (or None if not found)
        depth_col: Name of depth column (or None if not found)

    Returns:
        Series of unique sample identifier strings (e.g., "BH-01_5.5000")
    """
    if loc_col and loc_col in df.columns:
        loc_ids = df[loc_col].fillna("unknown").astype(str)
    else:
        loc_ids = pd.Series(["unknown"] * len(df), index=df.index)

    if depth_col and depth_col in df.columns:
        depths = df[depth_col].fillna(0).round(4).astype(str)
    else:
        depths = pd.Series(["0.0000"] * len(df), index=df.index)

    return loc_ids + "_" + depths


def _build_extended_customdata(
    df: pd.DataFrame,
    clean_test_name: str,
) -> List[List[str]]:
    """
    Build extended customdata array with [test_type, sample_id] per point.

    This enables JavaScript to dynamically count unique samples when traces
    are toggled, instead of using static visibility-based counting.

    PERFORMANCE: Vectorized sample ID creation is 20-40× faster than iterrows.

    Args:
        df: DataFrame with location and depth columns
        clean_test_name: Test type name (e.g., "Classification")

    Returns:
        List of [test_type, sample_id] for each row in df
    """
    if df.empty:
        return []

    loc_col = _find_column(df, SAMPLE_LOCATION_COLUMNS)
    depth_col = _find_column(df, SAMPLE_DEPTH_COLUMNS)

    # Vectorized sample ID creation - 20-40× faster than iterrows
    sample_ids = _create_sample_ids_vectorized(df, loc_col, depth_col)

    # Build list of [test_type, sample_id] using list comprehension on values
    return [[clean_test_name, sid] for sid in sample_ids.values]


def calculate_investigation_sample_counts(
    csv_data_with_investigations: Dict[str, Dict[str, Any]],
) -> Dict[str, int]:
    """
    Calculate unique sample counts per investigation across ALL sources (deduplicated).

    NOTE: This uses GLOBAL unique samples across all sources, so the same sample
    appearing in multiple CSVs is only counted once per investigation.

    A sample is defined as a unique Location ID + Top Depth combination.

    PERFORMANCE: Vectorized approach using pd.concat and groupby is 15-30× faster
    than nested iterrows loops.

    Args:
        csv_data_with_investigations: Dict mapping CSV names to dicts with:
            - "df": DataFrame with "Investigation" column
            - "param_column": Parameter column name

    Returns:
        Dictionary mapping investigation names to unique sample counts (deduplicated)
    """
    # Collect all data into a single DataFrame for vectorized processing
    all_samples = []

    for csv_name, data_info in csv_data_with_investigations.items():
        df = data_info["df"]
        if df.empty:
            continue

        # Find location and depth columns
        loc_col = _find_column(df, SAMPLE_LOCATION_COLUMNS)
        depth_col = _find_column(df, SAMPLE_DEPTH_COLUMNS)

        if loc_col is None or depth_col is None:
            continue

        # Extract relevant columns with vectorized operations
        sample_df = pd.DataFrame(
            {
                "investigation": df["Investigation"],
                "loc_id": df[loc_col].fillna("").astype(str),
                "depth": df[depth_col].fillna(0).round(4),
            }
        )
        # Filter out empty location IDs and invalid depths
        sample_df = sample_df[
            (sample_df["loc_id"] != "") & (sample_df["depth"].notna())
        ]
        all_samples.append(sample_df)

    if not all_samples:
        return {}

    # Combine all sources and deduplicate globally per investigation
    combined = pd.concat(all_samples, ignore_index=True)
    # Drop duplicates across all sources (global deduplication)
    unique_samples = combined.drop_duplicates(
        subset=["investigation", "loc_id", "depth"]
    )
    # Count unique samples per investigation
    counts = unique_samples.groupby("investigation").size().to_dict()

    return counts


def calculate_test_type_sample_counts(
    csv_data_with_investigations: Dict[str, Dict[str, Any]],
    csv_source_settings: Optional[Dict[str, Dict[str, Any]]] = None,
    default_source_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, int]:
    """
    Calculate unique sample counts per test type (CSV source) across all data.

    A sample is defined as a unique Location ID + Top Depth combination.
    This is different from point counts which count every data row.

    PERFORMANCE: Vectorized drop_duplicates is 15-25× faster than iterrows with sets.

    Args:
        csv_data_with_investigations: Dict mapping CSV names to dicts with:
            - "df": DataFrame with data
            - "param_column": Parameter column name
        csv_source_settings: Optional dict of per-CSV settings (for display name lookup)
        default_source_settings: Optional default settings fallback

    Returns:
        Dictionary mapping display test type names to unique sample counts
    """
    test_type_sample_counts: Dict[str, int] = {}

    for csv_name, data_info in csv_data_with_investigations.items():
        # Use display name if settings are provided, otherwise fallback to clean name
        if csv_source_settings is not None and default_source_settings is not None:
            test_name = get_test_type_display_name(
                csv_name, csv_source_settings, default_source_settings
            )
        else:
            test_name = csv_name.replace(" by Geology.csv", "").replace(".csv", "")
        df = data_info["df"]

        if df.empty:
            test_type_sample_counts[test_name] = 0
            continue

        # Find location and depth columns
        loc_col = _find_column(df, SAMPLE_LOCATION_COLUMNS)
        depth_col = _find_column(df, SAMPLE_DEPTH_COLUMNS)

        if loc_col is None or depth_col is None:
            test_type_sample_counts[test_name] = 0
            continue

        # Vectorized unique sample counting - 15-25× faster than iterrows
        sample_df = pd.DataFrame(
            {
                "loc_id": df[loc_col].fillna("").astype(str),
                "depth": df[depth_col].round(4),
            }
        )
        # Filter out empty location IDs and invalid depths
        sample_df = sample_df[
            (sample_df["loc_id"] != "") & (sample_df["depth"].notna())
        ]
        # Count unique combinations using drop_duplicates
        unique_count = len(sample_df.drop_duplicates())
        test_type_sample_counts[test_name] = unique_count

    return test_type_sample_counts


def calculate_global_unique_sample_count(
    csv_data_with_investigations: Dict[str, Dict[str, Any]],
) -> int:
    """
    Calculate total sample count as SUM of per-source unique samples.

    NOTE: This intentionally allows the same sample to be counted multiple times
    if it appears in multiple CSV sources. This is correct because the same
    physical sample can have different test values recorded in different sources
    (e.g., Moisture Content in Classification vs Triaxial tests).

    A sample is defined as a unique Location ID + Top Depth combination
    within each source.

    PERFORMANCE: Vectorized drop_duplicates is 15-25× faster than iterrows with sets.

    Args:
        csv_data_with_investigations: Dict mapping CSV names to dicts with:
            - "df": DataFrame with data
            - "param_column": Parameter column name

    Returns:
        Total count as sum of unique samples per source
    """
    total_count = 0

    for csv_name, data_info in csv_data_with_investigations.items():
        df = data_info["df"]
        if df.empty:
            continue

        # Find location and depth columns
        loc_col = _find_column(df, SAMPLE_LOCATION_COLUMNS)
        depth_col = _find_column(df, SAMPLE_DEPTH_COLUMNS)

        if loc_col is None or depth_col is None:
            continue

        # Vectorized unique sample counting - 15-25× faster than iterrows
        sample_df = pd.DataFrame(
            {
                "loc_id": df[loc_col].fillna("").astype(str),
                "depth": df[depth_col].round(4),
            }
        )
        sample_df = sample_df[
            (sample_df["loc_id"] != "") & (sample_df["depth"].notna())
        ]
        total_count += len(sample_df.drop_duplicates())

    return total_count


def calculate_global_deduplicated_sample_count(
    csv_data_with_investigations: Dict[str, Dict[str, Any]],
) -> int:
    """
    Calculate truly deduplicated sample count across ALL sources.

    This counts each unique sample only ONCE, even if it appears in multiple
    CSV sources. Used for investigation totals where we want a single count
    of physical samples tested.

    A sample is defined as a unique Location ID + Top Depth combination.

    PERFORMANCE: Vectorized pd.concat and drop_duplicates is 15-30× faster
    than nested iterrows with sets.

    Args:
        csv_data_with_investigations: Dict mapping CSV names to dicts with:
            - "df": DataFrame with data
            - "param_column": Parameter column name

    Returns:
        Count of globally unique samples (deduplicated across sources)
    """
    all_samples = []

    for csv_name, data_info in csv_data_with_investigations.items():
        df = data_info["df"]
        if df.empty:
            continue

        # Find location and depth columns
        loc_col = _find_column(df, SAMPLE_LOCATION_COLUMNS)
        depth_col = _find_column(df, SAMPLE_DEPTH_COLUMNS)

        if loc_col is None or depth_col is None:
            continue

        # Extract relevant columns with vectorized operations
        sample_df = pd.DataFrame(
            {
                "loc_id": df[loc_col].fillna("").astype(str),
                "depth": df[depth_col].round(4),
            }
        )
        sample_df = sample_df[
            (sample_df["loc_id"] != "") & (sample_df["depth"].notna())
        ]
        all_samples.append(sample_df)

    if not all_samples:
        return 0

    # Combine all sources and deduplicate globally
    combined = pd.concat(all_samples, ignore_index=True)
    return len(combined.drop_duplicates())


def add_dummy_circle_legend_traces(
    fig: go.Figure,
    legend_investigations: Set[str],
    investigation_color_map: Dict[str, str],
    investigation_counts: Dict[str, int],
) -> None:
    """
    Add invisible circle traces for consistent legend symbols.

    When force_circle_markers is True, these dummy traces with circle markers
    appear in the legend to provide consistent symbols. The real data traces
    (with various marker shapes) are hidden from legend but still visible.

    Args:
        fig: Plotly figure to add traces to
        legend_investigations: Set of investigation names that have data
        investigation_color_map: Dict mapping investigations to hex colors
        investigation_counts: Dict mapping investigations to data point counts
    """
    for investigation in sorted(legend_investigations):
        inv_color = investigation_color_map[investigation]
        rgba_color = hex_to_rgba(inv_color, alpha=1.0)

        # Legend includes count of data points (n=x)
        count = investigation_counts.get(investigation, 0)
        legend_name = f"{investigation} (n={count})"

        fig.add_trace(
            go.Scatter(
                x=[None],  # No data - invisible on plot
                y=[None],  # No data - invisible on plot
                mode="markers",
                marker=dict(
                    symbol="circle",  # Force circle for legend
                    size=10,
                    color=rgba_color,
                    line=dict(color="black", width=0.5),
                ),
                name=legend_name,
                legendgroup=investigation,  # Same group as real traces
                showlegend=True,
                hoverinfo="skip",
            )
        )


def add_total_count_legend_entry(
    fig: go.Figure,
    investigation_counts: Dict[str, int],
) -> None:
    """
    Add total count text entry to legend.

    Creates a text-only legend entry showing the total number of data points
    across all investigations.

    Args:
        fig: Plotly figure to add trace to
        investigation_counts: Dict mapping investigations to data point counts
    """
    total_count = sum(investigation_counts.values())
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="text",
            name=f"<b>Total n={total_count}</b>",
            showlegend=True,
            hoverinfo="skip",
            legendgroup="total_count",
            legendrank=9999,  # Force to bottom of legend
        )
    )


def add_dummy_outlier_legend_trace(
    fig: go.Figure,
    outlier_count: int = 0,
) -> None:
    """
    Add invisible circle trace for consistent Outlier legend symbol.

    Creates a dummy trace with a circle marker for the Outlier legend entry,
    matching the treatment of investigation legend entries. The real outlier
    traces use various marker shapes but are hidden from the legend.

    Args:
        fig: Plotly figure to add trace to
        outlier_count: Total number of outlier data points
    """
    legend_name = f"Outlier (n={outlier_count})" if outlier_count > 0 else "Outlier"

    fig.add_trace(
        go.Scatter(
            x=[None],  # No data - invisible on plot
            y=[None],  # No data - invisible on plot
            mode="markers",
            marker=dict(
                symbol="circle",  # Force circle for legend (consistent with investigations)
                size=10,
                color="red",
                line=dict(color="darkred", width=1),
            ),
            name=legend_name,
            legendgroup="Outlier",  # Same group as real outlier traces
            showlegend=True,
            hoverinfo="skip",
            legendrank=2000,  # Push outliers to bottom of legend
        )
    )


# ═══════════════════════════════════════════════════════════════════════════
# 📈 TRACE GENERATION SECTION
# ═══════════════════════════════════════════════════════════════════════════


def add_investigation_scatter_trace(
    fig: go.Figure,
    x_data: pd.Series,
    y_data: pd.Series,
    investigation: str,
    plotly_symbol: str,
    marker_size: float,
    rgba_color: str,
    legend_name: str,
    hover_text: List[str],
    show_legend: bool = True,
    legend_group: Optional[str] = None,
    custom_data: Optional[List[List[str]]] = None,
) -> None:
    """
    Add a scatter trace with investigation-based styling.

    Creates a scatter trace for one investigation/test-type combination.
    Handles consistent marker styling, legend grouping, and hover behavior.

    Args:
        fig: Plotly figure to add trace to
        x_data: X-axis values (parameter or LL)
        y_data: Y-axis values (depth or PI)
        investigation: Investigation name for grouping
        plotly_symbol: Plotly marker symbol (e.g., "circle", "triangle-up")
        marker_size: Marker size in Plotly units
        rgba_color: RGBA color string (e.g., "rgba(0,87,183,0.7)")
        legend_name: Display name in legend (e.g., "Investigation A (n=25)")
        hover_text: List of hover text strings for each point
        show_legend: Whether to show this trace in legend
        legend_group: Legend group name (defaults to investigation)
        custom_data: Custom data for filtering (e.g., [[test_type]] * n)
    """
    if legend_group is None:
        legend_group = investigation

    fig.add_trace(
        go.Scatter(
            x=x_data,
            y=y_data,
            mode="markers",
            marker=dict(
                symbol=plotly_symbol,
                size=marker_size,
                color=rgba_color,
                line=dict(color="black", width=0.5),
            ),
            name=legend_name,
            legendgroup=legend_group,
            showlegend=show_legend,
            hovertext=hover_text,
            hoverinfo="text",
            customdata=custom_data,
        )
    )


def add_outlier_traces(
    fig: go.Figure,
    outliers_by_source: Dict[str, Dict[str, Dict[str, Any]]],
    use_test_type_symbols: bool = True,
) -> int:
    """
    Add outlier traces for all collected outlier data.

    Creates red marker traces for outliers with their own "Outlier" legendgroup.
    Outliers can be hidden by clicking either:
    1. The "Outlier" entry in the legend (hides all outliers)
    2. An investigation entry (custom JS hides that investigation's outliers)

    NOTE: This function does NOT add the legend entry - call add_dummy_outlier_legend_trace()
    separately to add a consistent circle marker legend entry.

    The customdata for outlier traces contains [test_type, investigation, sample_id]
    to enable JavaScript to determine which investigation and sample each outlier belongs to.

    Args:
        fig: Plotly figure to add traces to
        outliers_by_source: Nested dict structure:
            {csv_name: {investigation: {
                "x": [values],
                "y": [values],
                "hover_text": [texts],
                "customdata": [[test_type, investigation, sample_id], ...],
                "marker_symbol": "symbol" (optional if use_test_type_symbols=True)
            }}}
        use_test_type_symbols: If True, use test-type marker symbols for outliers.
            If False, use uniform circle markers.

    Returns:
        Total count of outlier data points added

    Example:
        >>> outliers = {
        ...     "Classification by Geology.csv": {
        ...         "GI 1": {
        ...             "x": [1.2, 3.4],
        ...             "y": [5.6, 7.8],
        ...             "hover_text": ["Point 1", "Point 2"],
        ...             "customdata": [["Classification", "GI 1", "BH-01_5.5000"], ...],
        ...             "marker_symbol": "triangle-up"
        ...         }
        ...     }
        ... }
        >>> outlier_count = add_outlier_traces(fig, outliers, use_test_type_symbols=True)
        >>> add_dummy_outlier_legend_trace(fig, outlier_count)
    """
    total_outlier_count = 0

    for csv_name, investigations_dict in outliers_by_source.items():
        clean_test_name = csv_name.replace(" by Geology.csv", "").replace(".csv", "")

        for investigation, outlier_info in investigations_dict.items():
            if len(outlier_info.get("x", [])) == 0:
                continue

            # Count outliers
            total_outlier_count += len(outlier_info["x"])

            # Determine marker symbol
            if use_test_type_symbols and "marker_symbol" in outlier_info:
                marker_symbol = outlier_info["marker_symbol"]
            else:
                marker_symbol = "circle"

            # Use pre-collected customdata with [test_type, investigation, sample_id]
            # Fall back to building it without sample_id if not available (legacy)
            if "customdata" in outlier_info and outlier_info["customdata"]:
                customdata = outlier_info["customdata"]
            else:
                # Legacy fallback: [[test_type, investigation], ...]
                customdata = [
                    [clean_test_name, investigation]
                    for _ in range(len(outlier_info["x"]))
                ]

            # Use "Outlier" legendgroup for separate legend entry
            # showlegend=False - the dummy circle trace handles the legend entry
            # Custom JS will handle hiding when parent investigation is clicked
            fig.add_trace(
                go.Scatter(
                    x=outlier_info["x"],
                    y=outlier_info["y"],
                    mode="markers",
                    marker=dict(
                        symbol=marker_symbol,
                        size=10,
                        color="red",
                        line=dict(color="darkred", width=1),
                    ),
                    name="Outlier",
                    legendgroup="Outlier",  # Separate legend entry for outliers
                    showlegend=False,  # Dummy circle trace handles legend
                    hovertext=outlier_info.get("hover_text", []),
                    hoverinfo="text",
                    customdata=customdata,
                    legendrank=2000,  # Push outliers to bottom of legend
                )
            )

    return total_outlier_count


# ═══════════════════════════════════════════════════════════════════════════
# 📝 HOVER TEXT GENERATION SECTION
# ═══════════════════════════════════════════════════════════════════════════


def create_hover_text(
    df: pd.DataFrame,
    investigation: str,
    x_column: str,
    y_column: str,
    x_display: str,
    y_display: str,
    test_type: str,
    is_outlier: bool = False,
    location_id_column: str = "Location ID",
) -> List[str]:
    """
    Unified hover text generator for all plot types (depth, XY, PSD).

    Creates formatted HTML hover tooltips showing investigation, location,
    X and Y values, and test type. Works for both depth plots and XY plots.

    PERFORMANCE: Vectorized approach is 30-50× faster than iterrows().
    With 1,000 rows: iterrows ~90ms, vectorized ~2ms.

    All parameters are explicit primitives - no hidden config objects.

    Args:
        df: DataFrame with plot data
        investigation: Investigation name to display
        x_column: Column name for X-axis values (parameter for depth, x_param for XY)
        y_column: Column name for Y-axis values ("Top Depth" for depth, y_param for XY)
        x_display: Display label for X-axis (e.g., "Moisture Content (%)")
        y_display: Display label for Y-axis (e.g., "Depth (m)" or "Plasticity Index (%)")
        test_type: Test type name to display
        is_outlier: If True, adds "OUTLIER - " prefix to investigation name
        location_id_column: Column name for location IDs

    Returns:
        List of HTML-formatted hover text strings matching DataFrame row count

    Replaces:
        - create_depth_plot_hover_text()
        - create_xy_plot_hover_text()

    Example (depth plot):
        >>> hover_text = create_hover_text(
        ...     df, "Site A", "Moisture Content", "Top Depth",
        ...     "Moisture Content (%)", "Depth (m)", "Classification"
        ... )

    Example (XY plot):
        >>> hover_text = create_hover_text(
        ...     df, "Site A", "Liquid Limit", "Plasticity Index",
        ...     "Liquid Limit (%)", "Plasticity Index (%)", "Atterberg"
        ... )
    """
    if df.empty:
        return []

    prefix = "OUTLIER - " if is_outlier else ""

    # Vectorized string construction - 30-50× faster than iterrows
    location_ids = df[location_id_column].fillna("N/A").astype(str)
    x_values = df[x_column].fillna(0).round(2).astype(str)
    y_values = df[y_column].fillna(0).round(2).astype(str)

    # Build hover text using vectorized string concatenation
    hover_text = (
        f"<b>{prefix}{investigation}</b><br>"
        + "Location ID: "
        + location_ids
        + "<br>"
        + f"{x_display}: "
        + x_values
        + "<br>"
        + f"{y_display}: "
        + y_values
        + "<br>"
        + f"Test Type: {test_type}"
    )

    return hover_text.tolist()


# ═══════════════════════════════════════════════════════════════════════════
# ⚙️ AXIS CONFIGURATION PRESETS SECTION
# ═══════════════════════════════════════════════════════════════════════════


def _build_title_config(formation_name: str) -> Dict[str, Any]:
    """
    Build shared title configuration for Plotly layouts.

    Extracted to eliminate duplication between depth and XY layouts.
    This configuration is 100% identical across all plot types.

    Args:
        formation_name: Formation name to display as title

    Returns:
        Dict suitable for layout["title"]
    """
    return {
        "text": formation_name,
        "font": {"size": 14, "family": "Arial"},
        "x": 0.5,  # Center over plot area (xref='paper' makes this relative to plot area)
        "xref": "paper",  # 'paper' = plot area only (excludes margins)
        "xanchor": "center",  # Center the title text at x position
        "y": 0.98,  # Position title higher (near top of figure)
        "yanchor": "top",
    }


def _build_legend_config() -> Dict[str, Any]:
    """
    Build shared legend configuration for Plotly layouts.

    Extracted to eliminate duplication between depth and XY layouts.
    This configuration is 100% identical across all plot types.

    Returns:
        Dict suitable for layout["legend"]
    """
    return {
        "title": {
            "text": "<b>   Investigations</b><br> ",
            "font": {"size": 13, "family": "Arial", "color": "rgb(42, 63, 95)"},
        },
        "orientation": "v",
        "yanchor": "top",
        "y": 1,
        "xanchor": "left",
        "x": 1.02,
        "font": {"size": 12, "family": "Arial", "color": "rgb(42, 63, 95)"},
        "groupclick": "togglegroup",
        "itemdoubleclick": "toggle",
        # Liquid glass styling for legend - soft semi-transparent white border
        "bgcolor": "rgba(255, 255, 255, 0.85)",
        "bordercolor": "rgba(255, 255, 255, 0.4)",
        "borderwidth": 1,
    }


def get_plot_layout(
    formation_name: str,
    x_display: str,
    y_display: str,
    invert_y: bool = False,
    log_x: bool = False,
    x_side: str = "bottom",
    plot_type: str = "xy",
    x_range: Optional[Tuple[float, float]] = None,
    y_range: Optional[Tuple[float, float]] = None,
) -> Dict[str, Any]:
    """
    Unified layout configuration for all plot types (depth, XY, PSD).

    All parameters are explicit primitives - no hidden objects.
    Uses extracted helper functions to avoid code duplication.

    Args:
        formation_name: Formation name for title
        x_display: Display label for X-axis
        y_display: Display label for Y-axis
        invert_y: If True, reverse Y-axis (for depth plots)
        log_x: If True, use logarithmic X-axis scale (for PSD plots)
        x_side: X-axis position - "top" for depth plots, "bottom" otherwise
        plot_type: One of "depth", "xy", "psd" - used for figure size lookup
        x_range: Optional tuple (min, max) for X-axis range
        y_range: Optional tuple (min, max) for Y-axis range

    Returns:
        Dict suitable for fig.update_layout(**layout)

    Replaces:
        - get_depth_plot_layout()
        - get_xy_plot_layout()

    Example (depth plot):
        >>> layout = get_plot_layout(
        ...     "Gault Clay", "Moisture Content (%)", "Depth (m)",
        ...     invert_y=True, x_side="top", plot_type="depth"
        ... )

    Example (XY plot):
        >>> layout = get_plot_layout(
        ...     "Gault Clay", "Liquid Limit (%)", "Plasticity Index (%)",
        ...     plot_type="xy"
        ... )

    Example (PSD plot):
        >>> layout = get_plot_layout(
        ...     "Gault Clay", "Particle Size (mm)", "Percentage Passing (%)",
        ...     log_x=True, plot_type="psd"
        ... )
    """
    plotly_size = get_plotly_figure_size(plot_type)

    # === X-AXIS CONFIG ===
    xaxis_config: Dict[str, Any] = {
        "title": x_display,
        "showgrid": True,
        "gridwidth": 0.5,
        "gridcolor": "rgba(128,128,128,0.3)",
    }
    if x_side == "top":
        xaxis_config["side"] = "top"
    if log_x:
        xaxis_config["type"] = "log"
    if x_range is not None:
        xaxis_config["range"] = list(x_range)

    # === Y-AXIS CONFIG ===
    yaxis_config: Dict[str, Any] = {
        "title": y_display,
        "showgrid": True,
        "gridwidth": 0.5,
        "gridcolor": "rgba(128,128,128,0.3)",
    }
    if invert_y:
        yaxis_config["autorange"] = "reversed"
    if y_range is not None:
        yaxis_config["range"] = list(y_range)

    # === BUILD COMPLETE LAYOUT ===
    return {
        "title": _build_title_config(formation_name),
        "xaxis": xaxis_config,
        "yaxis": yaxis_config,
        "hovermode": "closest",
        "legend": _build_legend_config(),
        "plot_bgcolor": "white",
        "width": plotly_size["width"],
        "height": plotly_size["height"],
        "margin": dict(**plotly_size["margin"]),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 🔧 TEST TYPE UTILITIES SECTION
# ═══════════════════════════════════════════════════════════════════════════


def build_test_type_symbol_mapping(
    csv_names: List[str],
    csv_source_settings: Dict[str, Dict[str, Any]],
    default_source_settings: Dict[str, Any],
    test_types_in_formation: Set[str],
) -> Dict[str, str]:
    """
    Build mapping of test type names to Plotly marker symbols.

    Extracts marker symbols from CSV source settings and converts
    matplotlib markers to Plotly symbols.

    Args:
        csv_names: List of CSV filenames to process
        csv_source_settings: Dict mapping CSV names to settings with "marker" key
        default_source_settings: Default settings dict with "marker" key
        test_types_in_formation: Set of test types present in the data (using display names)

    Returns:
        Dict mapping display test type names to Plotly symbols

    Example:
        >>> build_test_type_symbol_mapping(
        ...     ["Classification by Geology.csv"],
        ...     {"Classification by Geology.csv": {"marker": "^", "plotted": True}},
        ...     {"marker": "o"},
        ...     {"Classification"}
        ... )
        {"Classification": "triangle-up"}
    """
    test_type_to_symbol: Dict[str, str] = {}

    for csv_name in sorted(csv_names):
        settings = csv_source_settings.get(csv_name, default_source_settings)
        # Get display name to match what's stored in test_types_in_formation
        display_test_name = get_test_type_display_name(
            csv_name, csv_source_settings, default_source_settings
        )

        if display_test_name in test_types_in_formation:
            marker_style = settings.get("marker", "o")
            plotly_symbol = MARKER_SYMBOL_MAP.get(marker_style, "circle")
            test_type_to_symbol[display_test_name] = plotly_symbol

    return test_type_to_symbol


# ═══════════════════════════════════════════════════════════════════════════
# ☑️ TEST TYPE CHECKBOX GENERATION SECTION
# ═══════════════════════════════════════════════════════════════════════════


def generate_test_type_checkbox_html(
    test_types_in_formation: Set[str],
    test_type_to_symbol: Dict[str, str],
    test_type_to_legend_name: Optional[Dict[str, str]] = None,
    test_type_counts: Optional[Dict[str, int]] = None,
) -> str:
    """
    Generate HTML/CSS/JS for test type filter checkboxes.

    Creates a fixed-position checkbox panel that allows users to toggle
    visibility of data points by test type (marker shape).

    Args:
        test_types_in_formation: Set of test type names present in the data
        test_type_to_symbol: Dict mapping test type names to Plotly symbols
        test_type_to_legend_name: Optional dict mapping test types to display names
            (defaults to test type name if not provided)
        test_type_counts: Optional dict mapping test types to data point counts
            (if provided, counts are displayed as "Test Type (n=X)")

    Returns:
        HTML string with checkbox div and JavaScript for filtering
    """
    if test_type_to_legend_name is None:
        test_type_to_legend_name = {}
    if test_type_counts is None:
        test_type_counts = {}

    # Calculate total count for header
    total_count = sum(test_type_counts.get(tt, 0) for tt in test_types_in_formation)

    test_type_checkboxes = []
    for test_type in sorted(test_types_in_formation):
        symbol = test_type_to_symbol.get(test_type, "circle")
        display_name = test_type_to_legend_name.get(test_type, test_type)
        symbol_display = UNICODE_SYMBOL_MAP.get(symbol, "●")

        # Add count to display name if available
        count = test_type_counts.get(test_type, 0)
        if count > 0:
            display_name = f"{display_name} (n={count})"

        # Create unique ID for checkbox-label association (sanitize test_type for valid HTML id)
        checkbox_id = (
            f"checkbox-{test_type.replace(' ', '-').replace('/', '-').lower()}"
        )

        test_type_checkboxes.append(
            f'    <div style="margin: 2px 0; display: flex; align-items: center;">\n'
            f'        <input type="checkbox" id="{checkbox_id}" class="test-type-checkbox" '
            f'data-symbol="{symbol}" data-test-type="{test_type}" checked '
            f'style="margin-right: 6px; cursor: pointer; width: 12px; height: 12px;">\n'
            f'        <label for="{checkbox_id}" style="cursor: pointer; display: flex; align-items: center; '
            f'user-select: none; {PANEL_STYLE_ITEM}">\n'
            f'            <span style="margin-right: 4px; {PANEL_STYLE_ITEM}">'
            f"{symbol_display}</span>\n"
            f"            <span>{display_name}</span>\n"
            f"        </label>\n"
            f"    </div>"
        )

    # Build header (without count - total will be at bottom)
    header_text = "Test Types"

    # Build total count entry for bottom of list
    total_count_entry = ""
    if total_count > 0:
        total_count_entry = (
            f'    <div style="margin-top: 4px; padding-top: 4px; '
            f'border-top: 1px solid rgba(255, 255, 255, 0.3);">\n'
            f'        <span style="font-weight: bold; {PANEL_STYLE_ITEM}">Total n={total_count}</span>\n'
            f"    </div>"
        )

    panel_left = PANEL_LAYOUT_CONFIG["left"]
    panel_width = PANEL_LAYOUT_CONFIG["width"]
    panel_top_offset = PANEL_LAYOUT_CONFIG.get("top_offset", 20)

    checkbox_html = f"""
<div id="testTypeCheckboxes" style="
    position: absolute;
    left: {panel_left}px;
    top: {panel_top_offset}px;
    {LIQUID_GLASS_STYLE}
    {PANEL_STYLE_ITEM}
    width: {panel_width}px;
    z-index: 1000;
">
    <div style="{PANEL_STYLE_HEADER} margin-bottom: 4px;">
        {header_text}
    </div>
{''.join(test_type_checkboxes)}
{total_count_entry}
</div>
    <script>
        document.querySelectorAll('.test-type-checkbox').forEach(checkbox => {{
            checkbox.addEventListener('change', function() {{
                const testType = this.getAttribute('data-test-type');
                const isChecked = this.checked;
                
                // Update the global state tracking object
                // This is used by updateAllTraceVisibility() to determine visibility
                if (typeof testTypeEnabled !== 'undefined') {{
                    testTypeEnabled[testType] = isChecked;
                    console.log('☑️ Test type toggled:', testType, '->', isChecked);
                    
                    // Use the unified visibility manager that respects BOTH filters
                    if (typeof updateAllTraceVisibility === 'function') {{
                        updateAllTraceVisibility();
                        return;  // Exit early - unified manager handles everything
                    }}
                }}
                
                // Fallback: Original behavior if unified manager not available
                // (This should not normally execute, but provides safety)
                const plotDiv = document.querySelector('.plotly-graph-div');
                const data = plotDiv.data;
                
                // Collect all trace indices that match this test type
                const matchingIndices = [];
                data.forEach((trace, idx) => {{
                    if (!trace.customdata || !Array.isArray(trace.customdata) || trace.customdata.length === 0) {{
                        return;
                    }}
                    const firstCustomData = trace.customdata[0];
                    if (!Array.isArray(firstCustomData)) return;
                    
                    const traceTestType = firstCustomData[0];
                    if (traceTestType === testType) {{
                        matchingIndices.push(idx);
                    }}
                }});
                
                // Batch update all matching traces in a SINGLE Plotly.restyle call
                if (matchingIndices.length > 0) {{
                    const visibilities = matchingIndices.map(() => isChecked);
                    Plotly.restyle(plotDiv, {{'visible': visibilities}}, matchingIndices);
                }}
            }});
        }});
    </script>
    """

    return checkbox_html


# ═══════════════════════════════════════════════════════════════════════════
# 📊 LIVE COUNT PANELS SECTION
# Non-interactive display panels showing real-time counts of visible data points
# ═══════════════════════════════════════════════════════════════════════════


def generate_live_count_metadata(
    test_types_in_formation: Set[str],
    investigation_counts: Dict[str, int],
    test_type_counts: Dict[str, int],
    investigation_sample_counts: Optional[Dict[str, int]] = None,
    test_type_sample_counts: Optional[Dict[str, int]] = None,
) -> str:
    """
    Generate JavaScript metadata for live count panels.

    Creates a JavaScript object containing initial count values for test types
    and investigations. This metadata is updated dynamically when trace
    visibility changes.

    Args:
        test_types_in_formation: Set of test type names present in the data
        investigation_counts: Dict mapping investigations to total point counts
        test_type_counts: Dict mapping test types to total point counts
        investigation_sample_counts: Dict mapping investigations to sample counts
        test_type_sample_counts: Dict mapping test types to sample counts

    Returns:
        JavaScript code string defining liveCountMetadata constant
    """
    import json

    # Default to empty dicts if sample counts not provided
    inv_sample_counts = investigation_sample_counts or {}
    tt_sample_counts = test_type_sample_counts or {}

    metadata = {
        "testTypeCounts": {tt: count for tt, count in test_type_counts.items()},
        "investigationCounts": {
            inv: count for inv, count in investigation_counts.items()
        },
        "testTypeSampleCounts": {tt: count for tt, count in tt_sample_counts.items()},
        "investigationSampleCounts": {
            inv: count for inv, count in inv_sample_counts.items()
        },
        "initialTestTypeCounts": {tt: count for tt, count in test_type_counts.items()},
        "initialInvestigationCounts": {
            inv: count for inv, count in investigation_counts.items()
        },
        "initialTestTypeSampleCounts": {
            tt: count for tt, count in tt_sample_counts.items()
        },
        "initialInvestigationSampleCounts": {
            inv: count for inv, count in inv_sample_counts.items()
        },
    }

    return f"const liveCountMetadata = {json.dumps(metadata, indent=2)};"


def generate_live_count_panels_html(
    test_types_in_formation: Set[str],
    investigation_counts: Dict[str, int],
    test_type_counts: Dict[str, int],
    test_type_to_legend_name: Optional[Dict[str, str]] = None,
    investigation_sample_counts: Optional[Dict[str, int]] = None,
    test_type_sample_counts: Optional[Dict[str, int]] = None,
    total_sample_count: Optional[int] = None,
    investigation_total_sample_count: Optional[int] = None,
) -> str:
    """
    Generate HTML for non-interactive live count display panels.

    Creates two fixed-position panels displaying:
    1. Live Test Type Counts - points and samples per test type
    2. Live Investigation Counts - points and samples per investigation

    Args:
        test_types_in_formation: Set of test type names present
        investigation_counts: Dict mapping investigations to total point counts
        test_type_counts: Dict mapping test types to total point counts
        test_type_to_legend_name: Optional dict for display name mapping
        investigation_sample_counts: Dict mapping investigations to sample counts
        test_type_sample_counts: Dict mapping test types to sample counts
        total_sample_count: Global unique sample count (prevents double-counting)

    Returns:
        HTML string with two fixed-position panels
    """
    if test_type_to_legend_name is None:
        test_type_to_legend_name = {tt: tt for tt in test_types_in_formation}

    # Default to empty dicts if sample counts not provided
    inv_sample_counts = investigation_sample_counts or {}
    tt_sample_counts = test_type_sample_counts or {}

    # === LIVE TEST TYPE COUNTS PANEL ===
    # Header row with column labels
    test_type_header = (
        f'    <div style="margin: 2px 0; display: flex; justify-content: space-between; {PANEL_STYLE_ITEM} font-size: 10px; opacity: 0.8;">\n'
        f'        <span style="flex: 3;">Test Type</span>\n'
        f'        <span style="flex: 1; text-align: right;">Points</span>\n'
        f'        <span style="flex: 1; text-align: right;">Tests</span>\n'
        f"    </div>"
    )

    test_type_rows = [test_type_header]
    for test_type in sorted(test_types_in_formation):
        display_name = test_type_to_legend_name.get(test_type, test_type)
        count = test_type_counts.get(test_type, 0)
        sample_count = tt_sample_counts.get(test_type, 0)
        test_type_rows.append(
            f'    <div style="margin: 2px 0; display: flex; justify-content: space-between; {PANEL_STYLE_ITEM}">\n'
            f'        <span style="flex: 3;">{display_name}</span>\n'
            f'        <span class="live-test-type-count" data-test-type="{test_type}" '
            f'style="flex: 1; text-align: right; font-weight: bold;">{count}</span>\n'
            f'        <span class="live-test-type-sample-count" data-test-type="{test_type}" '
            f'style="flex: 1; text-align: right; font-weight: bold;">{sample_count}</span>\n'
            f"    </div>"
        )

    test_type_total = sum(test_type_counts.get(tt, 0) for tt in test_types_in_formation)
    # Use global unique sample count if provided, otherwise fall back to sum
    # (which may double-count samples appearing in multiple test types)
    if total_sample_count is not None:
        test_type_sample_total = total_sample_count
    else:
        test_type_sample_total = sum(
            tt_sample_counts.get(tt, 0) for tt in test_types_in_formation
        )

    # Calculate top position based on number of test types (checkbox panel height)
    # Checkbox panel: top_offset + header + (n_test_types * 22px) + total + padding
    n_test_types = len(test_types_in_formation)
    checkbox_panel_height = 50 + (n_test_types * 22) + 30  # header + items + total
    vertical_gap = PANEL_LAYOUT_CONFIG["vertical_gap"]
    panel_left = PANEL_LAYOUT_CONFIG["left"]
    panel_width = PANEL_LAYOUT_CONFIG["width"]
    panel_top_offset = PANEL_LAYOUT_CONFIG.get("top_offset", 20)
    live_test_type_top = panel_top_offset + checkbox_panel_height + vertical_gap

    test_type_panel = f"""
<div id="liveTestTypeCounts" style="
    position: absolute;
    left: {panel_left}px;
    top: {live_test_type_top}px;
    {LIQUID_GLASS_STYLE}
    {PANEL_STYLE_ITEM}
    width: {panel_width}px;
    z-index: 1000;
">
    <div style="{PANEL_STYLE_HEADER} margin-bottom: 4px; border-bottom: 1px solid rgba(255, 255, 255, 0.3); padding-bottom: 4px;">
        Live Test Type Counts
    </div>
{''.join(test_type_rows)}
    <div style="margin-top: 6px; padding-top: 4px; border-top: 1px solid rgba(255, 255, 255, 0.3); display: flex; justify-content: space-between; font-weight: bold; {PANEL_STYLE_ITEM}">
        <span style="flex: 3;">Total Visible</span>
        <span id="live-test-type-total" style="flex: 1; text-align: right;">{test_type_total}</span>
        <span id="live-test-type-sample-total" style="flex: 1; text-align: right;">{test_type_sample_total}</span>
    </div>
</div>
    """

    # === LIVE INVESTIGATION COUNTS PANEL ===
    # Header row with column labels
    investigation_header = (
        f'    <div style="margin: 2px 0; display: flex; justify-content: space-between; {PANEL_STYLE_ITEM} font-size: 10px; opacity: 0.8;">\n'
        f'        <span style="flex: 3;">Investigation</span>\n'
        f'        <span style="flex: 1; text-align: right;">Points</span>\n'
        f'        <span style="flex: 1; text-align: right;">Samples</span>\n'
        f"    </div>"
    )

    investigation_rows = [investigation_header]
    for investigation in sorted(investigation_counts.keys()):
        count = investigation_counts[investigation]
        sample_count = inv_sample_counts.get(investigation, 0)
        investigation_rows.append(
            f'    <div style="margin: 2px 0; display: flex; justify-content: space-between; {PANEL_STYLE_ITEM}">\n'
            f'        <span style="flex: 3;">{investigation}</span>\n'
            f'        <span class="live-investigation-count" data-investigation="{investigation}" '
            f'style="flex: 1; text-align: right; font-weight: bold;">{count}</span>\n'
            f'        <span class="live-investigation-sample-count" data-investigation="{investigation}" '
            f'style="flex: 1; text-align: right; font-weight: bold;">{sample_count}</span>\n'
            f"    </div>"
        )

    investigation_total = sum(investigation_counts.values())
    # Use deduplicated investigation sample total if provided, separate from test type total
    if investigation_total_sample_count is not None:
        investigation_sample_total = investigation_total_sample_count
    else:
        investigation_sample_total = sum(inv_sample_counts.values())

    # Position investigation panel BELOW the live test type counts panel
    # Same left position, vertically aligned below
    # Test type panel height: header (~30px) + column header (~20px) + items (n_test_types * 22px) + total (~25px) + padding
    test_type_panel_height = (
        30 + 20 + (n_test_types * 22) + 25 + 16
    )  # header + col header + items + total + padding
    live_investigation_top = live_test_type_top + test_type_panel_height + vertical_gap

    investigation_panel = f"""
<div id="liveInvestigationCounts" style="
    position: absolute;
    left: {panel_left}px;
    top: {live_investigation_top}px;
    {LIQUID_GLASS_STYLE}
    {PANEL_STYLE_ITEM}
    width: {panel_width}px;
    z-index: 1000;
">
    <div style="{PANEL_STYLE_HEADER} margin-bottom: 4px; border-bottom: 1px solid rgba(255, 255, 255, 0.3); padding-bottom: 4px;">
        Live Investigation Counts
    </div>
{''.join(investigation_rows)}
    <div style="margin-top: 6px; padding-top: 4px; border-top: 1px solid rgba(255, 255, 255, 0.3); display: flex; justify-content: space-between; font-weight: bold; {PANEL_STYLE_ITEM}">
        <span style="flex: 3;">Total Visible</span>
        <span id="live-investigation-total" style="flex: 1; text-align: right;">{investigation_total}</span>
        <span id="live-investigation-sample-total" style="flex: 1; text-align: right;">{investigation_sample_total}</span>
    </div>
</div>
    """

    # === COUNT EXPLANATION INFO BOX ===
    # Position below investigation panel
    # MODIFICATION POINT: This is the explanatory text shown at the bottom of the left panel sidebar
    # explaining the difference between test totals and investigation sample totals
    n_investigations = len(investigation_counts)
    investigation_panel_height = (
        30 + 20 + (n_investigations * 22) + 25 + 16
    )  # header + col header + items + total + padding
    info_box_top = live_investigation_top + investigation_panel_height + vertical_gap

    # MODIFICATION POINT: Explanatory text about test vs investigation totals
    # This text appears in the bottom info box of the left panel sidebar
    explanation_text = (
        "Test totals count every individual measurement across all sources, "
        "while investigation totals count each physical sample only once — "
        "meaning test totals are usually larger because the same sample (Location ID + Top Depth) can "
        "appear in multiple test types or be subsampled in the lab."
    )

    info_box_panel = f"""
<div id="countExplanationBox" style="
    position: absolute;
    left: {panel_left}px;
    top: {info_box_top}px;
    {LIQUID_GLASS_STYLE}
    {PANEL_STYLE_ITEM}
    width: {panel_width}px;
    z-index: 1000;
    font-size: 11px;
    color: rgba(42, 63, 95, 0.7);
    line-height: 1.4;
">
    {explanation_text}
</div>
    """

    return test_type_panel + investigation_panel + info_box_panel


def generate_count_update_javascript(
    test_types_in_formation: Set[str],
    test_type_to_symbol: Dict[str, str],
) -> str:
    """
    Generate JavaScript for recalculating and updating live count panels.

    Creates event listeners for Plotly legend clicks and checkbox changes,
    and functions to recalculate visible counts based on trace visibility.

    The test type for each trace is determined from trace.customdata (which
    contains [testType] for each data point) rather than marker symbols,
    since marker symbols may not be unique per test type.

    Args:
        test_types_in_formation: Set of test type names present
        test_type_to_symbol: Dict mapping test types to Plotly symbols

    Returns:
        JavaScript code string with count update logic
    """
    js_code = """
<script>
    // === INITIALIZE TRACE METADATA ON PAGE LOAD ===
    let traceMetadata = [];
    let outlierTracesByInvestigation = {};  // Maps investigation -> [trace indices]
    
    // === UNIFIED VISIBILITY STATE TRACKING ===
    // Track which test types are enabled (checkbox checked)
    let testTypeEnabled = {};  // {testType: boolean}
    
    // Track which investigations are enabled (legend not clicked to hide)
    let investigationEnabled = {};  // {investigation: boolean}
    
    // Track global outlier visibility state (for "Outlier" legend entry click)
    let outliersEnabled = true;  // All outliers visible by default
    
    // Helper to get point count from trace data (handles binary-encoded data)
    function getTracePointCount(trace) {
        // Plotly may use binary encoding for large arrays
        // Check customdata length as it's always a regular array with one entry per point
        if (trace.customdata && Array.isArray(trace.customdata)) {
            return trace.customdata.length;
        }
        // Fallback: check if x is a regular array
        if (trace.x && Array.isArray(trace.x)) {
            return trace.x.filter(x => x !== null && x !== undefined).length;
        }
        // If x is binary-encoded object, use length from customdata or assume 0
        return 0;
    }
    
    function initializeTraceMetadata() {
        const plotDiv = document.querySelector('.plotly-graph-div');
        if (!plotDiv || !plotDiv.data) return;
        
        traceMetadata = [];
        outlierTracesByInvestigation = {};
        
        plotDiv.data.forEach((trace, idx) => {
            const legendGroup = trace.legendgroup || "";
            const traceName = trace.name || "";
            
            // Identify trace types
            const isTotalCountTrace = legendGroup === "total_count";
            const isOutlierTrace = traceName === "Outlier" || legendGroup === "Outlier";
            
            // Determine test type and investigation from customdata
            // Regular traces: customdata = [[test_type], [test_type], ...]
            // Outlier traces: customdata = [[test_type, investigation], [test_type, investigation], ...]
            let testType = null;
            let outlierInvestigation = null;
            
            if (trace.customdata && Array.isArray(trace.customdata) && trace.customdata.length > 0) {
                const firstCustomData = trace.customdata[0];
                if (Array.isArray(firstCustomData)) {
                    testType = firstCustomData[0] || null;
                    // For outlier traces, second element is the investigation
                    if (isOutlierTrace && firstCustomData.length > 1) {
                        outlierInvestigation = firstCustomData[1];
                    }
                } else if (typeof firstCustomData === 'string') {
                    testType = firstCustomData;
                }
            }
            
            // Get point count (handles binary-encoded data)
            const pointCount = getTracePointCount(trace);
            const hasData = pointCount > 0;
            
            // Determine investigation from legendgroup for regular traces
            let investigation = null;
            if (!isOutlierTrace && legendGroup && legendGroup !== "total_count" && legendGroup !== "Outlier") {
                investigation = legendGroup;
            }
            
            // Track outlier traces by their parent investigation
            if (isOutlierTrace && outlierInvestigation) {
                if (!outlierTracesByInvestigation[outlierInvestigation]) {
                    outlierTracesByInvestigation[outlierInvestigation] = [];
                }
                outlierTracesByInvestigation[outlierInvestigation].push(idx);
            }
            
            // Only include real data traces (have points, have test type, not special traces)
            const isRealDataTrace = hasData && testType !== null && !isTotalCountTrace && !isOutlierTrace;
            
            traceMetadata.push({
                traceIndex: idx,
                investigation: investigation,
                testType: testType,
                pointCount: pointCount,
                isRealDataTrace: isRealDataTrace,
                isOutlierTrace: isOutlierTrace,
                outlierInvestigation: outlierInvestigation
            });
        });
        
        // Log summary of data traces found
        const dataTraces = traceMetadata.filter(t => t.isRealDataTrace);
        const outlierTraces = traceMetadata.filter(t => t.isOutlierTrace);
        const testTypes = [...new Set(dataTraces.map(t => t.testType))];
        const investigations = [...new Set(dataTraces.map(t => t.investigation))];
        
        // Initialize state tracking objects from trace metadata
        // All test types and investigations start as enabled (visible)
        traceMetadata.forEach(meta => {
            if (meta.testType && testTypeEnabled[meta.testType] === undefined) {
                testTypeEnabled[meta.testType] = true;
            }
            if (meta.investigation && investigationEnabled[meta.investigation] === undefined) {
                investigationEnabled[meta.investigation] = true;
            }
            if (meta.outlierInvestigation && investigationEnabled[meta.outlierInvestigation] === undefined) {
                investigationEnabled[meta.outlierInvestigation] = true;
            }
        });
        
        // Also sync state from checkbox DOM state (in case checkboxes were unchecked)
        document.querySelectorAll('.test-type-checkbox').forEach(cb => {
            const testType = cb.getAttribute('data-test-type');
            if (testType) {
                testTypeEnabled[testType] = cb.checked;
            }
        });
        
        console.log(`✅ Initialized trace metadata: ${dataTraces.length} data traces, ${outlierTraces.length} outlier traces`);
        console.log("   Test types found:", testTypes);
        console.log("   Investigations found:", investigations);
        console.log("   Outlier traces by investigation:", outlierTracesByInvestigation);
        console.log("   Test type enabled state:", testTypeEnabled);
        console.log("   Investigation enabled state:", investigationEnabled);
    }
    
    // === TOGGLE OUTLIERS WHEN INVESTIGATION IS CLICKED ===
    // Note: This is now mostly handled by updateAllTraceVisibility() for proper state sync
    function toggleOutliersForInvestigation(investigation, visible) {
        const plotDiv = document.querySelector('.plotly-graph-div');
        if (!plotDiv || !outlierTracesByInvestigation[investigation]) return;
        
        const outlierIndices = outlierTracesByInvestigation[investigation];
        if (outlierIndices.length === 0) return;
        
        // Collect all valid outlier trace updates
        const validIndices = [];
        const visibilities = [];
        
        outlierIndices.forEach(idx => {
            const trace = plotDiv.data[idx];
            if (trace) {
                // Outliers visible only if: investigation visible AND global outliers enabled
                const shouldShow = visible && outliersEnabled;
                const newVisibility = shouldShow ? true : 'legendonly';
                validIndices.push(idx);
                visibilities.push(newVisibility);
            }
        });
        
        // Batch update all outlier traces in a SINGLE Plotly.restyle call
        if (validIndices.length > 0) {
            Plotly.restyle(plotDiv, {'visible': visibilities}, validIndices);
        }
    }
    
    // === UNIFIED VISIBILITY MANAGER ===
    // This function applies BOTH filter states (test type checkboxes AND investigation legend)
    // A trace is only visible if BOTH its test type is enabled AND its investigation is enabled
    function updateAllTraceVisibility() {
        const plotDiv = document.querySelector('.plotly-graph-div');
        if (!plotDiv || !plotDiv.data) return;
        
        const updates = [];  // Collect all updates for batch processing
        
        // Track which investigations have ANY visible data after applying filters
        // This determines if the legend entry should be greyed out
        const investigationHasVisibleData = {};
        
        traceMetadata.forEach((meta) => {
            // Skip traces that aren't real data or outliers (e.g., classification lines, dummy traces)
            if (!meta.isRealDataTrace && !meta.isOutlierTrace) return;
            
            const testType = meta.testType;
            const investigation = meta.isOutlierTrace ? meta.outlierInvestigation : meta.investigation;
            
            // Both filters must pass for trace to be visible
            // Default to true if state is undefined (not yet tracked)
            const testTypeOk = testTypeEnabled[testType] !== false;
            const investigationOk = investigationEnabled[investigation] !== false;
            
            // For outlier traces, also require global outliersEnabled to be true
            let shouldShow = testTypeOk && investigationOk;
            if (meta.isOutlierTrace && !outliersEnabled) {
                shouldShow = false;
            }
            
            // Track if this investigation has any visible data
            if (investigation) {
                if (!investigationHasVisibleData[investigation]) {
                    investigationHasVisibleData[investigation] = false;
                }
                if (shouldShow) {
                    investigationHasVisibleData[investigation] = true;
                }
            }
            
            // Use 'legendonly' for the dummy outlier trace (pointCount=0) to keep it in legend
            // Use true/false for real data/outlier traces
            const isDummyOutlierTrace = meta.isOutlierTrace && meta.pointCount === 0;
            const visibility = shouldShow ? true : (isDummyOutlierTrace ? 'legendonly' : false);
            
            updates.push({
                idx: meta.traceIndex,
                visible: visibility
            });
        });
        
        // Batch update all data traces in a SINGLE Plotly.restyle call
        // This is 10-50x faster than individual updates
        if (updates.length > 0) {
            const visibilityValues = updates.map(u => u.visible);
            const traceIndices = updates.map(u => u.idx);
            Plotly.restyle(plotDiv, {'visible': visibilityValues}, traceIndices);
        }
        
        // Update dummy legend traces (circle markers with showlegend=true but no data)
        // These control the visual state of legend entries (greyed out when 'legendonly')
        // Collect all updates first, then batch apply
        const dummyTraceUpdates = [];
        
        plotDiv.data.forEach((trace, idx) => {
            const legendGroup = trace.legendgroup || "";
            
            // Skip non-investigation traces
            if (!legendGroup || legendGroup === "Outlier" || legendGroup === "total_count") return;
            
            // Check if this is a dummy legend trace (has x=[null], y=[null], showlegend=true)
            const isDummyTrace = trace.showlegend === true && 
                                 trace.x && trace.x.length === 1 && trace.x[0] === null;
            
            if (isDummyTrace) {
                // Check if this investigation is enabled
                const invEnabled = investigationEnabled[legendGroup] !== false;
                
                // Use 'legendonly' to grey out the legend entry when investigation is disabled
                // Use true to show normally when enabled
                const newVisibility = invEnabled ? true : 'legendonly';
                
                // Only collect if different from current state
                const currentVisibility = trace.visible === undefined ? true : trace.visible;
                if (currentVisibility !== newVisibility) {
                    dummyTraceUpdates.push({idx: idx, visibility: newVisibility});
                }
            }
        });
        
        // Batch update all dummy traces in a SINGLE Plotly.restyle call
        if (dummyTraceUpdates.length > 0) {
            const dummyVisibilities = dummyTraceUpdates.map(d => d.visibility);
            const dummyIndices = dummyTraceUpdates.map(d => d.idx);
            Plotly.restyle(plotDiv, {'visible': dummyVisibilities}, dummyIndices);
        }
        
        // Update live count panels
        recalculateVisibleCounts();
    }
    
    // === RECALCULATE VISIBLE COUNTS ===
    function recalculateVisibleCounts() {
        const plotDiv = document.querySelector('.plotly-graph-div');
        if (!plotDiv || !plotDiv.data) return;
        
        // Reset all point counts to zero
        Object.keys(liveCountMetadata.testTypeCounts).forEach(tt => {
            liveCountMetadata.testTypeCounts[tt] = 0;
        });
        Object.keys(liveCountMetadata.investigationCounts).forEach(inv => {
            liveCountMetadata.investigationCounts[inv] = 0;
        });
        
        // Sets for unique sample counting (Approach B: dynamic sample counts)
        const samplesByTestType = {};
        const samplesByInvestigation = {};
        const allVisibleSamples = new Set();  // Global set for true total (no double-counting)
        
        // Initialize empty Sets for each category
        Object.keys(liveCountMetadata.testTypeCounts).forEach(tt => {
            samplesByTestType[tt] = new Set();
        });
        Object.keys(liveCountMetadata.investigationCounts).forEach(inv => {
            samplesByInvestigation[inv] = new Set();
        });
        
        // Process each trace for both point counts and sample collection
        traceMetadata.forEach((traceMeta) => {
            const trace = plotDiv.data[traceMeta.traceIndex];
            if (!trace) return;
            
            // Check if trace is visible (true or undefined means visible)
            // 'legendonly' means hidden via legend click
            const isVisible = trace.visible === true || trace.visible === undefined;
            if (!isVisible) return;
            
            // Handle regular data traces
            if (traceMeta.isRealDataTrace) {
                // Sum point counts (existing logic)
                if (traceMeta.testType && liveCountMetadata.testTypeCounts[traceMeta.testType] !== undefined) {
                    liveCountMetadata.testTypeCounts[traceMeta.testType] += traceMeta.pointCount;
                }
                if (traceMeta.investigation && liveCountMetadata.investigationCounts[traceMeta.investigation] !== undefined) {
                    liveCountMetadata.investigationCounts[traceMeta.investigation] += traceMeta.pointCount;
                }
                
                // Collect sample IDs for unique counting
                // customdata format: [[test_type, sample_id], [test_type, sample_id], ...]
                if (trace.customdata && Array.isArray(trace.customdata)) {
                    trace.customdata.forEach(cd => {
                        if (!Array.isArray(cd) || cd.length < 2) return;
                        
                        const testType = cd[0];
                        const sampleId = cd[1];
                        
                        if (testType && sampleId && samplesByTestType[testType]) {
                            samplesByTestType[testType].add(sampleId);
                        }
                        
                        // Add to global set for true total (no double-counting across test types)
                        if (sampleId) {
                            allVisibleSamples.add(sampleId);
                        }
                        
                        // Investigation from trace metadata (from legendgroup)
                        if (traceMeta.investigation && sampleId && samplesByInvestigation[traceMeta.investigation]) {
                            samplesByInvestigation[traceMeta.investigation].add(sampleId);
                        }
                    });
                }
            }
            
            // Handle outlier traces - they contribute to both test type and investigation counts
            if (traceMeta.isOutlierTrace && traceMeta.outlierInvestigation) {
                // Sum point counts
                if (traceMeta.testType && liveCountMetadata.testTypeCounts[traceMeta.testType] !== undefined) {
                    liveCountMetadata.testTypeCounts[traceMeta.testType] += traceMeta.pointCount;
                }
                if (liveCountMetadata.investigationCounts[traceMeta.outlierInvestigation] !== undefined) {
                    liveCountMetadata.investigationCounts[traceMeta.outlierInvestigation] += traceMeta.pointCount;
                }
                
                // Collect sample IDs from outlier traces
                // customdata format: [[test_type, investigation, sample_id], ...]
                if (trace.customdata && Array.isArray(trace.customdata)) {
                    trace.customdata.forEach(cd => {
                        if (!Array.isArray(cd)) return;
                        
                        const testType = cd[0];
                        // For outliers: cd[1] is investigation, cd[2] is sample_id
                        const investigation = cd.length >= 2 ? cd[1] : null;
                        const sampleId = cd.length >= 3 ? cd[2] : null;
                        
                        if (testType && sampleId && samplesByTestType[testType]) {
                            samplesByTestType[testType].add(sampleId);
                        }
                        
                        // Add to global set for true total
                        if (sampleId) {
                            allVisibleSamples.add(sampleId);
                        }
                        
                        if (investigation && sampleId && samplesByInvestigation[investigation]) {
                            samplesByInvestigation[investigation].add(sampleId);
                        }
                    });
                }
            }
        });
        
        // Update sample counts from Sets (dynamic counting)
        // Store the global total for use in updateLiveCountPanels
        let globalSampleTotal = allVisibleSamples.size;
        
        if (liveCountMetadata.testTypeSampleCounts) {
            Object.keys(liveCountMetadata.testTypeSampleCounts).forEach(tt => {
                liveCountMetadata.testTypeSampleCounts[tt] = samplesByTestType[tt] ? samplesByTestType[tt].size : 0;
            });
        }
        if (liveCountMetadata.investigationSampleCounts) {
            Object.keys(liveCountMetadata.investigationSampleCounts).forEach(inv => {
                liveCountMetadata.investigationSampleCounts[inv] = samplesByInvestigation[inv] ? samplesByInvestigation[inv].size : 0;
            });
        }
        
        updateLiveCountPanels(globalSampleTotal);
    }
    
    // === UPDATE DOM ELEMENTS ===
    function updateLiveCountPanels(globalSampleTotal) {
        // Update test type counts
        document.querySelectorAll('.live-test-type-count').forEach(span => {
            const testType = span.getAttribute('data-test-type');
            if (liveCountMetadata.testTypeCounts[testType] !== undefined) {
                span.textContent = liveCountMetadata.testTypeCounts[testType];
            }
        });
        
        // Update test type sample counts
        document.querySelectorAll('.live-test-type-sample-count').forEach(span => {
            const testType = span.getAttribute('data-test-type');
            if (liveCountMetadata.testTypeSampleCounts && liveCountMetadata.testTypeSampleCounts[testType] !== undefined) {
                span.textContent = liveCountMetadata.testTypeSampleCounts[testType];
            }
        });
        
        // Update test type total
        const testTypeTotal = Object.values(liveCountMetadata.testTypeCounts)
            .reduce((sum, count) => sum + count, 0);
        const testTypeTotalEl = document.getElementById('live-test-type-total');
        if (testTypeTotalEl) {
            testTypeTotalEl.textContent = testTypeTotal;
        }
        
        // Update test type sample total - use global sample count (no double-counting)
        const testTypeSampleTotalEl = document.getElementById('live-test-type-sample-total');
        if (testTypeSampleTotalEl && globalSampleTotal !== undefined) {
            testTypeSampleTotalEl.textContent = globalSampleTotal;
        }
        
        // Update investigation counts
        document.querySelectorAll('.live-investigation-count').forEach(span => {
            const investigation = span.getAttribute('data-investigation');
            if (liveCountMetadata.investigationCounts[investigation] !== undefined) {
                span.textContent = liveCountMetadata.investigationCounts[investigation];
            }
        });
        
        // Update investigation sample counts
        document.querySelectorAll('.live-investigation-sample-count').forEach(span => {
            const investigation = span.getAttribute('data-investigation');
            if (liveCountMetadata.investigationSampleCounts && liveCountMetadata.investigationSampleCounts[investigation] !== undefined) {
                span.textContent = liveCountMetadata.investigationSampleCounts[investigation];
            }
        });
        
        // Update investigation total
        const investigationTotal = Object.values(liveCountMetadata.investigationCounts)
            .reduce((sum, count) => sum + count, 0);
        const investigationTotalEl = document.getElementById('live-investigation-total');
        if (investigationTotalEl) {
            investigationTotalEl.textContent = investigationTotal;
        }
        
        // Update investigation sample total - use global sample count (same as test type total)
        const investigationSampleTotalEl = document.getElementById('live-investigation-sample-total');
        if (investigationSampleTotalEl && globalSampleTotal !== undefined) {
            investigationSampleTotalEl.textContent = globalSampleTotal;
        }
    }
    
    // === SETUP EVENT LISTENERS ===
    function setupLiveCountListeners() {
        const plotDiv = document.querySelector('.plotly-graph-div');
        if (!plotDiv) return;
        
        // Plotly legend click events - UNIFIED VISIBILITY MANAGEMENT
        // We intercept legend clicks to maintain synchronization with checkbox state
        plotDiv.on('plotly_legendclick', function(data) {
            const clickedTrace = plotDiv.data[data.curveNumber];
            const legendGroup = clickedTrace.legendgroup || "";
            const traceName = clickedTrace.name || "";
            
            // Handle "Outlier" legend click - BATCHED for performance
            if (legendGroup === "Outlier" || traceName === "Outlier") {
                // Toggle global outliers state
                outliersEnabled = !outliersEnabled;
                console.log(`🔄 Outliers toggled: ${!outliersEnabled} -> ${outliersEnabled}`);
                
                // Collect all outlier trace indices for batch update
                const outlierIndices = [];
                const visibilities = [];
                
                traceMetadata.forEach(meta => {
                    if (meta.isOutlierTrace) {
                        outlierIndices.push(meta.traceIndex);
                        // Only show if BOTH global outliers AND the investigation are enabled
                        const invEnabled = investigationEnabled[meta.outlierInvestigation] !== false;
                        const shouldShow = outliersEnabled && invEnabled;
                        visibilities.push(shouldShow ? true : 'legendonly');
                    }
                });
                
                // Single batch Plotly.restyle call for ALL outlier traces
                if (outlierIndices.length > 0) {
                    Plotly.restyle(plotDiv, {'visible': visibilities}, outlierIndices);
                }
                
                setTimeout(recalculateVisibleCounts, 100);
                return false;  // Prevent Plotly's slow default toggle
            }
            
            // Handle "total_count" trace - let Plotly handle this natively
            if (legendGroup === "total_count") {
                return true;  // Allow default Plotly toggle
            }
            
            // Check if this is an investigation trace
            const isInvestigationTrace = legendGroup && 
                                         legendGroup !== "Outlier" && 
                                         legendGroup !== "total_count" &&
                                         traceName !== "Outlier";
            
            if (isInvestigationTrace) {
                // Toggle the investigation state
                const currentState = investigationEnabled[legendGroup] !== false;
                investigationEnabled[legendGroup] = !currentState;
                
                console.log(`🔄 Investigation '${legendGroup}' toggled: ${currentState} -> ${!currentState}`);
                
                // Apply unified visibility (respects both checkbox AND legend state)
                updateAllTraceVisibility();
                
                // PREVENT Plotly's default toggle - we handle it ourselves
                // This is critical to avoid state conflicts
                return false;
            }
            
            // For any other traces, allow default behavior
            setTimeout(recalculateVisibleCounts, 100);
            return true;
        });
        
        plotDiv.on('plotly_legenddoubleclick', function(data) {
            // Double-click isolates one trace - need to sync outliers
            setTimeout(function() {
                // After double-click, check visibility of each investigation and sync outliers
                const plotDiv = document.querySelector('.plotly-graph-div');
                if (!plotDiv || !plotDiv.data) return;
                
                // Get visibility state of each investigation
                const investigationVisibility = {};
                traceMetadata.forEach(meta => {
                    if (meta.investigation && !meta.isOutlierTrace) {
                        const trace = plotDiv.data[meta.traceIndex];
                        const isVisible = trace.visible === true || trace.visible === undefined;
                        investigationVisibility[meta.investigation] = isVisible;
                    }
                });
                
                // Sync outlier visibility with their investigations
                Object.keys(investigationVisibility).forEach(inv => {
                    toggleOutliersForInvestigation(inv, investigationVisibility[inv]);
                });
                
                recalculateVisibleCounts();
            }, 100);
        });
        
        // Plotly restyle events (catches all visibility changes including checkboxes)
        plotDiv.on('plotly_restyle', function(data) {
            setTimeout(recalculateVisibleCounts, 100);
        });
        
        // === CLICK-TO-COPY TOOLTIP CONTENT ===
        // When user clicks on a data point, copy the hover text to clipboard
        plotDiv.on('plotly_click', function(data) {
            if (!data || !data.points || data.points.length === 0) return;
            
            const point = data.points[0];
            const hoverText = point.hovertext || point.text || '';
            
            if (!hoverText) {
                console.log('No hover text to copy');
                return;
            }
            
            // Convert HTML to plain text (strip tags)
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = hoverText;
            const plainText = tempDiv.textContent || tempDiv.innerText || '';
            
            // Copy to clipboard using modern API with fallback
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(plainText).then(function() {
                    showCopyNotification('Copied to clipboard!');
                }).catch(function(err) {
                    console.error('Failed to copy: ', err);
                    fallbackCopyToClipboard(plainText);
                });
            } else {
                fallbackCopyToClipboard(plainText);
            }
        });
        
        console.log("✅ Live count listeners attached with outlier sync");
    }
    
    // === CLIPBOARD FALLBACK FOR OLDER BROWSERS ===
    function fallbackCopyToClipboard(text) {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-9999px';
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            showCopyNotification('Copied to clipboard!');
        } catch (err) {
            console.error('Fallback copy failed: ', err);
            showCopyNotification('Copy failed - please copy manually');
        }
        document.body.removeChild(textArea);
    }
    
    // === COPY NOTIFICATION POPUP ===
    function showCopyNotification(message) {
        // Remove existing notification if any
        const existing = document.getElementById('copyNotification');
        if (existing) existing.remove();
        
        // Create notification element
        const notification = document.createElement('div');
        notification.id = 'copyNotification';
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 12px 24px;
            border-radius: 8px;
            font-family: Arial, sans-serif;
            font-size: 14px;
            z-index: 9999;
            animation: fadeInOut 2s ease-in-out;
        `;
        
        // Add animation keyframes if not already present
        if (!document.getElementById('copyNotificationStyles')) {
            const style = document.createElement('style');
            style.id = 'copyNotificationStyles';
            style.textContent = `
                @keyframes fadeInOut {
                    0% { opacity: 0; transform: translateX(-50%) translateY(20px); }
                    15% { opacity: 1; transform: translateX(-50%) translateY(0); }
                    85% { opacity: 1; transform: translateX(-50%) translateY(0); }
                    100% { opacity: 0; transform: translateX(-50%) translateY(-20px); }
                }
            `;
            document.head.appendChild(style);
        }
        
        document.body.appendChild(notification);
        
        // Remove after animation completes
        setTimeout(function() {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 2000);
    }
    
    // === INITIALIZATION ===
    document.addEventListener('DOMContentLoaded', function() {
        // Wait for Plotly to fully render
        setTimeout(function() {
            initializeTraceMetadata();
            setupLiveCountListeners();
        }, 500);
    });
    
    // Also try immediate initialization for cases where DOM is already loaded
    if (document.readyState === 'complete') {
        setTimeout(function() {
            initializeTraceMetadata();
            setupLiveCountListeners();
        }, 500);
    }
</script>
    """

    return js_code


# ═══════════════════════════════════════════════════════════════════════════
# 📋 FAQ PANEL SECTION
# Right-side FAQ panel for displaying helpful information about the plot
# ═══════════════════════════════════════════════════════════════════════════

# MODIFICATION POINT: FAQ panel dimensions
# Width matches depth plot area (880px), height adapts to content
# NOTE: top_offset is NOT duplicated here - uses shared PANEL_LAYOUT_CONFIG["top_offset"]
# to ensure left panels, legend, and FAQ panel all align at the same vertical position
FAQ_PANEL_CONFIG: Dict[str, int] = {
    "width": 880,  # Same as depth plot area width
    "right_margin": 20,  # Right margin from edge
}


def generate_faq_panel_html(
    faq_items: Optional[List[Dict[str, str]]] = None,
    panel_title: str = "FAQs",
) -> str:
    """
    Generate HTML for the FAQ panel on the right side of the plot.

    Creates a panel with the same styling as other panels (liquid glass)
    positioned to the right of the graph. The panel height adapts to content.
    - Width: Same as depth plot area (880px)
    - Height: Adapts to FAQ content (no fixed height)

    Args:
        faq_items: List of FAQ dictionaries with 'question' and 'answer' keys.
            Items can also have a 'section' key to display as section headers.
            If None, displays placeholder text.
        panel_title: Title for the FAQ panel header

    Returns:
        HTML string for the FAQ panel

    Example:
        >>> faq_items = [
        ...     {"section": "Getting Started"},  # Section header
        ...     {"question": "What is this plot?", "answer": "This shows..."},
        ...     {"section": "Advanced Features"},  # Another section header
        ...     {"question": "How to interpret?", "answer": "Higher values mean..."},
        ... ]
        >>> html = generate_faq_panel_html(faq_items)
    """
    panel_width = FAQ_PANEL_CONFIG["width"]
    # Use shared top_offset from PANEL_LAYOUT_CONFIG for alignment with left panels and legend
    panel_top = PANEL_LAYOUT_CONFIG["top_offset"]

    # Build FAQ content
    if faq_items and len(faq_items) > 0:
        faq_content_items = []
        for i, faq in enumerate(faq_items):
            # Check if this is a section header
            if "section" in faq:
                section_title = faq["section"]
                # Add extra margin for sections after the first one
                margin_top = "24px" if i > 0 else "0"
                faq_content_items.append(
                    f'        <div style="margin-top: {margin_top}; margin-bottom: 12px; '
                    f'padding-bottom: 6px; border-bottom: 2px solid rgba(42, 63, 95, 0.2);">\n'
                    f'            <span style="{PANEL_STYLE_ITEM} font-size: 14px; '
                    f'text-transform: uppercase; letter-spacing: 0.5px;">'
                    f"{section_title}</span>\n"
                    f"        </div>"
                )
            else:
                # Regular Q&A item
                question = faq.get("question", f"Question {i + 1}")
                answer = faq.get("answer", "No answer provided.")
                faq_content_items.append(
                    f'        <div style="margin-bottom: 16px;">\n'
                    f'            <div style="font-weight: bold; margin-bottom: 4px; {PANEL_STYLE_HEADER}">\n'
                    f"                Q: {question}\n"
                    f"            </div>\n"
                    f'            <div style="{PANEL_STYLE_ITEM} line-height: 1.5;">\n'
                    f"                A: {answer}\n"
                    f"            </div>\n"
                    f"        </div>"
                )
        faq_content = "\n".join(faq_content_items)
    else:
        # Placeholder content when no FAQs provided
        faq_content = f"""
        <div style="{PANEL_STYLE_ITEM} color: rgba(42, 63, 95, 0.6); font-style: italic;">
            No FAQs have been configured for this plot type yet.
            <br><br>
            FAQs can be added by passing faq_items to generate_faq_panel_html().
        </div>
"""

    faq_panel = f"""
<div id="faqPanel" style="
    position: absolute;
    top: {panel_top}px;
    right: 0;
    {LIQUID_GLASS_STYLE}
    width: {panel_width}px;
    z-index: 1000;
">
    <div style="{PANEL_STYLE_HEADER} margin-bottom: 12px; border-bottom: 1px solid rgba(255, 255, 255, 0.3); padding-bottom: 8px; font-size: 16px;">
        {panel_title}
    </div>
    <div style="padding-right: 8px;">
{faq_content}
    </div>
</div>
"""

    return faq_panel


# ═══════════════════════════════════════════════════════════════════════════
# 💾 HTML EXPORT SECTION
# ═══════════════════════════════════════════════════════════════════════════

# Default Plotly config for HTML export
DEFAULT_PLOTLY_CONFIG: Dict[str, Any] = {
    "doubleClickDelay": 500,
    "displayModeBar": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
}

# MODIFICATION POINT: Default FAQ items shared across all plot types
# This is the single source of truth for FAQ content
# Items with "section" key are displayed as section headers
DEFAULT_FAQ_ITEMS: List[Dict[str, str]] = [
    # === NAVIGATION & ZOOMING SECTION ===
    {"section": "Navigation & Zooming"},
    {
        "question": "How do I zoom into a specific area of the plot?",
        "answer": "Click and drag to draw a rectangle around the area you want to zoom "
        "into. The plot will automatically zoom to show only that selected region. "
        "This is useful for examining dense clusters of data points in detail.",
    },
    {
        "question": "How do I reset the zoom and see all the data again?",
        "answer": "Double-click anywhere inside the plot area to reset the view and "
        "return to the original zoom level showing all data points.",
    },
    {
        "question": "Can I pan around the plot when zoomed in?",
        "answer": "Yes! When zoomed in, you can click and drag while holding the Shift "
        "key to pan around the plot. Alternatively, use the modebar tools (the toolbar "
        "that appears in the top-right corner when you hover over the plot) to switch "
        "between zoom and pan modes.",
    },
    # === FILTERING DATA SECTION ===
    {"section": "Filtering Data"},
    {
        "question": "How do I show or hide data from specific investigations?",
        "answer": "Click on any investigation name in the legend (right side of plot) "
        "to toggle its visibility. Clicking once hides that investigation's data; "
        "clicking again shows it. The live count panels on the left will automatically "
        "update to reflect visible data.",
    },
    {
        "question": "What are the checkboxes on the left side for?",
        "answer": "The 'Test Types' checkboxes allow you to filter data by the type of "
        "test (e.g., Classification, Triaxial, Vane Tests). Each test type has a unique "
        "marker shape. Uncheck a box to hide all data points from that test type; check "
        "it again to show them.",
    },
    {
        "question": "How do I quickly reset all filtering back to default?",
        "answer": "Simply refresh the page (press F5 or click the browser refresh button). "
        "This will reload the plot with all investigations, test types, and outliers "
        "visible again. Note: Any zoom or pan changes will also be reset.",
    },
    # === DATA COUNTS SECTION ===
    {"section": "Understanding Data Counts"},
    {
        "question": "What are the 'Live Test Type Counts' and 'Live Investigation Counts' panels?",
        "answer": "These panels show real-time counts of visible data. Live Test Type "
        "Counts shows points and unique tests per test type. Live Investigation Counts "
        "shows points and unique samples per investigation. Both update dynamically when "
        "you filter data using the legend or checkboxes.",
    },
    {
        "question": "What's the difference between 'Points' and 'Tests/Samples' columns?",
        "answer": "Points = total individual measurements visible (a single sample can "
        "have multiple readings). Tests = unique laboratory tests per test type. "
        "Samples = unique physical samples (Location ID + Depth combinations) per "
        "investigation, deduplicated across test types. Note: Some points may have "
        "identical values and appear stacked on top of each other, making it look like "
        "there are fewer points than the count shows.",
    },
    {
        "question": "Why do the test type totals and investigation totals not match?",
        "answer": "Test totals count every individual measurement across all sources, "
        "while investigation totals count each physical sample only once. Test totals "
        "are usually larger because the same sample (Location ID + Top Depth) can appear "
        "in multiple test types, be subsampled in the laboratory, or have multiple "
        "readings at different conditions (e.g., varying cell pressures).",
    },
    # === DATA POINT DETAILS SECTION ===
    {"section": "Data Point Details"},
    {
        "question": "How do I see details about a specific data point?",
        "answer": "Hover your mouse over any data point to see a tooltip with: "
        "Investigation name, Location ID (borehole/trial pit reference), Parameter value "
        "(e.g., moisture content, strength), Depth, and Test type.",
    },
    {
        "question": "Can I copy the tooltip information?",
        "answer": "Yes! Click on any data point while the tooltip is showing to copy "
        "its contents to your clipboard. A notification will appear confirming the copy. "
        "The copied text is in plain format, suitable for pasting into reports or emails.",
    },
    {
        "question": "What are the red markers on the plot?",
        "answer": "Red markers indicate statistical outliers — data points that fall "
        "outside the expected range based on the dataset's distribution. These are "
        "flagged for review but not removed, as they may represent genuine unusual soil "
        "conditions, data entry errors, or laboratory anomalies. You can hide all "
        "outliers by clicking 'Outlier' in the legend.",
    },
    # === TOOLBAR SECTION ===
    {"section": "Plot Toolbar"},
    {
        "question": "What do the icons in the top-right toolbar do?",
        "answer": "The modebar provides additional controls: Camera icon = download plot "
        "as PNG image. Zoom icon = switch to zoom mode (drag to zoom). Pan icon = switch "
        "to pan mode (drag to move around). Home icon = reset to original zoom level. "
        "Autoscale icon = fit all visible data in view.",
    },
]


def build_combined_injection_and_faq(
    checkbox_html: str,
    live_count_panels_html: str,
    live_count_metadata_js: str,
    count_update_js: str,
    faq_items: Optional[List[Dict[str, str]]] = None,
    faq_title: str = "FAQs",
) -> Tuple[str, str]:
    """
    Build combined HTML/JS injection for left panels and FAQ panel for right sidebar.

    This is a unified helper function that consolidates the injection building logic
    for both depth plots and XY plots, following the DRY principle.

    Args:
        checkbox_html: Test type checkbox panel HTML
        live_count_panels_html: Live count panels HTML
        live_count_metadata_js: JavaScript for live count metadata
        count_update_js: JavaScript for count updates
        faq_items: Optional list of FAQ dicts (uses DEFAULT_FAQ_ITEMS if None)
        faq_title: Title for the FAQ panel

    Returns:
        Tuple of (combined_injection_html, faq_html)
    """
    # Build combined left sidebar injection
    combined_injection = (
        checkbox_html
        + live_count_panels_html
        + f"<script>\n{live_count_metadata_js}\n</script>"
        + count_update_js
        + LEGEND_ROUNDING_SCRIPT
    )

    # Build FAQ panel for right sidebar
    if faq_items is None:
        faq_items = DEFAULT_FAQ_ITEMS
    faq_html = generate_faq_panel_html(faq_items=faq_items, panel_title=faq_title)

    return combined_injection, faq_html


def save_plotly_html(
    fig: go.Figure,
    output_path: Path,
    checkbox_html: Optional[str] = None,
    faq_html: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Save Plotly figure as HTML with optional panel injection.

    Panels are embedded in the page (scroll with content) using a flex layout:
    - Left sidebar: Contains all control panels (checkboxes, live counts)
    - Center: Contains the Plotly graph
    - Right sidebar: Contains the FAQ panel (if provided)

    The page wrapper uses min-width: fit-content to ensure all sidebars are
    visible and the user can scroll horizontally if the viewport is too small.

    Args:
        fig: Plotly figure to save
        output_path: Path for output HTML file
        checkbox_html: Optional HTML string containing left sidebar panels
        faq_html: Optional HTML string containing the right FAQ panel
        config: Optional Plotly config dict (uses DEFAULT_PLOTLY_CONFIG if None)
    """
    # Create output directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Use default config if not provided
    if config is None:
        config = DEFAULT_PLOTLY_CONFIG

    # Generate HTML content
    html_content = fig.to_html(config=config, include_plotlyjs="cdn")

    # Inject panels with embedded layout if any panels are provided
    if checkbox_html or faq_html:
        # Spacing between sidebars and plot (150px on each side)
        sidebar_to_plot_spacing = 150

        # Extract panel width from config for sidebar sizing
        panel_width = PANEL_LAYOUT_CONFIG["width"]
        panel_left = PANEL_LAYOUT_CONFIG["left"]
        sidebar_width = (
            panel_width + panel_left + sidebar_to_plot_spacing
        )  # panels + left margin + spacing to plot

        # Calculate right sidebar width from FAQ config
        faq_width = FAQ_PANEL_CONFIG["width"]
        faq_margin = FAQ_PANEL_CONFIG["right_margin"]
        right_sidebar_width = (
            faq_width + faq_margin + sidebar_to_plot_spacing if faq_html else 0
        )

        # Build left sidebar HTML (empty if no checkbox_html)
        left_sidebar = ""
        if checkbox_html:
            left_sidebar = f"""
    <div id="panelSidebar" style="
        position: relative;
        width: {sidebar_width}px;
        min-width: {sidebar_width}px;
        flex-shrink: 0;
        padding-top: 0;
    ">
{checkbox_html}
    </div>"""

        # Build right sidebar HTML (empty if no faq_html)
        right_sidebar = ""
        if faq_html:
            right_sidebar = f"""
    <div id="faqSidebar" style="
        position: relative;
        width: {right_sidebar_width}px;
        min-width: {right_sidebar_width}px;
        flex-shrink: 0;
        padding-top: 0;
    ">
{faq_html}
    </div>"""

        # Create flex container wrapper for embedded layout
        # Uses width: fit-content to size to content, with small margin for breathing room
        wrapper_start = f"""
<div id="plotPageWrapper" style="
    display: flex;
    flex-direction: row;
    min-height: 100vh;
    width: fit-content;
    padding: 0 20px 20px 0;
    box-sizing: border-box;
">
{left_sidebar}
    <div id="plotContainer" style="
        flex-shrink: 0;
        min-width: 0;
    ">
"""
        wrapper_end = f"""
    </div>
{right_sidebar}
</div>
"""
        # Find the plotly div and wrap it
        # The plotly div is generated by fig.to_html() and contains the graph
        html_content = html_content.replace(
            "<div>",
            f"{wrapper_start}<div>",
            1,  # Only replace first occurrence (the main plotly container)
        )
        # Close the wrapper after the last div before </body>
        html_content = html_content.replace("</body>", f"{wrapper_end}</body>")

    # Write file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    logger.info(f"✅ Saved interactive Plotly HTML plot: {output_path}")


# ═══════════════════════════════════════════════════════════════════════════
# 🎯 HIGH-LEVEL PLOT GENERATION
# Complete depth plot generation functions for parameter scripts
# ═══════════════════════════════════════════════════════════════════════════


def generate_depth_plot(
    formation_name: str,
    plotly_data: Dict[str, pd.DataFrame],
    parameter_mappings: pd.DataFrame,
    param_name: str,
    param_display_name: str,
    output_folder: Path,
    investigation_colors: Union[List[str], Dict[str, str]],
    csv_source_settings: Dict[str, Dict[str, Any]],
    default_source_settings: Dict[str, Any],
    force_circle_markers: bool = True,
    mark_outliers: bool = True,
) -> None:
    """
    Generate a complete interactive Plotly depth plot for a single formation.

    This high-level function encapsulates the entire plotting workflow:
    1. Prepare data with parameter columns
    2. Calculate investigation counts and colors
    3. Add data traces for each investigation/test type
    4. Add legend traces and outlier traces
    5. Apply layout and generate checkboxes
    6. Save HTML file

    NOTE: CPT density lines are rendered in matplotlib plots only, not Plotly.

    Args:
        formation_name: Name of the geological formation
        plotly_data: Dict mapping CSV names to DataFrames with Investigation column
        parameter_mappings: DataFrame with csv_file, column_name, parameter columns
        param_name: Internal parameter name for column lookup
        param_display_name: Display label for parameter axis
        output_folder: Path to save HTML output
        investigation_colors: EITHER a List of hex color codes (will build per-formation mapping)
                             OR a Dict mapping investigation names to colors (use global mapping)
        csv_source_settings: Test type marker/size settings per CSV
        default_source_settings: Default marker settings for unmapped CSVs
        force_circle_markers: Whether to use circle markers in legend
        mark_outliers: Whether to display outliers with distinct styling
    """
    if not plotly_data:
        logger.warning(f"⚠️ No data for formation {formation_name} - skipping")
        return

    # === BUILD DATA STRUCTURE WITH PARAM COLUMNS ===
    csv_data_with_param_columns = _prepare_plotly_data_structure(
        plotly_data, parameter_mappings, param_name
    )

    if not csv_data_with_param_columns:
        logger.warning(f"⚠️ No valid data with parameter columns for {formation_name}")
        return

    # === INVESTIGATION COUNTS AND COLOR MAPPING ===
    investigation_counts = calculate_investigation_counts(csv_data_with_param_columns)

    all_investigations = set()
    for data_info in csv_data_with_param_columns.values():
        all_investigations.update(data_info["df"]["Investigation"].unique())

    # Handle both Dict (pre-computed global mapping) and List (build per-formation)
    if isinstance(investigation_colors, dict):
        # Use the pre-computed global color mapping directly
        investigation_color_map = investigation_colors
    else:
        # Build a per-formation color mapping from the list
        investigation_color_map = create_investigation_color_mapping(
            list(all_investigations), investigation_colors
        )

    # === CREATE FIGURE AND ADD TRACES ===
    fig = go.Figure()

    sorted_csv_items = sorted(
        csv_data_with_param_columns.items(),
        key=lambda x: csv_source_settings.get(x[0], {}).get("order", 999),
    )

    legend_investigations: Set[str] = set()
    test_types_in_formation: Set[str] = set()
    outliers_by_source: Dict[str, Dict[str, Dict[str, Any]]] = {}

    # === ADD DATA TRACES ===
    for csv_name, data_info in sorted_csv_items:
        df_with_inv = data_info["df"]
        param_column = data_info["param_column"]

        test_type_settings = csv_source_settings.get(csv_name, default_source_settings)
        marker_style = test_type_settings["marker"]
        marker_size = test_type_settings["marker_size"] / 5
        plot_alpha = test_type_settings["alpha"]

        # NOTE: plot_points setting is NOT used for Plotly plots - ALL data points
        # are always shown in interactive HTML plots (matching monolith behavior).
        # The plot_points setting only affects matplotlib plots where CPT data
        # may use density lines instead of individual points.

        plotly_symbol = MARKER_SYMBOL_MAP.get(marker_style, "circle")
        clean_test_name = csv_name.replace(" by Geology.csv", "").replace(".csv", "")
        # Get display name from config (e.g., "Shear Box" instead of "Shear Box Testing - Data")
        display_test_name = get_test_type_display_name(
            csv_name, csv_source_settings, default_source_settings
        )
        # CRITICAL: Use display_test_name (not clean_test_name) to match customdata
        # The trace customdata uses display_test_name, so checkboxes must use it too
        test_types_in_formation.add(display_test_name)

        for investigation in sorted(df_with_inv["Investigation"].unique()):
            inv_data = df_with_inv[df_with_inv["Investigation"] == investigation]

            # ═══════════════════════════════════════════════════════════════════════
            # NOTE: max_kpa filtering (e.g., Vane Tests max_kpa=129) is now handled
            # in the orchestrator Phase 3a (Script-Specific Filtering) BEFORE unified
            # data objects are created. This ensures counts match plotted data.
            # DO NOT add data filtering here - add it to apply_test_type_threshold_filtering()
            # in data_pipeline.py instead. See orchestrator.py Phase 3a docstring.
            # ═══════════════════════════════════════════════════════════════════════

            regular_data = inv_data[~inv_data["is_outlier_plot"]]
            outlier_data = inv_data[inv_data["is_outlier_plot"]]

            inv_color = investigation_color_map[investigation]
            rgba_color = hex_to_rgba(inv_color, plot_alpha)

            # === PLOTLY ALWAYS SHOWS ALL POINTS ===
            # Unlike matplotlib (which uses plot_points setting for CPT density lines),
            # Plotly interactive plots always show all data points for full interactivity.
            if len(regular_data) > 0:
                show_legend_inv = (
                    investigation not in legend_investigations
                    and not force_circle_markers
                )

                hover_text = create_hover_text(
                    df=regular_data,
                    investigation=investigation,
                    x_column=param_column,
                    y_column="Top Depth",
                    x_display=param_display_name,
                    y_display="Depth (m)",
                    test_type=display_test_name,
                    is_outlier=False,
                )

                legend_name = (
                    f"{investigation} (n={investigation_counts[investigation]})"
                )

                # Build extended customdata with [test_type, sample_id] for dynamic sample counting
                extended_customdata = _build_extended_customdata(
                    regular_data, display_test_name
                )

                add_investigation_scatter_trace(
                    fig=fig,
                    x_data=regular_data[param_column],
                    y_data=regular_data["Top Depth"],
                    investigation=investigation,
                    plotly_symbol=plotly_symbol,
                    marker_size=marker_size,
                    rgba_color=rgba_color,
                    legend_name=legend_name,
                    hover_text=hover_text,
                    show_legend=show_legend_inv,
                    custom_data=extended_customdata,
                )

                if show_legend_inv or force_circle_markers:
                    legend_investigations.add(investigation)

            # Collect outlier data for batch trace generation
            if mark_outliers and len(outlier_data) > 0:
                _collect_outlier_data_for_trace(
                    outliers_by_source,
                    csv_name,
                    investigation,
                    outlier_data,
                    param_column,
                    param_display_name,
                    display_test_name,  # Use display name for hover text
                    rgba_color,
                    plotly_symbol,
                )

    # NOTE: CPT density lines are generated in matplotlib only (not Plotly)
    # See matplotlib_utils.py for density line implementation

    # === ADD LEGEND TRACES ===
    if force_circle_markers:
        add_dummy_circle_legend_traces(
            fig, legend_investigations, investigation_color_map, investigation_counts
        )
        add_total_count_legend_entry(fig, investigation_counts)

    # === ADD OUTLIER TRACES ===
    if mark_outliers and outliers_by_source:
        outlier_count = add_outlier_traces(
            fig, outliers_by_source, use_test_type_symbols=True
        )
        add_dummy_outlier_legend_trace(fig, outlier_count)

    # === APPLY LAYOUT ===
    layout = get_plot_layout(
        formation_name=formation_name,
        x_display=param_display_name,
        y_display="Depth (m)",
        invert_y=True,
        x_side="top",
        plot_type="depth",
    )
    fig.update_layout(**layout)

    # === GENERATE CHECKBOXES ===
    test_type_to_symbol = build_test_type_symbol_mapping(
        list(csv_data_with_param_columns.keys()),
        csv_source_settings,
        default_source_settings,
        test_types_in_formation,
    )
    test_type_counts = calculate_test_type_counts(
        csv_data_with_param_columns, csv_source_settings, default_source_settings
    )

    # NOTE: test_type_to_legend_name is no longer needed since test_types_in_formation
    # now contains display_test_name values directly (e.g., "Shear Box" not "Shear Box Testing - Data")
    # The checkbox will display the test type name directly from test_types_in_formation
    test_type_to_legend_name = (
        None  # Display names are already in test_types_in_formation
    )

    checkbox_html = generate_test_type_checkbox_html(
        test_types_in_formation,
        test_type_to_symbol,
        test_type_to_legend_name=test_type_to_legend_name,
        test_type_counts=test_type_counts,
    )

    # === CALCULATE SAMPLE COUNTS ===
    investigation_sample_counts = calculate_investigation_sample_counts(
        csv_data_with_param_columns
    )
    test_type_sample_counts = calculate_test_type_sample_counts(
        csv_data_with_param_columns, csv_source_settings, default_source_settings
    )
    # Sum of per-source unique samples (intentionally allows same sample in multiple sources)
    # Used for test type total - counts tests not unique physical samples
    total_sample_count = calculate_global_unique_sample_count(
        csv_data_with_param_columns
    )
    # Truly deduplicated count - each physical sample counted once
    # Used for investigation total - counts unique physical samples
    investigation_total_sample_count = calculate_global_deduplicated_sample_count(
        csv_data_with_param_columns
    )

    # === GENERATE LIVE COUNT PANELS ===
    live_count_metadata_js = generate_live_count_metadata(
        test_types_in_formation,
        investigation_counts,
        test_type_counts,
        investigation_sample_counts=investigation_sample_counts,
        test_type_sample_counts=test_type_sample_counts,
    )

    live_count_panels_html = generate_live_count_panels_html(
        test_types_in_formation,
        investigation_counts,
        test_type_counts,
        investigation_sample_counts=investigation_sample_counts,
        test_type_sample_counts=test_type_sample_counts,
        total_sample_count=total_sample_count,
        investigation_total_sample_count=investigation_total_sample_count,
    )

    count_update_js = generate_count_update_javascript(
        test_types_in_formation,
        test_type_to_symbol,
    )

    # === BUILD COMBINED INJECTION AND FAQ (UNIFIED) ===
    combined_injection, faq_html = build_combined_injection_and_faq(
        checkbox_html=checkbox_html,
        live_count_panels_html=live_count_panels_html,
        live_count_metadata_js=live_count_metadata_js,
        count_update_js=count_update_js,
    )

    # === SAVE HTML ===
    output_folder.mkdir(parents=True, exist_ok=True)
    sanitized_name = sanitize_filename(formation_name)
    output_path = output_folder / f"{sanitized_name}.html"

    save_plotly_html(
        fig,
        output_path,
        checkbox_html=combined_injection,
        faq_html=faq_html,
        config=DEFAULT_PLOTLY_CONFIG,
    )

    logger.info(f"✅ Saved Plotly HTML: {output_path}")


def _prepare_plotly_data_structure(
    plotly_data: Dict[str, pd.DataFrame],
    parameter_mappings: pd.DataFrame,
    param_name: str,
) -> Dict[str, Dict[str, Any]]:
    """
    Prepare data structure for Plotly plotting with param columns identified.

    Args:
        plotly_data: Dict mapping CSV names to DataFrames
        parameter_mappings: DataFrame with csv_file, column_name, parameter columns
        param_name: Parameter name to filter mappings

    Returns:
        Dict mapping CSV names to {"df": DataFrame, "param_column": str}
    """
    csv_data_with_param_columns = {}

    for csv_name, df in plotly_data.items():
        # Find parameter column for this CSV
        param_mappings_filtered = parameter_mappings[
            (parameter_mappings["csv_file"] == csv_name)
            & (parameter_mappings["parameter"] == param_name)
        ]

        if param_mappings_filtered.empty:
            continue

        param_column = param_mappings_filtered["column_name"].iloc[0]

        if param_column not in df.columns:
            continue

        # Prepare dataframe with outlier plot column
        df_copy = df.copy()
        if "is_outlier" in df_copy.columns:
            df_copy["is_outlier_plot"] = df_copy["is_outlier"]
        else:
            df_copy["is_outlier_plot"] = False

        csv_data_with_param_columns[csv_name] = {
            "df": df_copy,
            "param_column": param_column,
        }

    return csv_data_with_param_columns


def _collect_outlier_data_for_trace(
    outliers_by_source: Dict[str, Dict[str, Dict[str, Any]]],
    csv_name: str,
    investigation: str,
    outlier_data: pd.DataFrame,
    param_column: str,
    param_display_name: str,
    clean_test_name: str,
    rgba_color: str,
    plotly_symbol: str,
) -> None:
    """
    Collect outlier data into nested structure for batch trace generation.

    PERFORMANCE: Vectorized hover text and sample ID generation is 15-25× faster
    than iterrows.

    Args:
        outliers_by_source: Nested dict to collect outliers into
        csv_name: Source CSV filename
        investigation: Investigation name
        outlier_data: DataFrame of outlier points
        param_column: Column name containing parameter values
        param_display_name: Display name for hover text
        clean_test_name: Test type name for hover text
        rgba_color: RGBA color string
        plotly_symbol: Plotly marker symbol
    """
    if outlier_data.empty:
        return

    if csv_name not in outliers_by_source:
        outliers_by_source[csv_name] = {}

    if investigation not in outliers_by_source[csv_name]:
        outliers_by_source[csv_name][investigation] = {
            "x": [],
            "y": [],
            "hover_text": [],
            "customdata": [],  # Extended customdata with sample_id
            "color": rgba_color,
            "marker_symbol": plotly_symbol,
        }

    outliers_by_source[csv_name][investigation]["x"].extend(
        outlier_data[param_column].tolist()
    )
    outliers_by_source[csv_name][investigation]["y"].extend(
        outlier_data["Top Depth"].tolist()
    )

    # Vectorized hover text generation - 15-25× faster than iterrows
    location_ids = outlier_data["Location ID"].fillna("N/A").astype(str)
    depths = outlier_data["Top Depth"].fillna(0).round(2).astype(str)
    param_values = outlier_data[param_column].fillna(0).round(2).astype(str)

    hover_text = (
        f"<b>OUTLIER - {investigation}</b><br>"
        + "Location ID: "
        + location_ids
        + "<br>"
        + "Depth: "
        + depths
        + " m<br>"
        + f"{param_display_name}: "
        + param_values
        + "<br>"
        + f"Test Type: {clean_test_name}"
    )
    outliers_by_source[csv_name][investigation]["hover_text"].extend(
        hover_text.tolist()
    )

    # Vectorized sample ID creation - 15-25× faster than iterrows
    loc_col = _find_column(outlier_data, SAMPLE_LOCATION_COLUMNS)
    depth_col = _find_column(outlier_data, SAMPLE_DEPTH_COLUMNS)
    sample_ids = _create_sample_ids_vectorized(outlier_data, loc_col, depth_col)

    # Build extended customdata: [test_type, investigation, sample_id]
    customdata = [[clean_test_name, investigation, sid] for sid in sample_ids.values]
    outliers_by_source[csv_name][investigation]["customdata"].extend(customdata)


# ═══════════════════════════════════════════════════════════════════════════
# 📊 DUAL-PARAMETER (X vs Y) PLOT GENERATION
# ═══════════════════════════════════════════════════════════════════════════


def generate_xy_plot(
    formation_name: str,
    plotly_data: Dict[str, pd.DataFrame],
    parameter_mappings: pd.DataFrame,
    x_param_name: str,
    y_param_name: str,
    x_display_name: str,
    y_display_name: str,
    output_folder: Path,
    investigation_colors: Union[List[str], Dict[str, str]],
    csv_source_settings: Dict[str, Dict[str, Any]],
    default_source_settings: Dict[str, Any],
    force_circle_markers: bool = True,
    mark_outliers: bool = True,
    classification_boundaries: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Generate a complete interactive Plotly X vs Y scatter plot for a single formation.

    This function is for dual-parameter plots like CV vs Cell Pressure where
    one parameter is plotted against another (not vs depth).

    Args:
        formation_name: Name of the geological formation
        plotly_data: Dict mapping CSV names to DataFrames with Investigation column
        parameter_mappings: DataFrame with csv_file, column_name, parameter columns
        x_param_name: Internal name for X-axis parameter
        y_param_name: Internal name for Y-axis parameter
        x_display_name: Display label for X-axis
        y_display_name: Display label for Y-axis
        output_folder: Path to save HTML output
        investigation_colors: EITHER a List of hex colors OR Dict mapping investigations
        csv_source_settings: Test type marker/size settings per CSV
        default_source_settings: Default marker settings for unmapped CSVs
        force_circle_markers: Whether to use circle markers in legend
        mark_outliers: Whether to display outliers with distinct styling
        classification_boundaries: Optional dict with boundary type settings:
            - "plasticity_chart": True to add A-line/U-line boundaries (for A-line plots)
            - "x_range": Tuple (min, max) for X-axis range (default: auto)
            - "y_range": Tuple (min, max) for Y-axis range (default: auto)
    """
    if not plotly_data:
        logger.warning(f"⚠️ No data for formation {formation_name} - skipping")
        return

    # === BUILD DATA STRUCTURE WITH BOTH PARAM COLUMNS ===
    csv_data_with_param_columns = _prepare_xy_data_structure(
        plotly_data, parameter_mappings, x_param_name, y_param_name
    )

    if not csv_data_with_param_columns:
        logger.warning(f"⚠️ No valid data with both parameters for {formation_name}")
        return

    # === INVESTIGATION COUNTS AND COLOR MAPPING ===
    investigation_counts = calculate_investigation_counts(csv_data_with_param_columns)

    all_investigations = set()
    for data_info in csv_data_with_param_columns.values():
        all_investigations.update(data_info["df"]["Investigation"].unique())

    if isinstance(investigation_colors, dict):
        investigation_color_map = investigation_colors
    else:
        investigation_color_map = create_investigation_color_mapping(
            list(all_investigations), investigation_colors
        )

    # === CREATE FIGURE AND ADD TRACES ===
    fig = go.Figure()

    sorted_csv_items = sorted(
        csv_data_with_param_columns.items(),
        key=lambda x: csv_source_settings.get(x[0], {}).get("order", 999),
    )

    legend_investigations: Set[str] = set()
    test_types_in_formation: Set[str] = set()
    outliers_by_source: Dict[str, Dict[str, Dict[str, Any]]] = {}

    # === ADD DATA TRACES ===
    for csv_name, data_info in sorted_csv_items:
        df_with_inv = data_info["df"]
        x_column = data_info["x_column"]
        y_column = data_info["y_column"]

        test_type_settings = csv_source_settings.get(csv_name, default_source_settings)
        marker_style = test_type_settings["marker"]
        marker_size = test_type_settings["marker_size"] / 5
        plot_alpha = test_type_settings["alpha"]

        plotly_symbol = MARKER_SYMBOL_MAP.get(marker_style, "circle")
        clean_test_name = csv_name.replace(" by Geology.csv", "").replace(".csv", "")
        # Get display name from config (e.g., "Shear Box" instead of "Shear Box Testing - Data")
        display_test_name = get_test_type_display_name(
            csv_name, csv_source_settings, default_source_settings
        )
        # CRITICAL: Use display_test_name (not clean_test_name) to match customdata
        # The trace customdata uses display_test_name, so checkboxes must use it too
        test_types_in_formation.add(display_test_name)

        for investigation in sorted(df_with_inv["Investigation"].unique()):
            inv_data = df_with_inv[df_with_inv["Investigation"] == investigation]

            # ═══════════════════════════════════════════════════════════════════════
            # NOTE: max_kpa filtering (e.g., Vane Tests max_kpa=129) is now handled
            # in the orchestrator Phase 3a (Script-Specific Filtering) BEFORE unified
            # data objects are created. This ensures counts match plotted data.
            # DO NOT add data filtering here - add it to apply_test_type_threshold_filtering()
            # in data_pipeline.py instead. See orchestrator.py Phase 3a docstring.
            # ═══════════════════════════════════════════════════════════════════════

            regular_data = inv_data[~inv_data["is_outlier_plot"]]
            outlier_data = inv_data[inv_data["is_outlier_plot"]]

            inv_color = investigation_color_map[investigation]
            rgba_color = hex_to_rgba(inv_color, plot_alpha)

            if len(regular_data) > 0:
                show_legend_inv = (
                    investigation not in legend_investigations
                    and not force_circle_markers
                )

                hover_text = create_hover_text(
                    df=regular_data,
                    investigation=investigation,
                    x_column=x_column,
                    y_column=y_column,
                    x_display=x_display_name,
                    y_display=y_display_name,
                    test_type=display_test_name,
                    is_outlier=False,
                )

                legend_name = (
                    f"{investigation} (n={investigation_counts[investigation]})"
                )

                # Build extended customdata with [test_type, sample_id] for dynamic sample counting
                extended_customdata = _build_extended_customdata(
                    regular_data, display_test_name
                )

                add_investigation_scatter_trace(
                    fig=fig,
                    x_data=regular_data[x_column],
                    y_data=regular_data[y_column],
                    investigation=investigation,
                    plotly_symbol=plotly_symbol,
                    marker_size=marker_size,
                    rgba_color=rgba_color,
                    legend_name=legend_name,
                    hover_text=hover_text,
                    show_legend=show_legend_inv,
                    custom_data=extended_customdata,
                )

                if show_legend_inv or force_circle_markers:
                    legend_investigations.add(investigation)

            # Collect outlier data for batch trace generation
            if mark_outliers and len(outlier_data) > 0:
                _collect_xy_outlier_data_for_trace(
                    outliers_by_source,
                    csv_name,
                    investigation,
                    outlier_data,
                    x_column,
                    y_column,
                    x_display_name,
                    y_display_name,
                    display_test_name,
                    rgba_color,
                    plotly_symbol,
                )

    # === ADD LEGEND TRACES ===
    if force_circle_markers:
        add_dummy_circle_legend_traces(
            fig, legend_investigations, investigation_color_map, investigation_counts
        )
        add_total_count_legend_entry(fig, investigation_counts)

    # === ADD OUTLIER TRACES ===
    if mark_outliers and outliers_by_source:
        outlier_count = add_outlier_traces(
            fig, outliers_by_source, use_test_type_symbols=True
        )
        add_dummy_outlier_legend_trace(fig, outlier_count)

    # === ADD CLASSIFICATION BOUNDARIES (if configured) ===
    annotations = []
    x_range_override = None
    y_range_override = None

    if classification_boundaries:
        # Add plasticity chart boundaries (A-line / U-line for Atterberg plots)
        if classification_boundaries.get("plasticity_chart", False):
            x_range_override = classification_boundaries.get("x_range", (0, 120))
            y_range_override = classification_boundaries.get("y_range", (0, 80))
            annotations = add_plasticity_chart_boundaries(
                fig, x_range_override, y_range_override
            )

    # === APPLY LAYOUT ===
    layout = get_plot_layout(
        formation_name=formation_name,
        x_display=x_display_name,
        y_display=y_display_name,
        invert_y=False,
        x_side="bottom",
        plot_type="xy",
        x_range=x_range_override,
        y_range=y_range_override,
    )
    if annotations:
        layout["annotations"] = annotations
    fig.update_layout(**layout)

    # === GENERATE CHECKBOXES ===
    test_type_to_symbol = build_test_type_symbol_mapping(
        list(csv_data_with_param_columns.keys()),
        csv_source_settings,
        default_source_settings,
        test_types_in_formation,
    )
    test_type_counts = calculate_test_type_counts(
        csv_data_with_param_columns, csv_source_settings, default_source_settings
    )
    checkbox_html = generate_test_type_checkbox_html(
        test_types_in_formation,
        test_type_to_symbol,
        test_type_counts=test_type_counts,
    )

    # === CALCULATE SAMPLE COUNTS ===
    investigation_sample_counts = calculate_investigation_sample_counts(
        csv_data_with_param_columns
    )
    test_type_sample_counts = calculate_test_type_sample_counts(
        csv_data_with_param_columns, csv_source_settings, default_source_settings
    )
    # Sum of per-source unique samples (intentionally allows same sample in multiple sources)
    # Used for test type total - counts tests not unique physical samples
    total_sample_count = calculate_global_unique_sample_count(
        csv_data_with_param_columns
    )
    # Truly deduplicated count - each physical sample counted once
    # Used for investigation total - counts unique physical samples
    investigation_total_sample_count = calculate_global_deduplicated_sample_count(
        csv_data_with_param_columns
    )

    # === GENERATE LIVE COUNT PANELS ===
    live_count_metadata_js = generate_live_count_metadata(
        test_types_in_formation,
        investigation_counts,
        test_type_counts,
        investigation_sample_counts=investigation_sample_counts,
        test_type_sample_counts=test_type_sample_counts,
    )

    live_count_panels_html = generate_live_count_panels_html(
        test_types_in_formation,
        investigation_counts,
        test_type_counts,
        investigation_sample_counts=investigation_sample_counts,
        test_type_sample_counts=test_type_sample_counts,
        total_sample_count=total_sample_count,
        investigation_total_sample_count=investigation_total_sample_count,
    )

    count_update_js = generate_count_update_javascript(
        test_types_in_formation,
        test_type_to_symbol,
    )

    # === BUILD COMBINED INJECTION AND FAQ (UNIFIED) ===
    combined_injection, faq_html = build_combined_injection_and_faq(
        checkbox_html=checkbox_html,
        live_count_panels_html=live_count_panels_html,
        live_count_metadata_js=live_count_metadata_js,
        count_update_js=count_update_js,
    )

    # === SAVE HTML ===
    output_folder.mkdir(parents=True, exist_ok=True)
    sanitized_name = sanitize_filename(formation_name)
    output_path = output_folder / f"{sanitized_name}.html"

    save_plotly_html(
        fig,
        output_path,
        checkbox_html=combined_injection,
        faq_html=faq_html,
        config=DEFAULT_PLOTLY_CONFIG,
    )

    logger.info(f"✅ Saved Plotly HTML (X vs Y): {output_path}")


def _prepare_xy_data_structure(
    plotly_data: Dict[str, pd.DataFrame],
    parameter_mappings: pd.DataFrame,
    x_param_name: str,
    y_param_name: str,
) -> Dict[str, Dict[str, Any]]:
    """
    Prepare data structure for X vs Y plots with both param columns identified.

    Args:
        plotly_data: Dict mapping CSV names to DataFrames
        parameter_mappings: DataFrame with csv_file, column_name, parameter columns
        x_param_name: X-axis parameter name to filter mappings
        y_param_name: Y-axis parameter name to filter mappings

    Returns:
        Dict mapping CSV names to {"df": DataFrame, "x_column": str, "y_column": str}
    """
    csv_data_with_param_columns = {}

    for csv_name, df in plotly_data.items():
        # Find X parameter column for this CSV
        x_mappings_filtered = parameter_mappings[
            (parameter_mappings["csv_file"] == csv_name)
            & (parameter_mappings["parameter"] == x_param_name)
        ]
        # Find Y parameter column for this CSV
        y_mappings_filtered = parameter_mappings[
            (parameter_mappings["csv_file"] == csv_name)
            & (parameter_mappings["parameter"] == y_param_name)
        ]

        if x_mappings_filtered.empty or y_mappings_filtered.empty:
            logger.debug(f"  Skipping {csv_name}: Missing X or Y parameter mapping")
            continue

        x_column = x_mappings_filtered["column_name"].iloc[0]
        y_column = y_mappings_filtered["column_name"].iloc[0]

        if x_column not in df.columns or y_column not in df.columns:
            logger.debug(f"  Skipping {csv_name}: X or Y column not in DataFrame")
            continue

        # Prepare dataframe with outlier plot column
        df_copy = df.copy()
        if "is_outlier" in df_copy.columns:
            df_copy["is_outlier_plot"] = df_copy["is_outlier"]
        else:
            df_copy["is_outlier_plot"] = False

        csv_data_with_param_columns[csv_name] = {
            "df": df_copy,
            "x_column": x_column,
            "y_column": y_column,
        }

    return csv_data_with_param_columns


def _collect_xy_outlier_data_for_trace(
    outliers_by_source: Dict[str, Dict[str, Dict[str, Any]]],
    csv_name: str,
    investigation: str,
    outlier_data: pd.DataFrame,
    x_column: str,
    y_column: str,
    x_display_name: str,
    y_display_name: str,
    clean_test_name: str,
    rgba_color: str,
    plotly_symbol: str,
) -> None:
    """
    Collect outlier data for X vs Y plots into nested structure for batch trace generation.

    PERFORMANCE: Vectorized hover text and sample ID generation is 15-25× faster
    than iterrows.

    Args:
        outliers_by_source: Nested dict to collect outliers into
        csv_name: Source CSV filename
        investigation: Investigation name
        outlier_data: DataFrame of outlier points
        x_column: Column name for X-axis values
        y_column: Column name for Y-axis values
        x_display_name: Display name for X-axis hover text
        y_display_name: Display name for Y-axis hover text
        clean_test_name: Test type name for hover text
        rgba_color: RGBA color string
        plotly_symbol: Plotly marker symbol
    """
    if outlier_data.empty:
        return

    if csv_name not in outliers_by_source:
        outliers_by_source[csv_name] = {}

    if investigation not in outliers_by_source[csv_name]:
        outliers_by_source[csv_name][investigation] = {
            "x": [],
            "y": [],
            "hover_text": [],
            "customdata": [],  # Extended customdata with sample_id
            "color": rgba_color,
            "marker_symbol": plotly_symbol,
        }

    outliers_by_source[csv_name][investigation]["x"].extend(
        outlier_data[x_column].tolist()
    )
    outliers_by_source[csv_name][investigation]["y"].extend(
        outlier_data[y_column].tolist()
    )

    # Vectorized hover text generation - 15-25× faster than iterrows
    location_ids = outlier_data["Location ID"].fillna("N/A").astype(str)
    x_values = outlier_data[x_column].fillna(0).round(2).astype(str)
    y_values = outlier_data[y_column].fillna(0).round(4).astype(str)

    hover_text = (
        f"<b>OUTLIER - {investigation}</b><br>"
        + "Location ID: "
        + location_ids
        + "<br>"
        + f"{x_display_name}: "
        + x_values
        + "<br>"
        + f"{y_display_name}: "
        + y_values
        + "<br>"
        + f"Test Type: {clean_test_name}"
    )
    outliers_by_source[csv_name][investigation]["hover_text"].extend(
        hover_text.tolist()
    )

    # Vectorized sample ID creation - 15-25× faster than iterrows
    loc_col = _find_column(outlier_data, SAMPLE_LOCATION_COLUMNS)
    depth_col = _find_column(outlier_data, SAMPLE_DEPTH_COLUMNS)
    sample_ids = _create_sample_ids_vectorized(outlier_data, loc_col, depth_col)

    # Build extended customdata: [test_type, investigation, sample_id]
    customdata = [[clean_test_name, investigation, sid] for sid in sample_ids.values]
    outliers_by_source[csv_name][investigation]["customdata"].extend(customdata)


# ═══════════════════════════════════════════════════════════════════════════
# 📈 PSD (PARTICLE SIZE DISTRIBUTION) PLOT GENERATION
# Line plots for particle size vs percentage passing
# ═══════════════════════════════════════════════════════════════════════════


def generate_psd_plot(
    formation_name: str,
    psd_data: pd.DataFrame,
    output_folder: Path,
    investigation_color_map: Dict[str, str],
    particle_size_column: str = "Particle Size",
    percentage_passing_column: str = "Percentage Passing",
    sample_id_column: str = "Sample_ID",
    average_by_investigation: bool = True,
    figure_width: int = 1000,
    figure_height: int = 700,
    x_limit_left: float = 0.001,
    x_limit_right: float = 200,
    y_limit_bottom: float = 0,
    y_limit_top: float = 105,
    line_width: float = 2,
    alpha_labeled: float = 1.0,
    alpha_unlabeled: float = 0.4,
) -> None:
    """
    Generate interactive Plotly particle size distribution plot.

    Creates PSD line plot with two modes:
    - MODE 1 (average_by_investigation=True): One averaged line per investigation
    - MODE 2 (average_by_investigation=False): One line per sample

    Args:
        formation_name: Geological formation name
        psd_data: DataFrame with Investigation, particle size, and percentage passing
        output_folder: Directory to save HTML plot
        investigation_color_map: Dict mapping investigations to hex colors
        particle_size_column: Column name for particle size values
        percentage_passing_column: Column name for percentage passing values
        sample_id_column: Column name for sample identifiers
        average_by_investigation: If True, average values per investigation
        figure_width: Figure width in pixels
        figure_height: Figure height in pixels
        x_limit_left: Minimum particle size (mm)
        x_limit_right: Maximum particle size (mm)
        y_limit_bottom: Minimum percentage passing
        y_limit_top: Maximum percentage passing
        line_width: Width of line plots
        alpha_labeled: Opacity for labeled (first) lines
        alpha_unlabeled: Opacity for unlabeled (subsequent) lines
    """
    if psd_data.empty:
        logger.warning(f"⚠️ No data for formation {formation_name} - skipping plot")
        return

    logger.info(f"📊 Generating Plotly PSD plot for: {formation_name}")

    fig = go.Figure()

    all_investigations = sorted(psd_data["Investigation"].unique())

    # Calculate investigation counts (unique samples per investigation)
    investigation_counts = {}
    for investigation in all_investigations:
        inv_data = psd_data[psd_data["Investigation"] == investigation]
        # Count unique samples using Sample_ID column
        investigation_counts[investigation] = inv_data[sample_id_column].nunique()

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

            particle_sizes = averaged_data[particle_size_column].tolist()
            percentage_passing = averaged_data[percentage_passing_column].tolist()

            if len(particle_sizes) == 0:
                continue

            inv_color = investigation_color_map.get(investigation, "#000000")
            legend_name = f"{investigation} (n={investigation_counts[investigation]})"

            fig.add_trace(
                go.Scatter(
                    x=particle_sizes,
                    y=percentage_passing,
                    mode="lines",
                    name=legend_name,
                    line=dict(color=inv_color, width=line_width),
                    opacity=alpha_labeled,
                    hovertemplate=(
                        f"<b>{investigation}</b><br>"
                        f"Particle Size: %{{x:.4f}} mm<br>"
                        f"Passing: %{{y:.1f}}%<extra></extra>"
                    ),
                )
            )
    else:
        # MODE 2: One line per sample (colored by investigation)
        labeled_investigations: Set[str] = set()

        for investigation in all_investigations:
            inv_data = psd_data[psd_data["Investigation"] == investigation].copy()

            if inv_data.empty:
                continue

            inv_color = investigation_color_map.get(investigation, "#000000")
            legend_name = f"{investigation} (n={investigation_counts[investigation]})"
            unique_samples = sorted(inv_data[sample_id_column].unique())

            for sample_id in unique_samples:
                sample_data = inv_data[inv_data[sample_id_column] == sample_id].copy()

                if sample_data.empty:
                    continue

                sample_data = sample_data.sort_values(by=particle_size_column)
                particle_sizes = sample_data[particle_size_column].tolist()
                percentage_passing = sample_data[percentage_passing_column].tolist()

                if len(particle_sizes) == 0:
                    continue

                # Label only first sample from each investigation for legend
                show_legend = investigation not in labeled_investigations
                if show_legend:
                    labeled_investigations.add(investigation)

                fig.add_trace(
                    go.Scatter(
                        x=particle_sizes,
                        y=percentage_passing,
                        mode="lines",
                        name=legend_name if show_legend else None,
                        legendgroup=investigation,
                        showlegend=show_legend,
                        line=dict(color=inv_color, width=line_width),
                        opacity=alpha_labeled if show_legend else alpha_unlabeled,
                        hovertemplate=(
                            f"<b>{sample_id}</b><br>"
                            f"Investigation: {investigation}<br>"
                            f"Particle Size: %{{x:.4f}} mm<br>"
                            f"Passing: %{{y:.1f}}%<extra></extra>"
                        ),
                    )
                )

    # === ADD TOTAL COUNT TRACE ===
    total_count = sum(investigation_counts.values())
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="text",
            name=f"<b>Total n={total_count}</b>",
            showlegend=True,
            hoverinfo="skip",
            legendgroup="total_count",
            legendrank=9999,
        )
    )

    # === CONFIGURE LAYOUT ===
    fig.update_layout(
        title=dict(text=formation_name, font=dict(size=14, color="black")),
        xaxis=dict(
            title="Particle Size (mm)",
            type="log",
            range=[np.log10(x_limit_left), np.log10(x_limit_right)],
            showgrid=True,
            gridwidth=1,
            gridcolor="lightgray",
        ),
        yaxis=dict(
            title="Percentage Passing (%)",
            range=[y_limit_bottom, y_limit_top],
            showgrid=True,
            gridwidth=1,
            gridcolor="lightgray",
        ),
        width=figure_width,
        height=figure_height,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.15,
            xanchor="center",
            x=0.5,
        ),
        margin=dict(l=60, r=40, t=60, b=100),
        plot_bgcolor="white",
    )

    # === SAVE ===
    output_folder.mkdir(parents=True, exist_ok=True)
    sanitized_name = sanitize_filename(formation_name)
    output_path = output_folder / f"{sanitized_name}.html"

    fig.write_html(str(output_path), include_plotlyjs="cdn")
    logger.info(f"✅ Saved Plotly PSD plot: {output_path}")


# ═══════════════════════════════════════════════════════════════════════════
# 📈 CPT DENSITY LINE TRACING SECTION
# Functions for generating CPT density lines per investigation
# ═══════════════════════════════════════════════════════════════════════════


def detect_segments(
    depth_array: np.ndarray, gap_threshold: float, min_length: float
) -> List[Tuple[int, int]]:
    """
    Identify continuous segments separated by gaps in depth data.

    Args:
        depth_array: 1D numpy array of depths (sorted)
        gap_threshold: Minimum gap size (m) to define new segment
        min_length: Minimum segment length (m) to retain

    Returns:
        List of (start_idx, end_idx) tuples for valid segments
    """
    if len(depth_array) == 0:
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


def add_cpt_density_line_traces(
    fig: go.Figure,
    cpt_data: pd.DataFrame,
    param_column: str,
    investigation_color_map: Dict[str, str],
    density_config: Dict[str, Any],
    density_line_settings: Dict[str, Any],
    min_points_threshold: int = 5,
) -> List[float]:
    """
    Add CPT density line traces to a Plotly figure, one per investigation.

    Args:
        fig: Plotly Figure object to add traces to
        cpt_data: DataFrame with CPT data including 'Investigation', 'Top Depth', and param_column
        param_column: Name of the parameter column
        investigation_color_map: Dict mapping investigation names to colors
        density_config: Density tracing configuration
        density_line_settings: Settings for density line appearance (linewidth, alpha, etc.)
        min_points_threshold: Minimum CPT points required to generate density line

    Returns:
        List of all parameter values from density traces (for x-axis scaling)
    """
    all_density_values = []

    if "Investigation" not in cpt_data.columns:
        logger.warning(
            "⚠️ CPT data missing 'Investigation' column - skipping density lines"
        )
        return all_density_values

    line_width = density_line_settings.get("linewidth", 1.0)
    line_alpha = density_line_settings.get("alpha", 1.0)

    for investigation in sorted(cpt_data["Investigation"].unique()):
        inv_cpt = cpt_data[cpt_data["Investigation"] == investigation]

        cpt_param_values = inv_cpt[param_column].values
        cpt_depth_values = inv_cpt["Top Depth"].values

        # Skip if insufficient points
        min_segment_length = density_config["segment_detection"]["min_segment_length"]
        if len(cpt_param_values) < min_points_threshold:
            logger.debug(
                f"  ⏭️ {investigation}: Insufficient CPT points for density line "
                f"({len(cpt_param_values)} points < {min_points_threshold})"
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

        # Add each segment as a separate trace
        for idx, (trace_depths, trace_strengths) in enumerate(density_traces):
            if len(trace_depths) > 0:
                fig.add_trace(
                    go.Scatter(
                        x=trace_strengths,
                        y=trace_depths,
                        mode="lines",
                        line=dict(
                            color=inv_color,
                            width=line_width,
                        ),
                        opacity=line_alpha,
                        name=investigation,
                        legendgroup=investigation,
                        showlegend=False,  # Don't duplicate legend entries
                        hovertemplate=(
                            f"<b>{investigation} (CPT Density)</b><br>"
                            f"Depth: %{{y:.2f}} m<br>"
                            f"Value: %{{x:.2f}}<extra></extra>"
                        ),
                        customdata=[["CPT"]] * len(trace_depths),
                    )
                )

                all_density_values.extend(trace_strengths.tolist())

        logger.info(
            f"  ✅ Added {len(density_traces)} density line segment(s) for {investigation}"
        )

    return all_density_values
