#!/usr/bin/env python3
"""
Run All Plotting Scripts - Batch Execution Utility
===================================================

This script executes all plotting scripts in the geotechnical_plotting/Plotting Scripts
directory, either sequentially or in parallel, with comprehensive logging and error handling.

ARCHITECTURAL OVERVIEW:

Responsibility:
Orchestrates the execution of all geotechnical parameter plotting scripts,
providing progress tracking, timing, error collection, and summary reporting.

Key Interactions:
- Input: Plotting scripts in geotechnical_plotting/Plotting Scripts/
- Processing: Runs each script as a subprocess with timeout protection
- Output: Console summary + optional log file with execution results

USAGE:
    # Run all scripts sequentially (default)
    python run_all_plotting_scripts.py

    # Run all scripts in parallel (faster but may use more resources)
    python run_all_plotting_scripts.py --parallel

    # Run specific scripts only
    python run_all_plotting_scripts.py --scripts UndrainedShearStrength MCvsDepth

    # Dry run - show what would be executed without running
    python run_all_plotting_scripts.py --dry-run

    # Set custom timeout (default 600 seconds per script)
    python run_all_plotting_scripts.py --timeout 900

    # Continue on error (don't stop if a script fails)
    python run_all_plotting_scripts.py --continue-on-error
"""

import argparse
import os
import subprocess
import sys
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# Use joblib with loky backend for matplotlib compatibility
from joblib import Parallel, delayed


# ═══════════════════════════════════════════════════════════════════════════
# ⚙️ CONFIGURATION TOGGLES
# ═══════════════════════════════════════════════════════════════════════════

# MODIFICATION POINT: Toggle for parallel or sequential execution
RUN_PARALLEL = True  # Set to False for sequential execution

# MODIFICATION POINT: Configuration for dynamic worker calculation
MIN_RESERVED_CPUS = 2  # Minimum CPUs reserved for OS
CPUS_PER_SCRIPT_INDIVIDUAL = 5  # CPUs per script when running individually
CPUS_PER_SCRIPT_PARALLEL = 3  # CPUs per script when running in batch parallel mode
CPUS_PER_SCRIPT = CPUS_PER_SCRIPT_INDIVIDUAL  # Default for worker calculation
MIN_CONCURRENT_SCRIPTS = 1  # Minimum concurrent scripts to run

# Environment variable used to signal reduced worker count to child scripts
PARALLEL_MODE_ENV_VAR = "GEOTECHNICAL_PLOTTING_BATCH_MODE"


# ═══════════════════════════════════════════════════════════════════════════
# 📍 PATH SETUP
# ═══════════════════════════════════════════════════════════════════════════

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parent  # Figures_3.0
PLOTTING_SCRIPTS_DIR = WORKSPACE_ROOT / "geotechnical_plotting" / "Plotting Scripts"

# Ensure logs folder exists
LOGS_DIR = WORKSPACE_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════
# 🏗️ LOGGING CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

# Force UTF-8 for stdout to handle emoji characters on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# 📊 DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ScriptResult:
    """Result of running a single plotting script."""

    script_name: str
    script_path: Path
    success: bool
    duration_seconds: float
    return_code: Optional[int] = None
    error_message: Optional[str] = None
    stdout: str = ""
    stderr: str = ""


@dataclass
class BatchResult:
    """Aggregated results of running all scripts."""

    total_scripts: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    total_duration_seconds: float = 0.0
    script_results: List[ScriptResult] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


# ═══════════════════════════════════════════════════════════════════════════
# 🔍 SCRIPT DISCOVERY
# ═══════════════════════════════════════════════════════════════════════════


def discover_plotting_scripts(
    scripts_dir: Path, specific_scripts: Optional[List[str]] = None
) -> List[Path]:
    """
    Discover all plotting scripts in the specified directory.

    Args:
        scripts_dir: Directory containing plotting scripts
        specific_scripts: Optional list of specific script names to run (without .py)

    Returns:
        List of Path objects for scripts to execute
    """
    if not scripts_dir.exists():
        logger.error(f"❌ Plotting scripts directory not found: {scripts_dir}")
        return []

    # Get all .py files, excluding __pycache__ and __init__.py
    all_scripts = [
        f
        for f in scripts_dir.glob("*.py")
        if f.name != "__init__.py" and not f.name.startswith("_")
    ]

    if specific_scripts:
        # Filter to only requested scripts
        specific_set = {s.replace(".py", "") for s in specific_scripts}
        all_scripts = [s for s in all_scripts if s.stem in specific_set]

        # Warn about any requested scripts that weren't found
        found_stems = {s.stem for s in all_scripts}
        missing = specific_set - found_stems
        if missing:
            logger.warning(f"⚠️ Requested scripts not found: {missing}")

    # Sort alphabetically for consistent ordering
    return sorted(all_scripts, key=lambda p: p.stem)


