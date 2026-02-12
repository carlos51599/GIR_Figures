#!/usr/bin/env python3
"""
SESRO Geotechnical Plotting - Shared Configuration Module
==========================================================

Single source of truth for ALL shared configuration across plotting scripts.
This module eliminates ~290 lines of duplicated configuration from each script.

ARCHITECTURAL OVERVIEW:

Responsibility:
Provides centralized configuration constants and a build_config_from_defaults()
function that generates complete CONFIG dictionaries for each parameter script.

Key Interactions:
- Input: Parameter-specific overrides from individual scripts
- Output: Complete CONFIG dictionary with all defaults merged
- Used by: All parameter plotting scripts (MCvsDepth, PI_vsDepth, etc.)

Navigation Guide:
- GEOLOGICAL MAPPINGS: Formation codes, descriptions, splitting rules
- CSV SOURCE SETTINGS: Test type markers, sizes, legend names
- PLOTTING DEFAULTS: Figure dimensions, axes, legend, grid settings
- OUTLIER DETECTION: IQR settings, thresholds
- FILTERING: Location exclusions, column variations
- OUTPUT CONTROL: Default plot/data generation settings
- build_config_from_defaults(): Main entry point for scripts

USAGE:
    from geotechnical_plotting.config.shared_config import build_config_from_defaults

    CONFIG = build_config_from_defaults(
        parameter_name="MoistureContent",
        display_name="Moisture Content (%)",
        manual_sheet_name="MCvsDeph",
    )
"""

from typing import Dict, Any, List, Optional
from copy import deepcopy


# ═══════════════════════════════════════════════════════════════════════════
# 🗺️ GEOLOGICAL MAPPINGS
# Single source of truth for all geological formation codes and descriptions
# ═══════════════════════════════════════════════════════════════════════════

GEOLOGY_CODE_DESCRIPTIONS: Dict[str, str] = {
    # Primary formations
    "KC": "Kimmeridge Clay Formation",
    "GF": "Gault Clay Formation",
    "LG": "Lower Greensand Formation",
    "RTD": "River Terrace Deposits",
    "HD": "Head Deposits",
    "AMKC": "Ampthill Clay Formation and Kimmeridge Clay Formation",
    "AC": "Ampthill Clay Formation",
    "AL": "Alluvium",
    "CG": "Corallian Group",
    "MG": "Made Ground",
    "TS": "Topsoil",
    # Formation splitting - weathered/unweathered variants
    "GF_W": "Gault Clay Formation (Weathered)",
    "GF_UW": "Gault Clay Formation (Unweathered)",
    "KC_W": "Kimmeridge Clay Formation (Weathered)",
    "KC_UW": "Kimmeridge Clay Formation (Unweathered)",
    # RTD sub-formations
    "RTD_1": "River Terrace Deposits (Northmoor)",
    "RTD_2": "River Terrace Deposits (Summertown-Radley)",
    "RTD_3": "River Terrace Deposits (Wolvercote)",
    "RTD_Undefined": "River Terrace Deposits (Undefined Classification)",
}
"""Complete mapping of geological formation codes to human-readable descriptions."""


DEFAULT_FORMATION_SPLITTING: Dict[str, Any] = {
    "enabled": True,
    "target_formations": ["GF", "KC"],
    "weathering_classification": {
        "weathered_suffix": "_W",
        "unweathered_suffix": "_UW",
        "fallback_classification": "undefined",
    },
    "rtd_classification": {
        "enabled": True,
        "target_formations": ["RTD"],
        "mapping": {
            "RTD_1": "rtd_1",
            "RTD_2": "rtd_2",
            "RTD_3": "rtd_3",
            "Superficial Deposits": "undefined",
            "Soliflucted": "undefined",
        },
        "fallback_classification": "undefined",
    },
}
"""Configuration for splitting formations by weathering and RTD classification."""


# ═══════════════════════════════════════════════════════════════════════════
# 📊 COLUMN VARIATIONS
# Standard column name variations for flexible CSV parsing
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_COLUMN_VARIATIONS: Dict[str, List[str]] = {
    "location_id": ["LocationID", "Location ID", "PointID", "BH_ID"],
    "geology_code": ["GeologyCode", "Geology Code", "Stratum"],
    "geology_code_description": [
        "GeologyCodeDescription",
        "Geology Code Description",
    ],
    "geology_code2": ["GeologyCode2", "Geology Code2", "Geology Code 2"],
    "geology_code2_description": [
        "GeologyCode2Description",
        "Geology Code2 Description",
        "Geology Code 2 Description",
    ],
    "top_depth": [
        "DepthTop",
        "SampleTop",
        "Test Depth",
        "SPT Top Depth",
        "Top Depth",
        "Depth Top",
        "Depth",
        "DepthBase",
    ],
    "cell_pressure": [
        "Stress at Stage End",
        "Cell Pressure",
        "Effective Stress",
        "Consolidation Stress",
    ],
}
"""Column name variations for flexible CSV parsing across different data sources."""


