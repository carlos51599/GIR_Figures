#!/usr/bin/env python3
"""
Investigation Summary CSV Export Module - Pure Extraction Version
Shared module for exporting investigation source tracking data to CSV.

AI-Optimized Monolith Implementation - Shared Module

Architectural Overview:

Responsibility:
Provides reusable functions for extracting investigation source data from
pre-processed formation datasets (from Plotly) and exporting to CSV files.
This module performs PURE EXTRACTION only - no CSV analysis, no investigation
lookups. All data must be pre-processed by the Plotly function with
Investigation column already populated.

Key Interactions:
- Input: Pre-processed formation data WITH Investigation column (from Plotly)
- Processing: Simple count extraction from pre-populated data
- Output: Investigation summary CSV with counts by formation/test type/investigation
- Integration: Called by parameter plotting scripts after Plotly plot generation

CRITICAL DESIGN PRINCIPLE:
This module ONLY extracts from data already processed by Plotly.
It does NOT:
- Load or analyze source CSVs
- Look up investigations from Location Details
- Filter data based on parameter columns
- Replicate any Plotly processing logic

All data passed to this module MUST have 'Investigation' column already populated.

Navigation Guide:
Core Functions:
- extract_investigation_sources(): Extracts counts from pre-populated data
- export_investigation_csv(): Writes investigation data to CSV file

Orchestrator Function:
- generate_investigation_summary(): Single CSV export (investigation_summary.csv)

Helper Functions:
- _process_csv_with_investigation(): Counts data per investigation (simple extraction)
- should_generate_output(): Master output toggle check
- should_generate_data_export(): Data export toggle check

CONFIGURATION ARCHITECTURE:
This module accepts explicit parameters only (no CONFIG access).
All configuration values are passed from the calling script's orchestrator.
This enables full testability and zero hidden dependencies.
"""

# Standard library imports
import logging
from pathlib import Path
from collections import defaultdict
from typing import Dict, Any, List

# Third-party imports
import pandas as pd

# Module-level logger
logger = logging.getLogger(__name__)

# Module-level constants
OUTPUT_COLUMNS = [
    "Formation",
    "Test Type",
    "Investigation",
    "Data Points",
    "Location Count",
    "Locations",
]  # Standard column order for investigation summary CSV


# ═══════════════════════════════════════════════════════════════════════════
# 🔧 OUTPUT CONTROL HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def should_generate_output(output_control: Dict[str, Any]) -> bool:
    """
    Check if ANY outputs should be generated based on master toggle.

    Args:
        output_control: output_control section from CONFIG

    Returns:
        True if master toggle is ON, False otherwise
    """
    return output_control.get("enabled", True)


def should_generate_data_export(
    export_name: str,
    output_control: Dict[str, Any],
) -> bool:
    """
    Check if a specific data export should be generated.

    Hierarchy:
    1. Master toggle must be ON
    2. Data category toggle must be ON
    3. Individual export toggle must be ON (if exists)

    Args:
        export_name: Name of export toggle in output_control["data"]
        output_control: output_control section from CONFIG

    Returns:
        True if data export should be generated, False otherwise
    """
    if not should_generate_output(output_control):
        return False

    data_config = output_control.get("data", {})
    category_toggle = data_config.get("enabled", True)

    if not category_toggle:
        return False

    # Check individual export toggle (default to True if not specified)
    return data_config.get(export_name, True)


# ═══════════════════════════════════════════════════════════════════════════
# 🔍 INVESTIGATION SOURCE EXTRACTION (Pure Extraction)
# ═══════════════════════════════════════════════════════════════════════════


def _process_csv_with_investigation(
    csv_name: str,
    df: pd.DataFrame,
    formation_name: str,
) -> List[Dict[str, Any]]:
    """
    Extract investigation counts from DataFrame with pre-populated Investigation column.

    Pure extraction function - counts rows per investigation without any filtering.
    The data MUST already have Investigation column populated by Plotly.

    Args:
        csv_name: Name of CSV file (e.g., "SPT by Geology.csv")
        df: DataFrame with Investigation column already populated
        formation_name: Name of geological formation

    Returns:
        list: Summary records as list of dicts

    Raises:
        ValueError: If DataFrame does not have Investigation column
    """
    # Validate Investigation column exists
    if "Investigation" not in df.columns:
        raise ValueError(
            f"DataFrame for {csv_name} in {formation_name} is missing "
            f"'Investigation' column. Data must be pre-processed by Plotly."
        )

    test_type = csv_name.replace(" by Geology.csv", "")

    # Count values and collect locations per investigation
    investigation_counts: Dict[str, int] = defaultdict(int)
    investigation_locations: Dict[str, set] = defaultdict(set)

    for _, row in df.iterrows():
        location_id = str(row.get("Location ID", "Unknown")).strip()
        investigation = str(row.get("Investigation", "Unknown")).strip()
        investigation_counts[investigation] += 1
        investigation_locations[investigation].add(location_id)

    # Create summary records
    records = []
    for investigation, count in investigation_counts.items():
        sorted_locations = sorted(investigation_locations[investigation])
        locations_str = " | ".join(sorted_locations)
        location_count = len(sorted_locations)
        records.append({
            "Formation": formation_name,
            "Test Type": test_type,
            "Investigation": investigation,
            "Data Points": count,
            "Location Count": location_count,
            "Locations": locations_str,
        })

    total_points = sum(investigation_counts.values())
    logger.info(
        f"      ✅ {test_type}: {len(investigation_counts)} investigations, "
        f"{total_points} data points"
    )

    return records