# ═══════════════════════════════════════════════════════════════════════════
# ⚡ SCRIPT EXECUTION
# ═══════════════════════════════════════════════════════════════════════════


def run_single_script(
    script_path: Path,
    python_executable: str,
    timeout_seconds: int = 600,
    capture_output: bool = True,
) -> ScriptResult:
    """
    Run a single plotting script as a subprocess.

    Args:
        script_path: Path to the Python script
        python_executable: Path to Python interpreter
        timeout_seconds: Maximum execution time before timeout
        capture_output: Whether to capture stdout/stderr

    Returns:
        ScriptResult with execution details
    """
    script_name = script_path.stem
    logger.info(f"🚀 Starting: {script_name}")
    start_time = time.time()

    try:
        result = subprocess.run(
            [python_executable, str(script_path)],
            capture_output=capture_output,
            text=True,
            timeout=timeout_seconds,
            cwd=str(script_path.parent),  # Run from script's directory
            encoding="utf-8",  # Handle emoji characters in subprocess output
            errors="replace",  # Replace undecodable bytes instead of crashing
        )

        duration = time.time() - start_time

        if result.returncode == 0:
            logger.info(f"✅ Completed: {script_name} ({duration:.1f}s)")
            return ScriptResult(
                script_name=script_name,
                script_path=script_path,
                success=True,
                duration_seconds=duration,
                return_code=result.returncode,
                stdout=result.stdout if capture_output else "",
                stderr=result.stderr if capture_output else "",
            )
        else:
            logger.error(f"❌ Failed: {script_name} (exit code {result.returncode})")
            return ScriptResult(
                script_name=script_name,
                script_path=script_path,
                success=False,
                duration_seconds=duration,
                return_code=result.returncode,
                error_message=f"Exit code {result.returncode}",
                stdout=result.stdout if capture_output else "",
                stderr=result.stderr if capture_output else "",
            )

    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        logger.error(f"⏰ Timeout: {script_name} (exceeded {timeout_seconds}s)")
        return ScriptResult(
            script_name=script_name,
            script_path=script_path,
            success=False,
            duration_seconds=duration,
            error_message=f"Timeout after {timeout_seconds} seconds",
        )

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"💥 Exception: {script_name} - {str(e)}")
        return ScriptResult(
            script_name=script_name,
            script_path=script_path,
            success=False,
            duration_seconds=duration,
            error_message=str(e),
        )


def _run_script_wrapper(args: Tuple[Path, str, int]) -> ScriptResult:
    """Wrapper function for parallel execution with logging."""
    script_path, python_executable, timeout_seconds = args
    # Log at start of each script (will be interleaved in parallel mode)
    print(f"🚀 Starting: {script_path.stem}", flush=True)
    result = run_single_script(script_path, python_executable, timeout_seconds)
    # Log completion with status
    status = "✅" if result.success else "❌"
    print(
        f"{status} Completed: {result.script_name} ({result.duration_seconds:.1f}s)",
        flush=True,
    )
    return result


# ═══════════════════════════════════════════════════════════════════════════
# 🔢 CPU-BASED WORKER CALCULATION
# ═══════════════════════════════════════════════════════════════════════════


