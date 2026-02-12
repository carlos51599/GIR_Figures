#!/usr/bin/env python3
"""
Manual Data Management Module for Geotechnical Plotting Scripts

Provides functionality to load, match, and mark manually identified
outliers and data additions from Excel spreadsheets. Works across
all parameter types and plotting scripts.

ARCHITECTURAL OVERVIEW:

Responsibility:
This module handles manual curation of geotechnical data by loading Excel-based
lists of points to exclude (outliers) or include (additions), matching them against
dataset points using Location ID + parameter value + y-value (depth or other parameter),
and marking the points with boolean columns for downstream filtering.

Key Interactions:
- Input: Excel files with manual outlier/addition lists, formation DataFrames
- Processing: Load Excel → Match by Location ID + values (with tolerance) →
  Add boolean columns (is_manual_outlier, is_manual_addition)
- Output: Modified DataFrames + summary reports + CSV exports
- Zero CONFIG dependencies in business logic (all primitives injected)
- Y-axis flexibility: Supports both depth-based plots and scatter plots (e.g., A-Line)

Navigation Guide:
Section markers (# ═════) delineate:
- Excel Loading Functions (load_manual_outliers, load_manual_additions)
- Marking Functions (mark_manual_outliers, mark_manual_additions)
- Summary Functions (print_manual_outlier_summary, export_manual_data_changes_csv)

DESIGN PATTERN: Configuration Injection
All functions accept explicit parameters. No CONFIG dependencies.
Functions are pure data transformations with complete type hints.

USAGE EXAMPLE:

```python
from manual_data_management import (
    load_manual_outliers,
    load_manual_additions,
    mark_manual_outliers,
    mark_manual_additions,
    print_manual_outlier_summary,
    export_manual_data_changes_csv,
)

# In main():
# Load manual data
manual_outliers_df = load_manual_outliers(
    parameter_name="EffectiveAngleFriction",
    excel_file="Data to Remove.xlsx",
    sheet_mapping={"EffectiveAngleFriction": "EffPhi"}
)

manual_additions_by_formation, manual_additions_df = load_manual_additions(
    parameter_name="EffectiveAngleFriction",
    excel_file="Data to Add.xlsx",
    sheet_mapping={"EffectiveAngleFriction": "EffPhi"},
    geology_code_descriptions={"GF_W": "Gault Clay Formation (Weathered)", ...}
)

# Mark manual data in formation groups
# For depth-based plots (defaults work for most cases):
mark_manual_outliers(
    formation_groups=formation_groups,
    manual_outliers_df=manual_outliers_df,
    parameter_mappings=parameter_mappings,
    # param_tolerance=0.01 (default - handles 2-decimal Excel rounding)
    # depth_tolerance=0.01 (default)
    # y_column_name="Top Depth" (default)
)

# For scatter plots (e.g., A-Line: Liquid Limit vs Plasticity Index):
mark_manual_outliers(
    formation_groups=formation_groups,
    manual_outliers_df=manual_outliers_df,
    parameter_mappings=parameter_mappings,
    y_column_name="Plasticity Index"  # Specify y-axis column explicitly
    # param_tolerance and depth_tolerance use defaults (0.01)
)

# Override defaults only if needed (e.g., very strict matching):
mark_manual_outliers(
    formation_groups=formation_groups,
    manual_outliers_df=manual_outliers_df,
    parameter_mappings=parameter_mappings,
    param_tolerance=1e-10,  # Explicit override for exact matching
    depth_tolerance=1e-10
)

mark_manual_additions(
    formation_groups=formation_groups,
    manual_additions_df=manual_additions_df,
    parameter_mappings=parameter_mappings,
    # All defaults work for standard use (tolerance=0.01, y_column="Top Depth")
)

# Print summary reports
print_manual_outlier_summary(
    manual_outliers_df=manual_outliers_df,
    formation_groups=formation_groups,
    parameter_mappings=parameter_mappings
)

# Export CSV summaries
export_manual_data_changes_csv(
    output_folder="Output",
    parameter_name="EffectiveAngleFriction",
    manual_outliers_df=manual_outliers_df,
    manual_additions_df=manual_additions_df,
    formation_groups=formation_groups,
    manual_additions_by_formation=manual_additions_by_formation,
    parameter_mappings=parameter_mappings,
    param_tolerance=1e-5,
    depth_tolerance=1e-5
)
```
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# 📥 EXCEL LOADING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def load_manual_outliers(
    parameter_name: str,
    excel_file: str,
    sheet_mapping: Dict[str, str],
    enabled: bool = True,
    swap_xy: bool = False,
) -> Optional[pd.DataFrame]:
    """
    Load manually identified outliers from Excel spreadsheet.

    Reads the Excel file and extracts manually identified outliers for the
    current parameter. These outliers are matched against data points by
    Location ID, parameter value, and depth.

    Args:
        parameter_name: Parameter name (e.g., "MoistureContent", "EffectiveAngleFriction")
        excel_file: Path to Excel file with manual outliers
        sheet_mapping: Dict mapping parameter names to sheet names
        enabled: Master toggle for manual outlier loading
        swap_xy: If True, swap x/y columns (for plots where Excel orientation differs from plot orientation)
                 Example: Excel has x=cv, y=CellPressure but plot has x=CellPressure, y=cv

    Returns:
        DataFrame with columns [Location ID, parameter_value, y_value, Test Type, Notes]
        or None if disabled/error occurs

    Column Standardization:
        - "Location ID" → "Location ID" (already standard)
        - "x" → "parameter_value" (X-axis value in plot)
        - "y" → "y_value" (Y-axis value in plot)
        - If swap_xy=True: Excel x→y_value, Excel y→parameter_value

    Error Handling:
        - Returns None if disabled, sheet not found, file not found, or missing columns
        - Logs appropriate warnings/errors for debugging
    """
    if not enabled:
        logger.info("⏭️ Manual outlier exclusion disabled")
        return None

    sheet_name = sheet_mapping.get(parameter_name)
    if not sheet_name:
        logger.warning(
            f"⚠️ No sheet mapping found for parameter '{parameter_name}' in manual outlier config"
        )
        return None

    try:
        logger.info(
            f"💾 Loading manual outliers from '{excel_file}' (Sheet: '{sheet_name}')..."
        )
        df_outliers = pd.read_excel(excel_file, sheet_name=sheet_name)

        # Standardize column names for matching
        if swap_xy:
            # Swap x/y for plots where Excel orientation differs from plot
            logger.info(
                "  🔄 Swapping x/y columns (Excel orientation differs from plot)"
            )
            df_outliers = df_outliers.rename(
                columns={
                    "Location ID": "Location ID",
                    "x": "y_value",  # Excel x → plot y
                    "y": "parameter_value",  # Excel y → plot x
                }
            )
        else:
            # Standard mapping
            df_outliers = df_outliers.rename(
                columns={
                    "Location ID": "Location ID",
                    "x": "parameter_value",
                    "y": "y_value",
                }
            )

        required_cols = ["Location ID", "parameter_value", "y_value"]
        if not all(col in df_outliers.columns for col in required_cols):
            logger.error(
                f"❌ Manual outlier Excel sheet '{sheet_name}' is missing required columns: {required_cols}"
            )
            return None

        # Clean up Location IDs (strip whitespace and normalize to uppercase for case-insensitive matching)
        df_outliers["Location ID"] = (
            df_outliers["Location ID"].astype(str).str.strip().str.upper()
        )

        logger.info(f"✅ Loaded {len(df_outliers)} manually identified outliers")
        return df_outliers

    except FileNotFoundError:
        logger.error(f"❌ Manual outlier Excel file not found: {excel_file}")
        return None
    except Exception as e:
        logger.error(f"❌ Failed to load manual outliers: {e}")
        return None


def load_manual_additions(
    parameter_name: str,
    excel_file: str,
    sheet_mapping: Dict[str, str],
    geology_code_descriptions: Dict[str, str],
    enabled: bool = True,
    swap_xy: bool = False,
) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame]:
    """
    Load manually added data points from Excel and organize by formation.

    Reads the Excel file and groups data points by their geological formation
    (based on Geology Code 2 column). These points will be plotted separately
    with a distinct "Manually Added" legend entry, not grouped by investigation
    or test type.

    Args:
        parameter_name: Parameter name (e.g., "EffectiveAngleFriction")
        excel_file: Path to Excel file with manual additions
        sheet_mapping: Dict mapping parameter names to sheet names
        geology_code_descriptions: Dict mapping geology codes to formation names
        enabled: Master toggle for manual additions loading
        swap_xy: If True, swap x/y columns (for plots where Excel orientation differs from plot orientation)

    Returns:
        Tuple of:
        - Dict[formation_name, DataFrame] with columns:
          [Location ID, parameter_value, y_value, Test Type, Geology Code 2, Formation]
        - Full DataFrame before grouping (for export verification)
        Empty dict and empty DataFrame if disabled or error occurs

    Column Standardization:
        - "Location ID" → "Location ID"
        - "x" → "parameter_value" (or y_value if swap_xy=True)
        - "y" → "y_value" (or parameter_value if swap_xy=True)
        - Adds "Formation" column by mapping Geology Code 2

    Data Cleaning:
        - Filters out rows with NaN parameter values
        - Filters out rows with "needs assigning" in Geology Code 2
        - Filters out rows with unmapped geology codes
    """
    if not enabled:
        logger.info("⏭️ Manual data control disabled")
        return {}, pd.DataFrame()

    sheet_name = sheet_mapping.get(parameter_name)
    if not sheet_name:
        logger.warning(
            f"⚠️ No sheet mapping for '{parameter_name}' in manual additions config"
        )
        return {}, pd.DataFrame()

    try:
        logger.info(
            f"💾 Loading manual additions from '{excel_file}' (Sheet: '{sheet_name}')..."
        )
        df_additions = pd.read_excel(excel_file, sheet_name=sheet_name)

        # Standardize column names
        if swap_xy:
            # Swap x/y for plots where Excel orientation differs from plot
            logger.info(
                "  🔄 Swapping x/y columns (Excel orientation differs from plot)"
            )
            df_additions = df_additions.rename(
                columns={
                    "Location ID": "Location ID",
                    "x": "y_value",  # Excel x → plot y
                    "y": "parameter_value",  # Excel y → plot x
                }
            )
        else:
            # Standard mapping
            df_additions = df_additions.rename(
                columns={
                    "Location ID": "Location ID",
                    "x": "parameter_value",
                    "y": "y_value",
                }
            )

        required_cols = [
            "Location ID",
            "parameter_value",
            "y_value",
            "Geology Code 2",
        ]
        if not all(col in df_additions.columns for col in required_cols):
            logger.error(
                f"❌ Sheet '{sheet_name}' missing required columns: {required_cols}"
            )
            return {}, pd.DataFrame()

        # Clean data - normalize Location IDs to uppercase for case-insensitive matching
        df_additions["Location ID"] = (
            df_additions["Location ID"].astype(str).str.strip().str.upper()
        )
        df_additions["Geology Code 2"] = (
            df_additions["Geology Code 2"].astype(str).str.strip()
        )

        # Filter out invalid rows
        initial_count = len(df_additions)
        df_additions = df_additions[
            df_additions["parameter_value"].notna()
        ]  # Remove NaN x values
        df_additions = df_additions[
            ~df_additions["Geology Code 2"].str.contains("needs assigning", na=False)
        ]

        filtered_count = initial_count - len(df_additions)
        if filtered_count > 0:
            logger.info(
                f"  ⚠️ Filtered out {filtered_count} invalid rows (NaN values or 'needs assigning')"
            )

        # Map geology codes to formation names
        df_additions["Formation"] = df_additions["Geology Code 2"].map(
            geology_code_descriptions
        )

        # Log unmapped geology codes
        unmapped = df_additions[df_additions["Formation"].isna()]
        if not unmapped.empty:
            unique_unmapped = unmapped["Geology Code 2"].unique()
            logger.warning(
                f"  ⚠️ Unmapped geology codes: {list(unique_unmapped)} ({len(unmapped)} rows)"
            )
            df_additions = df_additions[df_additions["Formation"].notna()]

        if df_additions.empty:
            logger.info("  ℹ️ No valid manual additions after filtering")
            return {}, pd.DataFrame()

        # Save full DataFrame for export verification
        df_additions_full = df_additions.copy()

        # Group by formation
        additions_by_formation = {}
        for formation, group_df in df_additions.groupby("Formation"):
            additions_by_formation[formation] = group_df.reset_index(drop=True)
            logger.info(f"  ✅ {formation}: {len(group_df)} manually added points")

        logger.info(
            f"✅ Loaded {len(df_additions)} manual additions across {len(additions_by_formation)} formations"
        )
        return additions_by_formation, df_additions_full

    except FileNotFoundError:
        logger.warning(f"⚠️ Manual additions file not found: {excel_file}")
        return {}, pd.DataFrame()
    except Exception as e:
        logger.error(f"❌ Failed to load manual additions: {e}")
        return {}, pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════
# 🏷️ MARKING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def mark_manual_outliers(
    formation_groups: Dict[str, Dict[str, pd.DataFrame]],
    manual_outliers_df: Optional[pd.DataFrame],
    parameter_mappings: pd.DataFrame,
    param_tolerance: float = 0.01,
    depth_tolerance: float = 0.01,
    y_column_name: str = "Top Depth",
    x_column_name: Optional[str] = None,
) -> None:
    """
    Mark manually identified outliers in formation dataframes.

    Adds 'is_manual_outlier' boolean column to each DataFrame based on matching
    Location ID, parameter value, and y-value from the manual outliers Excel.

    PERFORMANCE: Vectorized approach using merge is 20-50× faster than nested iterrows.
    Original O(n×m) complexity reduced to O(n+m) via rounded-value merge.

    Args:
        formation_groups: Nested dict of formation data (MODIFIED IN-PLACE)
                         {formation_name: {csv_name: DataFrame}}
        manual_outliers_df: DataFrame with manual outliers from Excel
        parameter_mappings: Parameter mapping DataFrame with columns
                           [csv_file, column_name, priority_rank, quality_score]
        param_tolerance: Tolerance for matching parameter values (default 0.01 for 2-decimal rounding)
        depth_tolerance: Tolerance for matching y-values (default 0.01 for 2-decimal rounding)
        y_column_name: Name of the y-axis column in DataFrames (default "Top Depth")
                      For depth-based plots: "Top Depth"
                      For scatter plots: e.g., "Plasticity Index", "CoefficientConsolidation_unified"
        x_column_name: Explicit name of the x-axis column (optional)
                      If None, uses first column from parameter_mappings
                      For dual-parameter plots (e.g., CV vs Cell Pressure): "Cell Pressure_unified"

    Side Effects:
        Modifies formation_groups in-place by adding 'is_manual_outlier' column

    Matching Logic (Vectorized):
        1. Round parameter and y-values to tolerance boundaries
        2. Normalize Location IDs to uppercase
        3. Use merge to find matches in O(n+m) time
        4. Mark matched rows with is_manual_outlier=True
    """
    if manual_outliers_df is None or manual_outliers_df.empty:
        logger.info(
            "⏭️ No manual outliers to mark - adding False column for consistency"
        )
        # Add column with all False values for consistency
        for csv_dict in formation_groups.values():
            for df in csv_dict.values():
                df["is_manual_outlier"] = False
        return

    logger.info("🚀 Marking manually identified outliers (vectorized)...")

    # === PREPARE OUTLIERS LOOKUP TABLE (VECTORIZED) ===
    # Calculate rounding precision from tolerance
    param_decimals = max(0, -int(np.floor(np.log10(param_tolerance))))
    depth_decimals = max(0, -int(np.floor(np.log10(depth_tolerance))))

    # Create normalized outlier lookup with rounded values
    outliers_lookup = manual_outliers_df.copy()
    outliers_lookup["_loc_key"] = (
        outliers_lookup["Location ID"].astype(str).str.strip().str.upper()
    )
    outliers_lookup["_param_rounded"] = outliers_lookup["parameter_value"].round(
        param_decimals
    )
    outliers_lookup["_y_rounded"] = outliers_lookup["y_value"].round(depth_decimals)
    # Keep only necessary columns for merge
    outliers_lookup = outliers_lookup[
        ["_loc_key", "_param_rounded", "_y_rounded"]
    ].drop_duplicates()

    total_marked = 0

    for formation_name, csv_dict in formation_groups.items():
        for csv_name, df in csv_dict.items():
            # Initialize column
            df["is_manual_outlier"] = False

            # Determine x-axis column
            if x_column_name is not None:
                param_col = x_column_name
            else:
                matching_mappings = parameter_mappings[
                    parameter_mappings["csv_file"] == csv_name
                ]
                if matching_mappings.empty:
                    continue
                param_col = matching_mappings["column_name"].iloc[0]

            if param_col not in df.columns or y_column_name not in df.columns:
                continue

            if df.empty:
                continue

            # === VECTORIZED MATCHING ===
            # Create temporary rounded columns for matching
            df["_loc_key"] = df["Location ID"].astype(str).str.strip().str.upper()
            df["_param_rounded"] = df[param_col].round(param_decimals)
            df["_y_rounded"] = df[y_column_name].round(depth_decimals)

            # Merge to find matches (indicator column shows which rows matched)
            merged = df.merge(
                outliers_lookup,
                on=["_loc_key", "_param_rounded", "_y_rounded"],
                how="left",
                indicator=True,
            )

            # Mark matched rows as outliers
            match_mask = merged["_merge"] == "both"
            matched_count = match_mask.sum()

            if matched_count > 0:
                # Get original indices that matched
                matched_indices = df.index[match_mask.values]
                df.loc[matched_indices, "is_manual_outlier"] = True
                total_marked += matched_count
                logger.info(
                    f"  ✅ {formation_name} | {csv_name}: Marked {matched_count} manual outliers"
                )

            # Clean up temporary columns
            df.drop(
                columns=["_loc_key", "_param_rounded", "_y_rounded"],
                inplace=True,
                errors="ignore",
            )

    logger.info(f"✅ Marking complete: Total of {total_marked} manual outliers marked")


def mark_manual_additions(
    formation_groups: Dict[str, Dict[str, pd.DataFrame]],
    manual_additions_df: Optional[pd.DataFrame],
    parameter_mappings: pd.DataFrame,
    param_tolerance: float = 0.01,
    depth_tolerance: float = 0.01,
    y_column_name: str = "Top Depth",
    x_column_name: Optional[str] = None,
) -> None:
    """
    Mark manually identified data points to add back to plots.

    Adds 'is_manual_addition' boolean column to each DataFrame based on matching
    Location ID, parameter value, and y-value from the manual additions Excel.
    These points will be included in 'without outliers' plots even if they were
    flagged as outliers by the IQR algorithm.

    PERFORMANCE: Vectorized approach using merge is 20-50× faster than nested iterrows.
    Original O(n×m) complexity reduced to O(n+m) via rounded-value merge.

    Args:
        formation_groups: Nested dict of formation data (MODIFIED IN-PLACE)
                         {formation_name: {csv_name: DataFrame}}
        manual_additions_df: DataFrame with manual additions from Excel (flat, all formations)
        parameter_mappings: Parameter mapping DataFrame with columns
                           [csv_file, column_name, priority_rank, quality_score]
        param_tolerance: Tolerance for matching parameter values (default 0.01 for 2-decimal rounding)
        depth_tolerance: Tolerance for matching y-values (default 0.01 for 2-decimal rounding)
        y_column_name: Name of the y-axis column in DataFrames (default "Top Depth")
                      For depth-based plots: "Top Depth"
                      For scatter plots: e.g., "Plasticity Index", "CoefficientConsolidation_unified"
        x_column_name: Explicit name of the x-axis column (optional)
                      If None, uses first column from parameter_mappings
                      For dual-parameter plots (e.g., CV vs Cell Pressure): "Cell Pressure_unified"

    Side Effects:
        Modifies formation_groups in-place by adding 'is_manual_addition' column

    Matching Logic (Vectorized):
        1. Round parameter and y-values to tolerance boundaries
        2. Normalize Location IDs to uppercase
        3. Use merge to find matches in O(n+m) time
        4. Mark matched rows with is_manual_addition=True
    """
    if manual_additions_df is None or manual_additions_df.empty:
        logger.info(
            "⏭️ No manual additions to mark - adding False column for consistency"
        )
        # Add column with all False values for consistency
        for csv_dict in formation_groups.values():
            for df in csv_dict.values():
                df["is_manual_addition"] = False
        return

    logger.info("🚀 Marking manually identified additions (vectorized)...")

    # === PREPARE ADDITIONS LOOKUP TABLE (VECTORIZED) ===
    # Calculate rounding precision from tolerance
    param_decimals = max(0, -int(np.floor(np.log10(param_tolerance))))
    depth_decimals = max(0, -int(np.floor(np.log10(depth_tolerance))))

    # Create normalized additions lookup with rounded values
    additions_lookup = manual_additions_df.copy()
    additions_lookup["_loc_key"] = (
        additions_lookup["Location ID"].astype(str).str.strip().str.upper()
    )
    additions_lookup["_param_rounded"] = additions_lookup["parameter_value"].round(
        param_decimals
    )
    additions_lookup["_y_rounded"] = additions_lookup["y_value"].round(depth_decimals)
    # Keep only necessary columns for merge
    additions_lookup = additions_lookup[
        ["_loc_key", "_param_rounded", "_y_rounded"]
    ].drop_duplicates()

    total_marked = 0

    for formation_name, csv_dict in formation_groups.items():
        for csv_name, df in csv_dict.items():
            # Initialize column
            df["is_manual_addition"] = False

            # Determine x-axis column
            if x_column_name is not None:
                param_col = x_column_name
            else:
                matching_mappings = parameter_mappings[
                    parameter_mappings["csv_file"] == csv_name
                ]
                if matching_mappings.empty:
                    continue
                param_col = matching_mappings["column_name"].iloc[0]

            if param_col not in df.columns or y_column_name not in df.columns:
                continue

            if df.empty:
                continue

            # === VECTORIZED MATCHING ===
            # Create temporary rounded columns for matching
            df["_loc_key"] = df["Location ID"].astype(str).str.strip().str.upper()
            df["_param_rounded"] = df[param_col].round(param_decimals)
            df["_y_rounded"] = df[y_column_name].round(depth_decimals)

            # Merge to find matches (indicator column shows which rows matched)
            merged = df.merge(
                additions_lookup,
                on=["_loc_key", "_param_rounded", "_y_rounded"],
                how="left",
                indicator=True,
            )

            # Mark matched rows as additions
            match_mask = merged["_merge"] == "both"
            matched_count = match_mask.sum()

            if matched_count > 0:
                # Get original indices that matched
                matched_indices = df.index[match_mask.values]
                df.loc[matched_indices, "is_manual_addition"] = True
                total_marked += matched_count
                logger.info(
                    f"  ✅ {formation_name} | {csv_name}: Marked {matched_count} manual additions"
                )

            # Clean up temporary columns
            df.drop(
                columns=["_loc_key", "_param_rounded", "_y_rounded"],
                inplace=True,
                errors="ignore",
            )

    logger.info(f"✅ Marking complete: Total of {total_marked} manual additions marked")


# ═══════════════════════════════════════════════════════════════════════════
# 📊 SUMMARY AND EXPORT FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def print_manual_outlier_summary(
    manual_outliers_df: Optional[pd.DataFrame],
    formation_groups: Dict[str, Dict[str, pd.DataFrame]],
    parameter_mappings: pd.DataFrame,
    y_column_name: str = "Top Depth",
    x_column_name: Optional[str] = None,
    param_tolerance: float = 0.01,
    depth_tolerance: float = 0.01,
) -> None:
    """
    Print summary table of manual outlier identification status.

    Shows which manual outliers from the Excel file were successfully
    identified and excluded, and provides reasons for any that weren't.

    Args:
        manual_outliers_df: DataFrame with manual outliers from Excel
        formation_groups: Formation data with is_manual_outlier column
        parameter_mappings: Parameter mappings to find column names
        y_column_name: Name of the y-axis column in DataFrames (default "Top Depth")
                      For depth-based plots: "Top Depth"
                      For scatter plots: e.g., "Plasticity Index", "CoefficientConsolidation_unified"
        x_column_name: Explicit name of the x-axis column (optional)
                      If None, uses first column from parameter_mappings
                      For dual-parameter plots: e.g., "Cell Pressure_unified"
        param_tolerance: Tolerance for matching parameter values (default 0.01)
                        Should match the tolerance used in mark_manual_outliers()
        depth_tolerance: Tolerance for matching depth values (default 0.01)
                        Should match the tolerance used in mark_manual_outliers()

    Output Format:
        Summary statistics + detailed table with columns:
        [#, Location ID, x (Param), y (Value), Test Type, Geology Code 2, Excluded?, Reason]
    """
    if manual_outliers_df is None or manual_outliers_df.empty:
        logger.info("⏭️ No manual outliers loaded - skipping summary")
        return

    logger.info("")
    logger.info("=" * 150)
    logger.info("📋 MANUAL OUTLIER EXCLUSION SUMMARY")
    logger.info("=" * 150)
    logger.info("")

    # Track identification status
    results = []

    for idx, outlier_row in manual_outliers_df.iterrows():
        location_id = outlier_row["Location ID"]
        param_value = outlier_row["parameter_value"]
        y_value = outlier_row["y_value"]
        test_type = outlier_row.get("Test Type", "Unknown")
        geology_code_2 = outlier_row.get("Geology Code 2", "Unknown")
        notes = outlier_row.get("Notes", "")

        # Search for this outlier in formation groups
        identified = False
        reason = "Not found in any formation data"

        for formation_name, csv_dict in formation_groups.items():
            for csv_name, df in csv_dict.items():
                # Determine x-axis column (same logic as mark_manual_outliers)
                if x_column_name is not None:
                    # Use explicit x column (for dual-parameter plots)
                    param_col = x_column_name
                else:
                    # Get parameter column from mappings (for single-parameter plots)
                    matching_mappings = parameter_mappings[
                        parameter_mappings["csv_file"] == csv_name
                    ]
                    if matching_mappings.empty:
                        continue
                    param_col = matching_mappings["column_name"].iloc[0]

                if param_col not in df.columns or y_column_name not in df.columns:
                    continue

                # Check if this location+value combination exists and is marked
                location_matches = df[df["Location ID"] == location_id]

                if not location_matches.empty:
                    # Check for matching parameter and y values
                    # Use the same tolerance as mark_manual_outliers() for consistency
                    for _, row in location_matches.iterrows():
                        param_match = np.isclose(
                            row[param_col], param_value, atol=param_tolerance
                        )
                        y_match = np.isclose(
                            row[y_column_name], y_value, atol=depth_tolerance
                        )

                        if param_match and y_match:
                            # Found the data point - check if marked as manual outlier
                            if "is_manual_outlier" in df.columns:
                                if row.get("is_manual_outlier", False):
                                    identified = True
                                    reason = "✅ Successfully identified and excluded"
                                else:
                                    reason = "Found but not marked (possible tolerance mismatch)"
                            else:
                                reason = "Found but is_manual_outlier column missing"
                            break

                    if not identified and reason == "Not found in any formation data":
                        reason = "Location ID exists but parameter/y-value don't match"

                if identified:
                    break

            if identified:
                break

        results.append(
            {
                "Entry #": idx + 1,
                "Location ID": location_id,
                "x (Param)": f"{param_value:.2f}",
                "y (Value)": f"{y_value:.2f}",
                "Test Type": test_type,
                "Geology Code 2": geology_code_2,
                "Excluded?": "✅ Yes" if identified else "❌ No",
                "Reason": reason,
                "Notes": notes,
            }
        )

    # Summary statistics
    total = len(results)
    identified_count = sum(1 for r in results if r["Excluded?"] == "✅ Yes")

    logger.info("📊 Summary Statistics:")
    logger.info(f"   Total manual outlier entries in Excel: {total}")
    logger.info(
        f"   Successfully identified & excluded: {identified_count} ({identified_count/total*100:.1f}%)"
    )
    logger.info(
        f"   Not identified: {total - identified_count} ({(total - identified_count)/total*100:.1f}%)"
    )
    logger.info("")

    # Print table header
    logger.info("📋 Detailed Breakdown:")
    logger.info("")
    header = (
        f"{'#':<5} | {'Location ID':<12} | {'x (Param)':<10} | {'y (Depth)':<10} | "
        f"{'Test Type':<25} | {'Geology Code 2':<15} | {'Excluded?':<12} | {'Reason':<50}"
    )
    logger.info(header)
    logger.info("-" * len(header))

    # Print table rows
    for result in results:
        logger.info(
            f"{result['Entry #']:<5} | {result['Location ID']:<12} | {result['x (Param)']:<10} | "
            f"{result['y (Value)']:<10} | {result['Test Type']:<25} | {result['Geology Code 2']:<15} | "
            f"{result['Excluded?']:<12} | {result['Reason']:<50}"
        )

    logger.info("")
    logger.info("=" * 150)


def print_manual_addition_summary(
    manual_additions_df: Optional[pd.DataFrame],
    formation_groups: Dict[str, Dict[str, pd.DataFrame]],
    parameter_mappings: pd.DataFrame,
    y_column_name: str = "Top Depth",
    x_column_name: Optional[str] = None,
) -> None:
    """
    Print summary table of manual addition identification status.

    Shows which manual additions from the Excel file were successfully
    identified and included, and provides reasons for any that weren't.

    Args:
        manual_additions_df: DataFrame with manual additions from Excel (flat, all formations)
        formation_groups: Formation data with is_manual_addition column
        parameter_mappings: Parameter mappings to find column names
        y_column_name: Name of the y-axis column in DataFrames (default "Top Depth")
        x_column_name: Explicit name of the x-axis column (optional)

    Output Format:
        Summary statistics + detailed table with columns:
        [#, Location ID, x (Param), y (Value), Formation, Added?, Reason]
    """
    if manual_additions_df is None or manual_additions_df.empty:
        logger.info("⏭️ No manual additions loaded - skipping summary")
        return

    logger.info("")
    logger.info("=" * 150)
    logger.info("📋 MANUAL ADDITION INCLUSION SUMMARY")
    logger.info("=" * 150)
    logger.info("")

    # Track identification status
    results = []

    for idx, addition_row in manual_additions_df.iterrows():
        location_id = addition_row["Location ID"]
        param_value = addition_row["parameter_value"]
        y_value = addition_row["y_value"]
        formation = addition_row.get("Formation", "Unknown")
        test_type = addition_row.get("Test Type", "Unknown")

        # Search for this addition in formation groups
        identified = False
        reason = "Not found in any formation data"

        for formation_name, csv_dict in formation_groups.items():
            for csv_name, df in csv_dict.items():
                # Determine x-axis column (same logic as mark_manual_outliers)
                if x_column_name is not None:
                    # Use explicit x column (for dual-parameter plots)
                    param_col = x_column_name
                else:
                    # Get parameter column from mappings (for single-parameter plots)
                    matching_mappings = parameter_mappings[
                        parameter_mappings["csv_file"] == csv_name
                    ]
                    if matching_mappings.empty:
                        continue
                    param_col = matching_mappings["column_name"].iloc[0]

                if param_col not in df.columns or y_column_name not in df.columns:
                    continue

                # Check if this location+value combination exists and is marked
                location_matches = df[df["Location ID"] == location_id]

                if not location_matches.empty:
                    # Check for matching parameter and y values
                    for _, row in location_matches.iterrows():
                        param_match = np.isclose(row[param_col], param_value, atol=1e-5)
                        y_match = np.isclose(row[y_column_name], y_value, atol=1e-5)

                        if param_match and y_match:
                            # Found the data point - check if marked as manual addition
                            if "is_manual_addition" in df.columns:
                                if row.get("is_manual_addition", False):
                                    identified = True
                                    reason = "✅ Successfully identified and included"
                                else:
                                    reason = "Found but not marked (possible tolerance mismatch)"
                            else:
                                reason = "Found but is_manual_addition column missing"
                            break

                    if not identified and reason == "Not found in any formation data":
                        reason = "Location ID exists but parameter/y-value don't match"

                if identified:
                    break

            if identified:
                break

        results.append(
            {
                "Entry #": idx + 1,
                "Location ID": location_id,
                "x (Param)": f"{param_value:.2f}",
                "y (Value)": f"{y_value:.2f}",
                "Formation": formation,
                "Added?": "✅ Yes" if identified else "❌ No",
                "Reason": reason,
            }
        )

    # Summary statistics
    total = len(results)
    identified_count = sum(1 for r in results if r["Added?"] == "✅ Yes")

    logger.info("📊 Summary Statistics:")
    logger.info(f"   Total manual addition entries in Excel: {total}")
    logger.info(
        f"   Successfully identified & included: {identified_count} ({identified_count/total*100:.1f}%)"
    )
    logger.info(
        f"   Not identified: {total - identified_count} ({(total - identified_count)/total*100:.1f}%)"
    )
    logger.info("")

    # Print table header
    logger.info("📋 Detailed Breakdown:")
    logger.info("")
    header = (
        f"{'#':<5} | {'Location ID':<12} | {'x (Param)':<10} | {'y (Value)':<10} | "
        f"{'Formation':<40} | {'Added?':<12} | {'Reason':<50}"
    )
    logger.info(header)
    logger.info("-" * len(header))

    # Print table rows
    for result in results:
        logger.info(
            f"{result['Entry #']:<5} | {result['Location ID']:<12} | {result['x (Param)']:<10} | "
            f"{result['y (Value)']:<10} | {result['Formation']:<40} | {result['Added?']:<12} | "
            f"{result['Reason']:<50}"
        )

    logger.info("")
    logger.info("=" * 150)


def export_manual_data_changes_csv(
    output_folder: str,
    parameter_name: str,
    manual_outliers_df: Optional[pd.DataFrame],
    manual_additions_df: Optional[pd.DataFrame],
    formation_groups: Dict[str, Dict[str, pd.DataFrame]],
    manual_additions_by_formation: Dict[str, pd.DataFrame],
    parameter_mappings: pd.DataFrame,
    param_tolerance: float = 0.01,
    depth_tolerance: float = 0.01,
) -> None:
    """
    Export CSV summaries of Data to Remove and Data to Add changes.

    Creates two CSV files in the investigation_series/manually_modified folder:
    1. data_removed.csv - Points from Data to Remove.xlsx and their identification status
    2. data_added.csv - Points from Data to Add.xlsx and their identification status

    CSV files are created even if no data was added or removed (empty files with headers).

    Args:
        output_folder: Base output folder path
        parameter_name: Parameter name for subfolder
        manual_outliers_df: DataFrame with manual outliers from Excel
        manual_additions_df: DataFrame with manual additions from Excel (flat, all formations)
        formation_groups: Formation data with is_manual_outlier/is_manual_addition columns
        manual_additions_by_formation: Dict mapping formations to manually added DataFrames
        parameter_mappings: Parameter mappings to find column names
        param_tolerance: Tolerance for matching parameter values (default 0.01 for 2-decimal rounding)
        depth_tolerance: Tolerance for matching y-values (default 0.01 for 2-decimal rounding)

    Side Effects:
        Creates CSV files in {output_folder}/{parameter_name}/investigation_series/manually_modified/
        - data_removed.csv
        - data_added.csv
    """
    # Create output directory
    manually_modified_folder = (
        Path(output_folder)
        / parameter_name
        / "investigation_series"
        / "manually_modified"
    )
    manually_modified_folder.mkdir(parents=True, exist_ok=True)

    logger.info("🚀 Exporting manual data changes to CSV...")

    # === EXPORT DATA TO REMOVE ===
    removed_csv_path = manually_modified_folder / "data_removed.csv"

    if manual_outliers_df is None or manual_outliers_df.empty:
        # Create empty CSV with headers
        empty_df = pd.DataFrame(
            columns=[
                "Entry #",
                "Location ID",
                "Parameter Value",
                "Y Value",
                "Test Type",
                "Successfully Excluded?",
                "Status",
                "Notes",
            ]
        )
        empty_df.to_csv(removed_csv_path, index=False, encoding="utf-8-sig")
        logger.info(f"  📄 Created empty data_removed.csv (no data to remove)")
    else:
        # Process manual outliers (implementation similar to print_manual_outlier_summary)
        results = []
        for idx, outlier_row in manual_outliers_df.iterrows():
            location_id = outlier_row["Location ID"]
            param_value = outlier_row["parameter_value"]
            y_value = outlier_row["y_value"]
            test_type = outlier_row.get("Test Type", "Unknown")
            notes = outlier_row.get("Notes", "")

            # Search for this outlier in formation groups
            identified = False
            status = "Not found in any formation data"

            for formation_name, csv_dict in formation_groups.items():
                for csv_name, df in csv_dict.items():
                    matching_mappings = parameter_mappings[
                        parameter_mappings["csv_file"] == csv_name
                    ]
                    if matching_mappings.empty:
                        continue

                    param_col = matching_mappings["column_name"].iloc[0]

                    if param_col not in df.columns or "Top Depth" not in df.columns:
                        continue

                    location_matches = df[df["Location ID"] == location_id]

                    if not location_matches.empty:
                        for _, row in location_matches.iterrows():
                            param_match = np.isclose(
                                row[param_col], param_value, atol=param_tolerance
                            )
                            y_match = np.isclose(
                                row["Top Depth"], y_value, atol=depth_tolerance
                            )

                            if param_match and y_match:
                                if "is_manual_outlier" in df.columns:
                                    if row.get("is_manual_outlier", False):
                                        identified = True
                                        status = "Successfully identified and excluded"
                                    else:
                                        status = "Found but not marked"
                                else:
                                    status = "is_manual_outlier column missing"
                                break

                        if (
                            not identified
                            and status == "Not found in any formation data"
                        ):
                            status = "Location exists but values don't match"

                    if identified:
                        break

                if identified:
                    break

            results.append(
                {
                    "Entry #": idx + 1,
                    "Location ID": location_id,
                    "Parameter Value": param_value,
                    "Y Value": y_value,
                    "Test Type": test_type,
                    "Successfully Excluded?": "Yes" if identified else "No",
                    "Status": status,
                    "Notes": notes,
                }
            )

        df_results = pd.DataFrame(results)
        df_results.to_csv(removed_csv_path, index=False, encoding="utf-8-sig")
        logger.info(
            f"  ✅ Exported data_removed.csv ({len(df_results)} entries, {sum(df_results['Successfully Excluded?'] == 'Yes')} excluded)"
        )

    # === EXPORT DATA TO ADD ===
    added_csv_path = manually_modified_folder / "data_added.csv"

    if manual_additions_df is None or manual_additions_df.empty:
        # Create empty CSV with headers
        empty_df = pd.DataFrame(
            columns=[
                "Entry #",
                "Location ID",
                "Parameter Value",
                "Y Value",
                "Formation",
                "Test Type",
                "Successfully Added?",
                "Status",
            ]
        )
        empty_df.to_csv(added_csv_path, index=False, encoding="utf-8-sig")
        logger.info(f"  📄 Created empty data_added.csv (no data to add)")
    else:
        # Process manual additions - check manual_additions_by_formation
        results = []
        for idx, addition_row in manual_additions_df.iterrows():
            location_id = addition_row["Location ID"]
            param_value = addition_row["parameter_value"]
            y_value = addition_row["y_value"]
            formation = addition_row.get("Formation", "Unknown")
            test_type = addition_row.get("Test Type", "Unknown")

            # Check if this addition exists in manual_additions_by_formation
            identified = False
            status = "Not found in manual additions structure"

            # Check manual_additions_by_formation dictionary (correct location)
            if formation in manual_additions_by_formation:
                formation_df = manual_additions_by_formation[formation]

                # Check for matching parameter and y values
                for _, row in formation_df.iterrows():
                    location_match = row["Location ID"] == location_id
                    param_match = np.isclose(
                        row["parameter_value"], param_value, atol=param_tolerance
                    )
                    y_match = np.isclose(row["y_value"], y_value, atol=depth_tolerance)

                    if location_match and param_match and y_match:
                        identified = True
                        status = f"Successfully added to {formation}"
                        break

            if not identified:
                # Fallback: Check if it was merged into formation_groups
                for formation_name, csv_dict in formation_groups.items():
                    for csv_name, df in csv_dict.items():
                        matching_mappings = parameter_mappings[
                            parameter_mappings["csv_file"] == csv_name
                        ]
                        if matching_mappings.empty:
                            continue

                        param_col = matching_mappings["column_name"].iloc[0]

                        if param_col not in df.columns or "Top Depth" not in df.columns:
                            continue

                        location_matches = df[df["Location ID"] == location_id]

                        if not location_matches.empty:
                            for _, row in location_matches.iterrows():
                                param_match = np.isclose(
                                    row[param_col], param_value, atol=param_tolerance
                                )
                                y_match = np.isclose(
                                    row["Top Depth"], y_value, atol=depth_tolerance
                                )

                                if param_match and y_match:
                                    if "is_manual_addition" in df.columns:
                                        if row.get("is_manual_addition", False):
                                            identified = True
                                            status = "Successfully merged into formation_groups"
                                        else:
                                            status = "Found in formation_groups but not marked"
                                    else:
                                        status = "is_manual_addition column missing"
                                    break

                            if identified:
                                break

                    if identified:
                        break

            results.append(
                {
                    "Entry #": idx + 1,
                    "Location ID": location_id,
                    "Parameter Value": param_value,
                    "Y Value": y_value,
                    "Formation": formation,
                    "Test Type": test_type,
                    "Successfully Added?": "Yes" if identified else "No",
                    "Status": status,
                }
            )

        df_results = pd.DataFrame(results)
        df_results.to_csv(added_csv_path, index=False, encoding="utf-8-sig")
        logger.info(
            f"  ✅ Exported data_added.csv ({len(df_results)} entries, {sum(df_results['Successfully Added?'] == 'Yes')} added)"
        )

    # Use absolute path to avoid ValueError when folders are at different levels
    logger.info(f"✅ Manual data changes exported to {manually_modified_folder}")


# ═══════════════════════════════════════════════════════════════════════════
# 📊 PSD-SPECIFIC MANUAL DATA FUNCTIONS
# These functions handle PSD data which is line-based (not point-based)
# Matching is done by Location ID + Top Depth (entire curves)
# ═══════════════════════════════════════════════════════════════════════════


def load_manual_outliers_psd(
    parameter_name: str,
    excel_file: str,
    sheet_mapping: Dict[str, str],
    enabled: bool = True,
) -> Optional[pd.DataFrame]:
    """
    Load manually identified PSD lines for removal from Excel (PSD-specific).

    PSD format differs from point-based scripts:
    - Excel columns: Location ID, Top Depth, Test Type, Geology Code 2, Notes
    - Matches entire lines (curves) by Location ID + Top Depth, not individual points

    Args:
        parameter_name: Parameter name (e.g., "ParticleSizeDistribution")
        excel_file: Path to Excel file with manual outliers
        sheet_mapping: Dict mapping parameter names to sheet names
        enabled: Master toggle for manual outlier loading

    Returns:
        DataFrame with columns [Location ID, Top Depth, Test Type, Geology Code 2, Notes]
        or None if disabled/error occurs
    """
    if not enabled:
        logger.info("⏭️ Manual outlier exclusion disabled")
        return None

    sheet_name = sheet_mapping.get(parameter_name)
    if not sheet_name:
        logger.warning(
            f"⚠️ No sheet mapping found for parameter '{parameter_name}' in manual outlier config"
        )
        return None

    try:
        logger.info(
            f"💾 Loading manual outliers from '{excel_file}' (Sheet: '{sheet_name}')..."
        )
        df_outliers = pd.read_excel(excel_file, sheet_name=sheet_name)

        # Verify required columns for PSD format
        required_cols = ["Location ID", "Top Depth"]
        if not all(col in df_outliers.columns for col in required_cols):
            logger.error(
                f"❌ Manual outlier Excel sheet '{sheet_name}' is missing required columns: {required_cols}"
            )
            logger.error(f"   Available columns: {list(df_outliers.columns)}")
            return None

        # Clean up Location IDs (strip whitespace and convert to uppercase)
        df_outliers["Location ID"] = (
            df_outliers["Location ID"].astype(str).str.strip().str.upper()
        )

        logger.info(
            f"✅ Loaded {len(df_outliers)} manually identified PSD lines to remove"
        )
        return df_outliers

    except FileNotFoundError:
        logger.error(f"❌ Manual outlier Excel file not found: {excel_file}")
        return None
    except Exception as e:
        logger.error(f"❌ Failed to load manual outliers: {e}")
        return None


def mark_manual_outliers_psd(
    formation_groups: Dict[str, Dict[str, pd.DataFrame]],
    manual_outliers_df: Optional[pd.DataFrame],
    depth_tolerance: float = 1e-5,
) -> None:
    """
    Mark manually identified PSD lines for removal (PSD-specific implementation).

    Unlike point-based scripts, PSD operates on entire lines (curves) per sample.
    This function marks all data points that belong to a sample (Location ID + Top Depth)
    identified in the manual outliers Excel as outliers.

    Args:
        formation_groups: Nested dict of formation data (MODIFIED IN-PLACE)
                         {formation_name: {csv_name: DataFrame}}
        manual_outliers_df: DataFrame with columns [Location ID, Top Depth, ...]
        depth_tolerance: Tolerance for matching depth values (e.g., 1e-5)

    Side Effects:
        Modifies formation_groups in-place by adding 'is_manual_outlier' column

    Matching Logic:
        For each DataFrame row, check if:
        1. Location ID matches exactly (after stripping whitespace)
        2. Top Depth matches within depth_tolerance

        If both match, mark ALL points with that Location ID + Top Depth as outliers
        (entire PSD curve for that sample)
    """
    if manual_outliers_df is None or manual_outliers_df.empty:
        logger.info("🔍 No manual outliers defined - skipping marking")
        for formation_name, csv_dict in formation_groups.items():
            for csv_name, df in csv_dict.items():
                if not df.empty:
                    df["is_manual_outlier"] = False
        return

    logger.info("🚀 Marking manually identified PSD lines for removal...")

    total_marked = 0
    outliers_by_loc = manual_outliers_df.groupby("Location ID")

    for formation_name, csv_dict in formation_groups.items():
        for csv_name, df in csv_dict.items():
            if df.empty:
                continue

            # Initialize column
            df["is_manual_outlier"] = False

            # Group current dataframe by Location ID (uppercase) for efficiency
            if "Location ID" not in df.columns:
                continue

            for loc_id, loc_group in df.groupby("Location ID"):
                loc_id_clean = str(loc_id).strip().upper()

                # Check if this Location ID has manual outliers
                if loc_id_clean not in outliers_by_loc.groups:
                    continue

                outlier_rows = outliers_by_loc.get_group(loc_id_clean)

                # Match by Top Depth
                for _, outlier_row in outlier_rows.iterrows():
                    outlier_depth = outlier_row["Top Depth"]

                    # Find matching depths in current location group
                    depth_matches = loc_group[
                        np.isclose(
                            loc_group["Top Depth"],
                            outlier_depth,
                            atol=depth_tolerance,
                            rtol=0,
                        )
                    ]

                    if not depth_matches.empty:
                        # Mark ALL points with this Location ID + Top Depth
                        df.loc[depth_matches.index, "is_manual_outlier"] = True
                        marked_count = len(depth_matches)
                        total_marked += marked_count
                        logger.debug(
                            f"  Marked {marked_count} points for {loc_id_clean} at depth {outlier_depth}m in {csv_name}"
                        )

    logger.info(
        f"✅ Marking complete: Total of {total_marked} PSD data points marked for removal"
    )