def extract_investigation_sources(
    grouped_by_formation: Dict[str, Dict[str, pd.DataFrame]],
) -> List[Dict[str, Any]]:
    """
    Extract investigation sources from pre-processed formation data.

    Pure extraction function - simply counts data per investigation from
    DataFrames that already have Investigation column populated by Plotly.

    Args:
        grouped_by_formation: Nested dict {formation_name: {csv_name: dataframe}}
                             Each DataFrame MUST have Investigation column

    Returns:
        list: Summary records as list of dicts with keys:
              ["Formation", "Test Type", "Investigation", "Data Points",
               "Location Count", "Locations"]

    Raises:
        ValueError: If any DataFrame is missing Investigation column
    """
    logger.info("🔍 Extracting investigation sources from pre-processed data...")

    summary_records = []

    # Iterate through formations
    for formation_name, csv_dict in grouped_by_formation.items():
        logger.info(f"   Processing formation: {formation_name}")

        # Process each CSV source (test type)
        for csv_name, df in csv_dict.items():
            logger.info(f"      📊 {csv_name}: {len(df)} rows")
            csv_records = _process_csv_with_investigation(
                csv_name,
                df,
                formation_name,
            )
            summary_records.extend(csv_records)

    logger.info(f"✅ Extracted {len(summary_records)} investigation source records")
    return summary_records


# ═══════════════════════════════════════════════════════════════════════════
# 💾 CSV EXPORT FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def export_investigation_csv(
    investigation_data: List[Dict[str, Any]],
    output_path: Path,
    columns: List[str],
) -> None:
    """
    Export investigation source data to CSV file.

    Converts list of investigation records to DataFrame, sorts for readability,
    and writes to CSV with specified column order. Creates output directory if
    needed.

    Args:
        investigation_data: List of dicts with investigation records
        output_path: Full path to output CSV file
        columns: List of column names in desired output order

    Raises:
        ValueError: If investigation_data is empty
        IOError: If CSV write fails
    """
    logger.info(f"💾 Exporting investigation summary to: {output_path}")

    if not investigation_data:
        logger.warning("⚠️ No investigation data to export - skipping CSV creation")
        return

    try:
        # Create output directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to DataFrame
        df = pd.DataFrame(investigation_data)

        # Sort for readability: Formation -> Test Type -> Investigation
        df_sorted = df.sort_values(
            ["Formation", "Test Type", "Investigation"], ignore_index=True
        )

        # Write CSV with specified column order
        df_sorted.to_csv(output_path, index=False, columns=columns, encoding="utf-8")

        logger.info(f"✅ Exported {len(df_sorted)} records to {output_path.name}")

    except Exception as e:
        logger.error(f"❌ Failed to export investigation CSV: {str(e)}")
        raise IOError(f"CSV export failed: {str(e)}") from e


# ═══════════════════════════════════════════════════════════════════════════
# 🎯 INVESTIGATION SUMMARY CSV EXPORT
# ═══════════════════════════════════════════════════════════════════════════


def _export_investigation_csv_with_outliers(
    data_with_outliers: List[Dict[str, Any]],
    data_folder: Path,
    output_control: Dict[str, Any],
) -> None:
    """
    Export investigation summary CSV.

    Helper function to keep generate_investigation_summary under 75 lines.
    Exports a single investigation summary CSV.
    Uses module-level OUTPUT_COLUMNS constant for column ordering.

    Args:
        data_with_outliers: Investigation records
        data_folder: Directory for output CSV files
        output_control: Output control configuration dict
    """
    csv_path = data_folder / "investigation_summary.csv"

    logger.info("💾 Writing investigation summary CSV...")
    logger.info(f"   Output: {csv_path.name}")

    if should_generate_data_export("investigation_summary_csv", output_control):
        export_investigation_csv(data_with_outliers, csv_path, OUTPUT_COLUMNS)
        logger.info("✅ Investigation summary CSV exported successfully")
    else:
        logger.info("   ⏭️ Skipping CSV export (disabled in output_control)")
        logger.info("✅ Investigation tracking complete (CSV export disabled)")


