#!/usr/bin/env python3
"""
Particle Size Distribution - Simplified Plotting Script
========================================================

Demonstrates the power of the shared modules by reducing a ~5,000 line script
to ~300 lines. All orchestration logic lives in the geotechnical_plotting
package's orchestrator module.

ARCHITECTURAL OVERVIEW:

Responsibility:
This script contains ONLY configuration. All orchestration, data processing,
plotting, and export logic lives in geotechnical_plotting package.

Key Interactions:
- Input: CONFIG dictionary with PSD-specific settings
- Processing: Delegates everything to run_psd_plotting_pipeline()
- Output: Interactive Plotly HTML plots, matplotlib PNGs, CSV summaries

Navigation Guide:
- CSV_SOURCE_SETTINGS: Per-test-type appearance settings
- PARTICLE_CLASSIFICATION: Soil classification categories (Clay, Silt, Sand, etc.)
- CONFIG: Built from shared defaults with PSD-specific overrides
- main(): Single call to run_psd_plotting_pipeline()

PSD-SPECIFIC FEATURES:
- Line plots (not scatter plots) connecting particle sizes
- Log scale X-axis for particle size (0.001 to 200 mm)
- Linear Y-axis for percentage passing (0 to 105%)
- One line per sample or averaged per investigation
- Particle classification bands (Clay, Silt, Sand, Gravel, Cobbles)

USAGE:
    python PSD.py
"""

import sys
import logging
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════
# 📍 PATH SETUP - Ensure parent directory is in sys.path for imports
# ═══════════════════════════════════════════════════════════════════════════

# Get the workspace root (two levels up from this script)
SCRIPT_DIR = Path(__file__).resolve().parent
PACKAGE_DIR = SCRIPT_DIR.parent  # geotechnical_plotting
WORKSPACE_ROOT = PACKAGE_DIR.parent  # Figures_3.0

# Add workspace root to sys.path if not already present
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

# ═══════════════════════════════════════════════════════════════════════════
# 📦 SHARED MODULE IMPORTS
# All heavy lifting is done by the shared geotechnical_plotting package
# ═══════════════════════════════════════════════════════════════════════════

# Shared configuration builder
from geotechnical_plotting.shared_config import build_config_from_defaults

# Orchestration pipeline - PSD-specific pipeline
from geotechnical_plotting.orchestrator import run_psd_plotting_pipeline

# ═══════════════════════════════════════════════════════════════════════════
# 🏗️ LOGGING CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

# Force UTF-8 for stdout to handle emoji characters on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# ⚙️ CONFIGURATION - PSD-SPECIFIC SETTINGS
# PSD is unique because it plots particle size (log scale) vs percentage passing
# with LINE plots connecting points for each sample, not scatter points vs depth
# ═══════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────
# CSV SOURCE SETTINGS - Per test type appearance (script-specific)
# For PSD, there's typically only one CSV source
# ─────────────────────────────────────────────────────────────────────────
CSV_SOURCE_SETTINGS = {
    "Particle Size Distribution Analysis - Data.csv": {
        "plotted": True,
        "order": 1,
        "plot_points": True,
        "marker": "o",
        "marker_size": 50,
        "alpha": 1,
        "legend_name_points": "PSD Analysis",
    },
}

# ─────────────────────────────────────────────────────────────────────────
# PARTICLE SIZE CLASSIFICATION - Soil type categories for plot annotations
# ─────────────────────────────────────────────────────────────────────────
PARTICLE_CLASSIFICATION = {
    "enabled": True,
    "subplot_height_ratio": 0.08,
    "spacing": 0.1,
    "font_size": 9,
    "font_weight": "bold",
    "line_width": 0.8,
    "line_color": "black",
    "categories": [
        {
            "name": "CLAY",
            "size_min": 0.001,
            "size_max": 0.002,
            "label": "< 0.002",
            "subcategories": None,
        },
        {
            "name": "SILT",
            "size_min": 0.002,
            "size_max": 0.06,
            "label": None,
            "subcategories": [
                {"name": "Fine", "size_min": 0.002, "size_max": 0.006},
                {"name": "Medium", "size_min": 0.006, "size_max": 0.02},
                {"name": "Coarse", "size_min": 0.02, "size_max": 0.06},
            ],
        },
        {
            "name": "SAND",
            "size_min": 0.06,
            "size_max": 2.0,
            "label": None,
            "subcategories": [
                {"name": "Fine", "size_min": 0.06, "size_max": 0.2},
                {"name": "Medium", "size_min": 0.2, "size_max": 0.6},
                {"name": "Coarse", "size_min": 0.6, "size_max": 2.0},
            ],
        },
        {
            "name": "GRAVEL",
            "size_min": 2.0,
            "size_max": 60,
            "label": None,
            "subcategories": [
                {"name": "Fine", "size_min": 2.0, "size_max": 6.0},
                {"name": "Medium", "size_min": 6.0, "size_max": 20},
                {"name": "Coarse", "size_min": 20, "size_max": 60},
            ],
        },
        {
            "name": "COBBLES",
            "size_min": 60,
            "size_max": 200,
            "label": "60 - 200",
            "subcategories": None,
        },
    ],
}

