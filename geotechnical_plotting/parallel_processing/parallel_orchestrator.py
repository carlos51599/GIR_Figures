#!/usr/bin/env python3
"""
Parallel Orchestrator Module
============================

High-level orchestration of parallel formation processing.
Handles data serialization, job dispatch, and result collection.

ARCHITECTURAL OVERVIEW:

Responsibility:
Coordinates parallel plot generation across multiple formations.
Prepares serializable data, dispatches joblib workers, collects results.

Key Interactions:
- Input: Formation data dicts, parameter mappings, config
- Processing: Serialize → Dispatch parallel jobs → Collect results
- Output: List of results + summary statistics

Navigation Guide:
- run_parallel_formation_plots(): Main entry point
- _prepare_serializable_tasks(): Convert data for workers
- _extract_serializable_config(): Pickle-safe config extraction
- _compile_parallel_summary(): Aggregate results statistics

AUTOMATIC FALLBACK:
If ANY parallel error occurs, this module raises ParallelExecutionError.
The caller (orchestrator.py) catches this and falls back to sequential.

This module can be safely deleted without affecting sequential operation.
"""

from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
import logging
import time
import copy

import pandas as pd

from .parallel_config import (
    should_use_parallel,
    get_effective_worker_count,
    get_parallel_config,
)
from .parallel_worker import worker_generate_formation_plots

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# 🚨 EXCEPTION CLASS
# ═══════════════════════════════════════════════════════════════════════════


class ParallelExecutionError(Exception):
    """
    Raised when parallel execution fails and fallback to sequential is needed.

    This exception is caught by the orchestrator to trigger automatic
    fallback to sequential processing. It should NOT be raised for
    recoverable errors - only for situations where parallel execution
    cannot continue.

    Attributes:
        message: Human-readable error description
        original_exception: The underlying exception that caused the failure
    """

    def __init__(
        self,
        message: str,
        original_exception: Optional[Exception] = None,
    ) -> None:
        """
        Initialize ParallelExecutionError.

        Args:
            message: Human-readable error description
            original_exception: The underlying exception (if any)
        """
        super().__init__(message)
        self.message = message
        self.original_exception = original_exception

    def __str__(self) -> str:
        """Return string representation of the error."""
        if self.original_exception:
            return f"{self.message} (caused by: {self.original_exception})"
        return self.message


# ═══════════════════════════════════════════════════════════════════════════
# 🔧 LOGGING HELPERS
# ═══════════════════════════════════════════════════════════════════════════


def _log_parallel_start(
    num_formations: int,
    worker_count: int,
    backend: str,
) -> None:
    """Log parallel processing start banner."""
    logger.info("=" * 60)
    logger.info("🚀 PARALLEL PROCESSING ENABLED")
    logger.info("   Formations: %d", num_formations)
    logger.info("   Workers: %d", worker_count)
    logger.info("   Backend: %s", backend)
    logger.info("=" * 60)


def _log_parallel_complete(summary: Dict[str, Any], duration: float) -> None:
    """Log parallel processing completion banner."""
    logger.info("=" * 60)
    logger.info("✅ PARALLEL PROCESSING COMPLETE")
    logger.info(
        "   Successful: %d/%d", summary["successful"], summary["total_formations"]
    )
    logger.info("   Plotly generated: %d", summary["plotly_generated"])
    logger.info("   matplotlib generated: %d", summary["matplotlib_generated"])
    logger.info("   Duration: %.1fs", duration)
    logger.info("   Est. Speedup: %.1fx", summary["parallel_speedup_estimate"])
    logger.info("=" * 60)


