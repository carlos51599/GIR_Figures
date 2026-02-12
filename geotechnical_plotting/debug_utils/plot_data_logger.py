"""
Plot Data Logger - Reusable debugging utility for comparing plot data.

This module provides standardized logging for plot data points to enable
systematic comparison between monolith and modular implementations.

Usage:
    from geotechnical_plotting.debug_utils import (
        PlotDataLogger,
        log_formation_data,
        enable_debug_logging,
    )

    # Enable debug logging for specific formations
    enable_debug_logging(formations=["Kimmeridge Clay Formation (Weathered)"])

    # In your plotting function:
    log_formation_data(
        source="MODULAR",
        formation_name=formation_name,
        csv_name=csv_name,
        df=df_filtered,
        x_column=x_column,
        y_column=y_column,
        filter_column=filter_column,
    )
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# 🏗️ CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

# Global debug configuration
_DEBUG_CONFIG = {
    "enabled": False,
    "formations": [],  # Empty = all formations
    "log_to_file": True,
    "log_dir": None,  # Set at runtime
    "csv_sources": [],  # Empty = all CSVs
    "include_all_columns": False,  # Log all column values per row
}


# ═══════════════════════════════════════════════════════════════════════════
# 🔧 CONFIGURATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def enable_debug_logging(
    formations: Optional[List[str]] = None,
    csv_sources: Optional[List[str]] = None,
    log_dir: Optional[str] = None,
    include_all_columns: bool = False,
) -> None:
    """
    Enable debug logging for plot data comparison.

    Args:
        formations: List of formation names to log (empty = all)
                   Examples: ["Kimmeridge Clay Formation (Weathered)", "KC_W"]
        csv_sources: List of CSV sources to log (empty = all)
        log_dir: Directory to save debug logs (defaults to workspace/logs)
        include_all_columns: If True, log all column values per row
    """
    _DEBUG_CONFIG["enabled"] = True
    _DEBUG_CONFIG["formations"] = formations or []
    _DEBUG_CONFIG["csv_sources"] = csv_sources or []
    _DEBUG_CONFIG["include_all_columns"] = include_all_columns

    if log_dir:
        _DEBUG_CONFIG["log_dir"] = Path(log_dir)
    else:
        # Default to workspace/logs
        workspace = Path(__file__).resolve().parent.parent.parent
        _DEBUG_CONFIG["log_dir"] = workspace / "logs"

    # Create log directory
    _DEBUG_CONFIG["log_dir"].mkdir(parents=True, exist_ok=True)

    logger.info(f"🔍 Plot data debug logging ENABLED")
    if formations:
        logger.info(f"   Formations: {formations}")
    else:
        logger.info(f"   Formations: ALL")


def disable_debug_logging() -> None:
    """Disable debug logging."""
    _DEBUG_CONFIG["enabled"] = False
    logger.info("🔍 Plot data debug logging DISABLED")


def _should_log_formation(formation_name: str) -> bool:
    """Check if this formation should be logged."""
    if not _DEBUG_CONFIG["enabled"]:
        return False

    if not _DEBUG_CONFIG["formations"]:
        return True  # Log all formations

    # Check for exact match or partial match
    for pattern in _DEBUG_CONFIG["formations"]:
        if pattern.lower() in formation_name.lower():
            return True

    return False


def _should_log_csv(csv_name: str) -> bool:
    """Check if this CSV source should be logged."""
    if not _DEBUG_CONFIG["csv_sources"]:
        return True  # Log all CSVs

    return csv_name in _DEBUG_CONFIG["csv_sources"]


# ═══════════════════════════════════════════════════════════════════════════
# 📊 DATA LOGGING CLASS
# ═══════════════════════════════════════════════════════════════════════════


class PlotDataLogger:
    """
    Structured logger for plot data points.

    Collects data points in a standardized format for comparison.
    """

    def __init__(self, source: str, parameter_name: str):
        """
        Initialize plot data logger.

        Args:
            source: Identifier for the source (e.g., "MONOLITH", "MODULAR")
            parameter_name: Name of parameter being plotted
        """
        self.source = source
        self.parameter_name = parameter_name
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.logged_data: Dict[str, Dict[str, List[Dict]]] = (
            {}
        )  # {formation: {csv: [rows]}}

    def log_formation_data(
        self,
        formation_name: str,
        csv_name: str,
        df: pd.DataFrame,
        x_column: str,
        y_column: str,
        filter_column: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log data points for a formation/CSV combination.

        Args:
            formation_name: Geological formation name
            csv_name: Source CSV file name
            df: DataFrame containing the data to be plotted
            x_column: Column name for X values
            y_column: Column name for Y values
            filter_column: Column used for filtering (e.g., "is_manual_outlier")
            context: Additional context info (columns present, row counts, etc.)
        """
        if not _should_log_formation(formation_name):
            return

        if not _should_log_csv(csv_name):
            return

        # Initialize nested dict if needed
        if formation_name not in self.logged_data:
            self.logged_data[formation_name] = {}
        if csv_name not in self.logged_data[formation_name]:
            self.logged_data[formation_name][csv_name] = []

        # Log header info
        logger.info(f"")
        logger.info(f"{'='*80}")
        logger.info(f"[{self.source}] Plot Data Debug - {formation_name}")
        logger.info(f"{'='*80}")
        logger.info(f"  CSV Source: {csv_name}")
        logger.info(f"  X Column: {x_column}")
        logger.info(f"  Y Column: {y_column}")
        logger.info(f"  Filter Column: {filter_column}")
        logger.info(f"  Total Rows: {len(df)}")

        # Log column presence checks
        if context:
            for key, value in context.items():
                logger.info(f"  {key}: {value}")

        # Log each data point
        logger.info(f"")
        logger.info(f"  Data Points ({len(df)} rows):")
        logger.info(f"  {'─'*70}")

        # Determine location column
        loc_col = None
        for col in ["Location ID", "LocationID"]:
            if col in df.columns:
                loc_col = col
                break

        # Determine depth column
        depth_col = None
        for col in ["Top Depth", "DepthTop"]:
            if col in df.columns:
                depth_col = col
                break

        for idx, row in df.iterrows():
            x_val = row.get(x_column, "N/A")
            y_val = row.get(y_column, "N/A")
            loc_id = row.get(loc_col, "N/A") if loc_col else "N/A"
            depth = row.get(depth_col, "N/A") if depth_col else "N/A"
            inv = row.get("Investigation", "N/A")

            # Log to console
            logger.info(
                f"    [{self.source}] {loc_id} | Depth={depth} | X={x_val} | Y={y_val} | Inv={inv}"
            )

            # Store for comparison
            row_data = {
                "Location ID": loc_id,
                "Depth": depth,
                "X": x_val,
                "Y": y_val,
                "Investigation": inv,
                "index": idx,
            }

            # Optionally include all columns
            if _DEBUG_CONFIG["include_all_columns"]:
                row_data["all_values"] = row.to_dict()

            self.logged_data[formation_name][csv_name].append(row_data)

        logger.info(f"  {'─'*70}")
        logger.info(f"{'='*80}")

    def save_to_file(self, filename: Optional[str] = None) -> Path:
        """
        Save logged data to JSON file for comparison.

        Args:
            filename: Custom filename (defaults to auto-generated)

        Returns:
            Path to saved file
        """
        if not filename:
            filename = (
                f"plot_data_{self.source}_{self.parameter_name}_{self.timestamp}.json"
            )

        log_dir = _DEBUG_CONFIG.get("log_dir", Path("logs"))
        log_dir.mkdir(parents=True, exist_ok=True)

        output_path = log_dir / filename

        # Convert to JSON-serializable format
        output_data = {
            "source": self.source,
            "parameter_name": self.parameter_name,
            "timestamp": self.timestamp,
            "formations": {},
        }

        for formation, csv_data in self.logged_data.items():
            output_data["formations"][formation] = {}
            for csv_name, rows in csv_data.items():
                # Convert any non-serializable values
                clean_rows = []
                for row in rows:
                    clean_row = {}
                    for k, v in row.items():
                        if pd.isna(v):
                            clean_row[k] = None
                        elif hasattr(v, "item"):  # numpy types
                            clean_row[k] = v.item()
                        else:
                            clean_row[k] = v
                    clean_rows.append(clean_row)
                output_data["formations"][formation][csv_name] = clean_rows

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, default=str)

        logger.info(f"📁 Saved debug data to: {output_path}")
        return output_path


