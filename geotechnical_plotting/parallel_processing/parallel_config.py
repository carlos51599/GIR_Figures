#!/usr/bin/env python3
"""
Parallel Processing Configuration Module
=========================================

This module contains ALL configuration and validation for parallel processing.
It is designed to be self-contained with minimal external dependencies.

ARCHITECTURAL OVERVIEW:

Responsibility:
Provides centralized configuration constants and validation functions for
parallel processing. Determines if/when parallel execution should be used.

Key Interactions:
- Input: Number of formations, parallel config dictionary
- Output: Validation results, worker counts, enable/disable decisions
- Used by: parallel_orchestrator.py, orchestrator.py (conditional)

Navigation Guide:
- DEFAULT_PARALLEL_CONFIG: All parallel settings with safe defaults
- validate_parallel_environment(): Environment capability checks
- get_effective_worker_count(): Calculate optimal worker count
- should_use_parallel(): Main decision function for parallel execution
- get_parallel_config(): Retrieve config from main CONFIG dict

MODIFICATION POINTS:
- DEFAULT_PARALLEL_CONFIG: Adjust worker counts, thresholds
- validate_parallel_environment(): Add new environment checks
- _is_interactive_environment(): Add new interactive detection

This module can be safely deleted without affecting sequential operation.
"""

from typing import Dict, Any, Tuple, Optional
import os
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# 📊 DEFAULT CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_PARALLEL_CONFIG: Dict[str, Any] = {
    # -------------------------------------------------------------------------
    # Master toggle - single point to enable/disable
    # Default OFF for safety - requires explicit opt-in
    # -------------------------------------------------------------------------
    "enabled": False,
    # -------------------------------------------------------------------------
    # Worker configuration
    # -1 = auto (use OPTIMAL_WORKERS_DEFAULT=5, or fewer if system has less CPUs)
    # -2 = CPU count - 1 (leave 1 for system)
    # Positive integer = explicit worker count
    #
    # EMPIRICAL FINDING (Dec 2025): Based on benchmarking, 4-5 workers provides
    # optimal throughput. Beyond 5-6 workers, serialization overhead and I/O
    # contention negate additional parallelization benefits.
    # See: reports/Why_Parallel_Not_Scaling_Analysis.md
    # -------------------------------------------------------------------------
    "max_workers": -1,
    # -------------------------------------------------------------------------
    # Optimal workers for auto mode (-1)
    # Empirically determined: 5 workers captures ~90% of parallelization benefit
    # Each worker gets enough CPU resources without excessive overhead
    # -------------------------------------------------------------------------
    "optimal_workers_default": 5,
    # -------------------------------------------------------------------------
    # Threshold settings
    # Don't parallelize if fewer formations than this (overhead not worth it)
    # -------------------------------------------------------------------------
    "min_formations_for_parallel": 3,
    # -------------------------------------------------------------------------
    # Safety settings
    # -------------------------------------------------------------------------
    "timeout_per_formation_seconds": 300,  # 5 min max per formation
    "max_memory_per_worker_mb": 2048,  # 2GB limit per worker (advisory)
    "fallback_on_error": True,  # If parallel fails, run sequential
    # -------------------------------------------------------------------------
    # Joblib settings
    # backend: "loky" (process-based, safest for matplotlib)
    #          "threading" (thread-based, NOT safe for matplotlib)
    #          "multiprocessing" (process-based, can have issues on Windows)
    # verbose: 0-50, higher = more output
    # -------------------------------------------------------------------------
    "backend": "loky",
    "verbose": 10,
    # -------------------------------------------------------------------------
    # Logging and debugging
    # -------------------------------------------------------------------------
    "log_worker_progress": True,
    "log_memory_usage": False,  # Enable for debugging only (adds overhead)
}
"""
Default parallel processing configuration with safe, conservative defaults.

All options are OFF by default to ensure:
1. No unexpected behavior changes
2. Explicit opt-in required
3. Easy troubleshooting (disable = revert to known-good sequential)
"""


