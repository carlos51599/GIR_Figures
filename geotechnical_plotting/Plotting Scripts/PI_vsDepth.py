#!/usr/bin/env python3
"""
Plasticity Index vs Depth - Simplified Plotting Script
=======================================================

Demonstrates the power of the shared modules by reducing a ~5,000 line script
to ~150 lines. All orchestration logic lives in the geotechnical_plotting
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
    python PI_vsDepth.py
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
# These match the sources defined in Global_Parameter_Mapping CSV for PlasticityIndex
# For Plasticity Index plots, typically only Classification by Geology has PI data
# ─────────────────────────────────────────────────────────────────────────
CSV_SOURCE_SETTINGS = {
    "Classification by Geology.csv": {
        "plotted": True,
        "order": 1,
        "plot_points": True,
        "marker": "^",  # Triangle-up (matches MCvsDepth and UndrainedShearStrength)
        "marker_size": 60,
        "alpha": 1,
        "legend_name_points": "Classification",
    },
}

# ─────────────────────────────────────────────────────────────────────────
# BUILD CONFIG FROM SHARED DEFAULTS
# Use absolute paths based on WORKSPACE_ROOT to work from any directory
# ─────────────────────────────────────────────────────────────────────────
CONFIG = build_config_from_defaults(
    # Required: Parameter identity
    parameter_name="PlasticityIndex",
    display_name="Plasticity Index (%)",
    csv_source_settings=CSV_SOURCE_SETTINGS,
    # Optional: Manual data sheet name (matches Excel sheet name)
    manual_sheet_name="PIvsDepth",
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
    # Hide test type shapes in legend (only one test type for PI)
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
    run_parameter_plotting_pipeline(CONFIG)