# ─────────────────────────────────────────────────────────────────────────
# PSD-SPECIFIC SETTINGS - Line plot configuration
# ─────────────────────────────────────────────────────────────────────────
PSD_SETTINGS = {
    "average_by_investigation": False,  # True = one line per investigation, False = one line per sample
    "location_id_labels": {
        "enabled": False,
        "font_size": 5,
        "font_weight": "normal",
        "color": "black",
        "alpha": 1,
        "offset_x": -0.05,
        "offset_y": 0,
    },
    "lines": {
        "linestyle": "-",
        "linewidth": 2,
        "alpha_labeled": 1.0,
        "alpha_unlabeled": 0.5,
    },
    "data_columns": {
        "particle_size": "Particle Size",  # X-axis data column
        "percentage_passing": "Percentage Passing",  # Y-axis data column
        "sample_reference": "Sample Reference",  # Sample identifier column
    },
}

# ─────────────────────────────────────────────────────────────────────────
# BUILD CONFIG FROM SHARED DEFAULTS
# Use absolute paths based on WORKSPACE_ROOT to work from any directory
# ─────────────────────────────────────────────────────────────────────────
CONFIG = build_config_from_defaults(
    # Required: Parameter identity
    parameter_name="ParticleSizeDistribution",
    display_name="Particle Size (mm)",
    csv_source_settings=CSV_SOURCE_SETTINGS,
    # Optional: Manual data sheet name
    manual_sheet_name="PSD",
    # Use absolute paths (WORKSPACE_ROOT is set in path setup section)
    mapping_csv=str(WORKSPACE_ROOT / "Parameter_CSV_Mapping.csv"),
    csv_source_folder=str(WORKSPACE_ROOT / "Openground CSVs"),
    output_base_folder=str(WORKSPACE_ROOT / "Output"),
    # Enable manually modified matplotlib plots
    output_control_override={
        "plots": {
            "investigation_series_plots_plotly_with_outliers": True,
            "investigation_series_plots_manually_modified": True,
        }
    },
    # PSD-specific plotting overrides
    plotting_override={
        "figure": {
            "width": 10,
            "height": 8,
            "dpi": 300,
        },
        "axes": {
            "x_label": "Particle Size (mm)",
            "x_label_size": 10,
            "x_label_weight": "normal",
            "x_label_pad": 50,
            "x_scale": "log",  # CRITICAL: Log scale for particle size
            "x_limit_left": 0.001,
            "x_limit_right": 200,
            "x_ticks": [0.001, 0.01, 0.1, 1, 10, 100, 200],
            "y_label": "Percentage Passing (%)",
            "y_label_size": 10,
            "y_label_weight": "normal",
            "y_limit_bottom": 0,
            "y_limit_top": 105,
            "y_ticks_spacing": 10,
            "invert_y": False,  # Do NOT invert Y-axis (unlike depth plots)
            "grid": True,
            "grid_which": "both",
            "grid_style": "-",
            "grid_width": 0.5,
            "grid_color": "gray",
            "grid_alpha": 0.5,
        },
        "legend": {
            "location": "lower right",
            "edgecolor": "black",
            "framealpha": 0.9,
            "fixed_width": True,
            "bbox_to_anchor_y": -0.17,
        },
    },
    # Enable parallel processing for formation plot generation
    parallel_processing_override={"enabled": True},
)

# Add PSD-specific settings to CONFIG
CONFIG["psd_settings"] = PSD_SETTINGS
CONFIG["particle_classification"] = PARTICLE_CLASSIFICATION


# ═══════════════════════════════════════════════════════════════════════════
# ⚡ MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════════════


if __name__ == "__main__":
    # Run the PSD-specific pipeline
    run_psd_plotting_pipeline(CONFIG)
