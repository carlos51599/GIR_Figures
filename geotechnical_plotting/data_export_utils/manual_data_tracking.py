#!/usr/bin/env python3
"""
Filtered Data Tracking Module for SESRO Plotting Scripts

Generates CSV report documenting ALL raw data points with a Status column
indicating whether each point is present in the manually modified plot or not.

ARCHITECTURAL OVERVIEW:

Responsibility:
One-to-one comparison module that lists every raw data point from OpenGround CSVs
and marks each with a Status column ("Plotted" or "Excluded") based on whether
it appears in the final manually modified matplotlib plot.

Key Interactions:
- Input: Parameter name, parameter mappings, plotted data, output folder
- Processing: Re-load raw CSVs → Flatten plotted data → Match each raw row → Export
- Output: Complete data comparison CSV with Status column for every raw data point
- Zero coupling: Self-contained, works independently of pipeline internals

Navigation Guide:
Single entry point: track_filtered_data()
Helper functions: _load_raw_csvs, _flatten_plotted_data, _build_comparison_table, _export_csv

CONFIGURATION ARCHITECTURE:
Module-level CONFIG dictionary with all configurable settings.
Also accesses calling script's CONFIG for csv_source_folder path.

MODULE CONFIG SETTINGS:
- output.excluded_only: If True, only output excluded data (reduces file size)
- column_variations: Maps standardized column names to possible CSV variations
- matching.transformed_csv_types: CSVs that use location+depth matching only
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, Set, Tuple
import pandas as pd
import numpy as np
import sys

# Import geology processing function from data_pipeline
from ..data_pipeline import create_enhanced_geological_strata_column

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# 🏗️ MODULE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

CONFIG = {
    # ═══════════════════════════════════════════════════════════════════════
    # OUTPUT CONTROL CONFIGURATION
    # ═══════════════════════════════════════════════════════════════════════
    "output": {
        "excluded_only": True,  # MODIFICATION POINT: If True, only output excluded data (reduces file size)
        # When True: Output file contains only Status="Excluded" rows
        # When False: Output file contains ALL rows (both Plotted and Excluded)
        "filename": "filtered_data_tracker.csv",  # Output filename (same regardless of excluded_only setting)
        "subfolder": "data",  # Subfolder within parameter output folder
    },
    # ═══════════════════════════════════════════════════════════════════════
    # COLUMN NAME VARIATIONS
    # Maps standardized column names to possible variations found in CSVs
    # ═══════════════════════════════════════════════════════════════════════
    "column_variations": {
        "location_id": [
            "LocationID",
            "Location ID",
        ],
        "geology_code": [
            "GeologyCode",
            "Geology Code",
        ],
        "geology_code_description": [
            "GeologyCodeDescription",
            "Geology Code Description",
        ],
        "geology_code2": [
            "GeologyCode2",
            "Geology Code2",
            "Geology Code 2",
        ],
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
            "Ground Water Strike",
            "Top Depth",
            "ResponseZoneTop",
            "Depth Top",
            "Depth",
        ],
    },
    # ═══════════════════════════════════════════════════════════════════════
    # MATCHING CONFIGURATION
    # Controls how raw data is matched to plotted data
    # ═══════════════════════════════════════════════════════════════════════
    "matching": {
        # CSVs that use transformed values (e.g., SPT N→cu)
        # These use location+depth matching only (not parameter value)
        "transformed_csv_types": [
            "SPT by Geology.csv",
        ],
        # Fallback value for missing formation/geology
        "unknown_formation_value": "Unknown",
    },
    # ═══════════════════════════════════════════════════════════════════════
    # DIAGNOSTIC LOGGING CONFIGURATION
    # Controls verbose logging for specific CSV types
    # ═══════════════════════════════════════════════════════════════════════
    "diagnostics": {
        # CSV types that get detailed diagnostic logging
        "verbose_csv_types": [
            "CPT by Geology.csv",
        ],
        "sample_rows_count": 3,  # Number of sample rows to log for diagnostics
        "max_locations_to_show": 10,  # Max affected locations to show in warnings
    },
}


def track_filtered_data(
    parameter_name: str,
    param_mappings: pd.DataFrame,
    plotted_formation_groups: Dict[str, Dict[str, pd.DataFrame]],
    output_folder: Path,
) -> None:
    """
    Track ALL raw data points with status indicating presence in plotted data.

    Creates a one-to-one comparison: every raw data point is listed with a
    Status column showing "Plotted" or "Excluded" based on whether it appears
    in the manually modified matplotlib plot.

    Args:
        parameter_name: Parameter being analyzed (e.g., "UndrainedShearStrength")
        param_mappings: Parameter mappings from Phase 1
        plotted_formation_groups: Final plotted data from Phase 4
                                  Dict[formation_name, Dict[csv_name, DataFrame]]
        output_folder: Output folder for parameter (e.g., Output/UndrainedShearStrength)

    Output:
        Creates CSV file: {output_folder}/data/filtered_data_tracker.csv
        Columns: CSV_Source, Location_ID, Parameter_Value, Depth, Formation, Status
    """
    logger.info("🚀 Starting Phase 7: Filtered Data Tracking...")

    try:
        # Import CONFIG from calling script's global scope
        calling_module = sys.modules["__main__"]
        calling_config = calling_module.CONFIG

        # === STEP 1: LOAD RAW CSV DATA ===
        logger.info("📂 Loading raw OpenGround CSVs...")
        raw_data_dict = _load_raw_csvs(param_mappings, calling_config)

        if not raw_data_dict:
            logger.warning(
                "⚠️  No raw CSV data loaded - skipping filtered data tracking"
            )
            return

        # === STEP 2: FLATTEN PLOTTED DATA INTO SET OF KEYS ===
        logger.info("📊 Extracting plotted data points...")
        full_keys, location_depth_keys = _get_plotted_keys(
            plotted_formation_groups, param_mappings, parameter_name
        )

        total_raw = sum(len(df) for df in raw_data_dict.values())
        logger.info(f"   - Raw data points: {total_raw}")
        logger.info(f"   - Plotted data keys (full): {len(full_keys)}")
        logger.info(
            f"   - Plotted data keys (location+depth): {len(location_depth_keys)}"
        )

        # === STEP 3: BUILD COMPARISON TABLE ===
        logger.info("🔍 Building one-to-one comparison table...")
        comparison_df = _build_comparison_table(
            raw_data_dict,
            full_keys,
            location_depth_keys,
            param_mappings,
            parameter_name,
        )

        if comparison_df.empty:
            logger.warning("⚠️  No comparison data generated")
            return

        # === STEP 4: GET OUTPUT SETTINGS ===
        excluded_only = CONFIG["output"]["excluded_only"]

        # Summary statistics (before filtering)
        plotted_count = (comparison_df["Status"] == "Plotted").sum()
        excluded_count = (comparison_df["Status"] == "Excluded").sum()

        # === STEP 5: EXPORT CSV REPORT ===
        logger.info("💾 Exporting data comparison CSV...")
        _export_comparison_csv(
            comparison_df, output_folder, parameter_name, excluded_only
        )

        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ Phase 7 Complete: Data comparison CSV generated")
        logger.info(f"   - Total raw data points: {len(comparison_df)}")
        logger.info(f"   - Plotted: {plotted_count}")
        logger.info(f"   - Excluded: {excluded_count}")
        if excluded_only:
            logger.info(f"   - Output mode: EXCLUDED ONLY (reduced file size)")
        else:
            logger.info(f"   - Output mode: ALL DATA (full comparison)")
        logger.info("=" * 80)

        # === DETAILED EXCLUSION ANALYSIS ===
        _analyze_exclusion_reasons(comparison_df, param_mappings, parameter_name)

    except Exception as e:
        logger.error(f"❌ Phase 7 failed: {str(e)}")
        logger.error("Continuing workflow without filtered data tracking...")
        import traceback

        logger.error(traceback.format_exc())


def _analyze_exclusion_reasons(
    comparison_df: pd.DataFrame,
    param_mappings: pd.DataFrame,
    parameter_name: str,
) -> None:
    """
    Analyze and log detailed reasons for data point exclusions.

    This function provides transparency about WHY data points were excluded,
    breaking down exclusions by:
    - Null parameter values (no measurement recorded)
    - Null formation/geology (cannot be assigned to a formation plot)
    - Not matched in plotted data (filtered by other pipeline stages)

    Args:
        comparison_df: DataFrame with Status column from _build_comparison_table
        param_mappings: Parameter mappings for column lookup
        parameter_name: Parameter name for logging
    """
    # Get CONFIG values
    unknown_value = CONFIG["matching"]["unknown_formation_value"]
    max_locations = CONFIG["diagnostics"]["max_locations_to_show"]
    verbose_csv_types = set(CONFIG["diagnostics"]["verbose_csv_types"])
    sample_rows_count = CONFIG["diagnostics"]["sample_rows_count"]

    logger.info("")
    logger.info("=" * 80)
    logger.info("📋 DETAILED EXCLUSION ANALYSIS")
    logger.info("=" * 80)

    excluded = comparison_df[comparison_df["Status"] == "Excluded"]

    if excluded.empty:
        logger.info("   No exclusions to analyze - all data points were plotted!")
        return

    # Analyze by CSV source
    for csv_name in excluded["CSV_Source"].unique():
        csv_excluded = excluded[excluded["CSV_Source"] == csv_name]
        total_excluded = len(csv_excluded)

        # Count exclusion reasons
        null_param = csv_excluded["Parameter_Value"].isna().sum()
        null_formation = (
            csv_excluded["Formation"].isna()
            | (csv_excluded["Formation"] == unknown_value)
        ).sum()
        non_null_param = csv_excluded["Parameter_Value"].notna().sum()

        # Non-null param with null formation = data exists but no geology
        has_data_no_geology = (
            csv_excluded["Parameter_Value"].notna()
            & (
                csv_excluded["Formation"].isna()
                | (csv_excluded["Formation"] == unknown_value)
            )
        ).sum()

        # Non-null param with valid formation but still excluded = pipeline filter
        has_data_has_geology_still_excluded = (
            csv_excluded["Parameter_Value"].notna()
            & csv_excluded["Formation"].notna()
            & (csv_excluded["Formation"] != unknown_value)
        ).sum()

        logger.info(f"\n   📊 {csv_name}: {total_excluded} excluded rows")
        logger.info(f"      - Null parameter value: {null_param}")
        logger.info(
            f"      - Has data but NULL formation (cannot assign to plot): {has_data_no_geology}"
        )
        logger.info(
            f"      - Has data AND formation but not in plotted data: {has_data_has_geology_still_excluded}"
        )

        # If there are points with data but no geology, show sample locations
        if has_data_no_geology > 0:
            no_geology_rows = csv_excluded[
                csv_excluded["Parameter_Value"].notna()
                & (
                    csv_excluded["Formation"].isna()
                    | (csv_excluded["Formation"] == unknown_value)
                )
            ]
            affected_locations = no_geology_rows["Location_ID"].unique()
            logger.info(
                f"      ⚠️  Locations with data but missing geology: {list(affected_locations[:max_locations])}"
            )
            if len(affected_locations) > max_locations:
                logger.info(
                    f"         ... and {len(affected_locations) - max_locations} more"
                )

            # Additional info for verbose CSV types
            if csv_name in verbose_csv_types:
                logger.info(
                    f"      💡 {csv_name} often has parameter data calculated but GeologyCode is NULL"
                )
                logger.info(
                    f"         These points cannot be plotted because formation grouping requires GeologyCode"
                )

        # If there are points with data AND geology still excluded, investigate
        if has_data_has_geology_still_excluded > 0:
            logger.info(
                f"      🔍 {has_data_has_geology_still_excluded} points have data AND formation but were not plotted"
            )
            logger.info(f"         Possible reasons:")
            logger.info(f"           - Location ID filtered (BP/CCT prefix exclusion)")
            logger.info(f"           - Manual outlier exclusion")
            logger.info(f"           - Key matching precision issue")

            # Show sample of these problematic rows
            problem_rows = csv_excluded[
                csv_excluded["Parameter_Value"].notna()
                & csv_excluded["Formation"].notna()
                & (csv_excluded["Formation"] != unknown_value)
            ]
            if len(problem_rows) > 0:
                sample = problem_rows.head(sample_rows_count)
                logger.info(f"         Sample excluded rows with valid data:")
                for _, row in sample.iterrows():
                    logger.info(
                        f"           - {row['Location_ID']} | {row['Formation']} | "
                        f"depth={row['Depth']} | value={row['Parameter_Value']}"
                    )

    logger.info("")
    logger.info("=" * 80)


def _load_raw_csvs(
    param_mappings: pd.DataFrame, calling_config: Dict[str, Any]
) -> Dict[str, pd.DataFrame]:
    """
    Load raw OpenGround CSVs WITHOUT any filtering.

    Loads CSVs in original state, keeping all rows. Adds standardized columns
    (Location ID, Top Depth, Geological_Strata) for comparison.

    Args:
        param_mappings: Parameter mappings DataFrame
        calling_config: Configuration dictionary from calling script

    Returns:
        Dict mapping CSV names to raw DataFrames
    """
    csv_folder = Path(calling_config["parameter"]["csv_source_folder"])
    raw_data_dict = {}

    # Get unique CSV files for this parameter
    csv_files = param_mappings["csv_file"].unique()

    # Get column variations from module CONFIG
    col_vars = CONFIG["column_variations"]

    for csv_file in csv_files:
        csv_path = csv_folder / csv_file

        if not csv_path.exists():
            logger.warning(f"⚠️  CSV file not found: {csv_path}")
            continue

        try:
            # Load CSV
            df = pd.read_csv(csv_path, encoding="utf-8-sig", low_memory=False)
            df.columns = df.columns.str.strip()

            # === STANDARDIZE LOCATION ID ===
            for col_name in col_vars["location_id"]:
                if col_name in df.columns and "Location ID" not in df.columns:
                    df.rename(columns={col_name: "Location ID"}, inplace=True)
                    break

            # === STANDARDIZE DEPTH COLUMN ===
            for col_name in col_vars["top_depth"]:
                if col_name in df.columns and "Top Depth" not in df.columns:
                    df.rename(columns={col_name: "Top Depth"}, inplace=True)
                    break

            # === STANDARDIZE GEOLOGICAL STRATA ===
            # Use the same method as data_pipeline.py for consistent geology processing
            # including formation splitting (weathered/unweathered classification)
            geology_code_descriptions = calling_config.get("mappings", {}).get(
                "geology_code_descriptions", {}
            )
            formation_splitting_config = calling_config.get("mappings", {}).get(
                "formation_splitting", {"enabled": False}
            )
            df = create_enhanced_geological_strata_column(
                df,
                csv_file,
                geology_code_descriptions,
                col_vars,
                formation_splitting_config,
            )

            # === STANDARDIZE GEOLOGY CODE (primary) ===
            if "GeologyCode" not in df.columns:
                for col_name in col_vars["geology_code"]:
                    if col_name in df.columns:
                        df.rename(columns={col_name: "GeologyCode"}, inplace=True)
                        break

            # === STANDARDIZE GEOLOGY CODE 2 (detailed classification) ===
            if "GeologyCode2" not in df.columns:
                for col_name in col_vars["geology_code2"]:
                    if col_name in df.columns:
                        df.rename(columns={col_name: "GeologyCode2"}, inplace=True)
                        break

            # Keep all rows - no filtering
            raw_data_dict[csv_file] = df
            logger.info(f"   ✅ Loaded {csv_file}: {len(df)} raw rows")

        except Exception as e:
            logger.warning(f"⚠️  Failed to load {csv_file}: {e}")
            continue

    return raw_data_dict


def _get_plotted_keys(
    plotted_formation_groups: Dict[str, Dict[str, pd.DataFrame]],
    param_mappings: pd.DataFrame,
    parameter_name: str,
) -> Tuple[Set[str], Set[str]]:
    """
    Extract sets of composite keys from plotted data for fast lookup.

    Creates two types of composite keys:
    1. Full keys: Location_ID|Parameter_Value|Depth (for non-transformed data)
    2. Location-Depth keys: Location_ID|Depth (for transformed data like SPT→cu)

    IMPORTANT: Uses repr() for exact float representation to avoid floating-point
    precision issues. When floats are read from CSV and passed through pandas,
    their internal binary representation is preserved. Using repr() captures
    this exact representation, ensuring raw CSV values match plotted DataFrame
    values exactly without any rounding/formatting discrepancies.

    Args:
        plotted_formation_groups: Dict[formation_name, Dict[csv_name, DataFrame]]
        param_mappings: Parameter mappings DataFrame
        parameter_name: Parameter name for column lookup

    Returns:
        Tuple of (full_keys_set, location_depth_keys_set)
    """
    full_keys = set()
    location_depth_keys = set()

    # Counters for summary logging
    cpt_keys_added = 0

    for formation_name, csv_dict in plotted_formation_groups.items():
        for csv_name, df in csv_dict.items():
            # Find parameter column for this CSV
            param_mapping = param_mappings[
                (param_mappings["csv_file"] == csv_name)
                & (param_mappings["parameter"] == parameter_name)
            ]

            if param_mapping.empty:
                logger.debug(f"   ⚠️ No mapping for {csv_name} in {formation_name}")
                continue

            param_column = param_mapping["column_name"].iloc[0]

            if (
                param_column not in df.columns
                or "Top Depth" not in df.columns
                or "Location ID" not in df.columns
            ):
                logger.debug(
                    f"   ⚠️ Missing columns in {csv_name}/{formation_name}: "
                    f"param={param_column in df.columns}, depth={'Top Depth' in df.columns}, loc={'Location ID' in df.columns}"
                )
                continue

            is_cpt = csv_name == "CPT by Geology.csv"

            # Extract keys from each row
            for _, row in df.iterrows():
                location_id = row["Location ID"]
                param_value = row[param_column]
                depth = row["Top Depth"]

                # Skip null values
                if pd.isna(param_value) or pd.isna(depth) or pd.isna(location_id):
                    continue

                # Use repr() for exact float representation - no precision loss
                # This ensures keys like "CPT402|5.99" match exactly between
                # raw CSV loading and plotted DataFrame values
                full_key = (
                    f"{location_id}|{repr(float(param_value))}|{repr(float(depth))}"
                )
                location_depth_key = f"{location_id}|{repr(float(depth))}"

                full_keys.add(full_key)
                location_depth_keys.add(location_depth_key)

                if is_cpt:
                    cpt_keys_added += 1

    # Log CPT summary (useful for validation)
    if cpt_keys_added > 0:
        logger.info(f"   📊 CPT plotted keys extracted: {cpt_keys_added}")

    return full_keys, location_depth_keys


def _build_comparison_table(
    raw_data_dict: Dict[str, pd.DataFrame],
    full_keys: Set[str],
    location_depth_keys: Set[str],
    param_mappings: pd.DataFrame,
    parameter_name: str,
) -> pd.DataFrame:
    """
    Build complete comparison table with Status column for every raw data point.

    Each raw data row gets a Status of "Plotted" if it matches plotted data.

    Matching strategy:
    - For SPT/CPT data: Uses Location_ID + Depth matching (since N→cu transformation
      changes the parameter value, and CPT has high-density depth values)
    - For other data: Uses full Location_ID + Parameter_Value + Depth matching

    IMPORTANT: Uses repr() for exact float representation to match _get_plotted_keys().

    Args:
        raw_data_dict: Dict mapping CSV names to raw DataFrames
        full_keys: Set of composite keys (Location_ID|Parameter_Value|Depth)
        location_depth_keys: Set of location+depth keys (Location_ID|Depth)
        param_mappings: Parameter mappings DataFrame
        parameter_name: Parameter name for column lookup

    Returns:
        DataFrame with all raw data points and Status column
    """
    # Get transformed CSV types from module CONFIG
    # These use location+depth matching only (not parameter value)
    transformed_csv_types = set(CONFIG["matching"]["transformed_csv_types"])
    unknown_value = CONFIG["matching"]["unknown_formation_value"]
    verbose_csv_types = set(CONFIG["diagnostics"]["verbose_csv_types"])
    sample_rows_count = CONFIG["diagnostics"]["sample_rows_count"]

    all_rows = []

    for csv_name, raw_df in raw_data_dict.items():
        # Find parameter column for this CSV
        param_mapping = param_mappings[
            (param_mappings["csv_file"] == csv_name)
            & (param_mappings["parameter"] == parameter_name)
        ]

        if param_mapping.empty:
            logger.warning(f"   ⚠️  No parameter mapping for {csv_name}")
            continue

        param_column = param_mapping["column_name"].iloc[0]

        # Validate required columns exist
        if param_column not in raw_df.columns:
            logger.warning(f"   ⚠️  Column '{param_column}' not in {csv_name}")
            continue
        if "Top Depth" not in raw_df.columns:
            logger.warning(f"   ⚠️  Column 'Top Depth' not in {csv_name}")
            continue
        if "Location ID" not in raw_df.columns:
            logger.warning(f"   ⚠️  Column 'Location ID' not in {csv_name}")
            continue

        # Determine matching strategy for this CSV
        use_location_depth_only = csv_name in transformed_csv_types
        is_verbose = csv_name in verbose_csv_types

        # Verbose diagnostics for configured CSV types
        if is_verbose:
            logger.info(f"   🔍 Processing raw {csv_name} data: {len(raw_df)} rows")
            logger.info(
                f"      Column dtypes: {param_column}={raw_df[param_column].dtype}, "
                f"Top Depth={raw_df['Top Depth'].dtype}, Location ID={raw_df['Location ID'].dtype}"
            )

            # Sample first few non-null rows
            non_null_df = raw_df[
                raw_df[param_column].notna() & raw_df["Top Depth"].notna()
            ]
            sample_size = min(sample_rows_count, len(non_null_df))
            for idx in range(sample_size):
                row = non_null_df.iloc[idx]
                raw_key = f"{row['Location ID']}|{repr(float(row['Top Depth']))}"
                in_plotted = raw_key in location_depth_keys
                logger.info(
                    f"      Sample raw row {idx}: "
                    f"loc='{row['Location ID']}' "
                    f"param={repr(row[param_column])} "
                    f"depth={repr(row['Top Depth'])} "
                    f"key='{raw_key}' in_plotted={in_plotted}"
                )

        # Counters for verbose diagnostics
        verbose_null = 0
        verbose_matched = 0
        verbose_unmatched = 0
        verbose_no_geology = 0

        # Process each raw row
        for _, row in raw_df.iterrows():
            location_id = row["Location ID"]
            param_value = row[param_column]
            depth = row["Top Depth"]
            formation = row.get("Geological_Strata", unknown_value)

            # Extract GeologyCode (primary) if available
            geology_code = row.get("GeologyCode", None)

            # Extract GeologyCode2 if available (standardized in _load_raw_csvs)
            geology_code_2 = row.get("GeologyCode2", None)

            # Determine exclusion reason for transparency
            exclusion_reason = ""

            # Handle null values - still include in output with "Excluded" status
            if pd.isna(param_value) or pd.isna(depth) or pd.isna(location_id):
                status = "Excluded"
                if pd.isna(param_value):
                    exclusion_reason = "Null parameter value"
                elif pd.isna(depth):
                    exclusion_reason = "Null depth"
                else:
                    exclusion_reason = "Null location ID"
                if is_verbose:
                    verbose_null += 1
            else:
                # Check for missing formation (cannot assign to formation plot)
                has_valid_formation = (
                    pd.notna(formation)
                    and formation != unknown_value
                    and formation.strip() != ""
                )

                if not has_valid_formation:
                    # Data exists but no geology - cannot be plotted
                    status = "Excluded"
                    exclusion_reason = (
                        "Missing geology/formation (cannot assign to plot)"
                    )
                    if is_verbose:
                        verbose_no_geology += 1
                else:
                    # Choose matching strategy based on CSV type
                    if use_location_depth_only:
                        # SPT/CPT: match by location + depth only using repr() for exact match
                        location_depth_key = f"{location_id}|{repr(float(depth))}"
                        if location_depth_key in location_depth_keys:
                            status = "Plotted"
                            exclusion_reason = ""  # Not excluded
                            if is_verbose:
                                verbose_matched += 1
                        else:
                            status = "Excluded"
                            exclusion_reason = "Not matched in plotted data (likely location filter or key mismatch)"
                            if is_verbose:
                                verbose_unmatched += 1
                    else:
                        # Non-transformed data: match by full composite key using repr()
                        full_key = f"{location_id}|{repr(float(param_value))}|{repr(float(depth))}"
                        if full_key in full_keys:
                            status = "Plotted"
                            exclusion_reason = ""
                        else:
                            status = "Excluded"
                            exclusion_reason = "Not matched in plotted data"

            all_rows.append(
                {
                    "CSV_Source": csv_name,
                    "Location_ID": location_id,
                    "Parameter_Value": param_value,
                    "Depth": depth,
                    "Formation": formation,
                    "GeologyCode": geology_code,
                    "GeologyCode2": geology_code_2,
                    "Status": status,
                    "Exclusion_Reason": exclusion_reason,
                }
            )

        # Log verbose matching summary for configured CSV types
        if is_verbose:
            logger.info(f"   📊 {csv_name} raw data matching summary:")
            logger.info(f"      - Null values (auto-excluded): {verbose_null}")
            logger.info(
                f"      - Missing geology (has data but no formation): {verbose_no_geology}"
            )
            logger.info(f"      - Matched (Plotted): {verbose_matched}")
            logger.info(f"      - Unmatched (Excluded): {verbose_unmatched}")

            # If there are points with missing geology, this is the main issue
            if verbose_no_geology > 0:
                logger.warning(
                    f"      ⚠️ {verbose_no_geology} points have parameter data but NULL GeologyCode!"
                )
                logger.warning(
                    f"         These points CANNOT be plotted because formation grouping requires geology."
                )
                logger.warning(
                    f"         This is a data quality issue in the source OpenGround CSV."
                )

            # If many unmatched, log sample unmatched keys for diagnosis
            if verbose_unmatched > 0 and verbose_matched == 0:
                logger.warning(
                    f"      ⚠️ NO matches! Checking for key format mismatch..."
                )
                # Get sample raw keys and plotted keys for comparison
                sample_raw_keys = []
                for _, row in raw_df.head(sample_rows_count).iterrows():
                    if pd.notna(row["Top Depth"]) and pd.notna(row["Location ID"]):
                        sample_raw_keys.append(
                            f"{row['Location ID']}|{repr(float(row['Top Depth']))}"
                        )
                # Get sample plotted keys that might match this CSV type
                csv_prefix = csv_name.split(" ")[
                    0
                ]  # e.g., "CPT" from "CPT by Geology.csv"
                sample_plotted_keys = [
                    k
                    for k in list(location_depth_keys)[:sample_rows_count]
                    if k.startswith(csv_prefix)
                ]
                logger.warning(f"      Sample RAW keys: {sample_raw_keys}")
                logger.warning(f"      Sample PLOTTED keys: {sample_plotted_keys}")

    if all_rows:
        return pd.DataFrame(all_rows)
    else:
        return pd.DataFrame()


def _export_comparison_csv(
    comparison_df: pd.DataFrame,
    output_folder: Path,
    parameter_name: str,
    excluded_only: bool = False,
) -> None:
    """
    Export data comparison CSV with Status column.

    Output structure:
    - {output_folder}/{parameter_name}/data/filtered_data_tracker.csv
      (or filtered_data_tracker_excluded_only.csv when excluded_only=True)

    Columns: CSV_Source, Location_ID, Parameter_Value, Depth, Formation, Status
    Sorted by: CSV_Source, Formation, Depth

    Args:
        comparison_df: DataFrame with all raw data points and Status column
        output_folder: Output folder for parameter
        parameter_name: Parameter name (for path and logging)
        excluded_only: If True, only export rows with Status="Excluded"
    """
    # Convert to Path object if string is passed
    output_folder = Path(output_folder)

    # Get output settings from module CONFIG
    output_config = CONFIG["output"]
    subfolder = output_config["subfolder"]

    # Create output directory
    data_folder = output_folder / parameter_name / subfolder
    data_folder.mkdir(parents=True, exist_ok=True)

    # Filter to excluded only if toggle is set
    if excluded_only:
        export_df = comparison_df[comparison_df["Status"] == "Excluded"].copy()
        logger.info(f"   📋 Filtering to excluded data only ({len(export_df)} rows)")
    else:
        export_df = comparison_df.copy()

    output_filename = output_config["filename"]

    # Sort for readability
    comparison_df_sorted = export_df.sort_values(
        by=["CSV_Source", "Formation", "Depth"]
    ).reset_index(drop=True)

    # Export CSV
    output_path = data_folder / output_filename
    comparison_df_sorted.to_csv(output_path, index=False)

    logger.info(f"   ✅ Saved: {output_path}")

    # Print breakdown by status
    status_counts = comparison_df_sorted.groupby("Status").size()
    logger.info("\n   Status breakdown:")
    for status, count in status_counts.items():
        logger.info(f"     - {status}: {count}")

    # Print breakdown by CSV source
    csv_status = (
        comparison_df_sorted.groupby(["CSV_Source", "Status"])
        .size()
        .unstack(fill_value=0)
    )
    logger.info("\n   By CSV source:")
    for csv_name in csv_status.index:
        plotted = csv_status.loc[csv_name].get("Plotted", 0)
        excluded = csv_status.loc[csv_name].get("Excluded", 0)
        total = plotted + excluded
        logger.info(
            f"     - {csv_name}: {plotted}/{total} plotted ({excluded} excluded)"
        )
