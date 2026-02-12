#!/usr/bin/env python3
"""
Parallel Worker Module
======================

This module contains the worker function that runs in a SEPARATE PROCESS.
It is completely stateless and isolated from the main process.

ARCHITECTURAL OVERVIEW:

Responsibility:
Execute plot generation for a single formation in complete isolation.
Each worker runs in its own process with its own matplotlib state.

Key Interactions:
- Input: Serialized formation data (records, columns, config)
- Processing: Reconstruct DataFrames, call plotting functions
- Output: Result dictionary with success/failure and paths

Navigation Guide:
- worker_generate_formation_plots(): Main worker entry point
- _generate_plotly_for_formation(): Generate Plotly HTML
- _generate_matplotlib_for_formation(): Generate matplotlib PNG
- _build_plot_data_structures(): Prepare data for plotting functions
- _reconstruct_dataframe(): Rebuild DataFrame from serialized records
- _setup_worker_logging(): Configure logging for worker process

CRITICAL SAFETY RULES:
1. matplotlib.use('Agg') MUST be called BEFORE any matplotlib import
2. All data must be passed as serializable primitives or dicts
3. No global state - everything passed as parameters
4. Returns dict only - no complex objects
5. Always call plt.close('all') to release memory

This module can be safely deleted without affecting sequential operation.
"""

from typing import Dict, Any, List, Tuple
import logging
import time
import os

# NOTE: matplotlib imports are INSIDE the worker function
# This ensures each process has its own matplotlib state


def _setup_worker_logging(worker_id: str) -> logging.Logger:
    """
    Configure logging for a worker process.

    Args:
        worker_id: Unique identifier for this worker

    Returns:
        Configured logger for the worker
    """
    logger = logging.getLogger(f"parallel.{worker_id}")

    # Only add handler if not already present (avoid duplicates)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            f"[%(asctime)s] [{worker_id}] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger


def _reconstruct_dataframe(
    records: List[Dict[str, Any]],
    columns: List[str],
) -> "pd.DataFrame":  # type: ignore
    """
    Reconstruct a pandas DataFrame from serialized records.

    Args:
        records: List of row dictionaries (from df.to_dict('records'))
        columns: Column names for the DataFrame

    Returns:
        Reconstructed pandas DataFrame
    """
    import pandas as pd

    if not records:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(records)

    # Ensure column order matches original
    if columns:
        # Only use columns that exist in records
        existing_cols = [c for c in columns if c in df.columns]
        df = df[existing_cols]

    return df


def _build_plot_data_structures(
    df_formation: "pd.DataFrame",  # type: ignore
    csv_source_info: Dict[str, str],
    formation_name: str,
    logger: logging.Logger,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, "pd.DataFrame"]]:  # type: ignore
    """
    Build data structures required by plotting functions.

    Args:
        df_formation: Combined formation DataFrame
        csv_source_info: Dict mapping csv_name -> param_column
        formation_name: Name of formation (for logging)
        logger: Logger instance

    Returns:
        Tuple of (csv_data_with_investigations, plotly_data)
    """
    csv_data_with_investigations: Dict[str, Dict[str, Any]] = {}
    plotly_data: Dict[str, Any] = {}

    for csv_name, param_column in csv_source_info.items():
        if param_column not in df_formation.columns:
            logger.warning(
                "[%s] Column '%s' not found for %s",
                formation_name,
                param_column,
                csv_name,
            )
            continue

        # Filter data for this CSV source
        if "csv_source" in df_formation.columns:
            csv_df = df_formation[df_formation["csv_source"] == csv_name].copy()
        else:
            csv_df = df_formation.copy()

        if len(csv_df) == 0:
            continue

        # For matplotlib - needs param_column info
        csv_data_with_investigations[csv_name] = {
            "df": csv_df,
            "param_column": param_column,
        }

        # For Plotly - just the DataFrame
        plotly_data[csv_name] = csv_df

    return csv_data_with_investigations, plotly_data