# ═══════════════════════════════════════════════════════════════════════════
# 🔍 FILTERING CONFIGURATION
# Location filtering and exclusion settings
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_FILTERING: Dict[str, Any] = {
    "location_filter": {
        "enabled": True,
        "exclude_prefixes": ["BP", "CCT"],
        "case_sensitive": False,
    },
    # Cell pressure threshold filtering - for consolidation plots
    "cell_pressure_threshold": {
        "enabled": False,  # Disabled by default - only CV scripts need this
        "max_value": 1500,  # Maximum Cell Pressure in kPa (inclusive)
    },
    # Formation-specific parameter thresholds - per-formation filtering
    "formation_parameter_thresholds": {
        "enabled": False,  # Disabled by default
        "thresholds": {},  # Dict of {formation_name: {parameter_name: {max_value/min_value: value}}}
    },
}
"""Default location filtering configuration to exclude specific prefixes."""


DEFAULT_EXCLUDE_PREFIXES: List[str] = ["BP", "CCT"]
"""Default location ID prefixes to exclude from plots."""


DEFAULT_CONSOLIDATION_FILTERING: Dict[str, Any] = {
    "enabled": False,  # Disabled by default - only CV scripts need this
    "apply_to_csvs": ["Consolidation by Geology.csv"],
}
"""Consolidation loading phase filtering - removes unloading phase data after max cell pressure per sample."""


DEFAULT_ROW_LEVEL_FALLBACK: Dict[str, Any] = {
    "enabled": False,  # Disabled by default - only needed for dual-param scripts with backup columns
    "parameters": [],  # List of parameter names to apply row-level fallback for
}
"""Row-level fallback configuration - creates unified columns for parameters with multiple source columns."""


# ═══════════════════════════════════════════════════════════════════════════
# 📉 OUTLIER DETECTION CONFIGURATION
# IQR-based outlier detection settings
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_OUTLIER_DETECTION: Dict[str, Any] = {
    "enabled": True,
    "method": "standard_iqr",
    "min_samples_for_detection": 5,
    "method_settings": {
        "standard_iqr": {
            "iqr_multiplier": 1.5,
            "quartile_boundaries": {
                "q1": 0.25,
                "q3": 0.75,
            },
        },
    },
    "output_folders": {
        "with_outliers": "with_outliers",
        "without_outliers": "without_outliers",
    },
}
"""Default outlier detection settings using IQR method."""


# ═══════════════════════════════════════════════════════════════════════════
# 🔬 INVESTIGATION TRACKING CONFIGURATION
# Settings for tracking data by investigation/borehole
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_INVESTIGATION_TRACKING: Dict[str, Any] = {
    "enabled": True,
    "location_details_csv": "Location Details.csv",
    "per_investigation_plots": {
        "fallback_investigation_name": "Unknown",
        "location_id_column_variants": ["LocationID", "Location ID"],
        "investigation_column_variants": ["Investigation"],
    },
}
"""Default investigation tracking configuration."""


# ═══════════════════════════════════════════════════════════════════════════
# 🎨 INVESTIGATION SERIES CONFIGURATION
# Colors and settings for investigation-based plot series
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_INVESTIGATION_COLORS: List[str] = [
    "#0070C0",  # Blue
    "#444444",  # Dark Gray
    "#596A19",  # Olive
    "#7CAE00",  # Lime Green
    "#B29800",  # Gold
    "#9F2F4E",  # Maroon
    "#D55E00",  # Orange
    "#8400CD",  # Purple
    "#C70077",  # Magenta
    "#E11A82",  # Pink
    "#FFD300",  # Yellow
    "#00BFC4",  # Cyan
    "#C0B3D3",  # Lavender
]
"""Default color palette for investigation series (rotates if more investigations)."""


DEFAULT_INVESTIGATION_SERIES: Dict[str, Any] = {
    "enabled": True,
    "output_folder": "investigation_series",
    "investigation_colors": DEFAULT_INVESTIGATION_COLORS,
    "legend": {
        "show_investigation_colors": True,
        "show_test_type_shapes": True,
        "investigation_label_prefix": "",
        "test_type_label_prefix": "",
        "force_circle_markers": True,
    },
}
"""Default investigation series configuration."""


# ═══════════════════════════════════════════════════════════════════════════
# 📈 PLOTTING CONFIGURATION
# Figure dimensions, axes, legend, and grid settings
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_PLOTTING: Dict[str, Any] = {
    "figure": {
        "width": 8.67,
        "height": 12,
        "dpi": 300,
    },
    "axes": {
        "x_label_position": "top",
        "x_label_size": 14,
        "x_label_weight": "normal",
        "y_label": "Depth (m)",
        "y_label_size": 14,
        "y_label_weight": "normal",
        "x_limit_left": 0,
        "y_margin": 1,
        "invert_y": True,
        "grid": True,
        "grid_which": "both",
        "grid_style": "-",
        "grid_width": 0.5,
        "grid_color": "gray",
        "grid_alpha": 0.3,
    },
    "legend": {
        "location": "upper center",
        "bbox_to_anchor": (0.5, -0.05),
        "ncol": 3,
        "edgecolor": "black",
        "framealpha": 0.9,
        "fixed_width": True,
    },
    "save": {
        "bbox_inches": "tight",
    },
}
"""Default plotting configuration for depth plots."""