def calculate_optimal_concurrent_scripts() -> int:
    """
    Calculate the optimal number of concurrent scripts based on available CPUs.

    Formula: (total_cpus - MIN_RESERVED_CPUS) // CPUS_PER_SCRIPT

    This ensures:
    - At least MIN_RESERVED_CPUS are left for OS operations
    - Each script has CPUS_PER_SCRIPT CPUs available for parallel formations
    - Returns at least MIN_CONCURRENT_SCRIPTS even on low-CPU systems

    Returns:
        int: Optimal number of concurrent scripts to run
    """
    total_cpus = os.cpu_count() or 4  # Default to 4 if detection fails
    available_for_scripts = total_cpus - MIN_RESERVED_CPUS
    # Use reduced CPUs per script in parallel mode for better concurrency
    concurrent_scripts = max(
        MIN_CONCURRENT_SCRIPTS, available_for_scripts // CPUS_PER_SCRIPT_PARALLEL
    )

    logger.info(f"🔢 CPU-based worker calculation:")
    logger.info(f"   Total CPUs:        {total_cpus}")
    logger.info(f"   Reserved for OS:   {MIN_RESERVED_CPUS}")
    logger.info(f"   Available:         {available_for_scripts}")
    logger.info(f"   CPUs per script:   {CPUS_PER_SCRIPT_PARALLEL} (batch mode)")
    logger.info(f"   Concurrent scripts: {concurrent_scripts}")

    return concurrent_scripts


# ═══════════════════════════════════════════════════════════════════════════
# 🎯 BATCH EXECUTION ORCHESTRATORS
# ═══════════════════════════════════════════════════════════════════════════


def run_scripts_sequential(
    scripts: List[Path],
    python_executable: str,
    timeout_seconds: int = 600,
    continue_on_error: bool = True,
) -> BatchResult:
    """
    Run all scripts sequentially.

    Args:
        scripts: List of script paths to execute
        python_executable: Path to Python interpreter
        timeout_seconds: Timeout per script
        continue_on_error: If False, stop on first error

    Returns:
        BatchResult with aggregated results
    """
    batch_result = BatchResult(total_scripts=len(scripts), start_time=datetime.now())

    logger.info(f"📋 Running {len(scripts)} scripts sequentially...")
    logger.info("=" * 60)

    for i, script_path in enumerate(scripts, 1):
        logger.info(f"[{i}/{len(scripts)}] Processing {script_path.stem}")

        result = run_single_script(script_path, python_executable, timeout_seconds)
        batch_result.script_results.append(result)
        batch_result.total_duration_seconds += result.duration_seconds

        if result.success:
            batch_result.successful += 1
        else:
            batch_result.failed += 1
            if not continue_on_error:
                logger.warning("⛔ Stopping due to error (--continue-on-error not set)")
                batch_result.skipped = len(scripts) - i
                break

    batch_result.end_time = datetime.now()
    return batch_result


def run_scripts_parallel(
    scripts: List[Path],
    python_executable: str,
    timeout_seconds: int = 600,
    max_workers: Optional[int] = None,
) -> BatchResult:
    """
    Run all scripts in parallel using joblib with loky backend.

    Uses joblib with loky backend for matplotlib compatibility - loky spawns
    fresh Python processes which avoids matplotlib threading issues.

    Args:
        scripts: List of script paths to execute
        python_executable: Path to Python interpreter
        timeout_seconds: Timeout per script
        max_workers: Maximum number of parallel processes (None = auto-calculate)

    Returns:
        BatchResult with aggregated results
    """
    batch_result = BatchResult(total_scripts=len(scripts), start_time=datetime.now())

    # Auto-calculate workers if not specified
    if max_workers is None:
        max_workers = calculate_optimal_concurrent_scripts()

    # Cap workers at number of scripts (no point having more workers than scripts)
    effective_workers = min(max_workers, len(scripts))

    # Set environment variable to signal batch mode to child scripts
    # This causes them to use fewer internal workers (CPUS_PER_SCRIPT_PARALLEL)
    os.environ[PARALLEL_MODE_ENV_VAR] = str(CPUS_PER_SCRIPT_PARALLEL)

    logger.info(
        f"📋 Running {len(scripts)} scripts in parallel ({effective_workers} concurrent)..."
    )
    logger.info("=" * 60)

    # Log all scripts to be executed
    print("\n📋 Scripts queued for parallel execution:")
    for i, script in enumerate(scripts, 1):
        print(f"   {i}. {script.stem}")
    print(
        f"\n🔧 Configuration: {effective_workers} concurrent scripts × {CPUS_PER_SCRIPT_PARALLEL} CPUs each (batch mode)"
    )
    print("=" * 60, flush=True)

    # Prepare arguments for parallel execution
    task_args = [(script, python_executable, timeout_seconds) for script in scripts]

    # Use joblib with loky backend (spawns fresh processes, safe for matplotlib)
    try:
        print("\n⏳ Starting parallel execution...\n", flush=True)
        results = Parallel(
            n_jobs=effective_workers,
            backend="loky",  # Safe for matplotlib - spawns fresh processes
            verbose=10,  # Show task dispatch progress
        )(delayed(_run_script_wrapper)(args) for args in task_args)

        # Process results
        for result in results:
            batch_result.script_results.append(result)
            batch_result.total_duration_seconds += result.duration_seconds

            if result.success:
                batch_result.successful += 1
            else:
                batch_result.failed += 1

    except Exception as e:
        logger.error(f"💥 Parallel execution error: {e}")
        # Mark all scripts as failed if parallel execution itself fails
        for script in scripts:
            if not any(r.script_path == script for r in batch_result.script_results):
                batch_result.failed += 1
                batch_result.script_results.append(
                    ScriptResult(
                        script_name=script.stem,
                        script_path=script,
                        success=False,
                        duration_seconds=0,
                        error_message=str(e),
                    )
                )
    finally:
        # Clean up environment variable after parallel execution
        if PARALLEL_MODE_ENV_VAR in os.environ:
            del os.environ[PARALLEL_MODE_ENV_VAR]

    batch_result.end_time = datetime.now()
    return batch_result


