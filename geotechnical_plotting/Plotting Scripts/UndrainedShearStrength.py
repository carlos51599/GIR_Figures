#!/usr/bin/env python3
"""
Undrained Shear Strength vs Depth - Simplified Plotting Script
===============================================================

Demonstrates the power of the shared modules by reducing a ~6,200 line script
to ~200 lines. All orchestration logic lives in the geotechnical_plotting
package's orchestrator module.

ARCHITECTURAL OVERVIEW:

Responsibility:
This script contains ONLY configuration. All orchestration, data processing,
plotting, and export logic lives in geotechnical_plotting package.

Key Interactions:
- Input: CONFIG dictionary with parameter-specific settings
- Processing: Delegates everything to run_parameter_plotting_pipeline()
- Output: Interactive Plotly HTML plots, matplotlib PNGs, CSV summaries

Navigation Guide:
- CSV_SOURCE_SETTINGS: Per-test-type appearance settings
- CONFIG: Built from shared defaults with parameter-specific overrides
- main(): Single call to run_parameter_plotting_pipeline()

USAGE:
    python UndrainedShearStrength.py
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

# Orchestration pipeline - runs the entire workflow
from geotechnical_plotting.orchestrator import run_parameter_plotting_pipeline

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
# ⚙️ CONFIGURATION - PARAMETER-SPECIFIC SETTINGS
# Only CSV source settings differ between parameter scripts - all other
# configuration is inherited from shared_config.py
# ═══════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────
# CSV SOURCE SETTINGS - Per test type appearance (script-specific)
# These match the sources defined in Global_Parameter_Mapping CSV for
# UndrainedShearStrength
# ─────────────────────────────────────────────────────────────────────────
CSV_SOURCE_SETTINGS = {
    "SPT by Geology.csv": {
        "plotted": True,
        "order": 1,
        "plot_points": True,
        "marker": "x",
        "marker_size": 55,
        "marker_thickness": 2,
        "alpha": 1,
        "legend_name_points": "SPT",
    },
    "CPT by Geology.csv": {
        "plotted": True,
        "order": 2,
        "plot_points": False,  # Dense data - use density line instead
        "marker": "s",
        "marker_size": 40,
        "alpha": 1,
        "legend_name_points": "CPT",
        # CPT-specific settings for auto-plotting when data is sparse
        "cpt_auto_plot_threshold": 50,
        "cpt_auto_plot_disable_density": True,
        # Density line tracing for CPT
        "density_line": {
            "enabled": True,
            "linewidth": 1.0,
            "linestyle": "-",
            "alpha": 1.0,
        },
    },
    "Triaxial Total Stress by Geology.csv": {
        "plotted": True,
        "order": 3,
        "plot_points": True,
        "marker": "D",
        "marker_size": 65,
        "alpha": 1,
        "legend_name_points": "Triaxial Total Stress",
    },
    "Vane Tests by Geology.csv": {
        "plotted": True,
        "order": 4,
        "plot_points": True,
        "marker": "o",
        "marker_size": 60,
        "alpha": 1,
        "legend_name_points": "Vane Tests",
        # Maximum kPa value filter - data points exceeding this value will be excluded
        # Hand vane measurements above 129 kPa are typically unreliable
        "max_kpa": 129,  # MODIFICATION POINT: Set to numeric value or None to disable
    },
    "Pressuremeter Test Results - General.csv": {
        "plotted": True,
        "order": 5,
        "plot_points": True,
        "marker": "^",
        "marker_size": 60,
        "alpha": 1,
        "legend_name_points": "Pressuremeter",
    },
}

# ─────────────────────────────────────────────────────────────────────────
# BUILD CONFIG FROM SHARED DEFAULTS
# Use absolute paths based on WORKSPACE_ROOT to work from any directory
# ─────────────────────────────────────────────────────────────────────────
CONFIG = build_config_from_defaults(
    # Required: Parameter identity
    parameter_name="UndrainedShearStrength",
    display_name="Undrained Shear Strength, cu (kPa)",
    csv_source_settings=CSV_SOURCE_SETTINGS,
    # Optional: Manual data sheet name
    manual_sheet_name="Undrained Shear Strength",  # Correct spelling - matches Excel sheet name
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
    # Enable parallel processing for formation plot generation
    parallel_processing_override={"enabled": True},
)

# ─────────────────────────────────────────────────────────────────────────
# EMPIRICAL CALCULATIONS - SPT N-to-cu conversion factors
# Required for UndrainedShearStrength to convert SPT N-values to cu using: cu = f1 × N
# ─────────────────────────────────────────────────────────────────────────
CONFIG["empirical_calculations"] = {
    "spt_to_cu_factors": {
        # Clay formations
        "KC": 4.5,
        "GF": 4.5,
        "LG": 4.5,
        "RTD": 4.5,
        "HD": 4.5,
        "AMKC": 4.5,
        "AC": 4.5,
        "AL": 4.5,
        "CG": 4.5,
        "MG": 4.5,
        "TS": 4.5,
        # Weathered/unweathered variants
        "KC_W": 4.5,
        "KC_UW": 4.5,
        "GF_W": 4.5,
        "GF_UW": 4.5,
        # Undefined formations
        "KC_undefined": 4.5,
        "GF_undefined": 4.5,
        # RTD sub-formations
        "RTD_1": 4.5,
        "RTD_2": 4.5,
        "RTD_3": 4.5,
        "RTD_Undefined": 4.5,
        # Default fallback
        "default_f1_factor": 4.5,
    }
}

# ─────────────────────────────────────────────────────────────────────────
# FORMATION-SPECIFIC LOCATION FILTERS
# Exclude specific location prefixes from certain formations only
# e.g., OS01/OS02 offshore boreholes excluded from KC formations only
# ─────────────────────────────────────────────────────────────────────────
CONFIG["filtering"]["location_filter"]["formation_specific_filters"] = {
    "OS01": ["KC_W", "KC_UW"],  # OS01 excluded only from KC weathered/unweathered
    "OS02": ["KC_W", "KC_UW"],  # OS02 excluded only from KC weathered/unweathered
}


# ═══════════════════════════════════════════════════════════════════════════
# ⚡ MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════════════


if __name__ == "__main__":
    run_parameter_plotting_pipeline(CONFIG)