def _build_separate_plot_data_structures(
    df_plotly: "pd.DataFrame",  # type: ignore
    df_matplotlib: "pd.DataFrame",  # type: ignore
    csv_source_info: Dict[str, str],
    formation_name: str,
    logger: logging.Logger,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, "pd.DataFrame"]]:  # type: ignore
    """
    Build SEPARATE data structures for Plotly and matplotlib.

    CRITICAL FIX: Uses different source DataFrames for each plot type:
    - df_plotly: Contains ALL points (including outliers marked)
    - df_matplotlib: Contains filtered points (outliers removed)

    This ensures Plotly shows all data with outliers visually marked,
    while matplotlib shows the "manually modified" cleaned dataset.

    Args:
        df_plotly: DataFrame for Plotly (all points)
        df_matplotlib: DataFrame for matplotlib (filtered)
        csv_source_info: Dict mapping csv_name -> param_column
        formation_name: Name of formation (for logging)
        logger: Logger instance

    Returns:
        Tuple of (csv_data_with_investigations for matplotlib, plotly_data)
    """
    csv_data_with_investigations: Dict[str, Dict[str, Any]] = {}
    plotly_data: Dict[str, Any] = {}

    for csv_name, param_column in csv_source_info.items():
        # Process Plotly data (all points)
        if param_column in df_plotly.columns:
            if "csv_source" in df_plotly.columns:
                plotly_csv_df = df_plotly[df_plotly["csv_source"] == csv_name].copy()
            else:
                plotly_csv_df = df_plotly.copy()

            if len(plotly_csv_df) > 0:
                plotly_data[csv_name] = plotly_csv_df
        else:
            logger.warning(
                "[%s] Plotly: Column '%s' not found for %s",
                formation_name,
                param_column,
                csv_name,
            )

        # Process matplotlib data (filtered - outliers removed)
        if param_column in df_matplotlib.columns:
            if "csv_source" in df_matplotlib.columns:
                matplotlib_csv_df = df_matplotlib[
                    df_matplotlib["csv_source"] == csv_name
                ].copy()
            else:
                matplotlib_csv_df = df_matplotlib.copy()

            if len(matplotlib_csv_df) > 0:
                csv_data_with_investigations[csv_name] = {
                    "df": matplotlib_csv_df,
                    "param_column": param_column,
                }
        else:
            logger.warning(
                "[%s] matplotlib: Column '%s' not found for %s",
                formation_name,
                param_column,
                csv_name,
            )

    return csv_data_with_investigations, plotly_data


def _generate_plotly_for_formation(
    formation_name: str,
    plotly_data: Dict[str, "pd.DataFrame"],  # type: ignore
    param_mappings: "pd.DataFrame",  # type: ignore
    config: Dict[str, Any],
    html_folder: "Path",  # type: ignore
    investigation_color_map: Dict[str, str],
    logger: logging.Logger,
) -> Tuple[bool, str, str]:
    """
    Generate Plotly HTML plot for a formation.

    Args:
        formation_name: Name of formation
        plotly_data: Dict mapping csv_name -> DataFrame
        param_mappings: Parameter mappings DataFrame
        config: Serializable config dictionary
        html_folder: Output folder path
        investigation_color_map: Color mapping
        logger: Logger instance

    Returns:
        Tuple of (success, path_or_empty, error_or_empty)
    """
    try:
        from geotechnical_plotting.plotting_utils.plotly_utils import (
            generate_depth_plot as generate_plotly_depth_plot,
        )

        html_folder.mkdir(parents=True, exist_ok=True)

        generate_plotly_depth_plot(
            formation_name=formation_name,
            plotly_data=plotly_data,
            parameter_mappings=param_mappings,
            param_name=config.get("source_parameter", "Parameter"),
            param_display_name=config.get("parameter_display_name", "Parameter"),
            output_folder=html_folder,
            investigation_colors=investigation_color_map,
            csv_source_settings=config.get("csv_source_settings", {}),
            default_source_settings=config.get("default_source_settings", {}),
            force_circle_markers=config.get("force_circle_markers", True),
            mark_outliers=True,
        )

        logger.info("✅ [%s] Plotly HTML generated", formation_name)
        return True, str(html_folder / f"{formation_name}.html"), ""

    except Exception as e:  # pylint: disable=broad-except
        logger.error("❌ [%s] Plotly generation failed: %s", formation_name, e)
        return False, "", f"Plotly failed: {str(e)}"