# ═══════════════════════════════════════════════════════════════════════════
# 📊 REPORTING
# ═══════════════════════════════════════════════════════════════════════════


def print_summary(batch_result: BatchResult) -> None:
    """Print execution summary to console."""
    logger.info("")
    logger.info("=" * 60)
    logger.info("📊 EXECUTION SUMMARY")
    logger.info("=" * 60)

    # Overall stats
    wall_clock_time = (
        (batch_result.end_time - batch_result.start_time).total_seconds()
        if batch_result.end_time and batch_result.start_time
        else batch_result.total_duration_seconds
    )

    logger.info(f"Total Scripts:    {batch_result.total_scripts}")
    logger.info(f"✅ Successful:    {batch_result.successful}")
    logger.info(f"❌ Failed:        {batch_result.failed}")
    if batch_result.skipped > 0:
        logger.info(f"⏭️ Skipped:       {batch_result.skipped}")
    logger.info(f"Wall Clock Time:  {wall_clock_time:.1f}s")
    logger.info(f"Total CPU Time:   {batch_result.total_duration_seconds:.1f}s")

    # Per-script breakdown
    logger.info("")
    logger.info("Per-Script Results:")
    logger.info("-" * 60)

    for result in sorted(batch_result.script_results, key=lambda r: r.script_name):
        status = "✅" if result.success else "❌"
        error_info = f" ({result.error_message})" if result.error_message else ""
        logger.info(
            f"  {status} {result.script_name}: {result.duration_seconds:.1f}s{error_info}"
        )

    # List failures at the end for visibility
    failures = [r for r in batch_result.script_results if not r.success]
    if failures:
        logger.info("")
        logger.info("❌ FAILED SCRIPTS:")
        logger.info("-" * 60)
        for result in failures:
            logger.info(f"  • {result.script_name}")
            if result.error_message:
                logger.info(f"    Error: {result.error_message}")
            if result.stderr:
                # Show last few lines of stderr
                stderr_lines = result.stderr.strip().split("\n")[-5:]
                for line in stderr_lines:
                    logger.info(f"    {line}")

    logger.info("")
    logger.info("=" * 60)