DEFAULT_MARKERS: Dict[str, Any] = {
    "edgecolors": "black",
    "linewidths": 0.3,
}
"""Default marker styling for scatter points."""


DEFAULT_PLOT_TITLE: Dict[str, Any] = {
    "enabled": True,
    "font_size": 16,
    "font_weight": "bold",
    "font_family": "Arial",
    "pad": 20,
}
"""Default plot title styling configuration."""


DEFAULT_SOURCE_SETTINGS: Dict[str, Any] = {
    "plotted": True,
    "plot_points": True,
    "marker": "o",
    "marker_size": 50,
    "alpha": 0.7,
    "legend_name_points": None,
}
"""Fallback settings for unmapped CSV sources."""


# ═══════════════════════════════════════════════════════════════════════════
# 📊 DENSITY TRACING CONFIGURATION (CPT-only feature)
# Settings for generating CPT density lines per investigation
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_DENSITY_TRACING: Dict[str, Any] = {
    "segment_detection": {
        "gap_threshold": 0.5,  # meters - defines segment boundaries
        "min_segment_length": 0.20,  # Minimum segment length to process
    },
    "moving_window": {
        "base_window_size": 0.30,  # Window size for mode calculation
        "adaptive_sensitivity": 0.5,  # k factor in adaptive formula
        "step_size_ratio": 0.2,  # step = window * ratio
        "min_points_per_window": 5,  # Minimum points to calculate mode
    },
    "mode_estimation": {
        "bin_strategy": "fd",  # Freedman-Diaconis rule
        "fallback_bins": 30,  # Fallback if FD fails
    },
    "cv_zones": {  # Depth-dependent CV values for adaptive windowing
        "cv_min": 18,  # Minimum CV for adaptive formula
        "cv_max": 58,  # Maximum CV for adaptive formula
    },
}
"""Default density tracing configuration for CPT data."""


# ═══════════════════════════════════════════════════════════════════════════
# ✅ OUTPUT CONTROL DEFAULTS
# Default settings for output generation toggles
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_OUTPUT_CONTROL: Dict[str, Any] = {
    "enabled": True,
    "plots": {
        "enabled": True,
        "investigation_series_plots_plotly_with_outliers": True,
        "investigation_series_plots_manually_modified": True,
    },
    "data": {
        "enabled": True,
        "investigation_summary_csv": True,
        "filtered_data_summary_csv": True,
    },
}
"""Default output control configuration (three-level hierarchy)."""


# ═══════════════════════════════════════════════════════════════════════════
# 📂 MANUAL DATA CONTROL DEFAULTS
# Settings for manual outlier exclusion and data additions
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_MANUAL_OUTLIER_EXCLUSION: Dict[str, Any] = {
    "enabled": True,
    "excel_file": "Data to Remove.xlsx",
    "data_to_add_file": "Data to Add.xlsx",
    "match_tolerance": {
        # Set to 0.01 to handle 2-decimal-place rounding (e.g., 189.495 ≈ 189.50)
        # Excel values are often rounded, while calculated values have more precision
        "parameter": 0.01,
        "depth": 0.01,
    },
    "output_folder": "manually_modified",
}
"""Default manual outlier exclusion configuration."""


# ═══════════════════════════════════════════════════════════════════════════
# ⚡ PARALLEL PROCESSING DEFAULTS
# Optional joblib-based parallel formation processing
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_PARALLEL_PROCESSING: Dict[str, Any] = {
    # Master toggle - OFF by default for safety (explicit opt-in required)
    "enabled": False,
    # Worker configuration: -1=auto, -2=auto-1, or explicit number
    "max_workers": -1,
    # Don't parallelize if fewer formations than this threshold
    "min_formations_for_parallel": 3,
    # Safety settings
    "timeout_per_formation_seconds": 300,  # 5 min max per formation
    "fallback_on_error": True,  # If parallel fails, run sequential
    # Joblib settings
    "backend": "loky",  # Process-based (safest for matplotlib)
    "verbose": 10,  # Joblib verbosity (0-50)
    # Logging
    "log_worker_progress": True,
}
"""Default parallel processing configuration (OFF by default for safety)."""