# ═══════════════════════════════════════════════════════════════════════════
# 🔍 ENVIRONMENT VALIDATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def validate_parallel_environment() -> Tuple[bool, str]:
    """
    Check if the current environment supports parallel processing.

    Performs multiple checks to ensure parallel execution will work safely:
    1. Joblib availability
    2. Interactive environment detection (Jupyter/IPython)
    3. Sufficient CPU cores

    Returns:
        Tuple of (is_valid: bool, reason_if_invalid: str)
        If is_valid is True, reason will be empty string.
        If is_valid is False, reason explains why.

    Example:
        >>> is_valid, reason = validate_parallel_environment()
        >>> if not is_valid:
        ...     logger.warning(f"Cannot use parallel: {reason}")
    """
    # Check 1: Joblib available
    try:
        import joblib  # noqa: F401
    except ImportError:
        return False, "joblib not installed (pip install joblib)"

    # Check 2: Not in interactive environment (Jupyter can have multiprocessing issues)
    if _is_interactive_environment():
        return (
            False,
            "Interactive environment detected (Jupyter/IPython) - parallel disabled for safety",
        )

    # Check 3: Sufficient CPU cores
    cpu_count = os.cpu_count() or 1
    if cpu_count < 2:
        return (
            False,
            f"Only {cpu_count} CPU core available - parallel requires at least 2",
        )

    # Check 4: Platform-specific checks (optional - can add more)
    # Windows has some multiprocessing quirks but loky handles them

    return True, ""


def _is_interactive_environment() -> bool:
    """
    Detect if running in Jupyter, IPython, or other interactive environment.

    Interactive environments often have issues with multiprocessing:
    - Jupyter: Process forking can cause kernel crashes
    - IPython: Similar issues with process isolation

    Returns:
        True if running in interactive environment, False otherwise
    """
    # Check 1: IPython/Jupyter
    try:
        from IPython import get_ipython

        ipython = get_ipython()
        if ipython is not None:
            # Check if it's specifically Jupyter (has 'kernel' in class name)
            if "zmqshell" in str(type(ipython)).lower():
                return True
            # Could be IPython terminal - slightly safer but still be cautious
            return True
    except ImportError:
        pass
    except Exception:
        # Any other exception - assume not interactive
        pass

    # Check 2: Check for common interactive indicators
    try:
        # Jupyter sets this environment variable
        if os.environ.get("JPY_PARENT_PID"):
            return True
    except Exception:
        pass

    return False


# ═══════════════════════════════════════════════════════════════════════════
# 🔢 WORKER COUNT CALCULATION
# ═══════════════════════════════════════════════════════════════════════════


def _calculate_auto_workers(optimal_default: int, cpu_count: int) -> int:
    """
    Calculate workers for auto mode (-1).

    Uses optimal default (5), but scales down if system has fewer CPUs.
    """
    min_cpus_required = optimal_default + 1
    if cpu_count >= min_cpus_required:
        logger.debug(
            "Auto mode: using %d workers (system has %d CPUs >= %d required)",
            optimal_default,
            cpu_count,
            min_cpus_required,
        )
        return optimal_default
    # Scale down for systems with fewer CPUs
    workers = max(1, cpu_count - 1)
    logger.info(
        "⚠️ System has only %d CPUs, reducing workers from %d to %d",
        cpu_count,
        optimal_default,
        workers,
    )
    return workers


def _calculate_explicit_workers(max_workers: int, cpu_count: int) -> int:
    """
    Calculate workers for explicit count mode.

    Validates system has capacity for requested workers.
    """
    min_cpus_required = max_workers + 1
    if cpu_count >= min_cpus_required:
        return max_workers
    # Scale down to what system can handle
    workers = max(1, cpu_count - 1)
    logger.warning(
        "⚠️ Requested %d workers but system has %d CPUs. Reducing to %d.",
        max_workers,
        cpu_count,
        workers,
    )
    return workers


# Environment variable used by run_all_plotting_scripts.py to signal reduced workers
BATCH_MODE_ENV_VAR = "GEOTECHNICAL_PLOTTING_BATCH_MODE"


