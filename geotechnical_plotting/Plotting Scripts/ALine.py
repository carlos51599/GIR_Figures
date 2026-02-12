#!/usr/bin/env python3
"""
A-Line (Plasticity Chart) - Simplified Dual-Parameter Plotting Script
======================================================================

Demonstrates the power of the shared modules by reducing a ~4,700 line script
to ~150 lines. All orchestration logic lives in the geotechnical_plotting
package's orchestrator module.

ARCHITECTURAL OVERVIEW:

Responsibility:
This script contains ONLY configuration. All orchestration, data processing,
plotting, and export logic lives in geotechnical_plotting package.
Plots Plasticity Index against Liquid Limit - a dual-parameter scatter plot
creating a standard geotechnical Atterberg plasticity chart (A-line diagram).

Key Interactions:
- Input: CONFIG dictionary with dual-parameter settings (LL + PI)
- Processing: Delegates everything to run_dual_parameter_plotting_pipeline()
- Output: Interactive Plotly HTML plots, matplotlib PNGs, CSV summaries

Navigation Guide:
- CSV_SOURCE_SETTINGS: Per-test-type appearance settings
- CONFIG: Built from shared defaults with A-line-specific overrides
- main(): Single call to run_dual_parameter_plotting_pipeline()

USAGE:
    python ALine.py
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

# Shared configuration builder for dual-parameter plots
from geotechnical_plotting.shared_config import build_dual_param_config_from_defaults

# Orchestration pipeline - runs the entire workflow for X vs Y plots
from geotechnical_plotting.orchestrator import run_dual_parameter_plotting_pipeline

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
# ⚙️ CONFIGURATION - DUAL PARAMETER-SPECIFIC SETTINGS
# Only CSV source settings differ between parameter scripts - all other
# configuration is inherited from shared_config.py
# ═══════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────
# CSV SOURCE SETTINGS - Per test type appearance (script-specific)
# For A-Line (Plasticity Chart), Classification by Geology has both LL and PI
# ─────────────────────────────────────────────────────────────────────────
CSV_SOURCE_SETTINGS = {
    "Classification by Geology.csv": {
        "plotted": True,
        "order": 1,
        "plot_points": True,
        "marker": "^",  # Triangle-up (consistent with old script)
        "marker_size": 60,
        "alpha": 1,
        "legend_name_points": "Classification",
    },
}

# ─────────────────────────────────────────────────────────────────────────
# BUILD CONFIG FROM SHARED DEFAULTS
# Use absolute paths based on WORKSPACE_ROOT to work from any directory
# ─────────────────────────────────────────────────────────────────────────
CONFIG = build_dual_param_config_from_defaults(
    # Required: Dual parameter identity
    x_parameter_name="LiquidLimit",
    y_parameter_name="PlasticityIndex",
    x_display_name="Liquid Limit (%)",
    y_display_name="Plasticity Index (%)",
    output_folder_name="ALine",
    csv_source_settings=CSV_SOURCE_SETTINGS,
    # Optional: Manual data sheet name (uses y_parameter_name by default)
    manual_sheet_name="PI",
    # Use absolute paths (WORKSPACE_ROOT is set in path setup section)
    mapping_csv=str(WORKSPACE_ROOT / "Parameter_CSV_Mapping.csv"),
    csv_source_folder=str(WORKSPACE_ROOT / "Openground CSVs"),
    output_base_folder=str(WORKSPACE_ROOT / "Output"),
    # Enable plotly interactive plots AND matplotlib PNG plots
    output_control_override={
        "plots": {
            "investigation_series_plots_plotly_with_outliers": True,
            "investigation_series_plots_manually_modified": True,
        }
    },
    # Filtering overrides - exclude specific locations
    filtering_override={
        "location_filter": {
            "enabled": True,
            "exclude_prefixes": ["BP", "CCT"],
            "case_sensitive": False,
        },
    },
    # Manual outlier exclusion - use absolute paths for Excel files
    manual_outlier_exclusion_override={
        "excel_file": str(WORKSPACE_ROOT / "Data to Remove.xlsx"),
        "data_to_add_file": str(WORKSPACE_ROOT / "Data to Add.xlsx"),
    },
    # Hide test type shapes in legend (only one test type for A-line)
    investigation_series_override={
        "legend": {
            "show_test_type_shapes": False,
        }
    },
    # A-line specific: Enable plasticity chart classification boundaries
    plotting_override={
        "classification_boundaries": {
            "plasticity_chart": True,  # Adds A-line, U-line, soil classification labels
            "x_range": (0, 120),  # Liquid Limit axis range
            "y_range": (0, 80),  # Plasticity Index axis range
        }
    },
    # Enable parallel processing for formation plot generation
    parallel_processing_override={"enabled": True},
)


# ═══════════════════════════════════════════════════════════════════════════
# ⚡ MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════════════


if __name__ == "__main__":
    run_dual_parameter_plotting_pipeline(CONFIG)