# ═══════════════════════════════════════════════════════════════════════════
# 🔧 CONFIGURATION BUILDER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries, with override values taking precedence.

    Args:
        base: Base dictionary with default values
        override: Override dictionary with custom values

    Returns:
        Merged dictionary with override values taking precedence
    """
    result = deepcopy(base)

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)

    return result


def build_config(
    plot_type: str,
    csv_source_settings: Dict[str, Dict[str, Any]],
    # Depth plot parameters
    parameter_name: Optional[str] = None,
    display_name: Optional[str] = None,
    source_parameter: Optional[str] = None,
    # XY plot parameters
    x_parameter_name: Optional[str] = None,
    y_parameter_name: Optional[str] = None,
    x_display_name: Optional[str] = None,
    y_display_name: Optional[str] = None,
    output_folder_name: Optional[str] = None,
    # Common optional parameters
    manual_sheet_name: Optional[str] = None,
    mapping_csv: str = "Parameter_CSV_Mapping.csv",
    csv_source_folder: str = "Openground CSVs",
    output_base_folder: str = "Output",
    # Section-level overrides
    output_control_override: Optional[Dict[str, Any]] = None,
    mappings_override: Optional[Dict[str, Any]] = None,
    filtering_override: Optional[Dict[str, Any]] = None,
    outlier_detection_override: Optional[Dict[str, Any]] = None,
    investigation_tracking_override: Optional[Dict[str, Any]] = None,
    investigation_series_override: Optional[Dict[str, Any]] = None,
    plotting_override: Optional[Dict[str, Any]] = None,
    manual_outlier_exclusion_override: Optional[Dict[str, Any]] = None,
    consolidation_filtering_override: Optional[Dict[str, Any]] = None,
    row_level_fallback_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Unified configuration builder for all plot types.

    This is the single entry point for building CONFIG dictionaries.
    It delegates to the appropriate specialized builder based on plot_type.

    Args:
        plot_type: One of "depth", "xy", or "psd"
        csv_source_settings: Script-specific CSV source settings (required for all)

        # Depth plot parameters (required when plot_type="depth"):
        parameter_name: Internal parameter name (e.g., "MoistureContent")
        display_name: Human-readable label (e.g., "Moisture Content (%)")
        source_parameter: Source parameter for derived parameters (optional)

        # XY plot parameters (required when plot_type="xy"):
        x_parameter_name: X-axis parameter name
        y_parameter_name: Y-axis parameter name
        x_display_name: X-axis display label
        y_display_name: Y-axis display label
        output_folder_name: Output subfolder name

        # Common optional parameters:
        manual_sheet_name: Sheet name in manual data Excel files
        mapping_csv: Path to global parameter mapping CSV
        csv_source_folder: Folder containing source CSV files
        output_base_folder: Base folder for all outputs

        # Section-level overrides (see individual builders for details)

    Returns:
        Complete CONFIG dictionary ready for use with run_plotting_pipeline()

    Replaces:
        - Direct calls to build_config_from_defaults()
        - Direct calls to build_dual_param_config_from_defaults()

    Example (depth plot):
        >>> CONFIG = build_config(
        ...     plot_type="depth",
        ...     parameter_name="MoistureContent",
        ...     display_name="Moisture Content (%)",
        ...     csv_source_settings=CSV_SOURCE_SETTINGS,
        ... )

    Example (XY plot):
        >>> CONFIG = build_config(
        ...     plot_type="xy",
        ...     x_parameter_name="Cell Pressure",
        ...     y_parameter_name="CoefficientConsolidation",
        ...     x_display_name="Cell Pressure (kPa)",
        ...     y_display_name="cv (m²/year)",
        ...     output_folder_name="CVvsCellPressure",
        ...     csv_source_settings=CSV_SOURCE_SETTINGS,
        ... )
    """
    if plot_type == "depth":
        # Validate required depth plot parameters
        if parameter_name is None or display_name is None:
            raise ValueError(
                "Depth plots require 'parameter_name' and 'display_name' parameters."
            )

        return build_config_from_defaults(
            parameter_name=parameter_name,
            display_name=display_name,
            csv_source_settings=csv_source_settings,
            source_parameter=source_parameter,
            manual_sheet_name=manual_sheet_name,
            mapping_csv=mapping_csv,
            csv_source_folder=csv_source_folder,
            output_base_folder=output_base_folder,
            output_control_override=output_control_override,
            mappings_override=mappings_override,
            filtering_override=filtering_override,
            outlier_detection_override=outlier_detection_override,
            investigation_tracking_override=investigation_tracking_override,
            investigation_series_override=investigation_series_override,
            plotting_override=plotting_override,
        )

    elif plot_type == "xy":
        # Validate required XY plot parameters
        if (
            x_parameter_name is None
            or y_parameter_name is None
            or x_display_name is None
            or y_display_name is None
            or output_folder_name is None
        ):
            raise ValueError(
                "XY plots require 'x_parameter_name', 'y_parameter_name', "
                "'x_display_name', 'y_display_name', and 'output_folder_name' parameters."
            )

        return build_dual_param_config_from_defaults(
            x_parameter_name=x_parameter_name,
            y_parameter_name=y_parameter_name,
            x_display_name=x_display_name,
            y_display_name=y_display_name,
            output_folder_name=output_folder_name,
            csv_source_settings=csv_source_settings,
            manual_sheet_name=manual_sheet_name,
            mapping_csv=mapping_csv,
            csv_source_folder=csv_source_folder,
            output_base_folder=output_base_folder,
            output_control_override=output_control_override,
            mappings_override=mappings_override,
            filtering_override=filtering_override,
            outlier_detection_override=outlier_detection_override,
            investigation_tracking_override=investigation_tracking_override,
            investigation_series_override=investigation_series_override,
            plotting_override=plotting_override,
            manual_outlier_exclusion_override=manual_outlier_exclusion_override,
            consolidation_filtering_override=consolidation_filtering_override,
            row_level_fallback_override=row_level_fallback_override,
        )

    elif plot_type == "psd":
        # PSD uses depth config with PSD-specific settings
        if parameter_name is None:
            parameter_name = "ParticleSizeDistribution"
        if display_name is None:
            display_name = "Particle Size Distribution"

        config = build_config_from_defaults(
            parameter_name=parameter_name,
            display_name=display_name,
            csv_source_settings=csv_source_settings,
            manual_sheet_name=manual_sheet_name,
            mapping_csv=mapping_csv,
            csv_source_folder=csv_source_folder,
            output_base_folder=output_base_folder,
            output_control_override=output_control_override,
            mappings_override=mappings_override,
            filtering_override=filtering_override,
            outlier_detection_override=outlier_detection_override,
            investigation_tracking_override=investigation_tracking_override,
            investigation_series_override=investigation_series_override,
            plotting_override=plotting_override,
        )

        # Add PSD-specific settings marker
        config["psd_settings"] = {
            "average_by_investigation": True,
            "data_columns": {
                "particle_size": "Particle Size",
                "percentage_passing": "Percentage Passing",
                "sample_reference": "Sample Reference",
            },
        }

        return config

    else:
        raise ValueError(
            f"Unknown plot_type: '{plot_type}'. " f"Valid options: 'depth', 'xy', 'psd'"
        )


