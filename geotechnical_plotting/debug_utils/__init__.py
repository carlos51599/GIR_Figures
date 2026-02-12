"""
Debug utilities for comparing monolith vs modular plot data.

This module provides tools for systematic comparison of data points
between the legacy monolith scripts and the new modular architecture.

THE MAIN EVENT: Point-to-point coordinate comparison is the critical
validation step for every monolith-to-modular conversion. A successful
conversion must show 100% match on all data point coordinates.

Usage:
    # For logging during script execution
    from geotechnical_plotting.debug_utils import enable_debug_logging, log_formation_data

    # For comparing results after execution
    from geotechnical_plotting.debug_utils import (
        run_full_comparison,
        quick_file_compare,
        extract_points_from_log,
        compare_point_lists,
    )
"""

from .plot_data_logger import (
    PlotDataLogger,
    log_formation_data,
    compare_plot_data_logs,
    enable_debug_logging,
    disable_debug_logging,
)

from .point_comparison import (
    DataPoint,
    FormationData,
    ComparisonResult,
    extract_points_from_log,
    extract_points_from_text_file,
    compare_point_lists,
    compare_formations,
    print_comparison_report,
    print_full_comparison_summary,
    run_full_comparison,
    quick_file_compare,
)

__all__ = [
    # Logging utilities
    "PlotDataLogger",
    "log_formation_data",
    "compare_plot_data_logs",
    "enable_debug_logging",
    "disable_debug_logging",
    # Point comparison utilities (THE MAIN EVENT)
    "DataPoint",
    "FormationData",
    "ComparisonResult",
    "extract_points_from_log",
    "extract_points_from_text_file",
    "compare_point_lists",
    "compare_formations",
    "print_comparison_report",
    "print_full_comparison_summary",
    "run_full_comparison",
    "quick_file_compare",
    # Automated comparison runner
    "run_comparison",  # From run_comparison.py
]

# Import run_comparison for programmatic use
from .run_comparison import run_comparison