def save_log_file(batch_result: BatchResult, log_path: Path) -> None:
    """Save detailed execution log to file."""
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("GEOTECHNICAL PLOTTING SCRIPTS - BATCH EXECUTION LOG\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write("=" * 80 + "\n\n")

        f.write("SUMMARY\n")
        f.write("-" * 40 + "\n")
        f.write(f"Total Scripts:  {batch_result.total_scripts}\n")
        f.write(f"Successful:     {batch_result.successful}\n")
        f.write(f"Failed:         {batch_result.failed}\n")
        f.write(f"Skipped:        {batch_result.skipped}\n")
        f.write(f"Total Duration: {batch_result.total_duration_seconds:.1f}s\n\n")

        f.write("DETAILED RESULTS\n")
        f.write("-" * 40 + "\n\n")

        for result in sorted(batch_result.script_results, key=lambda r: r.script_name):
            status = "SUCCESS" if result.success else "FAILED"
            f.write(f"Script: {result.script_name}\n")
            f.write(f"Status: {status}\n")
            f.write(f"Duration: {result.duration_seconds:.1f}s\n")
            if result.return_code is not None:
                f.write(f"Return Code: {result.return_code}\n")
            if result.error_message:
                f.write(f"Error: {result.error_message}\n")
            if result.stderr:
                f.write(f"Stderr:\n{result.stderr}\n")
            f.write("\n" + "-" * 40 + "\n\n")

    logger.info(f"📝 Detailed log saved to: {log_path}")


# ═══════════════════════════════════════════════════════════════════════════
# ⚡ MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════════════


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run all geotechnical plotting scripts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_all_plotting_scripts.py                     # Run all scripts sequentially
  python run_all_plotting_scripts.py --parallel          # Run in parallel
  python run_all_plotting_scripts.py --scripts MCvsDepth # Run specific script
  python run_all_plotting_scripts.py --dry-run           # Preview without running
        """,
    )

    parser.add_argument(
        "--parallel",
        action="store_true",
        default=None,  # None means use RUN_PARALLEL toggle
        help="Run scripts in parallel instead of sequentially",
    )

    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Run scripts sequentially (overrides --parallel and RUN_PARALLEL toggle)",
    )

    parser.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="Maximum parallel workers (default: auto-calculated from CPU count)",
    )

    parser.add_argument(
        "--scripts",
        nargs="+",
        help="Specific script names to run (without .py extension)",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Timeout in seconds per script (default: 600)",
    )

    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue running remaining scripts if one fails (sequential mode)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be executed without actually running",
    )

    parser.add_argument(
        "--save-log",
        action="store_true",
        help="Save detailed execution log to logs/ folder",
    )

    parser.add_argument(
        "--python",
        type=str,
        default=sys.executable,
        help="Python interpreter to use (default: current interpreter)",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_arguments()

    # Determine execution mode: --sequential overrides everything,
    # then --parallel, then RUN_PARALLEL toggle
    if args.sequential:
        use_parallel = False
    elif args.parallel:
        use_parallel = True
    else:
        use_parallel = RUN_PARALLEL  # Use the toggle at top of script

    logger.info("🎯 Geotechnical Plotting Scripts - Batch Runner")
    logger.info("=" * 60)
    logger.info(f"Workspace Root: {WORKSPACE_ROOT}")
    logger.info(f"Scripts Dir:    {PLOTTING_SCRIPTS_DIR}")
    logger.info(f"Python:         {args.python}")
    logger.info(f"Mode:           {'Parallel' if use_parallel else 'Sequential'}")
    if use_parallel:
        workers_info = str(args.max_workers) if args.max_workers else "auto (CPU-based)"
        logger.info(f"Max Workers:    {workers_info}")
    logger.info(f"Timeout:        {args.timeout}s per script")
    logger.info("")

    # Discover scripts
    scripts = discover_plotting_scripts(PLOTTING_SCRIPTS_DIR, args.scripts)

    if not scripts:
        logger.error("❌ No plotting scripts found!")
        return 1

    logger.info(f"📋 Found {len(scripts)} scripts to run:")
    for script in scripts:
        logger.info(f"   • {script.stem}")
    logger.info("")

    # Dry run - just show what would be executed
    if args.dry_run:
        logger.info("🔍 DRY RUN - No scripts will be executed")
        return 0

    # Execute scripts
    if use_parallel:
        batch_result = run_scripts_parallel(
            scripts,
            args.python,
            args.timeout,
            args.max_workers,
        )
    else:
        batch_result = run_scripts_sequential(
            scripts,
            args.python,
            args.timeout,
            args.continue_on_error,
        )

    # Print summary
    print_summary(batch_result)

    # Save log if requested
    if args.save_log:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = LOGS_DIR / f"batch_run_{timestamp}.log"
        save_log_file(batch_result, log_path)

    # Return non-zero exit code if any scripts failed
    return 0 if batch_result.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