def build_config_from_defaults(
    # Required: Parameter identity
    parameter_name: str,
    display_name: str,
    # Required: CSV source settings (script-specific)
    csv_source_settings: Dict[str, Dict[str, Any]],
    # Optional: Source parameter for derived parameters (e.g., Eu uses Cu)
    source_parameter: Optional[str] = None,
    # Optional: Manual data sheet mapping
    manual_sheet_name: Optional[str] = None,
    # Optional: File path overrides
    mapping_csv: str = "Parameter_CSV_Mapping.csv",
    csv_source_folder: str = "Openground CSVs",
    output_base_folder: str = "Output",
    # Optional: Section-level overrides (deep merged)
    output_control_override: Optional[Dict[str, Any]] = None,
    mappings_override: Optional[Dict[str, Any]] = None,
    filtering_override: Optional[Dict[str, Any]] = None,
    outlier_detection_override: Optional[Dict[str, Any]] = None,
    investigation_tracking_override: Optional[Dict[str, Any]] = None,
    investigation_series_override: Optional[Dict[str, Any]] = None,
    plotting_override: Optional[Dict[str, Any]] = None,
    parallel_processing_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a complete CONFIG dictionary by merging user overrides with shared defaults.

    DEPRECATED: Use build_config(plot_type="depth", ...) instead for new code.
    This function is retained for backwards compatibility.

    This function eliminates ~200 lines of duplicated configuration from each script.
    Scripts only need to specify their parameter-specific settings - everything else is inherited.

    Args:
        parameter_name: Internal parameter name (e.g., "MoistureContent")
        display_name: Human-readable label for axes (e.g., "Moisture Content (%)")
        csv_source_settings: Script-specific CSV source settings (required)
        manual_sheet_name: Sheet name in manual data Excel files (optional)
        mapping_csv: Path to global parameter mapping CSV
        csv_source_folder: Folder containing source CSV files
        output_base_folder: Base folder for all outputs
        output_control_override: Override output control settings
        mappings_override: Override geological mappings
        filtering_override: Override filtering settings
        outlier_detection_override: Override outlier detection settings
        investigation_tracking_override: Override investigation tracking settings
        investigation_series_override: Override investigation series settings
        plotting_override: Override plotting settings
        parallel_processing_override: Override parallel processing settings (enabled, max_workers, etc.)

    Returns:
        Complete CONFIG dictionary ready for use in plotting scripts

    Example:
        CSV_SOURCE_SETTINGS = {
            "Samples by Geology.csv": {
                "plotted": True,
                "order": 1,
                "marker": "o",
                "marker_size": 50,
                "legend_name_points": "Samples",
            },
            # ... more sources
        }

        CONFIG = build_config_from_defaults(
            parameter_name="MoistureContent",
            display_name="Moisture Content (%)",
            csv_source_settings=CSV_SOURCE_SETTINGS,
            manual_sheet_name="MCvsDeph",
        )
    """
    # Build parameter section
    parameter_config = {
        "name": parameter_name,
        "display_name": display_name,
        "mapping_csv": mapping_csv,
        "csv_source_folder": csv_source_folder,
        "output_base_folder": output_base_folder,
    }
    # Add source_parameter if provided (for derived parameters like Eu from Cu)
    if source_parameter:
        parameter_config["source_parameter"] = source_parameter

    # Build manual outlier exclusion section
    # Use source_parameter as the sheet key if provided (so removal uses source values)
    sheet_key = source_parameter if source_parameter else parameter_name
    manual_config = deepcopy(DEFAULT_MANUAL_OUTLIER_EXCLUSION)
    if manual_sheet_name:
        manual_config["sheets"] = {sheet_key: manual_sheet_name}
    else:
        manual_config["sheets"] = {sheet_key: parameter_name}

    # Build mappings section
    mappings_config = {
        "geology_code_descriptions": deepcopy(GEOLOGY_CODE_DESCRIPTIONS),
        "formation_splitting": deepcopy(DEFAULT_FORMATION_SPLITTING),
        "column_variations": deepcopy(DEFAULT_COLUMN_VARIATIONS),
    }
    if mappings_override:
        mappings_config = _deep_merge(mappings_config, mappings_override)

    # Build output control section
    output_control_config = deepcopy(DEFAULT_OUTPUT_CONTROL)
    if output_control_override:
        output_control_config = _deep_merge(
            output_control_config, output_control_override
        )

    # Build filtering section
    filtering_config = deepcopy(DEFAULT_FILTERING)
    if filtering_override:
        filtering_config = _deep_merge(filtering_config, filtering_override)

    # Build outlier detection section
    outlier_config = deepcopy(DEFAULT_OUTLIER_DETECTION)
    if outlier_detection_override:
        outlier_config = _deep_merge(outlier_config, outlier_detection_override)

    # Build investigation tracking section
    investigation_tracking_config = deepcopy(DEFAULT_INVESTIGATION_TRACKING)
    if investigation_tracking_override:
        investigation_tracking_config = _deep_merge(
            investigation_tracking_config, investigation_tracking_override
        )

    # Build investigation series section
    investigation_series_config = deepcopy(DEFAULT_INVESTIGATION_SERIES)
    if investigation_series_override:
        investigation_series_config = _deep_merge(
            investigation_series_config, investigation_series_override
        )

    # Build plotting section
    plotting_config = deepcopy(DEFAULT_PLOTTING)
    if plotting_override:
        plotting_config = _deep_merge(plotting_config, plotting_override)

    # Build parallel processing section
    parallel_processing_config = deepcopy(DEFAULT_PARALLEL_PROCESSING)
    if parallel_processing_override:
        parallel_processing_config = _deep_merge(
            parallel_processing_config, parallel_processing_override
        )

    # Assemble complete CONFIG dictionary
    config: Dict[str, Any] = {
        "parameter": parameter_config,
        "output_control": output_control_config,
        "manual_outlier_exclusion": manual_config,
        "mappings": mappings_config,
        "filtering": filtering_config,
        "outlier_detection": outlier_config,
        "investigation_tracking": investigation_tracking_config,
        "investigation_series": investigation_series_config,
        "plotting": plotting_config,
        "parallel_processing": parallel_processing_config,
        "csv_source_settings": deepcopy(csv_source_settings),
        "default_source_settings": deepcopy(DEFAULT_SOURCE_SETTINGS),
        "markers": deepcopy(DEFAULT_MARKERS),
        "plot_title": deepcopy(DEFAULT_PLOT_TITLE),
        "density_tracing": deepcopy(DEFAULT_DENSITY_TRACING),
    }

    return config


def build_dual_param_config_from_defaults(
    # Required: Dual parameter identity
    x_parameter_name: str,
    y_parameter_name: str,
    x_display_name: str,
    y_display_name: str,
    output_folder_name: str,
    # Required: CSV source settings (script-specific)
    csv_source_settings: Dict[str, Dict[str, Any]],
    # Optional: Manual data sheet mapping
    manual_sheet_name: Optional[str] = None,
    # Optional: File path overrides
    mapping_csv: str = "Parameter_CSV_Mapping.csv",
    csv_source_folder: str = "Openground CSVs",
    output_base_folder: str = "Output",
    # Optional: Section-level overrides (deep merged)
    output_control_override: Optional[Dict[str, Any]] = None,
    mappings_override: Optional[Dict[str, Any]] = None,
    filtering_override: Optional[Dict[str, Any]] = None,
    outlier_detection_override: Optional[Dict[str, Any]] = None,
    investigation_tracking_override: Optional[Dict[str, Any]] = None,
    investigation_series_override: Optional[Dict[str, Any]] = None,
    plotting_override: Optional[Dict[str, Any]] = None,
    manual_outlier_exclusion_override: Optional[Dict[str, Any]] = None,
    consolidation_filtering_override: Optional[Dict[str, Any]] = None,
    row_level_fallback_override: Optional[Dict[str, Any]] = None,
    parallel_processing_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a complete CONFIG dictionary for DUAL-PARAMETER (X vs Y) plots.

    DEPRECATED: Use build_config(plot_type="xy", ...) instead for new code.
    This function is retained for backwards compatibility.

    This function is for plots like CV vs Cell Pressure where one parameter
    is plotted against another (not vs depth). Eliminates duplicated
    configuration from each dual-parameter script.

    Args:
        x_parameter_name: X-axis parameter name (e.g., "Cell Pressure")
        y_parameter_name: Y-axis parameter name (e.g., "CoefficientConsolidation")
        x_display_name: X-axis display label (e.g., "Cell Pressure (kPa)")
        y_display_name: Y-axis display label (e.g., "cv (m²/year)")
        output_folder_name: Output subfolder name (e.g., "CoefficientConsolidationvsCellPressure")
        csv_source_settings: Script-specific CSV source settings (required)
        manual_sheet_name: Sheet name in manual data Excel files (optional)
        mapping_csv: Path to global parameter mapping CSV
        csv_source_folder: Folder containing source CSV files
        output_base_folder: Base folder for all outputs
        output_control_override: Override output control settings
        mappings_override: Override geological mappings
        filtering_override: Override filtering settings
        outlier_detection_override: Override outlier detection settings
        investigation_tracking_override: Override investigation tracking settings
        investigation_series_override: Override investigation series settings
        plotting_override: Override plotting settings
        manual_outlier_exclusion_override: Override manual outlier exclusion settings (excel_file paths, etc.)
        consolidation_filtering_override: Override consolidation filtering settings
        row_level_fallback_override: Override row-level fallback settings
        parallel_processing_override: Override parallel processing settings (enabled, max_workers, etc.)

    Returns:
        Complete CONFIG dictionary ready for use in dual-parameter plotting scripts

    Example:
        CONFIG = build_dual_param_config_from_defaults(
            x_parameter_name="Cell Pressure",
            y_parameter_name="CoefficientConsolidation",
            x_display_name="Cell Pressure (kPa)",
            y_display_name="cv (m²/year)",
            output_folder_name="CoefficientConsolidationvsCellPressure",
            csv_source_settings=CSV_SOURCE_SETTINGS,
            manual_sheet_name="cv",
        )
    """
    # Build row-level fallback section (for dual-param scripts with backup columns)
    row_level_fallback_config = deepcopy(DEFAULT_ROW_LEVEL_FALLBACK)
    if row_level_fallback_override:
        row_level_fallback_config = _deep_merge(
            row_level_fallback_config, row_level_fallback_override
        )

    # Build dual-parameter section (different from single-parameter)
    parameter_config = {
        "name": output_folder_name,  # Use output folder name as identifier
        "x_parameter": x_parameter_name,
        "y_parameter": y_parameter_name,
        "x_display_name": x_display_name,
        "y_display_name": y_display_name,
        "output_folder_name": output_folder_name,
        "mapping_csv": mapping_csv,
        "csv_source_folder": csv_source_folder,
        "output_base_folder": output_base_folder,
        "is_dual_parameter": True,  # Flag for orchestrator
        "row_level_fallback": row_level_fallback_config,  # Nested in parameter section
    }

    # Build manual outlier exclusion section
    manual_config = deepcopy(DEFAULT_MANUAL_OUTLIER_EXCLUSION)
    if manual_sheet_name:
        manual_config["sheets"] = {y_parameter_name: manual_sheet_name}
    else:
        manual_config["sheets"] = {y_parameter_name: y_parameter_name}
    if manual_outlier_exclusion_override:
        manual_config = _deep_merge(manual_config, manual_outlier_exclusion_override)

    # Build mappings section
    mappings_config = {
        "geology_code_descriptions": deepcopy(GEOLOGY_CODE_DESCRIPTIONS),
        "formation_splitting": deepcopy(DEFAULT_FORMATION_SPLITTING),
        "column_variations": deepcopy(DEFAULT_COLUMN_VARIATIONS),
    }
    if mappings_override:
        mappings_config = _deep_merge(mappings_config, mappings_override)

    # Build output control section
    output_control_config = deepcopy(DEFAULT_OUTPUT_CONTROL)
    if output_control_override:
        output_control_config = _deep_merge(
            output_control_config, output_control_override
        )

    # Build filtering section
    filtering_config = deepcopy(DEFAULT_FILTERING)
    if filtering_override:
        filtering_config = _deep_merge(filtering_config, filtering_override)

    # Build consolidation filtering section (for CV scripts - removes unloading phase data)
    consolidation_filtering_config = deepcopy(DEFAULT_CONSOLIDATION_FILTERING)
    if consolidation_filtering_override:
        consolidation_filtering_config = _deep_merge(
            consolidation_filtering_config, consolidation_filtering_override
        )

    # Build outlier detection section
    outlier_config = deepcopy(DEFAULT_OUTLIER_DETECTION)
    if outlier_detection_override:
        outlier_config = _deep_merge(outlier_config, outlier_detection_override)

    # Build investigation tracking section
    investigation_tracking_config = deepcopy(DEFAULT_INVESTIGATION_TRACKING)
    if investigation_tracking_override:
        investigation_tracking_config = _deep_merge(
            investigation_tracking_config, investigation_tracking_override
        )

    # Build investigation series section
    investigation_series_config = deepcopy(DEFAULT_INVESTIGATION_SERIES)
    if investigation_series_override:
        investigation_series_config = _deep_merge(
            investigation_series_config, investigation_series_override
        )

    # Build plotting section with X vs Y defaults
    dual_param_plotting_defaults = {
        "figure": {
            "width": 10,  # Wider for scatter plots
            "height": 8,
            "dpi": 300,
        },
        "axes": {
            "x_label_size": 10,
            "x_label_weight": "normal",
            "y_label_size": 10,
            "y_label_weight": "normal",
            "grid": True,
            "grid_which": "both",
            "grid_style": "-",
            "grid_width": 0.5,
            "grid_color": "gray",
            "grid_alpha": 0.3,
        },
        "legend": {
            "location": "upper left",
            "edgecolor": "black",
            "framealpha": 0.9,
            "ncol": 1,
            "fixed_width": True,
        },
        "save": {
            "bbox_inches": "tight",
        },
    }
    plotting_config = deepcopy(dual_param_plotting_defaults)
    if plotting_override:
        plotting_config = _deep_merge(plotting_config, plotting_override)

    # Build parallel processing section
    parallel_processing_config = deepcopy(DEFAULT_PARALLEL_PROCESSING)
    if parallel_processing_override:
        parallel_processing_config = _deep_merge(
            parallel_processing_config, parallel_processing_override
        )

    # Assemble complete CONFIG dictionary
    config: Dict[str, Any] = {
        "parameter": parameter_config,
        "output_control": output_control_config,
        "manual_outlier_exclusion": manual_config,
        "mappings": mappings_config,
        "filtering": filtering_config,
        "consolidation_filtering": consolidation_filtering_config,
        "outlier_detection": outlier_config,
        "investigation_tracking": investigation_tracking_config,
        "investigation_series": investigation_series_config,
        "plotting": plotting_config,
        "parallel_processing": parallel_processing_config,
        "csv_source_settings": deepcopy(csv_source_settings),
        "default_source_settings": deepcopy(DEFAULT_SOURCE_SETTINGS),
        "markers": deepcopy(DEFAULT_MARKERS),
        "plot_title": deepcopy(DEFAULT_PLOT_TITLE),
        "density_tracing": deepcopy(DEFAULT_DENSITY_TRACING),
    }

    return config


def get_geology_description(code: str) -> str:
    """
    Get human-readable description for a geological formation code.

    Args:
        code: Geological formation code (e.g., "GF", "KC_W")

    Returns:
        Human-readable description or the code itself if not found
    """
    return GEOLOGY_CODE_DESCRIPTIONS.get(code, code)


# ═══════════════════════════════════════════════════════════════════════════
# 📦 MODULE EXPORTS
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    # Unified builder function (recommended)
    "build_config",
    # Specialized builder functions (backwards compatible)
    "build_config_from_defaults",
    "build_dual_param_config_from_defaults",
    # Helper functions
    "get_geology_description",
    # Geological mappings
    "GEOLOGY_CODE_DESCRIPTIONS",
    "DEFAULT_FORMATION_SPLITTING",
    # Column variations
    "DEFAULT_COLUMN_VARIATIONS",
    # Filtering
    "DEFAULT_FILTERING",
    "DEFAULT_EXCLUDE_PREFIXES",
    "DEFAULT_CONSOLIDATION_FILTERING",
    "DEFAULT_ROW_LEVEL_FALLBACK",
    # Outlier detection
    "DEFAULT_OUTLIER_DETECTION",
    # Investigation tracking
    "DEFAULT_INVESTIGATION_TRACKING",
    # Investigation series
    "DEFAULT_INVESTIGATION_COLORS",
    "DEFAULT_INVESTIGATION_SERIES",
    # Plotting
    "DEFAULT_PLOTTING",
    "DEFAULT_MARKERS",
    "DEFAULT_PLOT_TITLE",
    # Default source settings (fallback)
    "DEFAULT_SOURCE_SETTINGS",
    # Output control
    "DEFAULT_OUTPUT_CONTROL",
    # Manual data control
    "DEFAULT_MANUAL_OUTLIER_EXCLUSION",
    # Density tracing
    "DEFAULT_DENSITY_TRACING",
    # Parallel processing
    "DEFAULT_PARALLEL_PROCESSING",
]
