# Guide: Comparing Monolith vs Modular Plot Data

This guide explains how to systematically compare data points between monolith and modular plotting implementations. **Point-to-point coordinate comparison is THE MAIN EVENT** - a successful conversion requires 100% match on all coordinates.

---

## Table of Contents

1. [THE MAIN EVENT: Point-to-Point Comparison](#the-main-event-point-to-point-comparison)
2. [Quick Start Workflow](#quick-start-workflow)
3. [Debug Utilities Overview](#debug-utilities-overview)
4. [Step-by-Step Process](#step-by-step-process)
5. [Using the Comparison Module](#using-the-comparison-module)
6. [Common Issues Found](#common-issues-found)
7. [Debugging Checklist](#debugging-checklist)
8. [Cleanup](#cleanup)

---

## THE MAIN EVENT: Point-to-Point Comparison

### Why This Matters

When converting a monolith script to the modular architecture, the **ONLY** way to verify correctness is to compare every single data point coordinate between both implementations:

| Check                   | What It Validates                      |
| ----------------------- | -------------------------------------- |
| **Location ID matches** | Same boreholes/locations being plotted |
| **Depth matches**       | Same depth records selected            |
| **X value matches**     | X-axis parameter correctly extracted   |
| **Y value matches**     | Y-axis parameter correctly extracted   |

### Success Criteria

A successful conversion must show:
- ✅ **100% match** on all point coordinates
- ✅ **Same point count** per formation
- ✅ **Identical (Location, Depth, X, Y)** tuples

Any mismatch indicates a bug in the conversion that must be fixed.

### The Goal

```
✅ PERFECT MATCH: 100.0% (255/255)
🎉 ALL FORMATIONS MATCH - CONVERSION SUCCESSFUL!
```

---

## Quick Start Workflow

### The Standard Process (Every Conversion)

```
1. ADD LOGGING    →  Add debug logging to BOTH existing scripts
2. RUN BOTH       →  Execute monolith AND modular, capture output
3. EXTRACT POINTS →  Extract data points from logs
4. COMPARE 100%   →  Verify every point matches exactly
5. CLEANUP        →  Remove debug logging code
```

### Fastest Path

```powershell
# 1. Run both scripts with logging, capture to files
cd "c:\...\Old_SESRO Plotting Scripts"
python "Volume_Consolidation_Coefficient copy 6.py" 2>&1 | Out-File "..\logs\monolith_mv.log" -Encoding utf8

cd "c:\...\geotechnical_plotting\Plotting Scripts"
python "MVvsCellPressure.py" 2>&1 | Out-File "..\logs\modular_mv.log" -Encoding utf8

# 2. Extract points for target formation (e.g., KC UW)
Get-Content "..\logs\monolith_mv.log" | Select-String -Pattern "\[M\].*Depth=" | 
    ForEach-Object { $_.Line } | Out-File "..\logs\monolith_points.txt"

Get-Content "..\logs\modular_mv.log" | Select-String -Pattern "\[m\].*Depth=" | 
    ForEach-Object { $_.Line } | Out-File "..\logs\modular_points.txt"

# 3. Compare - NO OUTPUT = PERFECT MATCH
Compare-Object (Get-Content "..\logs\monolith_points.txt") (Get-Content "..\logs\modular_points.txt")
```

If `Compare-Object` returns **no output**, you have a 100% match!

---

## Debug Utilities Overview

The `debug_utils` module provides tools for this comparison:

```
geotechnical_plotting/
├── debug_utils/
│   ├── __init__.py              # Exports all utilities
│   ├── plot_data_logger.py      # Logging during execution
│   └── point_comparison.py      # Point extraction & comparison
```

### Key Functions

| Function                    | Purpose                                  |
| --------------------------- | ---------------------------------------- |
| `enable_debug_logging()`    | Enable logging for specific formations   |
| `log_formation_data()`      | Log data points during plotting          |
| `extract_points_from_log()` | Parse log file into DataPoint objects    |
| `compare_point_lists()`     | Compare two point lists, get match stats |
| `run_full_comparison()`     | Complete comparison workflow             |
| `quick_file_compare()`      | Compare extracted point files            |

---

## Step-by-Step Process

### Step 1: Add Debug Logging to BOTH Scripts

**CRITICAL**: Add logging to the EXISTING scripts. Do NOT recreate data extraction separately.

#### In the Modular Script (matplotlib_utils.py)

Find the `generate_xy_plot` function around line 1160 where `df_filtered` is prepared:

```python
# >>> ADD THIS LOGGING BLOCK <<<
# Debug logging for point-to-point comparison
if "Kimmeridge" in formation_name:  # Adjust formation filter as needed
    logger.info(f"")
    logger.info(f"{'='*80}")
    logger.info(f"[MODULAR] DEBUG: {formation_name}")
    logger.info(f"[MODULAR] csv_name: {csv_name}")
    logger.info(f"[MODULAR] x_column: {x_column}")
    logger.info(f"[MODULAR] y_column: {y_column}")
    logger.info(f"[MODULAR] rows: {len(df_filtered)}")
    logger.info(f"[MODULAR] Data points:")
    for idx, row in df_filtered.iterrows():
        x_val = row.get(x_column, "N/A")
        y_val = row.get(y_column, "N/A")
        loc_id = row.get("Location ID", row.get("LocationID", "N/A"))
        depth = row.get("Top Depth", row.get("DepthTop", "N/A"))
        logger.info(f"    [m] {loc_id} | Depth={depth} | X={x_val} | Y={y_val}")
    logger.info(f"{'='*80}")
```

#### In the Monolith Script

Find the equivalent plotting function where data is prepared for plotting:

```python
# >>> ADD THIS LOGGING BLOCK <<<
# Debug logging for point-to-point comparison
if "Kimmeridge" in formation_name:  # Adjust formation filter as needed
    logger.info(f"")
    logger.info(f"{'='*80}")
    logger.info(f"[MONOLITH] DEBUG: {formation_name}")
    logger.info(f"[MONOLITH] csv_name: {csv_name}")
    logger.info(f"[MONOLITH] x_column: {x_column}")
    logger.info(f"[MONOLITH] y_column: {y_column}")
    logger.info(f"[MONOLITH] rows: {len(df_filtered)}")
    logger.info(f"[MONOLITH] Data points:")
    for idx, row in df_filtered.iterrows():
        x_val = row.get(x_column, "N/A")
        y_val = row.get(y_column, "N/A")
        loc_id = row.get("Location ID", row.get("LocationID", "N/A"))
        depth = row.get("Top Depth", row.get("DepthTop", "N/A"))
        logger.info(f"    [M] {loc_id} | Depth={depth} | X={x_val} | Y={y_val}")
    logger.info(f"{'='*80}")
```

### Step 2: Run Both Scripts

```powershell
# Run monolith and capture output
cd "c:\...\Old_SESRO Plotting Scripts"
python "Volume_Consolidation_Coefficient copy 6.py" 2>&1 | Out-File "..\logs\monolith_mv.log" -Encoding utf8

# Run modular and capture output  
cd "c:\...\geotechnical_plotting\Plotting Scripts"
python "MVvsCellPressure.py" 2>&1 | Out-File "..\logs\modular_mv.log" -Encoding utf8
```

### Step 3: Extract Data Points

Extract just the data point lines from each log:

```powershell
# Extract monolith points (pattern [M])
Get-Content "..\logs\monolith_mv.log" | Select-String -Pattern "\[M\].*Depth=" | 
    ForEach-Object { $_.Line } | Out-File "..\logs\monolith_points.txt"

# Extract modular points (pattern [m])
Get-Content "..\logs\modular_mv.log" | Select-String -Pattern "\[m\].*Depth=" | 
    ForEach-Object { $_.Line } | Out-File "..\logs\modular_points.txt"

# Count points
(Get-Content "..\logs\monolith_points.txt").Count
(Get-Content "..\logs\modular_points.txt").Count
```

### Step 4: Compare Points (THE MAIN EVENT)

```powershell
# Compare - NO OUTPUT means 100% MATCH
Compare-Object (Get-Content "..\logs\monolith_points.txt") (Get-Content "..\logs\modular_points.txt")
```

**Expected Result**: No output = Perfect match!

If there ARE differences, the output will show:
- `<=` indicates lines only in monolith
- `=>` indicates lines only in modular

### Step 5: Cleanup

After successful comparison, remove the debug logging blocks from both scripts.

---

## Using the Comparison Module

For programmatic comparison, use the `point_comparison` module:

### Quick File Comparison

```python
from geotechnical_plotting.debug_utils import quick_file_compare

# Compare extracted point files
result = quick_file_compare(
    "logs/monolith_points.txt",
    "logs/modular_points.txt",
    "Kimmeridge Clay Formation (Weathered)"
)

if result.is_perfect_match:
    print("✅ CONVERSION SUCCESSFUL!")
else:
    print(f"❌ {result.match_percentage}% match - needs review")
```

### Full Log Comparison

```python
from geotechnical_plotting.debug_utils import run_full_comparison

# Compare full log files
results = run_full_comparison(
    "logs/monolith_mv.log",
    "logs/modular_mv.log",
    formation_filter="Kimmeridge"  # Optional filter
)

# Check if all formations match
all_match = all(r.is_perfect_match for r in results.values())
```

### Extract and Compare Programmatically

```python
from geotechnical_plotting.debug_utils import (
    extract_points_from_log,
    compare_formations,
    print_full_comparison_summary,
)

# Extract from both logs
monolith_data = extract_points_from_log("logs/monolith.log", "MONOLITH")
modular_data = extract_points_from_log("logs/modular.log", "MODULAR")

# Compare all formations
results = compare_formations(monolith_data, modular_data)

# Print detailed report
print_full_comparison_summary(results)
```

---

## Common Issues Found

### Issue 1: Wrong Column Name (Most Common)

**Symptom:** Y values are `nan` or completely different  
**Example:** Modular shows `Y=nan`, Monolith shows `Y=1.81`

**Root Cause:** Not checking for unified columns from row-level fallback

**Fix:**
```python
# BEFORE (wrong)
y_column = y_mappings["column_name"].iloc[0]

# AFTER (correct)
y_unified = f"{y_param_name}_unified"
y_column = (
    y_unified if y_unified in df.columns
    else y_mappings["column_name"].iloc[0]
)
```

### Issue 2: Filter Not Applied

**Symptom:** Modular has more points than monolith  
**Example:** Modular shows 265 points, Monolith shows 255

**Root Cause:** `is_manual_outlier` filter not being applied

**Fix:** Ensure filter is applied before plotting:
```python
if filter_column and filter_column in df.columns:
    df_filtered = df[~df[filter_column]].copy()
```

### Issue 3: Missing Formation Data

**Symptom:** Formation exists in monolith but missing in modular  
**Root Cause:** Formation mapping or CSV lookup issue

### Issue 4: Different X/Y Values

**Symptom:** Same point count but different coordinate values  
**Root Cause:** Different column being used, or transformation applied differently

### Issue 5: Empirical Calculations Missing (SPT N-to-cu Conversion)

**Symptom:** Same locations and depths but X values differ by a constant factor  
**Example:** Monolith X=366.43, Modular X=81.43 (factor ~4.5)

**Root Cause:** Monolith applies empirical conversion (e.g., SPT N × f1 = cu), modular uses raw values

**Fix:** Add empirical calculations config to modular script:
```python
CONFIG["empirical_calculations"] = {
    "spt_to_cu_factors": {
        "KC": 4.5, "GF": 4.5, "KC_W": 4.5, "KC_UW": 4.5,
        # ... all formations
        "default_f1_factor": 4.5,
    }
}
```

Then ensure orchestrator.py applies these calculations in Phase 2.

### Issue 6: Formation-Specific Location Filtering Missing

**Symptom:** Modular has extra points from specific location prefixes (e.g., OS01, OS02)  
**Example:** Modular shows OS01 boreholes that monolith filters out for KC formations

**Root Cause:** Monolith has `formation_specific_filters` that exclude certain locations from specific formations only

**Fix:** Add formation-specific filters to modular script:
```python
CONFIG["filtering"]["location_filter"]["formation_specific_filters"] = {
    "OS01": ["KC_W", "KC_UW"],  # OS01 excluded only from KC weathered/unweathered
    "OS02": ["KC_W", "KC_UW"],  # OS02 excluded only from KC weathered/unweathered
}
```

The filtering is applied in Phase 3a of the orchestrator after formation grouping.

### Issue 7: Test Pit or Additional Investigation Data

**Symptom:** Modular has extra TP (test pit) or BH points not in monolith  
**Example:** TP301, TP302 etc. appear in modular but not monolith

**Root Cause:** Different investigations being processed, or different folder filtering

**Investigation:** Check if the extra points are from specific investigations or CSV sources

---

## Debugging Checklist

When comparing monolith vs modular output, verify these in order:

### Pre-Comparison Checks

- [ ] **Debug logging added** to BOTH existing scripts (not new extraction code)
- [ ] **Same formation filter** used in both (e.g., "Kimmeridge")
- [ ] **Both scripts ran successfully** with no errors

### Point Comparison Checks

- [ ] **Point count matches** between monolith and modular
- [ ] **Location IDs match** (same boreholes selected)
- [ ] **Depths match** (same records selected)
- [ ] **X values match** (same column used)
- [ ] **Y values match** (same column used)

### If Mismatch Found

- [ ] Check column names in log output (x_column, y_column)
- [ ] Check for `_unified` column usage
- [ ] Check filter application (is_manual_outlier)
- [ ] Check row counts before/after filtering

---

## Cleanup

After successful comparison:

1. **Remove debug logging blocks** from both scripts
2. **Delete log files** in `logs/` folder
3. **Delete extracted point files** (monolith_points.txt, modular_points.txt)

```powershell
# Clean up log files
Remove-Item "logs\*_mv.log" -ErrorAction SilentlyContinue
Remove-Item "logs\*_points.txt" -ErrorAction SilentlyContinue
```

---

## Summary

**THE MAIN EVENT** of every monolith-to-modular conversion is point-to-point coordinate comparison:

1. **Add logging** to BOTH existing scripts
2. **Run both** and capture output to log files
3. **Extract points** from logs
4. **Compare 100%** - verify every coordinate matches
5. **Cleanup** debug code after success

A conversion is only successful when you achieve **100% match** on all data point coordinates.

---

## Appendix: Automated Comparison Script

For convenience, you can use the automated comparison runner in `tests/run_comparison.py`:

```powershell
# Run the full comparison workflow
cd "c:\...\Figures_3.0"
python tests/run_comparison.py
```

This script:
1. Runs both monolith and modular scripts
2. Captures output to `logs/` folder
3. Extracts debug points using the [M] and [m] markers
4. Compares points and reports match percentage

### Creating a New Comparison Script

To create a comparison for a different parameter:

```python
#!/usr/bin/env python3
"""
Run monolith and modular scripts and capture debug output for comparison.
"""

import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
LOGS_DIR = WORKSPACE / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Update these for your parameter
MONOLITH_SCRIPT = WORKSPACE / "Old_SESRO Plotting Scripts" / "YourMonolith.py"
MODULAR_SCRIPT = WORKSPACE / "geotechnical_plotting" / "Plotting Scripts" / "YourModular.py"

# ... (see tests/run_comparison.py for full implementation)
```

### Interpreting Results

| Result       | Meaning                                          |
| ------------ | ------------------------------------------------ |
| 100% match   | ✅ Conversion successful                          |
| 90%+ match   | Close - check formation filters or data sources  |
| 50-90% match | Configuration gap - check empirical calculations |
| <50% match   | Major issue - check column mappings              |

### Common Fix Progression

From our experience converting `UndrainedShearStrength`:

1. **52.2% match** → Missing SPT N-to-cu conversion (empirical calculations)
2. **83.1% match** → Missing formation-specific filters (OS01/OS02)  
3. **90.5% match** → Extra test pit data from different investigations

Each fix is cumulative - address issues in order of impact.