def get_effective_worker_count(
    num_formations: int,
    config: Dict[str, Any],
) -> int:
    """
    Calculate optimal worker count based on formations, config, and system resources.

    EMPIRICAL OPTIMIZATION (Dec 2025): 5 workers is optimal for most systems.
    Beyond 5-6 workers, serialization overhead negates benefits.
    See: reports/Why_Parallel_Not_Scaling_Analysis.md

    When running as part of a batch (GEOTECHNICAL_PLOTTING_BATCH_MODE env var set),
    uses the value from that env var (typically 3) to reduce resource contention.

    Args:
        num_formations: Number of formations to process
        config: Parallel configuration dictionary

    Returns:
        Effective number of workers to use (always >= 1)
    """
    # Check if running in batch mode (set by run_all_plotting_scripts.py)
    batch_mode_workers = os.environ.get(BATCH_MODE_ENV_VAR)
    if batch_mode_workers:
        try:
            workers = int(batch_mode_workers)
            logger.debug(
                "Batch mode detected: using %d workers (env var %s)",
                workers,
                BATCH_MODE_ENV_VAR,
            )
            # Apply formation constraint and return early
            workers = min(workers, num_formations)
            workers = max(1, workers)
            return workers
        except ValueError:
            logger.warning(
                "Invalid %s value '%s', using normal calculation",
                BATCH_MODE_ENV_VAR,
                batch_mode_workers,
            )

    max_workers = config.get("max_workers", -1)
    optimal_default = config.get("optimal_workers_default", 5)
    cpu_count = os.cpu_count() or 1

    # Determine base worker count from config
    if max_workers == -1:
        workers = _calculate_auto_workers(optimal_default, cpu_count)
    elif max_workers == -2:
        workers = max(1, cpu_count - 1)
    elif max_workers > 0:
        workers = _calculate_explicit_workers(max_workers, cpu_count)
    else:
        logger.warning("Invalid max_workers=%d, using optimal default", max_workers)
        workers = min(optimal_default, max(1, cpu_count - 1))

    # Apply constraints
    workers = min(workers, num_formations)  # Don't exceed formations
    if cpu_count > 2:
        workers = min(workers, cpu_count - 1)  # Leave 1 CPU free
    workers = max(1, workers)  # Always at least 1

    logger.debug(
        "Worker calc: max_workers=%d, cpus=%d, formations=%d, effective=%d",
        max_workers,
        cpu_count,
        num_formations,
        workers,
    )
    return workers


# ═══════════════════════════════════════════════════════════════════════════
# 🎯 MAIN DECISION FUNCTION
# ═══════════════════════════════════════════════════════════════════════════


def should_use_parallel(
    num_formations: int,
    config: Dict[str, Any],
) -> Tuple[bool, str]:
    """
    Determine if parallel processing should be used for this run.

    This is the main decision function that checks all gates:
    1. Master toggle (enabled flag)
    2. Environment validation
    3. Formation count threshold

    Args:
        num_formations: Number of formations to process
        config: Parallel configuration dictionary

    Returns:
        Tuple of (should_use: bool, reason: str)
        If should_use is True, reason explains what will happen.
        If should_use is False, reason explains why not.

    Example:
        >>> config = {"enabled": True, "min_formations_for_parallel": 3}
        >>> should_use, reason = should_use_parallel(10, config)
        >>> if should_use:
        ...     run_parallel()
        ... else:
        ...     logger.info(f"Sequential mode: {reason}")
    """
    # Gate 1: Check master toggle
    if not config.get("enabled", False):
        return False, "Parallel processing disabled in config (enabled=False)"

    # Gate 2: Check environment
    env_valid, env_reason = validate_parallel_environment()
    if not env_valid:
        return False, f"Environment check failed: {env_reason}"

    # Gate 3: Check formation count threshold
    min_formations = config.get("min_formations_for_parallel", 3)
    if num_formations < min_formations:
        return (
            False,
            f"Too few formations ({num_formations} < {min_formations} threshold)",
        )

    # All gates passed - parallel is go
    worker_count = get_effective_worker_count(num_formations, config)
    return (
        True,
        f"Parallel enabled: {num_formations} formations, {worker_count} workers",
    )


# ═══════════════════════════════════════════════════════════════════════════
# 🔧 CONFIG RETRIEVAL HELPER
# ═══════════════════════════════════════════════════════════════════════════