def _generate_matplotlib_for_formation(
    formation_name: str,
    csv_data_with_investigations: Dict[str, Dict[str, Any]],
    config: Dict[str, Any],
    png_folder: "Path",  # type: ignore
    investigation_color_map: Dict[str, str],
    logger: logging.Logger,
) -> Tuple[bool, str, str]:
    """
    Generate matplotlib PNG plot for a formation.

    Args:
        formation_name: Name of formation
        csv_data_with_investigations: Data structure for matplotlib
        config: Serializable config dictionary
        png_folder: Output folder path
        investigation_color_map: Color mapping
        logger: Logger instance

    Returns:
        Tuple of (success, path_or_empty, error_or_empty)
    """
    try:
        from geotechnical_plotting.plotting_utils.matplotlib_utils import (
            generate_manually_modified_depth_plot,
        )

        png_folder.mkdir(parents=True, exist_ok=True)

        generate_manually_modified_depth_plot(
            formation_name=formation_name,
            csv_data_with_investigations=csv_data_with_investigations,
            parameter_display_name=config.get("parameter_display_name", "Parameter"),
            output_folder=png_folder,
            investigation_color_map=investigation_color_map,
            csv_source_settings=config.get("csv_source_settings", {}),
            show_test_type_legend=config.get("show_test_type_legend", True),
            density_tracing_config=config.get("density_tracing_config", None),
        )

        # Import plt for cleanup
        import matplotlib.pyplot as plt

        plt.close("all")

        logger.info("✅ [%s] matplotlib PNG generated", formation_name)
        return True, str(png_folder / f"{formation_name}.png"), ""

    except Exception as e:  # pylint: disable=broad-except
        logger.error("❌ [%s] matplotlib generation failed: %s", formation_name, e)
        return False, "", f"matplotlib failed: {str(e)}"


def worker_generate_formation_plots(
    formation_name: str,
    formation_records: List[Dict[str, Any]],
    formation_columns: List[str],
    parameter_mappings_records: List[Dict[str, Any]],
    parameter_mappings_columns: List[str],
    config_serializable: Dict[str, Any],
    output_paths: Dict[str, str],
    investigation_color_map: Dict[str, str],
    csv_source_info: Dict[str, str],
    # New parameters for separate Plotly/matplotlib data
    plotly_records: List[Dict[str, Any]] = None,
    plotly_columns: List[str] = None,
    matplotlib_records: List[Dict[str, Any]] = None,
    matplotlib_columns: List[str] = None,
) -> Dict[str, Any]:
    """
    Worker function to generate plots for a single formation in a separate process.

    CRITICAL FIX: Now accepts SEPARATE plotly and matplotlib data to ensure:
    - Plotly gets ALL points (including outliers marked for visual distinction)
    - matplotlib gets filtered data (outliers removed per manual modifications)

    Args:
        formation_name: Name of geological formation
        formation_records: Legacy combined data (for backwards compatibility)
        formation_columns: Legacy combined columns
        parameter_mappings_records: Serialized parameter mappings
        parameter_mappings_columns: Parameter mapping column names
        config_serializable: Pickle-safe config dictionary
        output_paths: Dict with html_folder and png_folder paths
        investigation_color_map: Investigation -> color mapping
        csv_source_info: CSV name -> parameter column mapping
        plotly_records: Plotly-specific data records (all points)
        plotly_columns: Plotly-specific column names
        matplotlib_records: matplotlib-specific data records (filtered)
        matplotlib_columns: matplotlib-specific column names

    Returns dict with: formation, success, matplotlib_path, plotly_path,
    error, duration_seconds, worker_id, matplotlib_generated, plotly_generated.
    """
    start_time = time.time()

    # CRITICAL: Set matplotlib backend BEFORE any imports
    import matplotlib

    matplotlib.use("Agg")
    from pathlib import Path

    worker_id = f"worker-{os.getpid()}"
    logger = _setup_worker_logging(worker_id)
    result = _init_result_dict(formation_name, worker_id)

    try:
        logger.info("🚀 [%s] Starting plot generation", formation_name)

        # Use separate datasets if provided, otherwise fall back to legacy combined data
        use_plotly_records = (
            plotly_records if plotly_records is not None else formation_records
        )
        use_plotly_columns = (
            plotly_columns if plotly_columns is not None else formation_columns
        )
        use_matplotlib_records = (
            matplotlib_records if matplotlib_records is not None else formation_records
        )
        use_matplotlib_columns = (
            matplotlib_columns if matplotlib_columns is not None else formation_columns
        )

        # Reconstruct DataFrames for each plot type
        df_plotly = _reconstruct_dataframe(use_plotly_records, use_plotly_columns)
        df_matplotlib = _reconstruct_dataframe(
            use_matplotlib_records, use_matplotlib_columns
        )

        param_mappings = _reconstruct_dataframe(
            parameter_mappings_records, parameter_mappings_columns
        )

        logger.info(
            "📊 [%s] Reconstructed: Plotly=%d rows, matplotlib=%d rows, %d sources",
            formation_name,
            len(df_plotly),
            len(df_matplotlib),
            len(csv_source_info),
        )

        # Build separate data structures for Plotly and matplotlib
        csv_data_matplotlib, plotly_data = _build_separate_plot_data_structures(
            df_plotly, df_matplotlib, csv_source_info, formation_name, logger
        )

        if not csv_data_matplotlib and not plotly_data:
            result["error"] = "No valid data after reconstruction"
            result["duration_seconds"] = time.time() - start_time
            return result

        html_folder = Path(output_paths["html_folder"])
        png_folder = Path(output_paths["png_folder"])

        _execute_plot_generation(
            result,
            formation_name,
            plotly_data,
            csv_data_matplotlib,
            param_mappings,
            config_serializable,
            html_folder,
            png_folder,
            investigation_color_map,
            logger,
        )

    except Exception as e:  # pylint: disable=broad-except
        import traceback

        result["error"] = f"{str(e)}\n{traceback.format_exc()}"
        logger.error("❌ [%s] Failed: %s", formation_name, e)
        _cleanup_matplotlib()

    result["duration_seconds"] = time.time() - start_time
    return result


