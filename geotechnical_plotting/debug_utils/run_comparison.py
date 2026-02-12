#!/usr/bin/env python3
"""
Automated Monolith vs Modular Point Comparison Runner

This script runs both monolith and modular plotting scripts, captures their debug
output, extracts data points, and compares them to validate the conversion.

Usage:
    python run_comparison.py [parameter_name]

    # Examples:
    python run_comparison.py UndrainedShearStrength
    python run_comparison.py MVvsCellPressure

Prerequisites:
    1. Debug logging must be added to BOTH scripts with markers:
       - Monolith: [M] prefix (e.g., logger.info(f"[M] {loc} | Depth={d} | X={x}"))
       - Modular: [m] prefix (e.g., logger.info(f"[m] {loc} | Depth={d} | X={x}"))

    2. Both scripts must filter for the same formation (e.g., "Kimmeridge...Unweathered")

    3. Folder filtering should match (e.g., "manually_modified" in output path)

Results Interpretation:
    - 100% match: Conversion successful
    - 90%+ match: Close - check formation filters or data sources
    - 50-90% match: Configuration gap - check empirical calculations
    - <50% match: Major issue - check column mappings
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple, Set
from collections import defaultdict

# Workspace root (parent of geotechnical_plotting)
WORKSPACE = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = WORKSPACE / "logs"


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION - Update these for different parameters
# ═══════════════════════════════════════════════════════════════════════════

SCRIPT_CONFIGS = {
    "UndrainedShearStrength": {
        "monolith": "Old_SESRO Plotting Scripts/UndrainedShearStrength copy 13.py",
        "modular": "geotechnical_plotting/Plotting Scripts/UndrainedShearStrength.py",
        "log_prefix": "cu",
    },
    "MVvsCellPressure": {
        "monolith": "Old_SESRO Plotting Scripts/Volume_Consolidation_Coefficient copy 6.py",
        "modular": "geotechnical_plotting/Plotting Scripts/MVvsCellPressure.py",
        "log_prefix": "mv",
    },
    # Add more parameters here as needed
}


# ═══════════════════════════════════════════════════════════════════════════
# SCRIPT EXECUTION
# ═══════════════════════════════════════════════════════════════════════════


def run_script(script_path: Path, log_name: str) -> int:
    """
    Run a script and capture output to log file.

    Args:
        script_path: Path to the Python script
        log_name: Name for the log file (without extension)

    Returns:
        Exit code from the script
    """
    LOGS_DIR.mkdir(exist_ok=True)
    log_path = LOGS_DIR / f"{log_name}.log"
    print(f"Running {script_path.name}...")
    print(f"Output will be saved to: {log_path}")

    # Determine working directory
    # Monolith scripts expect to run from WORKSPACE root (Figures_3.0)
    # Modular scripts handle their own paths
    cwd = WORKSPACE if "Old_SESRO" in str(script_path) else str(script_path.parent)

    with open(log_path, "w", encoding="utf-8") as log_file:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        log_file.write(result.stdout)

    print(f"  Exit code: {result.returncode}")
    print(f"  Log saved to: {log_path}")
    return result.returncode


# ═══════════════════════════════════════════════════════════════════════════
# POINT EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════


def extract_points(log_path: Path, pattern: str, output_name: str) -> int:
    """
    Extract debug point lines from log file.

    Args:
        log_path: Path to the log file
        pattern: Pattern to search for (e.g., "[M]" or "[m]")
        output_name: Name for the output file (without extension)

    Returns:
        Number of points extracted
    """
    output_path = LOGS_DIR / f"{output_name}.txt"
    count = 0

    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    with open(output_path, "w", encoding="utf-8") as out:
        for line in lines:
            if pattern in line and "Depth=" in line:
                out.write(line.strip() + "\n")
                count += 1

    print(f"  Extracted {count} points to {output_path}")
    return count


def extract_data_portion(line: str) -> str:
    """
    Extract just the data portion (Location | Depth | X) from a log line.

    Strips timestamp and log level, extracts everything after the [M]/[m] marker.

    Args:
        line: Full log line

    Returns:
        Just the data portion (e.g., "BH208 | Depth=3.8 | X=58.5")
    """
    if " | Depth=" in line:
        for marker in ["[M]", "[m]", "[x]"]:
            if marker in line:
                idx = line.index(marker) + len(marker)
                return line[idx:].strip()
    return line.strip()


# ═══════════════════════════════════════════════════════════════════════════
# COMPARISON
# ═══════════════════════════════════════════════════════════════════════════


def compare_points() -> Tuple[bool, float, Set[str], Set[str]]:
    """
    Compare extracted points between monolith and modular.

    Returns:
        Tuple of (is_perfect_match, match_percentage, only_monolith, only_modular)
    """
    monolith_path = LOGS_DIR / "monolith_points.txt"
    modular_path = LOGS_DIR / "modular_points.txt"

    if not monolith_path.exists() or not modular_path.exists():
        print("ERROR: Point files not found!")
        return False, 0.0, set(), set()

    # Read and extract data portions
    with open(monolith_path, "r", encoding="utf-8") as f:
        monolith_lines = [
            extract_data_portion(line) for line in f.readlines() if line.strip()
        ]

    with open(modular_path, "r", encoding="utf-8") as f:
        modular_lines = [
            extract_data_portion(line) for line in f.readlines() if line.strip()
        ]

    print(f"\n{'='*60}")
    print("COMPARISON RESULTS")
    print(f"{'='*60}")
    print(f"Monolith points: {len(monolith_lines)}")
    print(f"Modular points:  {len(modular_lines)}")

    # Convert to sets for comparison
    monolith_set = set(monolith_lines)
    modular_set = set(modular_lines)

    only_in_monolith = monolith_set - modular_set
    only_in_modular = modular_set - monolith_set
    matching = monolith_set & modular_set

    print(f"\nMatching points:     {len(matching)}")
    print(f"Only in monolith:    {len(only_in_monolith)}")
    print(f"Only in modular:     {len(only_in_modular)}")

    if len(only_in_monolith) == 0 and len(only_in_modular) == 0:
        total = len(matching)
        print(f"\n{'='*60}")
        print(f"✅ PERFECT MATCH: 100.0% ({total}/{total})")
        print("🎉 ALL FORMATIONS MATCH - CONVERSION SUCCESSFUL!")
        print(f"{'='*60}")
        return True, 100.0, only_in_monolith, only_in_modular
    else:
        match_pct = len(matching) / max(len(monolith_set), len(modular_set), 1) * 100
        print(f"\n{'='*60}")
        print(f"❌ MISMATCH DETECTED! ({match_pct:.1f}% match)")
        print(f"{'='*60}")

        if only_in_monolith:
            print(f"\nSample points ONLY IN MONOLITH (first 10):")
            for line in sorted(list(only_in_monolith))[:10]:
                print(f"  {line}")

        if only_in_modular:
            print(f"\nSample points ONLY IN MODULAR (first 10):")
            for line in sorted(list(only_in_modular))[:10]:
                print(f"  {line}")

        return False, match_pct, only_in_monolith, only_in_modular


def analyze_differences(only_modular: Set[str]) -> None:
    """
    Analyze extra points in modular by grouping them by location prefix.

    Args:
        only_modular: Set of point strings only in modular
    """
    if not only_modular:
        return

    print(f"\n{'='*60}")
    print("ANALYSIS: Extra points in modular by location prefix")
    print(f"{'='*60}")

    by_prefix = defaultdict(list)
    for point in sorted(only_modular):
        parts = point.split(" | ")
        if parts:
            loc = parts[0]
            prefix = loc[:3] if len(loc) >= 3 else loc
            by_prefix[prefix].append(point)

    for prefix in sorted(by_prefix.keys()):
        print(f"\n{prefix}: {len(by_prefix[prefix])} points")
        for p in by_prefix[prefix][:3]:
            print(f"    {p}")
        if len(by_prefix[prefix]) > 3:
            print(f"    ... and {len(by_prefix[prefix]) - 3} more")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════


def run_comparison(parameter_name: str) -> bool:
    """
    Run full comparison workflow for a parameter.

    Args:
        parameter_name: Name of the parameter to compare

    Returns:
        True if comparison succeeded (100% match)
    """
    if parameter_name not in SCRIPT_CONFIGS:
        print(f"ERROR: Unknown parameter '{parameter_name}'")
        print(f"Available parameters: {list(SCRIPT_CONFIGS.keys())}")
        return False

    config = SCRIPT_CONFIGS[parameter_name]
    log_prefix = config["log_prefix"]

    print("=" * 60)
    print(f"MONOLITH vs MODULAR POINT COMPARISON: {parameter_name}")
    print("=" * 60)

    # Run monolith
    print(f"\n[1/2] Running MONOLITH script...")
    monolith_path = WORKSPACE / config["monolith"]
    run_script(monolith_path, f"monolith_{log_prefix}")

    # Run modular
    print(f"\n[2/2] Running MODULAR script...")
    modular_path = WORKSPACE / config["modular"]
    run_script(modular_path, f"modular_{log_prefix}")

    # Extract points
    print("\nExtracting debug points...")
    extract_points(LOGS_DIR / f"monolith_{log_prefix}.log", "[M]", "monolith_points")
    extract_points(LOGS_DIR / f"modular_{log_prefix}.log", "[m]", "modular_points")

    # Compare
    is_match, pct, only_monolith, only_modular = compare_points()

    # Analyze differences
    if only_modular:
        analyze_differences(only_modular)

    return is_match


if __name__ == "__main__":
    # Get parameter name from command line or use default
    if len(sys.argv) > 1:
        param_name = sys.argv[1]
    else:
        param_name = "UndrainedShearStrength"  # Default

    success = run_comparison(param_name)
    sys.exit(0 if success else 1)