def get_parallel_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract parallel processing configuration from main CONFIG dictionary.

    Retrieves the parallel_processing section from CONFIG, falling back to
    DEFAULT_PARALLEL_CONFIG if not present.

    Args:
        config: Main CONFIG dictionary from parameter script

    Returns:
        Parallel processing configuration dictionary

    Example:
        >>> from geotechnical_plotting import build_config_from_defaults
        >>> CONFIG = build_config_from_defaults(...)
        >>> parallel_config = get_parallel_config(CONFIG)
        >>> if parallel_config["enabled"]:
        ...     print("Parallel is enabled!")
    """
    return config.get("parallel_processing", DEFAULT_PARALLEL_CONFIG.copy())


# ═══════════════════════════════════════════════════════════════════════════
# 🧪 DEBUG AND DIAGNOSTIC FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def get_parallel_diagnostics() -> Dict[str, Any]:
    """
    Get diagnostic information about parallel processing capabilities.

    Useful for troubleshooting and debugging parallel processing issues.

    Returns:
        Dictionary with diagnostic information including:
        - cpu_count: Number of CPUs detected
        - joblib_available: Whether joblib is installed
        - joblib_version: Version of joblib (if available)
        - interactive_environment: Whether running in interactive mode
        - environment_valid: Overall environment validity
        - environment_reason: Reason if environment is invalid

    Example:
        >>> diag = get_parallel_diagnostics()
        >>> print(f"CPUs: {diag['cpu_count']}")
        >>> print(f"Joblib: {diag['joblib_available']} v{diag.get('joblib_version', 'N/A')}")
    """
    diagnostics = {
        "cpu_count": os.cpu_count() or 1,
        "interactive_environment": _is_interactive_environment(),
    }

    # Check joblib
    try:
        import joblib

        diagnostics["joblib_available"] = True
        diagnostics["joblib_version"] = joblib.__version__
    except ImportError:
        diagnostics["joblib_available"] = False
        diagnostics["joblib_version"] = None

    # Overall environment check
    env_valid, env_reason = validate_parallel_environment()
    diagnostics["environment_valid"] = env_valid
    diagnostics["environment_reason"] = (
        env_reason if not env_valid else "All checks passed"
    )

    return diagnostics


def print_parallel_status(config: Dict[str, Any]) -> None:
    """
    Print human-readable parallel processing status to logger.

    Useful for debugging and confirming parallel configuration.

    Args:
        config: Parallel configuration dictionary
    """
    logger.info("=" * 60)
    logger.info("📊 PARALLEL PROCESSING STATUS")
    logger.info("=" * 60)

    diag = get_parallel_diagnostics()

    logger.info(f"  Enabled in config: {config.get('enabled', False)}")
    logger.info(f"  Environment valid: {diag['environment_valid']}")
    if not diag["environment_valid"]:
        logger.info(f"  Environment issue: {diag['environment_reason']}")
    logger.info(f"  CPU count: {diag['cpu_count']}")
    logger.info(f"  Joblib available: {diag['joblib_available']}")
    if diag["joblib_available"]:
        logger.info(f"  Joblib version: {diag['joblib_version']}")
    logger.info(f"  Interactive mode: {diag['interactive_environment']}")
    logger.info(f"  Max workers setting: {config.get('max_workers', -1)}")
    logger.info(
        f"  Min formations threshold: {config.get('min_formations_for_parallel', 3)}"
    )
    logger.info(f"  Backend: {config.get('backend', 'loky')}")
    logger.info(f"  Fallback on error: {config.get('fallback_on_error', True)}")
    logger.info("=" * 60)


# ═══════════════════════════════════════════════════════════════════════════
# 📦 MODULE EXPORTS
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    # Configuration
    "DEFAULT_PARALLEL_CONFIG",
    # Validation
    "validate_parallel_environment",
    # Worker calculation
    "get_effective_worker_count",
    # Decision function
    "should_use_parallel",
    # Config retrieval
    "get_parallel_config",
    # Diagnostics
    "get_parallel_diagnostics",
    "print_parallel_status",
]