def _execute_parallel_jobs(
    serialized_tasks: List[Dict[str, Any]],
    worker_count: int,
    p_config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Execute parallel jobs using joblib.

    Args:
        serialized_tasks: List of task dicts for workers
        worker_count: Number of workers to use
        p_config: Parallel configuration

    Returns:
        List of result dicts from workers
    """
    from joblib import Parallel, delayed

    return Parallel(
        n_jobs=worker_count,
        backend=p_config.get("backend", "loky"),
        verbose=p_config.get("verbose", 10),
        timeout=p_config.get("timeout_per_formation_seconds", 300),
    )(delayed(worker_generate_formation_plots)(**task) for task in serialized_tasks)


# ═══════════════════════════════════════════════════════════════════════════
# 📊 MAIN ORCHESTRATION FUNCTION
# ═══════════════════════════════════════════════════════════════════════════


def run_parallel_formation_plots(
    manually_modified_data: Dict[str, Dict[str, pd.DataFrame]],
    plotly_unified_data: Dict[str, Dict[str, pd.DataFrame]],
    parameter_mappings: pd.DataFrame,
    config: Dict[str, Any],
    output_paths: Dict[str, Path],
    investigation_color_map: Dict[str, str],
    parallel_config: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Execute parallel plot generation for all formations.

    Args:
        manually_modified_data: {formation_name: {csv_name: DataFrame}}
        plotly_unified_data: {formation_name: {csv_name: DataFrame}}
        parameter_mappings: Parameter mapping DataFrame
        config: Complete CONFIG dictionary
        output_paths: Dict with 'html_folder', 'png_folder' Path objects
        investigation_color_map: Pre-computed investigation -> color mapping
        parallel_config: Override parallel settings (optional)

    Returns:
        Tuple of (results list, summary dict)

    Raises:
        ParallelExecutionError: If parallel fails and fallback_on_error is True
    """
    p_config = parallel_config or get_parallel_config(config)

    all_formations = set(manually_modified_data.keys()) | set(
        plotly_unified_data.keys()
    )
    num_formations = len(all_formations)

    # Pre-flight validation
    should_parallel, reason = should_use_parallel(num_formations, p_config)
    if not should_parallel:
        logger.info("⏭️ Skipping parallel: %s", reason)
        raise ParallelExecutionError(reason)

    worker_count = get_effective_worker_count(num_formations, p_config)
    _log_parallel_start(num_formations, worker_count, p_config.get("backend", "loky"))

    start_time = time.time()

    try:
        serialized_tasks = _prepare_serializable_tasks(
            manually_modified_data,
            plotly_unified_data,
            parameter_mappings,
            config,
            output_paths,
            investigation_color_map,
        )
        logger.info("📦 Prepared %d serialized tasks", len(serialized_tasks))

        results = _execute_parallel_jobs(serialized_tasks, worker_count, p_config)

    except Exception as e:  # pylint: disable=broad-except
        logger.error("❌ Parallel execution failed: %s", e)
        if p_config.get("fallback_on_error", True):
            raise ParallelExecutionError(f"Parallel failed: {e}", e) from e
        raise

    total_duration = time.time() - start_time
    summary = _compile_parallel_summary(results, total_duration, worker_count)
    _log_parallel_complete(summary, total_duration)

    return results, summary


# ═══════════════════════════════════════════════════════════════════════════
# 📦 DATA SERIALIZATION
# ═══════════════════════════════════════════════════════════════════════════


def _serialize_formation_data(
    combined_data: Dict[str, pd.DataFrame],
    parameter_mappings: pd.DataFrame,
    source_parameter: str,
) -> Tuple[List[Dict[str, Any]], List[str], Dict[str, str]]:
    """
    Serialize a single formation's data for worker consumption.

    CRITICAL FIX: Different CSVs have different column names for the same
    parameter (e.g., "Moisture Content" vs "Initial MC" vs "NMC"). We must
    collect ALL columns from ALL CSVs to preserve each CSV's unique columns.

    Returns:
        Tuple of (all_records, columns, csv_source_info)
    """
    all_records: List[Dict[str, Any]] = []
    all_columns_set: set = set()  # Use a set to collect unique columns from ALL CSVs
    csv_source_info: Dict[str, str] = {}

    for csv_name, df in combined_data.items():
        # Collect ALL columns from this CSV (each CSV may have different columns)
        all_columns_set.update(df.columns.tolist())

        df_with_source = df.copy()
        df_with_source["csv_source"] = csv_name
        all_records.extend(df_with_source.to_dict("records"))

        param_mapping = parameter_mappings[
            (parameter_mappings["csv_file"] == csv_name)
            & (parameter_mappings["parameter"] == source_parameter)
        ]
        if not param_mapping.empty:
            csv_source_info[csv_name] = param_mapping["column_name"].iloc[0]

    # Convert set to sorted list for deterministic ordering
    columns = sorted(list(all_columns_set))

    # Ensure csv_source is included
    if "csv_source" not in columns:
        columns.append("csv_source")

    return all_records, columns, csv_source_info


def _prepare_serializable_tasks(
    manually_modified_data: Dict[str, Dict[str, pd.DataFrame]],
    plotly_unified_data: Dict[str, Dict[str, pd.DataFrame]],
    parameter_mappings: pd.DataFrame,
    config: Dict[str, Any],
    output_paths: Dict[str, Path],
    investigation_color_map: Dict[str, str],
) -> List[Dict[str, Any]]:
    """
    Convert formation data to pickle-safe dictionaries for workers.

    CRITICAL FIX: Serializes BOTH plotly_unified_data AND manually_modified_data
    separately to ensure Plotly gets all points (including outliers marked) while
    matplotlib gets filtered data (outliers removed). Previously only one combined
    dataset was used, causing point count discrepancies.
    """
    tasks: List[Dict[str, Any]] = []

    param_mappings_records = parameter_mappings.to_dict("records")
    param_mappings_columns = list(parameter_mappings.columns)
    config_serializable = _extract_serializable_config(config)

    parameter_name = config["parameter"]["name"]
    source_parameter = config["parameter"].get("source_parameter", parameter_name)

    all_formations = set(manually_modified_data.keys()) | set(
        plotly_unified_data.keys()
    )

    for formation_name in sorted(all_formations):
        matplotlib_data = manually_modified_data.get(formation_name, {})
        plotly_data = plotly_unified_data.get(formation_name, {})

        if not matplotlib_data and not plotly_data:
            continue

        # Serialize BOTH datasets separately - this is the critical fix
        # Plotly needs ALL points (including outliers marked)
        # matplotlib needs filtered data (outliers removed)
        plotly_records, plotly_columns, plotly_csv_info = (
            _serialize_formation_data(plotly_data, parameter_mappings, source_parameter)
            if plotly_data
            else ([], [], {})
        )

        matplotlib_records, matplotlib_columns, matplotlib_csv_info = (
            _serialize_formation_data(
                matplotlib_data, parameter_mappings, source_parameter
            )
            if matplotlib_data
            else ([], [], {})
        )

        # Use plotly_csv_info as primary (has all CSVs), fall back to matplotlib
        csv_source_info = plotly_csv_info or matplotlib_csv_info

        task = {
            "formation_name": formation_name,
            # Plotly data (all points including outliers marked)
            "plotly_records": plotly_records,
            "plotly_columns": plotly_columns,
            # matplotlib data (outliers removed)
            "matplotlib_records": matplotlib_records,
            "matplotlib_columns": matplotlib_columns,
            # Legacy field for backwards compatibility - remove after verification
            "formation_records": plotly_records or matplotlib_records,
            "formation_columns": plotly_columns or matplotlib_columns,
            "parameter_mappings_records": param_mappings_records,
            "parameter_mappings_columns": param_mappings_columns,
            "config_serializable": config_serializable,
            "output_paths": {
                "html_folder": str(output_paths.get("html_folder", "")),
                "png_folder": str(output_paths.get("png_folder", "")),
            },
            "investigation_color_map": dict(investigation_color_map),
            "csv_source_info": csv_source_info,
        }
        tasks.append(task)

    return tasks


def _get_minimal_safe_config() -> Dict[str, Any]:
    """Return minimal fallback config when serialization fails."""
    return {
        "parameter_name": "Parameter",
        "parameter_display_name": "Parameter Value",
        "source_parameter": "Parameter",
        "csv_source_settings": {},
        "default_source_settings": {},
        "show_test_type_legend": True,
        "force_circle_markers": True,
        "density_tracing_config": None,
        "generate_plotly": True,
        "generate_matplotlib": True,
    }


def _extract_serializable_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract pickle-safe config items for worker processes."""
    import pickle

    parameter_config = config.get("parameter", {})
    inv_series_config = config.get("investigation_series", {})
    output_control = config.get("output_control", {})

    safe_config = {
        "parameter_name": parameter_config.get("name", "Parameter"),
        "parameter_display_name": parameter_config.get(
            "display_name", "Parameter Value"
        ),
        "source_parameter": parameter_config.get(
            "source_parameter", parameter_config.get("name", "Parameter")
        ),
        "csv_source_settings": {},
        "default_source_settings": config.get("default_source_settings", {}),
        "show_test_type_legend": inv_series_config.get("legend", {}).get(
            "show_test_type_shapes", True
        ),
        "force_circle_markers": inv_series_config.get("legend", {}).get(
            "force_circle_markers", True
        ),
        "density_tracing_config": config.get("density_tracing", None),
        "generate_plotly": _should_generate_plotly(output_control),
        "generate_matplotlib": _should_generate_matplotlib(output_control),
    }

    # Safely extract csv_source_settings
    for csv_name, settings in config.get("csv_source_settings", {}).items():
        try:
            safe_settings = copy.deepcopy(settings)
            pickle.dumps(safe_settings)
            safe_config["csv_source_settings"][csv_name] = safe_settings
        except Exception:  # pylint: disable=broad-except
            logger.debug("Skipping non-serializable settings for %s", csv_name)

    try:
        pickle.dumps(safe_config)
    except Exception:  # pylint: disable=broad-except
        logger.warning("Config serialization issue, using minimal config")
        return _get_minimal_safe_config()

    return safe_config


def _should_generate_plotly(output_control: Dict[str, Any]) -> bool:
    """Check if Plotly HTML plots should be generated."""
    if not output_control.get("enabled", True):
        return False
    if not output_control.get("plots", {}).get("enabled", True):
        return False
    return output_control.get("plots", {}).get(
        "investigation_series_plots_plotly_with_outliers", True
    )


def _should_generate_matplotlib(output_control: Dict[str, Any]) -> bool:
    """Check if matplotlib PNG plots should be generated."""
    if not output_control.get("enabled", True):
        return False
    if not output_control.get("plots", {}).get("enabled", True):
        return False
    return output_control.get("plots", {}).get(
        "investigation_series_plots_manually_modified", True
    )


# ═══════════════════════════════════════════════════════════════════════════
# 📊 RESULT COMPILATION
# ═══════════════════════════════════════════════════════════════════════════


def _compile_parallel_summary(
    results: List[Dict[str, Any]],
    parallel_duration: float,
    workers_used: int,
) -> Dict[str, Any]:
    """
    Compile summary statistics from parallel execution results.

    Args:
        results: List of result dicts from workers
        parallel_duration: Total parallel execution time
        workers_used: Number of workers that were used

    Returns:
        Summary dictionary with aggregated statistics
    """
    total_formations = len(results)
    successful = sum(1 for r in results if r.get("success", False))
    failed = total_formations - successful

    plotly_generated = sum(1 for r in results if r.get("plotly_generated", False))
    matplotlib_generated = sum(
        1 for r in results if r.get("matplotlib_generated", False)
    )

    # Estimate what sequential time would have been
    sequential_estimate = sum(r.get("duration_seconds", 0) for r in results)

    # Calculate speedup
    if parallel_duration > 0:
        speedup = sequential_estimate / parallel_duration
    else:
        speedup = 1.0

    # Collect any errors
    errors = [
        {"formation": r["formation"], "error": r["error"]}
        for r in results
        if r.get("error")
    ]

    return {
        "total_formations": total_formations,
        "successful": successful,
        "failed": failed,
        "plotly_generated": plotly_generated,
        "matplotlib_generated": matplotlib_generated,
        "workers_used": workers_used,
        "total_duration_seconds": parallel_duration,
        "sequential_estimate_seconds": sequential_estimate,
        "parallel_speedup_estimate": speedup,
        "errors": errors,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 📦 MODULE EXPORTS
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    "run_parallel_formation_plots",
    "ParallelExecutionError",
]