def _execute_investigation_tracking_workflow(
    grouped_by_formation: Dict[str, Dict[str, pd.DataFrame]],
    data_folder: Path,
    output_control: Dict[str, Any],
) -> None:
    """
    Execute investigation tracking workflow (pure extraction only).

    Helper function for generate_investigation_summary. Executes the sequence:
    extract sources from pre-populated data -> export CSV.
    All parameters are explicit (no CONFIG access).

    Args:
        grouped_by_formation: Pre-processed data with Investigation column
        data_folder: Directory for output CSV files
        output_control: Output control configuration dict
    """
    # === EXTRACT INVESTIGATION SOURCES (PURE EXTRACTION) ===
    logger.info("🔍 Extracting sources from pre-processed formation data...")
    investigation_data = extract_investigation_sources(grouped_by_formation)

    if not investigation_data:
        logger.warning("⚠️ No investigation data extracted - no CSV to export")
        return

    # === EXPORT CSV ===
    _export_investigation_csv_with_outliers(
        investigation_data,
        data_folder,
        output_control,
    )


def generate_investigation_summary(
    grouped_by_formation: Dict[str, Dict[str, pd.DataFrame]],
    parameter_mappings: pd.DataFrame,  # Kept for API compatibility, not used
    parameter_name: str,  # Kept for API compatibility, not used
    csv_source_folder: str,  # Kept for API compatibility, not used
    location_details_csv_name: str,  # Kept for API compatibility, not used
    data_folder: Path,
    output_control: Dict[str, Any],
    enabled: bool = True,
) -> None:
    """
    Generate investigation summary CSV from pre-processed data.

    Pure extraction function - extracts investigation counts from DataFrames
    that already have Investigation column populated by Plotly.

    IMPORTANT: grouped_by_formation MUST contain DataFrames with Investigation
    column already populated. This module does NOT look up investigations.

    Args:
        grouped_by_formation: Pre-processed data from Plotly with Investigation column
        parameter_mappings: (Unused - kept for API compatibility)
        parameter_name: (Unused - kept for API compatibility)
        csv_source_folder: (Unused - kept for API compatibility)
        location_details_csv_name: (Unused - kept for API compatibility)
        data_folder: Directory for output CSV files
        output_control: Output control configuration dict
        enabled: Whether investigation tracking is enabled (from CONFIG)

    Output:
        Creates: {data_folder}/investigation_summary.csv
    """
    logger.info("🚀 Starting Phase 5: Investigation Source Tracking...")

    if not enabled:
        logger.info("⚠️ Investigation tracking disabled - skipping Phase 5")
        return

    try:
        _execute_investigation_tracking_workflow(
            grouped_by_formation,
            data_folder,
            output_control,
        )
        logger.info("✅ Phase 5 complete: Investigation tracking finished successfully")

    except Exception as e:
        logger.error(f"❌ Phase 5 failed: {str(e)}")
        logger.warning("⚠️ Continuing without investigation tracking...")
        raise


# ═══════════════════════════════════════════════════════════════════════════
# 🔧 AI CONTEXT RECOVERY
# ═══════════════════════════════════════════════════════════════════════════


def _ai_context_recovery_summary() -> str:
    """
    AI Context Recovery: Summary of this module's purpose and usage.

    Returns:
        str: Summary for AI navigation and comprehension
    """
    return """
    Investigation Summary CSV Module - Pure Extraction Version
    ===========================================================
    
    PURPOSE:
    Exports investigation source tracking data to CSV.
    PURE EXTRACTION ONLY - no CSV analysis, no investigation lookups.
    
    CRITICAL DESIGN PRINCIPLE:
    This module ONLY extracts from data already processed by Plotly.
    All DataFrames MUST have 'Investigation' column pre-populated.
    
    EXPORT:
    generate_investigation_summary() exports: investigation_summary.csv
    
    CORE FUNCTIONS:
    - extract_investigation_sources(): Count data per investigation (pure extraction)
    - export_investigation_csv(): Write data to CSV file
    
    INTEGRATION:
    Import and call from plotting scripts AFTER Plotly plot generation.
    The Plotly function must populate Investigation column before calling this.
    """


if __name__ == "__main__":
    # Module self-test / usage example
    print(_ai_context_recovery_summary())