def _init_result_dict(formation_name: str, worker_id: str) -> Dict[str, Any]:
    """Initialize the result dictionary with default values."""
    return {
        "formation": formation_name,
        "success": False,
        "matplotlib_path": None,
        "plotly_path": None,
        "error": None,
        "duration_seconds": 0,
        "worker_id": worker_id,
        "matplotlib_generated": False,
        "plotly_generated": False,
    }


def _execute_plot_generation(
    result: Dict[str, Any],
    formation_name: str,
    plotly_data: Dict[str, Any],
    csv_data: Dict[str, Dict[str, Any]],
    param_mappings: "pd.DataFrame",  # type: ignore
    config: Dict[str, Any],
    html_folder: "Path",  # type: ignore
    png_folder: "Path",  # type: ignore
    investigation_color_map: Dict[str, str],
    logger: logging.Logger,
) -> None:
    """Execute both Plotly and matplotlib plot generation."""
    errors = []

    # Generate Plotly
    if config.get("generate_plotly", True) and plotly_data:
        success, path, error = _generate_plotly_for_formation(
            formation_name,
            plotly_data,
            param_mappings,
            config,
            html_folder,
            investigation_color_map,
            logger,
        )
        result["plotly_generated"] = success
        if path:
            result["plotly_path"] = path
        if error:
            errors.append(error)

    # Generate matplotlib
    if config.get("generate_matplotlib", True) and csv_data:
        success, path, error = _generate_matplotlib_for_formation(
            formation_name,
            csv_data,
            config,
            png_folder,
            investigation_color_map,
            logger,
        )
        result["matplotlib_generated"] = success
        if path:
            result["matplotlib_path"] = path
        if error:
            errors.append(error)

    # Compile results
    result["success"] = result["plotly_generated"] or result["matplotlib_generated"]
    if errors:
        result["error"] = "; ".join(errors)

    if result["success"]:
        logger.info("✅ [%s] Complete", formation_name)
    else:
        logger.warning("⚠️ [%s] No plots generated", formation_name)


def _cleanup_matplotlib() -> None:
    """Safely cleanup matplotlib resources."""
    try:
        import matplotlib.pyplot as plt

        plt.close("all")
    except Exception:  # pylint: disable=broad-except
        pass


# ═══════════════════════════════════════════════════════════════════════════
# 📦 MODULE EXPORTS
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    "worker_generate_formation_plots",
]
