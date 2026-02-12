#!/usr/bin/env python3
"""
Plotting Pipeline Orchestration Module - AI-Optimized Monolith
SESRO GIR Geotechnical Parameter Plotting

ARCHITECTURAL OVERVIEW:

Responsibility:
Orchestrates the complete plotting pipeline for any geotechnical parameter.
Takes a CONFIG dictionary and runs all phases: data loading, formation grouping,
outlier filtering, manual data control, plot generation, and CSV export.

Key Interactions:
- Input: Complete CONFIG dictionary from parameter script
- Processing: Coordinates all shared modules (data, analysis, plotting, export)
- Output: Plotly HTML + matplotlib PNG + investigation summaries + filtered data tracking

Navigation Guide (use VS Code outline Ctrl+Shift+O):
1. OUTPUT CONTROL HELPERS: Check if outputs should be generated
2. PLOT GENERATION ORCHESTRATOR: Generate Plotly and matplotlib plots
3. MAIN PIPELINE ORCHESTRATOR: run_parameter_plotting_pipeline()

CONFIGURATION ARCHITECTURE:
- Single CONFIG parameter passed in from parameter script
- All configuration extracted in orchestrator, passed as primitives to business logic
- Zero global CONFIG access in helper functions

USAGE:
    from geotechnical_plotting.orchestration import run_parameter_plotting_pipeline
    run_parameter_plotting_pipeline(CONFIG)
"""

# Standard library imports
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Set, Optional, Tuple

# Third-party imports
import pandas as pd

# Local imports - data pipeline (from data_pipeline.py at root level)
from .data_pipeline import (
    extract_parameter_mappings,
    load_csv_data,
    load_location_details,
    add_investigation_column,
    group_data_by_formation_unified,
    prepare_unified_data_objects,
    filter_outliers_from_formations,
    apply_cell_pressure_threshold_filtering,
    apply_formation_parameter_threshold_filtering,
    apply_test_type_threshold_filtering,
    apply_row_level_fallback,
    apply_empirical_calculations,
    apply_formation_specific_filters,
    apply_value_transformation,
)

# Local imports - manual data (from manual_data.py at root level)
from .manual_data import (
    load_manual_outliers,
    mark_manual_outliers,
    load_manual_additions,
    mark_manual_additions,
    load_manual_outliers_psd,
    mark_manual_outliers_psd,
)

# Local imports - export utilities
from .data_export_utils import (
    generate_investigation_summary,
    track_filtered_data,
    should_generate_output,
    should_generate_data_export,
)

# Local imports - plotting utilities
from .plotting_utils import (
    generate_depth_plot,
    generate_xy_plot,
    generate_manually_modified_depth_plot,
    generate_matplotlib_xy_plot,
    generate_plotly_psd_plot,
    generate_matplotlib_psd_plot,
    create_investigation_color_mapping,
)

# ═══════════════════════════════════════════════════════════════════════════
# ⚡ OPTIONAL PARALLEL PROCESSING IMPORT
# This import is conditional - parallel processing is an OPTIONAL overlay.
# If the parallel_processing module fails to import or parallel is disabled,
# the system automatically falls back to sequential processing.
# ═══════════════════════════════════════════════════════════════════════════
try:
    from .parallel_processing import (
        run_parallel_formation_plots,
        ParallelExecutionError,
        should_use_parallel,
        get_parallel_config,
    )

    PARALLEL_AVAILABLE = True
except ImportError as e:
    # Parallel processing not available - will use sequential processing
    PARALLEL_AVAILABLE = False

    # Define placeholder for ParallelExecutionError to avoid NameError
    class ParallelExecutionError(Exception):  # type: ignore
        """Placeholder when parallel module unavailable."""

        pass


# Logging Configuration
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# 🔧 HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def _create_sample_identifier(
    location_id: str, depth_top: Optional[float] = None
) -> str:
    """
    Create sample identifier string in format 'LocationID_Depth' or just 'LocationID'.

    Combines location ID and depth to create a unique identifier string
    for labeling individual samples in PSD plots (e.g., "BH01_12.5").
    If depth is missing or empty, falls back to using just the location ID.

    Args:
        location_id: Location identifier (e.g., "BH01", "BH18")
        depth_top: Depth value to use for suffix (e.g., 12.5, 8.0)

    Returns:
        Formatted sample identifier string (e.g., "BH01_12.5" or "BH01")

    Example:
        >>> _create_sample_identifier("BH01", 12.5)
        "BH01_12.5"
        >>> _create_sample_identifier("BH18", 8.0)
        "BH18_8.0"
        >>> _create_sample_identifier("BH09", None)
        "BH09"
    """
    if depth_top is not None and pd.notna(depth_top):
        return f"{location_id}_{depth_top}"
    return str(location_id)


# ═══════════════════════════════════════════════════════════════════════════
# 🔧 OUTPUT CONTROL HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def _should_generate_plot(plot_name: str, output_control: Dict[str, Any]) -> bool:
    """
    Check if a specific plot should be generated based on three-level hierarchy.

    Uses should_generate_output from export module for master toggle check,
    then checks category and item toggles.

    Args:
        plot_name: Key in output_control["plots"] (e.g., "investigation_series_plots_plotly_with_outliers")
        output_control: output_control section from CONFIG

    Returns:
        True if plot should be generated based on three-level hierarchy
    """
    # Level 1: Master toggle
    if not should_generate_output(output_control):
        return False

    # Level 2: Category toggle (plots.enabled)
    if not output_control.get("plots", {}).get("enabled", True):
        return False

    # Level 3: Item toggle
    return output_control.get("plots", {}).get(plot_name, False)


# ═══════════════════════════════════════════════════════════════════════════
# 🎨 PLOT GENERATION ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════


def _generate_investigation_series_plots(
    parameter_mappings: pd.DataFrame,
    plotly_unified_data: Dict[str, Dict[str, pd.DataFrame]],
    manually_modified_data: Dict[str, Dict[str, pd.DataFrame]],
    config: Dict[str, Any],
) -> None:
    """
    Orchestrate generation of investigation-series plots (Plotly and Matplotlib).

    Uses shared generate_depth_plot and generate_manually_modified_depth_plot
    functions for all the heavy lifting.

    Args:
        parameter_mappings: DataFrame with csv_file, column_name, parameter columns
        plotly_unified_data: Formation-grouped data with Investigation column
        manually_modified_data: Formation-grouped data for manually modified plots
        config: Complete CONFIG dictionary
    """
    # Extract config values (orchestrator boundary)
    inv_series_config = config["investigation_series"]
    if not inv_series_config["enabled"]:
        logger.info("⏭️ Investigation-series plots disabled - skipping")
        return

    parameter_name = config["parameter"]["name"]
    parameter_display_name = config["parameter"]["display_name"]
    output_folder = config["parameter"]["output_base_folder"]
    output_control = config["output_control"]
    outlier_config = config["outlier_detection"]
    # For derived parameters, source_parameter is used for mapping lookups
    source_parameter = config["parameter"].get("source_parameter", parameter_name)

    all_formations = set(plotly_unified_data.keys()) | set(
        manually_modified_data.keys()
    )
    logger.info(f"🚀 Generating plots for {len(all_formations)} formations")

    # Setup output folders - Standard structure:
    # Output/{ParameterName}/
    #     data/               <- CSV exports
    #     html_interactive/   <- Plotly HTMLs
    #     manually_modified_png/  <- matplotlib PNGs
    param_output_folder = Path(output_folder) / parameter_name
    html_folder = param_output_folder / "html_interactive"
    manually_modified_folder = param_output_folder / "manually_modified_png"

    # Extract plotting config values
    investigation_colors = inv_series_config["investigation_colors"]
    csv_source_settings = config["csv_source_settings"]
    default_source_settings = config["default_source_settings"]
    force_circle_markers = inv_series_config["legend"]["force_circle_markers"]
    show_test_type_shapes = inv_series_config["legend"]["show_test_type_shapes"]

    # Extract density tracing config for CPT data
    density_tracing_config = config.get("density_tracing", None)

    plotly_count = 0
    matplotlib_count = 0

    # Collect all investigations for unified color mapping
    all_investigations: Set[str] = set()
    for formation_data in plotly_unified_data.values():
        for csv_data in formation_data.values():
            if "Investigation" in csv_data.columns:
                all_investigations.update(csv_data["Investigation"].unique())

    # Create unified color map for both Plotly and matplotlib
    investigation_color_map = create_investigation_color_mapping(
        list(all_investigations), investigation_colors
    )

    # ═══════════════════════════════════════════════════════════════════════
    # ⚡ PARALLEL PROCESSING BRANCH (Optional)
    # If parallel processing is enabled and available, attempt parallel execution.
    # On ANY failure, automatically fall back to sequential processing.
    # ═══════════════════════════════════════════════════════════════════════
    parallel_config = config.get("parallel_processing", {})
    use_parallel = (
        PARALLEL_AVAILABLE
        and parallel_config.get("enabled", False)
        and len(all_formations) >= parallel_config.get("min_formations_for_parallel", 3)
    )

    if use_parallel:
        try:
            logger.info("🚀 Attempting parallel plot generation...")
            output_paths = {
                "html_folder": html_folder,
                "png_folder": manually_modified_folder,
            }
            results, summary = run_parallel_formation_plots(
                manually_modified_data=manually_modified_data,
                plotly_unified_data=plotly_unified_data,
                parameter_mappings=parameter_mappings,
                config=config,
                output_paths=output_paths,
                investigation_color_map=investigation_color_map,
            )

            # Log any individual formation failures
            for r in results:
                if not r.get("success"):
                    logger.warning(
                        f"⚠️ {r['formation']}: {r.get('error', 'Unknown error')}"
                    )

            logger.info(
                f"✅ Parallel complete: {summary['successful']}/{summary['total_formations']} formations"
            )
            logger.info(
                f"✅ Generated {summary['plotly_generated']} Plotly plots, "
                f"{summary['matplotlib_generated']} matplotlib plots"
            )
            return  # Exit early - parallel handled everything

        except ParallelExecutionError as e:
            logger.info(f"⏭️ Falling back to sequential: {e}")
            # Fall through to sequential processing below
        except Exception as e:
            logger.warning(f"⚠️ Unexpected parallel error, falling back: {e}")
            # Fall through to sequential processing below

    # ═══════════════════════════════════════════════════════════════════════
    # 📊 SEQUENTIAL PROCESSING (Default path)
    # This is the original sequential loop - executes if:
    # - Parallel is disabled
    # - Parallel module not available
    # - Parallel execution failed
    # ═══════════════════════════════════════════════════════════════════════
    plotly_count = 0
    matplotlib_count = 0

    for formation_name in sorted(all_formations):
        # === PLOTLY HTML PLOTS ===
        plotly_count = _generate_plotly_plot_for_formation(
            formation_name=formation_name,
            plotly_unified_data=plotly_unified_data,
            parameter_mappings=parameter_mappings,
            parameter_name=parameter_name,
            source_parameter=source_parameter,
            parameter_display_name=parameter_display_name,
            html_folder=html_folder,
            investigation_color_map=investigation_color_map,
            csv_source_settings=csv_source_settings,
            default_source_settings=default_source_settings,
            force_circle_markers=force_circle_markers,
            output_control=output_control,
            plotly_count=plotly_count,
            # NOTE: density_tracing_config removed from Plotly - density lines are matplotlib only
        )

        # === MATPLOTLIB MANUALLY MODIFIED PLOTS ===
        matplotlib_count = _generate_matplotlib_plot_for_formation(
            formation_name=formation_name,
            manually_modified_data=manually_modified_data,
            parameter_mappings=parameter_mappings,
            parameter_name=parameter_name,
            source_parameter=source_parameter,
            parameter_display_name=parameter_display_name,
            manually_modified_folder=manually_modified_folder,
            investigation_color_map=investigation_color_map,
            csv_source_settings=csv_source_settings,
            output_control=output_control,
            matplotlib_count=matplotlib_count,
            show_test_type_legend=show_test_type_shapes,
            density_tracing_config=density_tracing_config,
        )

    logger.info(
        f"✅ Generated {plotly_count} Plotly plots, {matplotlib_count} matplotlib plots"
    )


