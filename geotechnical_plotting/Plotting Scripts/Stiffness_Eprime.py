#!/usr/bin/env python3
"""
Drained Stiffness E' vs Depth - Derived Parameter Plotting Script
===================================================================

This script generates Drained Stiffness (E') plots by transforming
Undrained Shear Strength (Cu) data using formation-specific multipliers
and applying the E' = Eu × 0.6 relationship.

DERIVED PARAMETER ARCHITECTURE:
- Source Parameter: UndrainedShearStrength (Cu in kPa)
- Transformation: E' = (Cu × Eu_multiplier × 0.6) / 1000 (converts to MPa)
- Combined multipliers: KC_W=120, KC_UW=150, GF_W=120, GF_UW=150
  (calculated as: Eu_multiplier × 0.6, e.g., 200 × 0.6 = 120)

KEY FEATURE: Imports CSV_SOURCE_SETTINGS from UndrainedShearStrength.py
to maintain single source of truth for test type appearance settings.

ARCHITECTURAL OVERVIEW:

Responsibility:
This script contains ONLY configuration. The Cu→E' transformation is applied
by the orchestrator when 'value_transformation' config is present.

Key Interactions:
- Imports: CSV_SOURCE_SETTINGS from UndrainedShearStrength (shared config)
- Input: CONFIG with value_transformation for Cu→E' conversion
- Processing: Delegates everything to run_parameter_plotting_pipeline()
- Output: E' plots in Output/DrainedStiffnessEprime/

USAGE:
    python Stiffness_Eprime.py
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
# ═══════════════════════════════════════════════════════════════════════════

# Shared configuration builder
from geotechnical_plotting.shared_config import build_config_from_defaults

# Orchestration pipeline - runs the entire workflow
from geotechnical_plotting.orchestrator import run_parameter_plotting_pipeline

# ─────────────────────────────────────────────────────────────────────────
# IMPORT CSV_SOURCE_SETTINGS FROM UNDRAINED SHEAR STRENGTH
# This is the key reuse pattern - single source of truth for test type settings
# Note: Using importlib since "Plotting Scripts" folder has spaces in name
# ─────────────────────────────────────────────────────────────────────────
import importlib.util

_cu_script_path = SCRIPT_DIR / "UndrainedShearStrength.py"
_spec = importlib.util.spec_from_file_location(
    "UndrainedShearStrength", _cu_script_path
)
_cu_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cu_module)
CSV_SOURCE_SETTINGS = _cu_module.CSV_SOURCE_SETTINGS

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
# ⚙️ CONFIGURATION - DRAINED STIFFNESS E' SETTINGS
# ═══════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────
# E' MULTIPLIER CALCULATION
# E' = Eu × 0.6, so combined multiplier = Eu_multiplier × 0.6
# ─────────────────────────────────────────────────────────────────────────
EU_TO_EPRIME_FACTOR = 0.6

# Eu multipliers from Stiffness_Eu.py
EU_MULTIPLIERS = {
    "KC_W": 200,
    "KC_UW": 250,
    "GF_W": 200,
    "GF_UW": 250,
}

# Calculate combined E' multipliers (Eu_multiplier × 0.6)
EPRIME_MULTIPLIERS = {
    formation: multiplier * EU_TO_EPRIME_FACTOR
    for formation, multiplier in EU_MULTIPLIERS.items()
}

# ─────────────────────────────────────────────────────────────────────────
# BUILD CONFIG FROM SHARED DEFAULTS
# ─────────────────────────────────────────────────────────────────────────
CONFIG = build_config_from_defaults(
    # Parameter identity - output folder name
    parameter_name="DrainedStiffnessEprime",
    # Display name for E' (transformed values)
    display_name="Drained Stiffness E' (MPa)",
    # Reuse CSV source settings from UndrainedShearStrength
    csv_source_settings=CSV_SOURCE_SETTINGS,
    # Source parameter - look up Cu data from mapping CSV
    # This is also used for manual data sheet key (removal uses Cu values)
    source_parameter="UndrainedShearStrength",
    # Manual data sheet name (same as Cu for data removal/addition)
    manual_sheet_name="Undrained Shear Strength",
    # Use absolute paths
    mapping_csv=str(WORKSPACE_ROOT / "Parameter_CSV_Mapping.csv"),
    csv_source_folder=str(WORKSPACE_ROOT / "Openground CSVs"),
    output_base_folder=str(WORKSPACE_ROOT / "Output"),
    # Enable outputs
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
# Same as UndrainedShearStrength - converts SPT N-values to Cu first
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
# VALUE TRANSFORMATION - Cu to E' conversion
# E' = (Cu × Eu_multiplier × 0.6) / 1000  (kPa to MPa)
# ─────────────────────────────────────────────────────────────────────────
CONFIG["value_transformation"] = {
    "enabled": True,
    # Formation-specific combined multipliers (Eu_multiplier × 0.6)
    "multiplier_by_formation": EPRIME_MULTIPLIERS,
    # Unit conversion: kPa to MPa
    "unit_divisor": 1000,
    # Only apply to these formations (others will be skipped)
    "applicable_formations": ["KC_W", "KC_UW", "GF_W", "GF_UW"],
}

# ─────────────────────────────────────────────────────────────────────────
# FORMATION-SPECIFIC LOCATION FILTERS
# Same as UndrainedShearStrength
# ─────────────────────────────────────────────────────────────────────────
CONFIG["filtering"]["location_filter"]["formation_specific_filters"] = {
    "OS01": ["KC_W", "KC_UW"],
    "OS02": ["KC_W", "KC_UW"],
}


# ═══════════════════════════════════════════════════════════════════════════
# ⚡ MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════════════


if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("🔄 Stiffness E' (Drained) - Derived from Undrained Shear Strength")
    logger.info("   E' = Eu × 0.6, where Eu = Cu × formation_multiplier")
    logger.info("   CSV_SOURCE_SETTINGS imported from UndrainedShearStrength.py")
    logger.info("=" * 80)
    logger.info(f"   E' multipliers: {EPRIME_MULTIPLIERS}")
    run_parameter_plotting_pipeline(CONFIG)