# ═══════════════════════════════════════════════════════════════════════════
# 🔍 CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


# Global loggers for easy access
_ACTIVE_LOGGERS: Dict[str, PlotDataLogger] = {}


def log_formation_data(
    source: str,
    formation_name: str,
    csv_name: str,
    df: pd.DataFrame,
    x_column: str,
    y_column: str,
    filter_column: Optional[str] = None,
    parameter_name: str = "unknown",
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Convenience function to log formation data.

    Creates or reuses a PlotDataLogger instance for the given source.

    Args:
        source: Identifier (e.g., "MONOLITH", "MODULAR")
        formation_name: Geological formation name
        csv_name: Source CSV file name
        df: DataFrame to log
        x_column: X column name
        y_column: Y column name
        filter_column: Filter column name
        parameter_name: Parameter being plotted
        context: Additional context info
    """
    if not _DEBUG_CONFIG["enabled"]:
        return

    # Get or create logger for this source
    logger_key = f"{source}_{parameter_name}"
    if logger_key not in _ACTIVE_LOGGERS:
        _ACTIVE_LOGGERS[logger_key] = PlotDataLogger(source, parameter_name)

    _ACTIVE_LOGGERS[logger_key].log_formation_data(
        formation_name=formation_name,
        csv_name=csv_name,
        df=df,
        x_column=x_column,
        y_column=y_column,
        filter_column=filter_column,
        context=context,
    )


def save_all_debug_logs() -> List[Path]:
    """
    Save all active debug logs to files.

    Returns:
        List of paths to saved files
    """
    saved_paths = []
    for logger_key, data_logger in _ACTIVE_LOGGERS.items():
        path = data_logger.save_to_file()
        saved_paths.append(path)
    return saved_paths


# ═══════════════════════════════════════════════════════════════════════════
# 📊 COMPARISON FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def compare_plot_data_logs(
    monolith_log_path: str,
    modular_log_path: str,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compare two plot data log files and generate difference report.

    Args:
        monolith_log_path: Path to monolith log JSON
        modular_log_path: Path to modular log JSON
        output_path: Optional path to save comparison report

    Returns:
        Dictionary with comparison results
    """
    with open(monolith_log_path, "r") as f:
        monolith_data = json.load(f)

    with open(modular_log_path, "r") as f:
        modular_data = json.load(f)

    comparison = {
        "matching_formations": [],
        "missing_in_modular": [],
        "extra_in_modular": [],
        "formation_differences": {},
    }

    # Compare formations
    monolith_formations = set(monolith_data.get("formations", {}).keys())
    modular_formations = set(modular_data.get("formations", {}).keys())

    comparison["matching_formations"] = list(monolith_formations & modular_formations)
    comparison["missing_in_modular"] = list(monolith_formations - modular_formations)
    comparison["extra_in_modular"] = list(modular_formations - monolith_formations)

    # Compare data points for matching formations
    for formation in comparison["matching_formations"]:
        mono_formation_data = monolith_data["formations"][formation]
        mod_formation_data = modular_data["formations"][formation]

        formation_diff = {
            "csv_differences": {},
            "point_count_match": True,
            "value_differences": [],
        }

        for csv_name in set(mono_formation_data.keys()) | set(
            mod_formation_data.keys()
        ):
            mono_rows = mono_formation_data.get(csv_name, [])
            mod_rows = mod_formation_data.get(csv_name, [])

            if len(mono_rows) != len(mod_rows):
                formation_diff["point_count_match"] = False
                formation_diff["csv_differences"][csv_name] = {
                    "monolith_count": len(mono_rows),
                    "modular_count": len(mod_rows),
                }

            # Compare individual points
            for i, (mono_row, mod_row) in enumerate(zip(mono_rows, mod_rows)):
                if mono_row.get("X") != mod_row.get("X") or mono_row.get(
                    "Y"
                ) != mod_row.get("Y"):
                    formation_diff["value_differences"].append(
                        {
                            "csv": csv_name,
                            "row_index": i,
                            "location": mono_row.get("Location ID"),
                            "monolith": {
                                "X": mono_row.get("X"),
                                "Y": mono_row.get("Y"),
                            },
                            "modular": {"X": mod_row.get("X"), "Y": mod_row.get("Y")},
                        }
                    )

        if formation_diff["csv_differences"] or formation_diff["value_differences"]:
            comparison["formation_differences"][formation] = formation_diff

    # Save comparison if path provided
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(comparison, f, indent=2, default=str)
        logger.info(f"📊 Saved comparison report to: {output_path}")

    return comparison


def print_comparison_summary(comparison: Dict[str, Any]) -> None:
    """Print a human-readable summary of comparison results."""
    print("\n" + "=" * 80)
    print("PLOT DATA COMPARISON SUMMARY")
    print("=" * 80)

    print(f"\n✅ Matching Formations: {len(comparison['matching_formations'])}")
    for f in comparison["matching_formations"]:
        print(f"   - {f}")

    if comparison["missing_in_modular"]:
        print(f"\n❌ Missing in Modular: {len(comparison['missing_in_modular'])}")
        for f in comparison["missing_in_modular"]:
            print(f"   - {f}")

    if comparison["extra_in_modular"]:
        print(f"\n⚠️ Extra in Modular: {len(comparison['extra_in_modular'])}")
        for f in comparison["extra_in_modular"]:
            print(f"   - {f}")

    if comparison["formation_differences"]:
        print(
            f"\n🔍 Formations with Differences: {len(comparison['formation_differences'])}"
        )
        for formation, diff in comparison["formation_differences"].items():
            print(f"\n   {formation}:")
            if diff["csv_differences"]:
                for csv, counts in diff["csv_differences"].items():
                    print(
                        f"      {csv}: Monolith={counts['monolith_count']}, Modular={counts['modular_count']}"
                    )
            if diff["value_differences"]:
                print(f"      Value differences: {len(diff['value_differences'])} rows")
                for vd in diff["value_differences"][:5]:  # Show first 5
                    print(
                        f"         {vd['location']}: M={vd['monolith']} vs m={vd['modular']}"
                    )
    else:
        print("\n✅ No differences found!")

    print("\n" + "=" * 80)