def _generate_plotly_plot_for_formation(
    formation_name: str,
    plotly_unified_data: Dict[str, Dict[str, pd.DataFrame]],
    parameter_mappings: pd.DataFrame,
    parameter_name: str,
    source_parameter: str,
    parameter_display_name: str,
    html_folder: Path,
    investigation_color_map: Dict[str, str],
    csv_source_settings: Dict[str, Dict[str, Any]],
    default_source_settings: Dict[str, Any],
    force_circle_markers: bool,
    output_control: Dict[str, Any],
    plotly_count: int,
) -> int:
    """
    Generate Plotly HTML plot for a single formation.

    Args:
        formation_name: Name of geological formation
        plotly_unified_data: All formation data
        parameter_mappings: Parameter mapping DataFrame
        parameter_name: Internal parameter name (used for output folder/file naming)
        source_parameter: Source parameter name (used for mapping lookups)
        parameter_display_name: Display label for axes
        html_folder: Output folder for HTML files
        investigation_color_map: Colors per investigation
        csv_source_settings: Settings per CSV source
        default_source_settings: Default settings for unmapped sources
        force_circle_markers: Use circles in legend
        output_control: Output control config
        plotly_count: Current count of generated plots

    Returns:
        Updated plotly_count
    """
    if not _should_generate_plot(
        "investigation_series_plots_plotly_with_outliers", output_control
    ):
        return plotly_count

    plotly_data_for_formation = plotly_unified_data.get(formation_name, {})
    if plotly_data_for_formation:
        generate_depth_plot(
            formation_name=formation_name,
            plotly_data=plotly_data_for_formation,
            parameter_mappings=parameter_mappings,
            param_name=source_parameter,
            param_display_name=parameter_display_name,
            output_folder=html_folder,
            investigation_colors=investigation_color_map,
            csv_source_settings=csv_source_settings,
            default_source_settings=default_source_settings,
            force_circle_markers=force_circle_markers,
            mark_outliers=True,
            # NOTE: density_tracing_config removed - density lines are matplotlib only
        )
        plotly_count += 1

    return plotly_count


