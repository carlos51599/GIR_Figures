#!/usr/bin/env python3
"""
CV vs Cell Pressure - Simplified Dual-Parameter Plotting Script
================================================================

Demonstrates the power of the shared modules by reducing a ~5,000 line script
to ~200 lines. All orchestration logic lives in the geotechnical_plotting
package's orchestrator module.

ARCHITECTURAL OVERVIEW:

Responsibility:
This script contains ONLY configuration. All orchestration, data processing,
plotting, and export logic lives in geotechnical_plotting package.
Plots Coefficient of Consolidation (cv) against Cell Pressure - a dual-parameter
scatter plot rather than parameter vs depth.

Key Interactions:
- Input: CONFIG dictionary with dual-parameter settings
- Processing: Delegates everything to run_dual_parameter_plotting_pipeline()
- Output: Interactive Plotly HTML plots, matplotlib PNGs, CSV summaries

Navigation Guide:
- CSV_SOURCE_SETTINGS: Per-test-type appearance settings
- CONFIG: Built from shared defaults with dual-parameter-specific overrides
- main(): Single call to run_dual_parameter_plotting_pipeline()

USAGE:
    python CVvsCellPressure.py
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
# For CV vs Cell Pressure, Consolidation by Geology has both parameters
# ─────────────────────────────────────────────────────────────────────────
CSV_SOURCE_SETTINGS = {
    "Consolidation by Geology.csv": {
        "plotted": True,
        "order": 1,
        "plot_points": True,
        "marker": "o",
        "marker_size": 60,
        "alpha": 1,
        "legend_name_points": "Consolidation",
    },
}

# ─────────────────────────────────────────────────────────────────────────
# BUILD CONFIG FROM SHARED DEFAULTS
# Use absolute paths based on WORKSPACE_ROOT to work from any directory
# ─────────────────────────────────────────────────────────────────────────
CONFIG = build_dual_param_config_from_defaults(
    # Required: Dual parameter identity
    x_parameter_name="Cell Pressure",
    y_parameter_name="CoefficientConsolidation",
    x_display_name="Cell Pressure (kPa)",
    y_display_name="cv (m²/year)",
    output_folder_name="CoefficientConsolidationvsCellPressure",
    csv_source_settings=CSV_SOURCE_SETTINGS,
    # Optional: Manual data sheet name (uses y_parameter_name by default)
    manual_sheet_name="cv",
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
    # Filtering overrides - exclude specific locations + threshold filters
    filtering_override={
        "location_filter": {
            "enabled": True,
            "exclude_prefixes": ["BP", "CCT", "TP17", "TP08", "TP09", "TP07"],
            "case_sensitive": False,
        },
        # Cell pressure threshold - filter out data points exceeding max value
        "cell_pressure_threshold": {
            "enabled": True,
            "max_value": 1500,  # Maximum Cell Pressure in kPa (inclusive)
        },
        # Formation-specific parameter thresholds
        "formation_parameter_thresholds": {
            "enabled": True,
            "thresholds": {
                "Kimmeridge Clay Formation (Unweathered)": {
                    "CoefficientConsolidation": {
                        "max_value": 5.0,  # Maximum cv in m²/year for KC_UW
                    },
                },
            },
        },
    },
    # Manual outlier exclusion - use absolute paths for Excel files
    manual_outlier_exclusion_override={
        "excel_file": str(WORKSPACE_ROOT / "Data to Remove.xlsx"),
        "data_to_add_file": str(WORKSPACE_ROOT / "Data to Add.xlsx"),
    },
    # Consolidation filtering - remove unloading phase data after max cell pressure
    consolidation_filtering_override={
        "enabled": True,
        "apply_to_csvs": ["Consolidation by Geology.csv"],
    },
    # Row-level fallback - creates unified columns for parameters with multiple source columns
    row_level_fallback_override={
        "enabled": True,
        "parameters": ["CoefficientConsolidation", "Cell Pressure"],
    },
    # Hide test type shapes in legend (only one test type for CV)
    investigation_series_override={
        "legend": {
            "show_test_type_shapes": False,
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