def _generate_matplotlib_plot_for_formation(
    formation_name: str,
    manually_modified_data: Dict[str, Dict[str, pd.DataFrame]],
    parameter_mappings: pd.DataFrame,
    parameter_name: str,
    source_parameter: str,
    parameter_display_name: str,
    manually_modified_folder: Path,
    investigation_color_map: Dict[str, str],
    csv_source_settings: Dict[str, Dict[str, Any]],
    output_control: Dict[str, Any],
    matplotlib_count: int,
    show_test_type_legend: bool = True,
    density_tracing_config: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Generate matplotlib PNG plot for a single formation.

    Args:
        formation_name: Name of geological formation
        manually_modified_data: Manually modified formation data
        parameter_mappings: Parameter mapping DataFrame
        parameter_name: Internal parameter name (used for output folder/file naming)
        source_parameter: Source parameter name (used for mapping lookups)
        parameter_display_name: Display label for axes
        manually_modified_folder: Output folder for PNG files
        investigation_color_map: Colors per investigation
        csv_source_settings: Settings per CSV source
        output_control: Output control config
        matplotlib_count: Current count of generated plots
        show_test_type_legend: Whether to show test type legend entries
        density_tracing_config: Configuration for CPT density line tracing

    Returns:
        Updated matplotlib_count
    """
    if not _should_generate_plot(
        "investigation_series_plots_manually_modified", output_control
    ):
        return matplotlib_count

    manually_modified_for_formation = manually_modified_data.get(formation_name, {})
    if not manually_modified_for_formation:
        return matplotlib_count

    # Prepare data structure for matplotlib function
    csv_data_with_investigations = {}
    for csv_name, df in manually_modified_for_formation.items():
        # Find parameter column from mappings (use source_parameter for lookup)
        param_mappings_filtered = parameter_mappings[
            (parameter_mappings["csv_file"] == csv_name)
            & (parameter_mappings["parameter"] == source_parameter)
        ]
        if not param_mappings_filtered.empty:
            param_column = param_mappings_filtered["column_name"].iloc[0]
            if param_column in df.columns:
                csv_data_with_investigations[csv_name] = {
                    "df": df,
                    "param_column": param_column,
                }

    if csv_data_with_investigations:
        generate_manually_modified_depth_plot(
            formation_name=formation_name,
            csv_data_with_investigations=csv_data_with_investigations,
            parameter_display_name=parameter_display_name,
            output_folder=manually_modified_folder,
            investigation_color_map=investigation_color_map,
            csv_source_settings=csv_source_settings,
            show_test_type_legend=show_test_type_legend,
            density_tracing_config=density_tracing_config,
        )
        matplotlib_count += 1

    return matplotlib_count


# ═══════════════════════════════════════════════════════════════════════════
# ⚡ MAIN PIPELINE ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════


def run_parameter_plotting_pipeline(config: Dict[str, Any]) -> bool:
    """
    Run the complete plotting pipeline for a geotechnical parameter.

    DEPRECATED: Use run_plotting_pipeline(config, plot_type="depth") instead.
    This function is retained for backwards compatibility.

    This orchestrator executes all phases:
    1. Parameter mapping extraction
    2. CSV data loading
    3. Formation grouping
    4. Outlier filtering
    5. Manual data control
    6. Unified data object creation
    7. Plot generation (Plotly + matplotlib)
    8. Investigation summary export
    9. Filtered data tracking

    Args:
        config: Complete CONFIG dictionary built from shared defaults

    Returns:
        True if pipeline completed successfully, False otherwise
    """
    # === CONFIGURATION EXTRACTION (Orchestrator Boundary) ===
    parameter_name = config["parameter"]["name"]
    # Support source_parameter for derived parameters (e.g., Eu uses Cu data)
    source_parameter = config["parameter"].get("source_parameter", parameter_name)
    mapping_csv = config["parameter"]["mapping_csv"]
    csv_source_folder = config["parameter"]["csv_source_folder"]
    output_folder = config["parameter"]["output_base_folder"]
    parameter_display_name = config["parameter"]["display_name"]

    logger.info("=" * 80)
    logger.info(f"🚀 {parameter_display_name} - Simplified Pipeline")
    logger.info("=" * 80)
    logger.info(f"📊 Parameter: {parameter_name}")
    if source_parameter != parameter_name:
        logger.info(f"📊 Source Parameter: {source_parameter}")
    logger.info(f"📁 CSV Source: {csv_source_folder}")
    logger.info(f"📁 Output: {output_folder}")

    try:
        # === PHASE 1: PARAMETER MAPPING EXTRACTION ===
        # Use source_parameter for mapping lookup (allows derived parameters)
        param_mappings = _execute_phase1_parameter_mapping(
            source_parameter, mapping_csv
        )
        if param_mappings is None:
            return False

        # === PHASE 2: CSV DATA LOADING ===
        csv_data_dict = _execute_phase2_csv_loading(
            param_mappings, csv_source_folder, config
        )
        if csv_data_dict is None:
            return False

        # === PHASE 3: FORMATION GROUPING ===
        formation_groups = _execute_phase3_formation_grouping(
            csv_data_dict, param_mappings
        )
        if formation_groups is None:
            return False

        # === PHASE 3a: SCRIPT-SPECIFIC FILTERING (Location + Test-Type Thresholds) ===
        # ═══════════════════════════════════════════════════════════════════════════
        # ⚠️ ALL DATA FILTERING MUST HAPPEN HERE, BEFORE UNIFIED DATA OBJECTS ⚠️
        # DO NOT add filtering to plotly_utils.py or matplotlib_utils.py!
        # See _execute_phase3a_script_specific_filtering() docstring for details.
        # ═══════════════════════════════════════════════════════════════════════════
        _execute_phase3a_script_specific_filtering(
            formation_groups, param_mappings, config
        )

        # === PHASE 3b: OUTLIER FILTERING ===
        _execute_phase3b_outlier_filtering(formation_groups, param_mappings, config)

        # === PHASE 3c: MANUAL DATA CONTROL ===
        # NOTE: Manual data control MUST happen BEFORE value transformation
        # so that removal matching uses original values (e.g., Cu) not transformed (Eu)
        # Use source_parameter for manual data sheet lookup (e.g., "UndrainedShearStrength")
        # For depth plots: y_column = "Top Depth" (default)
        apply_manual_data_control(
            formation_groups=formation_groups,
            param_mappings=param_mappings,
            parameter_name=source_parameter,
            config=config,
            x_column=None,  # Derived from param_mappings
            y_column="Top Depth",
        )

        # === PHASE 3-TRANSFORM: VALUE TRANSFORMATION (e.g., Cu → Eu) ===
        # Applied after manual data control so removal matching uses source values
        _execute_value_transformation(formation_groups, param_mappings, config)

        # === PHASE 4: CREATE UNIFIED DATA OBJECTS ===
        plotly_unified_data, manually_modified_data = _execute_phase4_unified_data(
            formation_groups, csv_source_folder, config
        )

        # === PHASE 4b: INVESTIGATION SERIES PLOT GENERATION ===
        logger.info("")
        logger.info("🎨 Phase 4b: Generating investigation-series plots...")
        _generate_investigation_series_plots(
            parameter_mappings=param_mappings,
            plotly_unified_data=plotly_unified_data,
            manually_modified_data=manually_modified_data,
            config=config,
        )
        logger.info("✅ Investigation-series plots complete")

        # === PHASE 5: INVESTIGATION TRACKING ===
        _execute_phase5_investigation_tracking(
            plotly_unified_data,
            param_mappings,
            parameter_name,
            csv_source_folder,
            config,
        )

        # === PHASE 6: FILTERED DATA TRACKING ===
        _execute_phase6_filtered_data_tracking(
            manually_modified_data,
            param_mappings,
            parameter_name,
            output_folder,
            config,
        )

        # === COMPLETE ===
        logger.info("")
        logger.info("=" * 80)
        logger.info("🎉 Pipeline complete!")
        logger.info("=" * 80)
        return True

    except Exception as e:
        logger.error(f"❌ Pipeline failed: {e}")
        raise


def _execute_phase1_parameter_mapping(
    parameter_name: str, mapping_csv: str
) -> Optional[pd.DataFrame]:
    """
    Execute Phase 1: Extract parameter mappings.

    Args:
        parameter_name: Parameter to extract mappings for
        mapping_csv: Path to mapping CSV file

    Returns:
        Parameter mappings DataFrame, or None if empty
    """
    logger.info("")
    logger.info("📋 Phase 1: Extracting parameter mappings...")
    param_mappings = extract_parameter_mappings(parameter_name, mapping_csv)

    if param_mappings.empty:
        logger.error(f"❌ No data sources found for '{parameter_name}'")
        return None

    logger.info(f"✅ Found {len(param_mappings)} data sources")
    return param_mappings


def _execute_phase2_csv_loading(
    param_mappings: pd.DataFrame,
    csv_source_folder: str,
    config: Dict[str, Any],
) -> Optional[Dict[str, pd.DataFrame]]:
    """
    Execute Phase 2: Load CSV data.

    Args:
        param_mappings: Parameter mappings from Phase 1
        csv_source_folder: Folder containing source CSVs
        config: Complete CONFIG dictionary

    Returns:
        Dictionary of loaded CSVs, or None if empty
    """
    logger.info("")
    logger.info("💾 Phase 2: Loading CSV data...")

    # Get list of CSV files to load
    csv_files = [
        Path(csv_source_folder) / row["csv_file"]
        for _, row in param_mappings.iterrows()
    ]

    csv_data_dict = load_csv_data(
        csv_files=csv_files,
        geology_code_descriptions=config["mappings"]["geology_code_descriptions"],
        column_variations=config["mappings"]["column_variations"],
        formation_splitting_config=config["mappings"]["formation_splitting"],
        filter_enabled=config["filtering"]["location_filter"]["enabled"],
        exclude_prefixes=config["filtering"]["location_filter"]["exclude_prefixes"],
        case_sensitive=config["filtering"]["location_filter"]["case_sensitive"],
        consolidation_filtering_config=config.get("consolidation_filtering"),
    )

    if not csv_data_dict:
        logger.error("❌ No CSV data loaded")
        return None

    logger.info(f"✅ Loaded {len(csv_data_dict)} CSV files")

    # === APPLY EMPIRICAL CALCULATIONS (e.g., SPT N to cu conversion) ===
    empirical_config = config.get("empirical_calculations")
    if empirical_config:
        # Use source_parameter for empirical calculations (supports derived parameters like Eu)
        # Stiffness Eu uses source_parameter="UndrainedShearStrength" to trigger SPT N→cu conversion
        parameter_name = config.get("parameter", {}).get("name", "Unknown")
        source_parameter = config["parameter"].get("source_parameter", parameter_name)
        f1_factors = empirical_config.get("spt_to_cu_factors")
        geology_codes = config["mappings"]["geology_code_descriptions"]

        logger.info(f"🔬 Applying empirical calculations for '{source_parameter}'...")
        for csv_name, df in csv_data_dict.items():
            # Find the column to transform from param_mappings
            matching_row = param_mappings[
                param_mappings["csv_file"].str.contains(
                    csv_name.replace(".csv", ""), case=False
                )
            ]
            if not matching_row.empty:
                column_name = matching_row.iloc[0]["column_name"]
                csv_data_dict[csv_name] = apply_empirical_calculations(
                    df_copy=df,
                    parameter_name=source_parameter,  # Use source_parameter, not derived name
                    csv_name=csv_name,
                    column_name=column_name,
                    f1_factor_config=f1_factors,
                    geology_code_descriptions=geology_codes,
                )
        logger.info("✅ Empirical calculations applied")

    return csv_data_dict


def _execute_phase3_formation_grouping(
    csv_data_dict: Dict[str, pd.DataFrame],
    param_mappings: pd.DataFrame,
) -> Optional[Dict[str, Dict[str, pd.DataFrame]]]:
    """
    Execute Phase 3: Group data by formation.

    For depth plots, delegates to group_data_by_formation_unified() with
    y_column="Top Depth".

    Args:
        csv_data_dict: Loaded CSV data
        param_mappings: Parameter mappings

    Returns:
        Formation groups dictionary, or None if empty
    """
    logger.info("")
    logger.info("🔄 Phase 3: Grouping data by formation...")

    # Use unified function with default y_column="Top Depth" for depth plots
    formation_groups = group_data_by_formation_unified(
        csv_data_dict=csv_data_dict,
        x_param_mappings=param_mappings,
        y_param_mappings=None,
        x_column=None,
        y_column="Top Depth",
    )

    if not formation_groups:
        logger.error("❌ No formation groups created")
        return None

    logger.info(f"✅ Created {len(formation_groups)} formation groups")
    return formation_groups


def _execute_value_transformation(
    formation_groups: Dict[str, Dict[str, pd.DataFrame]],
    param_mappings: pd.DataFrame,
    config: Dict[str, Any],
) -> None:
    """
    Execute Value Transformation phase: Apply value transformations (e.g., Cu → Eu).

    Transforms parameter values using formation-specific multipliers and unit conversion.
    Only runs if 'value_transformation' config is present and enabled.

    Args:
        formation_groups: Formation-grouped data (MODIFIED IN-PLACE)
        param_mappings: Parameter mappings
        config: Complete CONFIG dictionary
    """
    transformation_config = config.get("value_transformation")

    if not transformation_config:
        return

    if not transformation_config.get("enabled", True):
        return

    logger.info("")
    logger.info("🔄 Phase 3-Transform: Applying value transformation...")

    apply_value_transformation(
        formation_groups=formation_groups,
        parameter_mappings=param_mappings,
        transformation_config=transformation_config,
        geology_code_descriptions=config["mappings"]["geology_code_descriptions"],
    )


def _execute_phase3a_script_specific_filtering(
    formation_groups: Dict[str, Dict[str, pd.DataFrame]],
    param_mappings: pd.DataFrame,
    config: Dict[str, Any],
) -> None:
    """
    Execute Phase 3a: Script-Specific Filtering (ALL custom thresholds).

    ═══════════════════════════════════════════════════════════════════════════════
    ⚠️ CRITICAL ARCHITECTURAL REQUIREMENT - READ BEFORE MODIFYING ⚠️
    ═══════════════════════════════════════════════════════════════════════════════

    This phase applies ALL script-specific filtering BEFORE unified data objects
    are created. This is ESSENTIAL for the following reasons:

    1. COUNTS MATCH PLOTTED DATA: Investigation counts and test type counts are
       calculated from unified data objects. If filtering happens AFTER unification,
       counts will include filtered-out data points, causing user confusion.

    2. SINGLE SOURCE OF TRUTH: Unified data objects should be the single source of
       truth for all plotting and count calculations. ALL data filtering must be
       complete before these objects are created.

    3. NO DUPLICATE FILTERING: By filtering here, we avoid duplicating filter logic
       in plotly_utils.py and matplotlib_utils.py. One filter location = one bug fix.

    ═══════════════════════════════════════════════════════════════════════════════
    ❌ ANTI-PATTERN - NEVER ADD FILTERING TO PLOTTING UTILITIES ❌
    ═══════════════════════════════════════════════════════════════════════════════

    If you are tempted to add data filtering inside plotly_utils.py or
    matplotlib_utils.py, STOP and add it here instead. Filtering inside plotting
    functions causes count/plot mismatches because counts are calculated from
    unified data objects BEFORE the plotting functions are called.

    Example of what NOT to do:
    ```python
    # ❌ WRONG - Inside generate_depth_plot() or similar
    for inv_id in investigations:
        inv_data = df[df["Investigation"] == inv_id]
        if max_kpa := settings.get("max_kpa"):
            inv_data = inv_data[inv_data[param_col] <= max_kpa]  # TOO LATE!
        # Counts were already calculated before this loop...
    ```

    ═══════════════════════════════════════════════════════════════════════════════
    ✅ FILTERS APPLIED IN THIS PHASE:
    ═══════════════════════════════════════════════════════════════════════════════

    1. Formation-Specific Location Filtering
       - Excludes specific Location ID prefixes from specific formations
       - Config: CONFIG["filtering"]["location_filter"]["formation_specific_filters"]
       - Example: Exclude OS01/OS02 from KC_W and KC_UW formations

    2. Test-Type Threshold Filtering (max_kpa, min_kpa)
       - Applies test-type-specific parameter thresholds from CSV_SOURCE_SETTINGS
       - Config: CONFIG["csv_source_settings"]["<csv_name>"]["max_kpa"]
       - Example: Vane Tests max_kpa=129 filters unreliable hand vane readings

    3. Cell Pressure Threshold Filtering (XY plots only - handled in dual pipeline)
       - Filters data where X parameter exceeds threshold
       - Config: CONFIG["filtering"]["cell_pressure_threshold"]
       - Example: Remove consolidation data with Cell Pressure > 1500 kPa

    4. Formation Parameter Threshold Filtering (XY plots only - handled in dual pipeline)
       - Formation-specific parameter limits
       - Config: CONFIG["filtering"]["formation_parameter_thresholds"]
       - Example: KC_UW cv values > 5.0 m²/year

    ═══════════════════════════════════════════════════════════════════════════════

    Args:
        formation_groups: Formation-grouped data (MODIFIED IN-PLACE)
        param_mappings: Parameter mappings for finding column names
        config: Complete CONFIG dictionary
    """
    logger.info("")
    logger.info(
        "🔧 Phase 3a: Script-Specific Filtering (Location + Test-Type Thresholds)..."
    )

    # ─────────────────────────────────────────────────────────────────────────
    # FILTER 1: Formation-Specific Location Filtering
    # ─────────────────────────────────────────────────────────────────────────
    location_filter = config["filtering"]["location_filter"]
    formation_specific_filters = location_filter.get("formation_specific_filters")

    if formation_specific_filters:
        logger.info("  📍 Applying formation-specific location filters...")
        total_filtered = apply_formation_specific_filters(
            formation_groups=formation_groups,
            formation_specific_filters=formation_specific_filters,
            geology_code_descriptions=config["mappings"]["geology_code_descriptions"],
            case_sensitive=location_filter.get("case_sensitive", False),
        )
        if total_filtered > 0:
            logger.info(
                f"  ✅ Formation-specific location filtering: {total_filtered} rows removed"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # FILTER 2: Test-Type Threshold Filtering (max_kpa, min_kpa)
    # ─────────────────────────────────────────────────────────────────────────
    csv_source_settings = config.get("csv_source_settings", {})
    if csv_source_settings:
        # Check if any test type has threshold settings
        has_thresholds = any(
            settings.get("max_kpa") is not None or settings.get("min_kpa") is not None
            for settings in csv_source_settings.values()
        )
        if has_thresholds:
            logger.info("  📊 Applying test-type threshold filters...")
            apply_test_type_threshold_filtering(
                formation_groups=formation_groups,
                parameter_mappings=param_mappings,
                csv_source_settings=csv_source_settings,
            )

    logger.info("✅ Script-specific filtering complete")


def _execute_phase3b_outlier_filtering(
    formation_groups: Dict[str, Dict[str, pd.DataFrame]],
    param_mappings: pd.DataFrame,
    config: Dict[str, Any],
) -> None:
    """
    Execute Phase 3b: Apply outlier filtering.

    Args:
        formation_groups: Formation-grouped data (MODIFIED IN-PLACE)
        param_mappings: Parameter mappings
        config: Complete CONFIG dictionary
    """
    logger.info("")
    logger.info("🧹 Phase 3b: Applying outlier filtering...")
    outlier_config = config["outlier_detection"]
    iqr_settings = outlier_config["method_settings"]["standard_iqr"]

    filter_outliers_from_formations(
        formation_groups=formation_groups,
        parameter_mappings=param_mappings,
        enabled=outlier_config["enabled"],
        min_samples=outlier_config["min_samples_for_detection"],
        iqr_multiplier=iqr_settings["iqr_multiplier"],
        q1_boundary=iqr_settings["quartile_boundaries"]["q1"],
        q3_boundary=iqr_settings["quartile_boundaries"]["q3"],
    )
    logger.info("✅ Outlier filtering complete")


def resolve_manual_data_paths(config: Dict[str, Any]) -> Tuple[str, str]:
    """
    Resolve manual data file paths relative to workspace.

    Extracts path resolution logic that was duplicated in depth and XY versions.
    Resolves relative paths to absolute using workspace root (csv_source_folder parent).

    Args:
        config: Complete CONFIG dictionary

    Returns:
        Tuple of (excel_file_path, data_to_add_file_path) as absolute paths

    Replaces:
        - Path resolution block in _execute_phase3c_manual_data_control()
        - Path resolution block in _execute_dual_phase3c_manual_data_control()
    """
    manual_config = config.get("manual_outlier_exclusion", {})

    # Get csv_source_folder from config (works for both depth and dual-param configs)
    if "csv_source_folder" in config.get("parameter", {}):
        csv_source_folder = config["parameter"]["csv_source_folder"]
    else:
        csv_source_folder = config.get("csv_source_folder", "")

    csv_folder_path = Path(csv_source_folder)
    workspace_root = csv_folder_path.parent

    # Resolve excel_file path (Data to Remove.xlsx)
    excel_file_cfg = manual_config.get("excel_file", "Data to Remove.xlsx")
    excel_file_path = Path(excel_file_cfg)
    if not excel_file_path.is_absolute():
        excel_file = str(workspace_root / excel_file_cfg)
    else:
        excel_file = str(excel_file_path)

    # Resolve data_to_add_file path (Data to Add.xlsx)
    add_file_cfg = manual_config.get("data_to_add_file", "Data to Add.xlsx")
    add_file_path = Path(add_file_cfg)
    if not add_file_path.is_absolute():
        data_to_add_file = str(workspace_root / add_file_cfg)
    else:
        data_to_add_file = str(add_file_path)

    return excel_file, data_to_add_file


def apply_manual_data_control(
    formation_groups: Dict[str, Dict[str, pd.DataFrame]],
    param_mappings: pd.DataFrame,
    parameter_name: str,
    config: Dict[str, Any],
    x_column: Optional[str] = None,
    y_column: str = "Top Depth",
) -> None:
    """
    Unified manual data control for all plot types.

    For depth plots: y_column = "Top Depth" (default)
    For XY plots: y_column = y_parameter column name

    Replaces:
        - _execute_phase3c_manual_data_control()
        - _execute_dual_phase3c_manual_data_control()

    Args:
        formation_groups: Formation-grouped data (MODIFIED IN-PLACE)
        param_mappings: Parameter mappings (Y parameter for XY plots)
        parameter_name: Parameter name for sheet lookup (e.g., "MoistureContent")
        config: Complete CONFIG dictionary
        x_column: Explicit X column name. If None, derived from param_mappings.
                  For depth plots, this is the parameter column.
                  For XY plots, this is the X parameter column (e.g., "Cell Pressure").
        y_column: Y column name. Default "Top Depth" for depth plots.
                  For XY plots, pass the y_parameter column name.

    Side Effects:
        Modifies formation_groups in-place by adding:
        - 'is_manual_outlier' column
        - 'is_manual_addition' column
    """
    logger.info("")
    logger.info("📝 Phase 3c: Applying manual data control...")

    manual_config = config.get("manual_outlier_exclusion", {})
    if not manual_config.get("enabled", False):
        logger.info("⏭️ Manual data control disabled - skipping")
        # Still add False columns for consistency
        for csv_dict in formation_groups.values():
            for df in csv_dict.values():
                df["is_manual_outlier"] = False
                df["is_manual_addition"] = False
        return

    # === PATH RESOLUTION (uses shared helper) ===
    excel_file, data_to_add_file = resolve_manual_data_paths(config)

    # === LOAD AND MARK MANUAL OUTLIERS ===
    manual_outliers_df = load_manual_outliers(
        parameter_name=parameter_name,
        excel_file=excel_file,
        sheet_mapping=manual_config.get("sheets", {}),
        enabled=manual_config.get("enabled", False),
    )

    # Determine column names for marking
    # For depth plots: x_column = None (use param_mappings), y_column = "Top Depth"
    # For XY plots: x_column = X param column, y_column = Y param column
    mark_manual_outliers(
        formation_groups=formation_groups,
        manual_outliers_df=manual_outliers_df,
        parameter_mappings=param_mappings,
        param_tolerance=manual_config.get("match_tolerance", {}).get("parameter", 0.01),
        depth_tolerance=manual_config.get("match_tolerance", {}).get("depth", 0.01),
        x_column_name=x_column,
        y_column_name=y_column,
    )

    # === LOAD AND MARK MANUAL ADDITIONS ===
    _, manual_additions_df = load_manual_additions(
        parameter_name=parameter_name,
        excel_file=data_to_add_file,
        sheet_mapping=manual_config.get("sheets", {}),
        geology_code_descriptions=config.get("mappings", {}).get(
            "geology_code_descriptions", {}
        ),
        enabled=manual_config.get("enabled", False),
    )

    mark_manual_additions(
        formation_groups=formation_groups,
        manual_additions_df=manual_additions_df,
        parameter_mappings=param_mappings,
        param_tolerance=manual_config.get("match_tolerance", {}).get("parameter", 0.01),
        depth_tolerance=manual_config.get("match_tolerance", {}).get("depth", 0.01),
        x_column_name=x_column,
        y_column_name=y_column,
    )

    logger.info("✅ Manual data control complete")


def _execute_phase4_unified_data(
    formation_groups: Dict[str, Dict[str, pd.DataFrame]],
    csv_source_folder: str,
    config: Dict[str, Any],
) -> Tuple[Dict[str, Dict[str, pd.DataFrame]], Dict[str, Dict[str, pd.DataFrame]]]:
    """
    Execute Phase 4: Create unified data objects.

    Args:
        formation_groups: Formation-grouped data
        csv_source_folder: Folder containing source CSVs
        config: Complete CONFIG dictionary

    Returns:
        Tuple of (plotly_unified_data, manually_modified_data)
    """
    logger.info("")
    logger.info("📊 Phase 4: Preparing unified data objects...")

    inv_config = config["investigation_tracking"]
    location_details = load_location_details(
        csv_folder=csv_source_folder,
        location_csv_name=inv_config["location_details_csv"],
        location_id_variants=inv_config["per_investigation_plots"][
            "location_id_column_variants"
        ],
        investigation_variants=inv_config["per_investigation_plots"][
            "investigation_column_variants"
        ],
    )

    plotly_unified_data, manually_modified_data = prepare_unified_data_objects(
        formation_groups=formation_groups,
        location_details=location_details,
        fallback_investigation_name=inv_config["per_investigation_plots"][
            "fallback_investigation_name"
        ],
        csv_source_settings=config["csv_source_settings"],
        default_source_settings=config["default_source_settings"],
    )

    logger.info("✅ Unified data objects ready")
    return plotly_unified_data, manually_modified_data


def _execute_phase5_investigation_tracking(
    plotly_unified_data: Dict[str, Dict[str, pd.DataFrame]],
    param_mappings: pd.DataFrame,
    parameter_name: str,
    csv_source_folder: str,
    config: Dict[str, Any],
) -> None:
    """
    Execute Phase 5: Generate investigation summary.

    Args:
        plotly_unified_data: Unified data with Investigation column
        param_mappings: Parameter mappings
        parameter_name: Parameter being processed
        csv_source_folder: Folder containing source CSVs
        config: Complete CONFIG dictionary
    """
    output_control = config["output_control"]
    if not output_control.get("data", {}).get("investigation_summary_csv", True):
        return

    logger.info("")
    logger.info("📋 Phase 5: Generating investigation summary...")

    inv_config = config["investigation_tracking"]
    output_folder = config["parameter"]["output_base_folder"]
    parameter_output_folder = Path(output_folder) / parameter_name
    data_folder = parameter_output_folder / "data"

    generate_investigation_summary(
        grouped_by_formation=plotly_unified_data,
        parameter_mappings=param_mappings,
        parameter_name=parameter_name,
        csv_source_folder=csv_source_folder,
        location_details_csv_name=inv_config["location_details_csv"],
        data_folder=data_folder,
        output_control=output_control,
        enabled=inv_config["enabled"],
    )

    logger.info("✅ Investigation summary complete")


def _execute_phase6_filtered_data_tracking(
    manually_modified_data: Dict[str, Dict[str, pd.DataFrame]],
    param_mappings: pd.DataFrame,
    parameter_name: str,
    output_folder: str,
    config: Dict[str, Any],
) -> None:
    """
    Execute Phase 6: Generate filtered data tracking.

    Args:
        manually_modified_data: Data for tracking
        param_mappings: Parameter mappings
        parameter_name: Parameter being processed
        output_folder: Base output folder
        config: Complete CONFIG dictionary
    """
    output_control = config["output_control"]
    if not output_control.get("data", {}).get("filtered_data_summary_csv", True):
        return

    logger.info("")
    logger.info("📊 Phase 6: Generating filtered data tracking...")

    track_filtered_data(
        parameter_name=parameter_name,
        param_mappings=param_mappings,
        plotted_formation_groups=manually_modified_data,
        output_folder=Path(output_folder),
    )

    logger.info("✅ Filtered data tracking complete")


# ═══════════════════════════════════════════════════════════════════════════
# � UNIFIED PIPELINE ORCHESTRATOR
# Single entry point for all plot types (depth, xy, psd)
# ═══════════════════════════════════════════════════════════════════════════


def run_plotting_pipeline(config: Dict[str, Any], plot_type: str = "auto") -> bool:
    """
    Unified plotting pipeline for all plot types.

    This is the single entry point that handles depth plots, XY plots, and PSD plots
    by delegating to the appropriate specialized pipeline function. It uses
    get_axis_parameters() to extract plot-type-specific differences.

    Args:
        config: Complete CONFIG dictionary built from build_config_from_defaults()
                or build_dual_param_config_from_defaults()
        plot_type: One of:
            - "depth": Parameter vs Depth plots (e.g., Moisture Content, SPT)
            - "xy": Parameter vs Parameter plots (e.g., CV vs Cell Pressure)
            - "psd": Particle Size Distribution plots
            - "auto": Auto-detect from config structure (default)

    Returns:
        True if pipeline completed successfully, False otherwise

    Replaces:
        - Direct calls to run_parameter_plotting_pipeline()
        - Direct calls to run_dual_parameter_plotting_pipeline()
        - Direct calls to run_psd_plotting_pipeline()

    Example (depth plot):
        >>> from geotechnical_plotting import run_plotting_pipeline
        >>> CONFIG = build_config_from_defaults(
        ...     parameter_name="MoistureContent",
        ...     display_name="Moisture Content (%)",
        ...     csv_source_settings=CSV_SOURCE_SETTINGS,
        ... )
        >>> run_plotting_pipeline(CONFIG, plot_type="depth")

    Example (XY plot):
        >>> CONFIG = build_dual_param_config_from_defaults(
        ...     x_parameter_name="Cell Pressure",
        ...     y_parameter_name="CoefficientConsolidation",
        ...     x_display_name="Cell Pressure (kPa)",
        ...     y_display_name="cv (m²/year)",
        ...     output_folder_name="CVvsCellPressure",
        ...     csv_source_settings=CSV_SOURCE_SETTINGS,
        ... )
        >>> run_plotting_pipeline(CONFIG, plot_type="xy")

    Example (auto-detect):
        >>> # plot_type is auto-detected from config structure
        >>> run_plotting_pipeline(CONFIG)  # Works for any config type
    """
    # === AUTO-DETECT PLOT TYPE IF NOT SPECIFIED ===
    if plot_type == "auto":
        plot_type = _detect_plot_type(config)
        logger.info(f"🔍 Auto-detected plot type: {plot_type}")

    # === DELEGATE TO APPROPRIATE PIPELINE ===
    if plot_type == "depth":
        return run_parameter_plotting_pipeline(config)
    elif plot_type == "xy":
        return run_dual_parameter_plotting_pipeline(config)
    elif plot_type == "psd":
        run_psd_plotting_pipeline(config)
        return True
    else:
        logger.error(
            f"❌ Unknown plot_type: '{plot_type}'. "
            f"Valid options: 'depth', 'xy', 'psd', 'auto'"
        )
        return False


def _detect_plot_type(config: Dict[str, Any]) -> str:
    """
    Auto-detect plot type from CONFIG structure.

    Detection rules:
    - If config["parameter"]["is_dual_parameter"] is True → "xy"
    - If config["parameter"]["x_parameter"] exists → "xy"
    - If config["psd_settings"] exists → "psd"
    - Otherwise → "depth"

    Args:
        config: Complete CONFIG dictionary

    Returns:
        Plot type string: "depth", "xy", or "psd"
    """
    param_config = config.get("parameter", {})

    # Check for dual-parameter flag
    if param_config.get("is_dual_parameter", False):
        return "xy"

    # Check for x_parameter key (present in dual-param configs)
    if "x_parameter" in param_config:
        return "xy"

    # Check for PSD settings
    if "psd_settings" in config:
        return "psd"

    # Default to depth
    return "depth"


# ═══════════════════════════════════════════════════════════════════════════
# �🔧 AI CONTEXT RECOVERY
# ═══════════════════════════════════════════════════════════════════════════


def _ai_context_recovery_summary() -> str:
    """
    AI Context Recovery: Summary of this module's purpose and usage.

    Returns:
        str: Summary for AI navigation and comprehension
    """
    return """
    Plotting Pipeline Orchestration Module
    ======================================

    PURPOSE:
    Orchestrates complete plotting pipeline for any geotechnical parameter.
    Reduces each parameter script from ~600 lines to ~100 lines.

    MAIN ENTRY POINTS:
    - run_plotting_pipeline(config, plot_type) - UNIFIED entry point (recommended)
    - run_parameter_plotting_pipeline(config) - runs all phases for depth plots
    - run_dual_parameter_plotting_pipeline(config) - runs all phases for X vs Y plots
    - run_psd_plotting_pipeline(config) - runs all phases for PSD plots

    PHASES:
    1. Parameter mapping extraction
    2. CSV data loading
    3. Formation grouping
    4. Outlier filtering
    5. Manual data control
    6. Unified data object creation
    7. Plot generation (Plotly + matplotlib)
    8. Investigation summary export
    9. Filtered data tracking

    USAGE (RECOMMENDED - unified function):
    from geotechnical_plotting.orchestration import run_parameter_plotting_pipeline
    from geotechnical_plotting.config.shared_config import build_config_from_defaults

    CONFIG = build_config_from_defaults(...)
    run_parameter_plotting_pipeline(CONFIG)
    """


# ═══════════════════════════════════════════════════════════════════════════
# 📊 DUAL-PARAMETER (X vs Y) PIPELINE ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════


def run_dual_parameter_plotting_pipeline(config: Dict[str, Any]) -> bool:
    """
    Run the complete plotting pipeline for dual-parameter (X vs Y) plots.

    DEPRECATED: Use run_plotting_pipeline(config, plot_type="xy") instead.
    This function is retained for backwards compatibility.

    This orchestrator is for plots like CV vs Cell Pressure where one parameter
    is plotted against another (not vs depth).

    Executes all phases:
    1. Dual parameter mapping extraction (X and Y parameters)
    2. CSV data loading
    3. Formation grouping
    4. Outlier filtering
    5. Manual data control
    6. Unified data object creation
    7. Plot generation (Plotly X vs Y)
    8. Investigation summary export
    9. Filtered data tracking

    Args:
        config: Complete CONFIG dictionary built from build_dual_param_config_from_defaults

    Returns:
        True if pipeline completed successfully, False otherwise
    """
    # === CONFIGURATION EXTRACTION (Orchestrator Boundary) ===
    param_config = config["parameter"]
    x_parameter_name = param_config["x_parameter"]
    y_parameter_name = param_config["y_parameter"]
    x_display_name = param_config["x_display_name"]
    y_display_name = param_config["y_display_name"]
    output_folder_name = param_config["output_folder_name"]
    mapping_csv = param_config["mapping_csv"]
    csv_source_folder = param_config["csv_source_folder"]
    output_folder = param_config["output_base_folder"]

    logger.info("=" * 80)
    logger.info(f"🚀 {y_display_name} vs {x_display_name} - Dual-Parameter Pipeline")
    logger.info("=" * 80)
    logger.info(f"📊 X Parameter: {x_parameter_name}")
    logger.info(f"📊 Y Parameter: {y_parameter_name}")
    logger.info(f"📁 CSV Source: {csv_source_folder}")
    logger.info(f"📁 Output: {output_folder}")

    try:
        # === PHASE 1: DUAL PARAMETER MAPPING EXTRACTION ===
        x_param_mappings, y_param_mappings = _execute_dual_phase1_parameter_mapping(
            x_parameter_name, y_parameter_name, mapping_csv
        )
        if x_param_mappings is None or y_param_mappings is None:
            return False

        # Combine mappings for data loading (union of both parameters' CSVs)
        combined_mappings = _combine_dual_parameter_mappings(
            x_param_mappings, y_param_mappings
        )

        # === PHASE 2: CSV DATA LOADING ===
        csv_data_dict = _execute_phase2_csv_loading(
            combined_mappings, csv_source_folder, config
        )
        if csv_data_dict is None:
            return False

        # === PHASE 2b: ROW-LEVEL FALLBACK (for dual-parameter plots) ===
        _execute_dual_phase2b_row_level_fallback(
            csv_data_dict, x_param_mappings, y_param_mappings, config
        )

        # === PHASE 3: FORMATION GROUPING (dual-parameter mode) ===
        formation_groups = _execute_dual_phase3_formation_grouping(
            csv_data_dict, x_param_mappings, y_param_mappings
        )
        if formation_groups is None:
            return False

        # === PHASE 3a: THRESHOLD FILTERING (Cell Pressure + Formation-Specific) ===
        _execute_dual_phase3a_threshold_filtering(
            formation_groups, x_param_mappings, y_param_mappings, config
        )

        # === PHASE 3b: OUTLIER FILTERING (on Y parameter) ===
        _execute_dual_phase3b_outlier_filtering(
            formation_groups, y_param_mappings, config
        )

        # === PHASE 3c: MANUAL DATA CONTROL ===
        # For dual-parameter plots, get column names from mappings
        x_column_name = (
            x_param_mappings["column_name"].iloc[0]
            if not x_param_mappings.empty
            else None
        )
        y_column_name = (
            y_param_mappings["column_name"].iloc[0]
            if not y_param_mappings.empty
            else "Top Depth"
        )

        apply_manual_data_control(
            formation_groups=formation_groups,
            param_mappings=y_param_mappings,
            parameter_name=y_parameter_name,
            config=config,
            x_column=x_column_name,
            y_column=y_column_name,
        )

        # === PHASE 4: CREATE UNIFIED DATA OBJECTS ===
        plotly_unified_data = _execute_dual_phase4_unified_data(
            formation_groups, csv_source_folder, config
        )

        # === PHASE 4b: INVESTIGATION SERIES PLOT GENERATION ===
        logger.info("")
        logger.info("🎨 Phase 4b: Generating X vs Y investigation-series plots...")
        _generate_dual_param_investigation_series_plots(
            x_param_mappings=x_param_mappings,
            y_param_mappings=y_param_mappings,
            plotly_unified_data=plotly_unified_data,
            config=config,
        )
        logger.info("✅ Investigation-series plots complete")

        # === PHASE 5: INVESTIGATION TRACKING ===
        _execute_phase5_investigation_tracking(
            plotly_unified_data,
            y_param_mappings,  # Use Y parameter mappings for tracking
            output_folder_name,
            csv_source_folder,
            config,
        )

        # === PHASE 6: FILTERED DATA TRACKING ===
        _execute_phase6_filtered_data_tracking(
            plotly_unified_data,
            y_param_mappings,
            output_folder_name,
            output_folder,
            config,
        )

        # === COMPLETE ===
        logger.info("")
        logger.info("=" * 80)
        logger.info("🎉 Dual-parameter pipeline complete!")
        logger.info("=" * 80)
        return True

    except Exception as e:
        logger.error(f"❌ Dual-parameter pipeline failed: {e}")
        raise


def _execute_dual_phase1_parameter_mapping(
    x_parameter_name: str,
    y_parameter_name: str,
    mapping_csv: str,
) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """
    Execute Phase 1: Extract dual parameter mappings (X and Y).

    Args:
        x_parameter_name: X-axis parameter to extract mappings for
        y_parameter_name: Y-axis parameter to extract mappings for
        mapping_csv: Path to mapping CSV file

    Returns:
        Tuple of (x_param_mappings, y_param_mappings) DataFrames, or (None, None)
    """
    logger.info("")
    logger.info("📋 Phase 1: Extracting dual parameter mappings...")

    x_mappings = extract_parameter_mappings(x_parameter_name, mapping_csv)
    y_mappings = extract_parameter_mappings(y_parameter_name, mapping_csv)

    if x_mappings.empty:
        logger.error(f"❌ No data sources found for X parameter '{x_parameter_name}'")
        return None, None

    if y_mappings.empty:
        logger.error(f"❌ No data sources found for Y parameter '{y_parameter_name}'")
        return None, None

    logger.info(
        f"✅ Found {len(x_mappings)} X-axis sources, {len(y_mappings)} Y-axis sources"
    )
    return x_mappings, y_mappings


def _combine_dual_parameter_mappings(
    x_mappings: pd.DataFrame,
    y_mappings: pd.DataFrame,
) -> pd.DataFrame:
    """
    Combine X and Y parameter mappings for data loading.

    Args:
        x_mappings: X parameter mappings
        y_mappings: Y parameter mappings

    Returns:
        Combined mappings with unique CSV files
    """
    combined = pd.concat([x_mappings, y_mappings], ignore_index=True)
    # Keep only unique CSV files
    return combined.drop_duplicates(subset=["csv_file"])


def _execute_dual_phase2b_row_level_fallback(
    csv_data_dict: Dict[str, pd.DataFrame],
    x_param_mappings: pd.DataFrame,
    y_param_mappings: pd.DataFrame,
    config: Dict[str, Any],
) -> None:
    """
    Execute Phase 2b: Apply row-level fallback for parameters with multiple sources.

    For dual-parameter plots (e.g., CV vs Cell Pressure), this creates unified
    columns for parameters that have multiple source columns (e.g., primary cv
    column + backup cv column).

    Args:
        csv_data_dict: Loaded CSV data (MODIFIED IN-PLACE)
        x_param_mappings: X parameter mappings
        y_param_mappings: Y parameter mappings
        config: Complete CONFIG dictionary
    """
    logger.info("")
    logger.info("🔄 Phase 2b: Applying row-level fallback...")

    # Check if row-level fallback is configured
    row_level_fallback_config = config.get("parameter", {}).get(
        "row_level_fallback", {}
    )
    if not row_level_fallback_config.get("enabled", False):
        logger.info("⏭️ Row-level fallback disabled - skipping")
        return

    fallback_parameters = row_level_fallback_config.get("parameters", [])
    if not fallback_parameters:
        # Default: apply fallback to both X and Y parameters
        x_param_name = config["parameter"].get("x_parameter")
        y_param_name = config["parameter"].get("y_parameter")
        fallback_parameters = [p for p in [x_param_name, y_param_name] if p]

    # Combine mappings for fallback
    combined_mappings = pd.concat(
        [x_param_mappings, y_param_mappings], ignore_index=True
    )

    apply_row_level_fallback(
        csv_data_dict=csv_data_dict,
        parameter_mappings=combined_mappings,
        fallback_parameters=fallback_parameters,
    )
    logger.info("✅ Row-level fallback complete")


def _execute_dual_phase3_formation_grouping(
    csv_data_dict: Dict[str, pd.DataFrame],
    x_param_mappings: pd.DataFrame,
    y_param_mappings: pd.DataFrame,
) -> Optional[Dict[str, Dict[str, pd.DataFrame]]]:
    """
    Execute Phase 3: Group data by formation for dual parameters.

    Delegates to group_data_by_formation_unified() which handles both
    depth and XY plot types. For XY plots, only includes CSVs that have
    BOTH X and Y parameters.

    Args:
        csv_data_dict: Loaded CSV data
        x_param_mappings: X parameter mappings
        y_param_mappings: Y parameter mappings

    Returns:
        Formation groups dictionary, or None if empty
    """
    logger.info("")
    logger.info("🔄 Phase 3: Grouping data by formation (dual-parameter)...")

    # Find CSVs that have BOTH parameters
    x_csvs = set(x_param_mappings["csv_file"].unique())
    y_csvs = set(y_param_mappings["csv_file"].unique())
    common_csvs = x_csvs & y_csvs

    if not common_csvs:
        logger.error("❌ No CSVs contain both X and Y parameters")
        return None

    logger.info(f"📊 CSVs with both parameters: {common_csvs}")

    # Filter to only CSVs with both parameters
    filtered_csv_data = {
        csv_name: df
        for csv_name, df in csv_data_dict.items()
        if csv_name in common_csvs
    }

    # Get Y column name for unified function
    y_param_name = (
        y_param_mappings["parameter"].iloc[0] if not y_param_mappings.empty else None
    )

    # Use unified formation grouping with explicit Y column
    formation_groups = group_data_by_formation_unified(
        csv_data_dict=filtered_csv_data,
        x_param_mappings=x_param_mappings,
        y_param_mappings=y_param_mappings,
        x_column=None,  # Derived from mappings
        y_column=y_param_name if y_param_name else "Top Depth",
    )

    if not formation_groups:
        logger.error("❌ No formation groups created")
        return None

    logger.info(f"✅ Created {len(formation_groups)} formation groups")
    return formation_groups


def _execute_dual_phase3a_threshold_filtering(
    formation_groups: Dict[str, Dict[str, pd.DataFrame]],
    x_param_mappings: pd.DataFrame,
    y_param_mappings: pd.DataFrame,
    config: Dict[str, Any],
) -> None:
    """
    Execute Phase 3a: Apply threshold filtering (Cell Pressure + Formation-Specific).

    This phase applies two types of threshold filters:
    1. Cell Pressure Threshold: Removes data where X parameter exceeds max value
    2. Formation-Specific: Removes data where parameters exceed formation-specific limits

    Args:
        formation_groups: Formation-grouped data (MODIFIED IN-PLACE)
        x_param_mappings: X parameter mappings (for cell pressure filtering)
        y_param_mappings: Y parameter mappings (for formation-specific filtering)
        config: Complete CONFIG dictionary
    """
    logger.info("")
    logger.info("🔧 Phase 3a: Applying threshold filtering...")

    # Extract filtering configs
    filtering_config = config.get("filtering", {})
    cell_pressure_config = filtering_config.get("cell_pressure_threshold", {})
    formation_threshold_config = filtering_config.get(
        "formation_parameter_thresholds", {}
    )

    # Combine Y mappings with X mappings for formation-specific filtering
    combined_mappings = pd.concat(
        [x_param_mappings, y_param_mappings], ignore_index=True
    )

    # Apply cell pressure threshold filtering
    apply_cell_pressure_threshold_filtering(
        formation_groups, x_param_mappings, cell_pressure_config
    )

    # Apply formation-specific parameter threshold filtering
    apply_formation_parameter_threshold_filtering(
        formation_groups, combined_mappings, formation_threshold_config
    )

    logger.info("✅ Threshold filtering complete")


def _execute_dual_phase3b_outlier_filtering(
    formation_groups: Dict[str, Dict[str, pd.DataFrame]],
    y_param_mappings: pd.DataFrame,
    config: Dict[str, Any],
) -> None:
    """
    Execute Phase 3b: Apply outlier filtering (on Y parameter).

    Args:
        formation_groups: Formation-grouped data (MODIFIED IN-PLACE)
        y_param_mappings: Y parameter mappings
        config: Complete CONFIG dictionary
    """
    logger.info("")
    logger.info("🧹 Phase 3b: Applying outlier filtering (on Y parameter)...")
    outlier_config = config["outlier_detection"]
    iqr_settings = outlier_config["method_settings"]["standard_iqr"]

    filter_outliers_from_formations(
        formation_groups=formation_groups,
        parameter_mappings=y_param_mappings,
        enabled=outlier_config["enabled"],
        min_samples=outlier_config["min_samples_for_detection"],
        iqr_multiplier=iqr_settings["iqr_multiplier"],
        q1_boundary=iqr_settings["quartile_boundaries"]["q1"],
        q3_boundary=iqr_settings["quartile_boundaries"]["q3"],
    )
    logger.info("✅ Outlier filtering complete")


def _execute_dual_phase4_unified_data(
    formation_groups: Dict[str, Dict[str, pd.DataFrame]],
    csv_source_folder: str,
    config: Dict[str, Any],
) -> Dict[str, Dict[str, pd.DataFrame]]:
    """
    Execute Phase 4: Create unified data objects for dual-parameter plots.

    Args:
        formation_groups: Formation-grouped data
        csv_source_folder: Folder containing source CSVs
        config: Complete CONFIG dictionary

    Returns:
        plotly_unified_data with Investigation column
    """
    logger.info("")
    logger.info("📊 Phase 4: Preparing unified data objects...")

    inv_config = config["investigation_tracking"]
    location_details = load_location_details(
        csv_folder=csv_source_folder,
        location_csv_name=inv_config["location_details_csv"],
        location_id_variants=inv_config["per_investigation_plots"][
            "location_id_column_variants"
        ],
        investigation_variants=inv_config["per_investigation_plots"][
            "investigation_column_variants"
        ],
    )

    # For dual-parameter, we only need plotly_unified_data
    plotly_unified_data, _ = prepare_unified_data_objects(
        formation_groups=formation_groups,
        location_details=location_details,
        fallback_investigation_name=inv_config["per_investigation_plots"][
            "fallback_investigation_name"
        ],
        csv_source_settings=config["csv_source_settings"],
        default_source_settings=config["default_source_settings"],
    )

    logger.info("✅ Unified data objects ready")
    return plotly_unified_data


def _generate_dual_param_investigation_series_plots(
    x_param_mappings: pd.DataFrame,
    y_param_mappings: pd.DataFrame,
    plotly_unified_data: Dict[str, Dict[str, pd.DataFrame]],
    config: Dict[str, Any],
) -> None:
    """
    Orchestrate generation of dual-parameter (X vs Y) investigation-series plots.

    Generates both Plotly (HTML interactive) and matplotlib (PNG) plots.

    Args:
        x_param_mappings: X parameter mappings DataFrame
        y_param_mappings: Y parameter mappings DataFrame
        plotly_unified_data: Formation-grouped data with Investigation column
        config: Complete CONFIG dictionary
    """
    # Extract config values (orchestrator boundary)
    inv_series_config = config["investigation_series"]
    if not inv_series_config["enabled"]:
        logger.info("⏭️ Investigation-series plots disabled - skipping")
        return

    param_config = config["parameter"]
    x_parameter_name = param_config["x_parameter"]
    y_parameter_name = param_config["y_parameter"]
    x_display_name = param_config["x_display_name"]
    y_display_name = param_config["y_display_name"]
    output_folder_name = param_config["output_folder_name"]
    output_folder = param_config["output_base_folder"]
    output_control = config["output_control"]
    outlier_config = config["outlier_detection"]

    logger.info(f"🚀 Generating plots for {len(plotly_unified_data)} formations")

    # Setup output folders - Standard structure:
    # Output/{ParameterName}/
    #     data/               <- CSV exports
    #     html_interactive/   <- Plotly HTMLs
    #     manually_modified_png/  <- matplotlib PNGs
    param_output_folder = Path(output_folder) / output_folder_name
    html_folder = param_output_folder / "html_interactive"
    matplotlib_folder = param_output_folder / "manually_modified_png"

    # Extract plotting config values
    investigation_colors = inv_series_config["investigation_colors"]
    csv_source_settings = config["csv_source_settings"]
    default_source_settings = config["default_source_settings"]
    force_circle_markers = inv_series_config["legend"]["force_circle_markers"]
    show_test_type_shapes = inv_series_config["legend"]["show_test_type_shapes"]

    # Extract classification boundaries (for A-line plots, etc.)
    plotting_config = config.get("plotting", {})
    classification_boundaries = plotting_config.get("classification_boundaries")

    # Combine mappings for plot generation
    combined_mappings = pd.concat(
        [x_param_mappings, y_param_mappings], ignore_index=True
    )

    # Collect all investigations for unified color mapping
    all_investigations: Set[str] = set()
    for formation_data in plotly_unified_data.values():
        for csv_data in formation_data.values():
            if "Investigation" in csv_data.columns:
                all_investigations.update(csv_data["Investigation"].unique())

    # Create unified color map
    investigation_color_map = create_investigation_color_mapping(
        list(all_investigations), investigation_colors
    )

    plotly_count = 0
    matplotlib_count = 0

    for formation_name in sorted(plotly_unified_data.keys()):
        plotly_data_for_formation = plotly_unified_data.get(formation_name, {})
        if not plotly_data_for_formation:
            continue

        # === GENERATE PLOTLY HTML PLOT ===
        if _should_generate_plot(
            "investigation_series_plots_plotly_with_outliers", output_control
        ):
            generate_xy_plot(
                formation_name=formation_name,
                plotly_data=plotly_data_for_formation,
                parameter_mappings=combined_mappings,
                x_param_name=x_parameter_name,
                y_param_name=y_parameter_name,
                x_display_name=x_display_name,
                y_display_name=y_display_name,
                output_folder=html_folder,
                investigation_colors=investigation_color_map,
                csv_source_settings=csv_source_settings,
                default_source_settings=default_source_settings,
                force_circle_markers=force_circle_markers,
                mark_outliers=True,
                classification_boundaries=classification_boundaries,
            )
            plotly_count += 1

        # === GENERATE MATPLOTLIB PNG PLOT ===
        if _should_generate_plot(
            "investigation_series_plots_manually_modified", output_control
        ):
            # Prepare data structure for matplotlib function
            matplotlib_data = _prepare_matplotlib_xy_data(
                plotly_data_for_formation,
                combined_mappings,
                x_parameter_name,
                y_parameter_name,
            )

            if matplotlib_data:
                generate_matplotlib_xy_plot(
                    formation_name=formation_name,
                    csv_data_with_investigations=matplotlib_data,
                    x_display_name=x_display_name,
                    y_display_name=y_display_name,
                    output_folder=matplotlib_folder,
                    investigation_color_map=investigation_color_map,
                    csv_source_settings=csv_source_settings,
                    filter_column="is_manual_outlier",
                    include_manual_additions=True,
                    show_test_type_legend=show_test_type_shapes,
                    classification_boundaries=classification_boundaries,
                )
                matplotlib_count += 1

    logger.info(
        f"✅ Generated {plotly_count} Plotly plots, {matplotlib_count} matplotlib plots"
    )


def _prepare_matplotlib_xy_data(
    plotly_data: Dict[str, pd.DataFrame],
    parameter_mappings: pd.DataFrame,
    x_param_name: str,
    y_param_name: str,
) -> Dict[str, Dict[str, Any]]:
    """
    Prepare data structure for matplotlib X vs Y plotting.

    Args:
        plotly_data: Dict mapping CSV names to DataFrames
        parameter_mappings: DataFrame with csv_file, column_name, parameter columns
        x_param_name: X parameter name
        y_param_name: Y parameter name

    Returns:
        Dict mapping CSV names to {"df": DataFrame, "x_column": str, "y_column": str}
    """
    matplotlib_data = {}

    for csv_name, df in plotly_data.items():
        # Find X parameter column for this CSV
        x_mappings = parameter_mappings[
            (parameter_mappings["csv_file"] == csv_name)
            & (parameter_mappings["parameter"] == x_param_name)
        ]
        # Find Y parameter column for this CSV
        y_mappings = parameter_mappings[
            (parameter_mappings["csv_file"] == csv_name)
            & (parameter_mappings["parameter"] == y_param_name)
        ]

        if x_mappings.empty or y_mappings.empty:
            continue

        # Check for unified columns first (created by row-level fallback)
        # This is critical for parameters with multiple source columns
        x_unified = f"{x_param_name}_unified"
        y_unified = f"{y_param_name}_unified"

        x_column = (
            x_unified if x_unified in df.columns else x_mappings["column_name"].iloc[0]
        )
        y_column = (
            y_unified if y_unified in df.columns else y_mappings["column_name"].iloc[0]
        )

        if x_column not in df.columns or y_column not in df.columns:
            continue

        matplotlib_data[csv_name] = {
            "df": df,
            "x_column": x_column,
            "y_column": y_column,
        }

    return matplotlib_data


# ═══════════════════════════════════════════════════════════════════════════
# 📈 PSD (PARTICLE SIZE DISTRIBUTION) PIPELINE
# Specialized pipeline for line-based PSD plots
# ═══════════════════════════════════════════════════════════════════════════


def run_psd_plotting_pipeline(config: Dict[str, Any]) -> None:
    """
    Execute complete PSD plotting pipeline.

    DEPRECATED: Use run_plotting_pipeline(config, plot_type="psd") instead.
    This function is retained for backwards compatibility.

    PSD requires specialized handling because:
    - Line plots (not scatter plots) connecting particle sizes
    - Log scale X-axis for particle size (0.001 to 200 mm)
    - Data grouped by sample (Location ID + Sample Reference)
    - Optional averaging per investigation
    - Particle classification bands (Clay, Silt, Sand, Gravel, Cobbles)

    Args:
        config: Complete CONFIG dictionary with PSD-specific settings

    Phases:
        1. Extract parameter mappings for PSD data
        2. Load CSV data with formation grouping
        3. Prepare PSD data with sample identifiers
        4. Generate Plotly HTML and matplotlib PNG plots
        5. Generate investigation summary CSV
    """
    # === EXTRACT CONFIGURATION ===
    # Parameter section contains paths
    param_config = config.get("parameter", {})
    parameter_name = param_config.get("name", "ParticleSizeDistribution")
    display_name = param_config.get("display_name", "Particle Size Distribution")
    mapping_csv = param_config.get("mapping_csv", "")
    csv_source_folder = param_config.get("csv_source_folder", "")
    output_base_folder = param_config.get("output_base_folder", "")
    # Use parameter_name as default output folder name
    output_folder_name = param_config.get("output_folder_name", parameter_name)

    csv_source_settings = config.get("csv_source_settings", {})
    default_source_settings = config.get("default_source_settings", {})
    output_control = config.get("output_control", {})

    # PSD-specific settings
    psd_settings = config.get("psd_settings", {})
    average_by_investigation = psd_settings.get("average_by_investigation", True)
    data_columns = psd_settings.get("data_columns", {})
    particle_size_column = data_columns.get("particle_size", "Particle Size")
    percentage_passing_column = data_columns.get(
        "percentage_passing", "Percentage Passing"
    )
    sample_reference_column = data_columns.get("sample_reference", "Sample Reference")

    # Investigation series settings
    investigation_series_config = config.get("investigation_series", {})
    investigation_colors = investigation_series_config.get(
        "investigation_colors",
        [
            "#1f77b4",
            "#ff7f0e",
            "#2ca02c",
            "#d62728",
            "#9467bd",
            "#8c564b",
            "#e377c2",
            "#7f7f7f",
            "#bcbd22",
            "#17becf",
        ],
    )

    # Plotting settings
    plotting_config = config.get("plotting", {})
    axes_config = plotting_config.get("axes", {})
    x_limit_left = axes_config.get("x_limit_left", 0.001)
    x_limit_right = axes_config.get("x_limit_right", 200)
    y_limit_bottom = axes_config.get("y_limit_bottom", 0)
    y_limit_top = axes_config.get("y_limit_top", 105)

    # Particle classification settings
    particle_classification = config.get("particle_classification", {})
    show_classification_legend = particle_classification.get("enabled", True)

    # === OUTPUT FOLDER SETUP ===
    # Standard folder structure:
    # Output/{ParameterName}/
    #     data/               <- CSV exports
    #     html_interactive/   <- Plotly HTMLs
    #     manually_modified_png/  <- matplotlib PNGs
    output_base = Path(output_base_folder)
    output_folder = output_base / output_folder_name

    html_folder = output_folder / "html_interactive"
    matplotlib_folder = output_folder / "manually_modified_png"

    html_folder.mkdir(parents=True, exist_ok=True)
    matplotlib_folder.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 80)
    logger.info(f"🚀 {display_name} - PSD Pipeline")
    logger.info("=" * 80)
    logger.info(f"📊 Parameter: {parameter_name}")
    logger.info(f"📁 CSV Source: {csv_source_folder}")
    logger.info(f"📁 Output: {output_base_folder}")
    logger.info("")

    # === PHASE 1: EXTRACT PARAMETER MAPPINGS ===
    logger.info("📋 Phase 1: Extracting PSD parameter mappings...")
    psd_mappings = extract_parameter_mappings(parameter_name, mapping_csv)

    if psd_mappings.empty:
        logger.error(f"❌ No mappings found for parameter: {parameter_name}")
        return

    logger.info(f"✅ Found {len(psd_mappings)} CSV sources for '{parameter_name}'")
    logger.info("")

    # === PHASE 2: LOAD CSV DATA ===
    logger.info("💾 Phase 2: Loading CSV data...")

    # Get list of CSV files to load
    csv_files = [
        Path(csv_source_folder) / row["csv_file"] for _, row in psd_mappings.iterrows()
    ]

    csv_dict = load_csv_data(
        csv_files=csv_files,
        geology_code_descriptions=config["mappings"]["geology_code_descriptions"],
        column_variations=config["mappings"]["column_variations"],
        formation_splitting_config=config["mappings"]["formation_splitting"],
        filter_enabled=config["filtering"]["location_filter"]["enabled"],
        exclude_prefixes=config["filtering"]["location_filter"]["exclude_prefixes"],
        case_sensitive=config["filtering"]["location_filter"]["case_sensitive"],
    )

    if not csv_dict:
        logger.error("❌ No CSV data loaded")
        return

    logger.info(f"✅ Loaded {len(csv_dict)} CSV files")
    logger.info("")

    # === PHASE 3: GROUP BY FORMATION ===
    logger.info("🔄 Phase 3: Grouping data by formation...")
    # Use unified formation grouping with default y_column="Top Depth" for PSD
    formation_data = group_data_by_formation_unified(
        csv_data_dict=csv_dict,
        x_param_mappings=psd_mappings,
        y_param_mappings=None,
        x_column=None,  # Derived from psd_mappings
        y_column="Top Depth",
    )

    if not formation_data:
        logger.error("❌ No formation groups created")
        return

    logger.info(f"✅ Created {len(formation_data)} formation groups")
    logger.info("")

    # === PHASE 3b: ADD INVESTIGATION COLUMN ===
    logger.info("📊 Phase 3b: Adding investigation column...")
    inv_config = config.get("investigation_tracking", {})
    location_details = load_location_details(
        csv_folder=csv_source_folder,
        location_csv_name=inv_config.get(
            "location_details_csv", "Location Details.csv"
        ),
        location_id_variants=inv_config.get("per_investigation_plots", {}).get(
            "location_id_column_variants",
            ["Location ID", "LocID", "LocationID", "Hole ID", "HoleID"],
        ),
        investigation_variants=inv_config.get("per_investigation_plots", {}).get(
            "investigation_column_variants",
            ["Investigation", "Investigation Name", "Project"],
        ),
    )

    # Add Investigation column to all formation data
    fallback_name = inv_config.get("per_investigation_plots", {}).get(
        "fallback_investigation_name", "Unknown Investigation"
    )
    for formation_name, csv_dict_for_formation in formation_data.items():
        for csv_name, df in csv_dict_for_formation.items():
            df_with_inv = add_investigation_column(df, location_details, fallback_name)
            formation_data[formation_name][csv_name] = df_with_inv

    logger.info("✅ Investigation column added")
    logger.info("")

    # === PHASE 3c: MANUAL DATA MANAGEMENT ===
    manual_config = config.get("manual_outlier_exclusion", {})
    manual_enabled = manual_config.get("enabled", False)

    if manual_enabled:
        logger.info("🏷️ Phase 3c: Manual data management...")

        # Get manual outlier configuration
        from pathlib import Path as PathLib

        # Build path relative to workspace root
        # The CSV source folder is typically in the workspace root, so use its parent
        csv_folder_path = PathLib(csv_source_folder)
        workspace_root = csv_folder_path.parent

        # Get excel file path - could be absolute or relative
        excel_file_cfg = manual_config.get("excel_file", "Data to Remove.xlsx")
        excel_file_path = PathLib(excel_file_cfg)

        # If relative, make absolute from workspace root
        if not excel_file_path.is_absolute():
            excel_file = str(workspace_root / excel_file_cfg)
        else:
            excel_file = str(excel_file_path)

        sheet_mapping = manual_config.get("sheets", {})
        depth_tolerance = manual_config.get("match_tolerance", {}).get("depth", 1e-5)

        # Load manual outliers (PSD-specific)
        manual_outliers_df = load_manual_outliers_psd(
            parameter_name=parameter_name,
            excel_file=excel_file,
            sheet_mapping=sheet_mapping,
            enabled=manual_enabled,
        )

        # Mark manual outliers (PSD-specific)
        mark_manual_outliers_psd(
            formation_groups=formation_data,
            manual_outliers_df=manual_outliers_df,
            depth_tolerance=depth_tolerance,
        )

        logger.info("✅ Manual data management complete")
        logger.info("")
    else:
        logger.info("⏭️ Manual data management disabled - skipping")
        logger.info("")

    # === PHASE 4: GENERATE PSD PLOTS ===
    logger.info("🎨 Phase 4: Generating PSD plots...")

    # Collect all investigations for unified color mapping
    all_investigations: Set[str] = set()
    for formation_name, csv_data in formation_data.items():
        for csv_name, df in csv_data.items():
            if "Investigation" in df.columns:
                all_investigations.update(df["Investigation"].unique())

    investigation_color_map = create_investigation_color_mapping(
        list(all_investigations), investigation_colors
    )

    plotly_count = 0
    matplotlib_count = 0

    for formation_name in sorted(formation_data.keys()):
        csv_data = formation_data[formation_name]

        # Combine all CSV data for this formation
        all_dfs = []
        for csv_name, df in csv_data.items():
            if (
                particle_size_column in df.columns
                and percentage_passing_column in df.columns
            ):
                df_copy = df.copy()
                # Create sample identifier using Location ID + Top Depth
                # This matches the monolith behavior where each unique sample
                # is identified by its location and depth, not sample reference
                df_copy["Sample_ID"] = df_copy.apply(
                    lambda row: _create_sample_identifier(
                        row.get("Location ID", "UNK"), row.get("Top Depth")
                    ),
                    axis=1,
                )
                all_dfs.append(df_copy)

        if not all_dfs:
            continue

        combined_df = pd.concat(all_dfs, ignore_index=True)

        # Create filtered version for manually_modified plots (exclude manual outliers)
        if "is_manual_outlier" in combined_df.columns:
            filtered_df = combined_df[~combined_df["is_manual_outlier"]].copy()
        else:
            filtered_df = combined_df.copy()

        # === GENERATE PLOTLY HTML PLOT (with all data) ===
        if _should_generate_plot(
            "investigation_series_plots_plotly_with_outliers", output_control
        ):
            generate_plotly_psd_plot(
                formation_name=formation_name,
                psd_data=combined_df,
                output_folder=html_folder,
                investigation_color_map=investigation_color_map,
                particle_size_column=particle_size_column,
                percentage_passing_column=percentage_passing_column,
                sample_id_column="Sample_ID",
                average_by_investigation=average_by_investigation,
                x_limit_left=x_limit_left,
                x_limit_right=x_limit_right,
                y_limit_bottom=y_limit_bottom,
                y_limit_top=y_limit_top,
            )
            plotly_count += 1

        # === GENERATE MATPLOTLIB PNG PLOT (filtered - manual outliers excluded) ===
        if _should_generate_plot(
            "investigation_series_plots_manually_modified", output_control
        ):
            generate_matplotlib_psd_plot(
                formation_name=formation_name,
                psd_data=filtered_df,
                output_folder=matplotlib_folder,
                investigation_color_map=investigation_color_map,
                particle_size_column=particle_size_column,
                percentage_passing_column=percentage_passing_column,
                sample_id_column="Sample_ID",
                average_by_investigation=average_by_investigation,
                show_classification_legend=show_classification_legend,
                x_limit_left=x_limit_left,
                x_limit_right=x_limit_right,
                y_limit_bottom=y_limit_bottom,
                y_limit_top=y_limit_top,
            )
            matplotlib_count += 1

    logger.info(
        f"✅ Generated {plotly_count} Plotly plots, {matplotlib_count} matplotlib plots"
    )
    logger.info("")

    # === PHASE 5: INVESTIGATION SUMMARY CSV ===
    if output_control.get("data", {}).get("investigation_summary_csv", True):
        logger.info("📋 Phase 5: Generating investigation summary CSV...")
        data_folder = output_folder / "data"
        data_folder.mkdir(parents=True, exist_ok=True)

        generate_investigation_summary(
            grouped_by_formation=formation_data,
            parameter_mappings=psd_mappings,
            parameter_name=parameter_name,
            csv_source_folder=csv_source_folder,
            location_details_csv_name=inv_config.get(
                "location_details_csv", "Location Details.csv"
            ),
            data_folder=data_folder,
            output_control=output_control,
            enabled=inv_config.get("enabled", True),
        )
        logger.info("✅ Investigation summary complete")
        logger.info("")
    else:
        logger.info("⏭️ Investigation summary CSV disabled - skipping")
        logger.info("")

    # === PHASE 6: FILTERED DATA TRACKING CSV ===
    if output_control.get("data", {}).get("filtered_data_summary_csv", True):
        logger.info("📊 Phase 6: Generating filtered data tracking CSV...")

        track_filtered_data(
            parameter_name=parameter_name,
            param_mappings=psd_mappings,
            plotted_formation_groups=formation_data,
            output_folder=output_base,  # Use base folder, not parameter-specific folder
        )
        logger.info("✅ Filtered data tracking complete")
        logger.info("")
    else:
        logger.info("⏭️ Filtered data tracking CSV disabled - skipping")
        logger.info("")

    logger.info("=" * 80)
    logger.info("🎉 PSD pipeline complete!")
    logger.info("=" * 80)
