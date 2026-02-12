#!/usr/bin/env python3
"""
SESRO Geotechnical Plotting - Parallel Processing Module
=========================================================

Joblib-based parallel processing for formation plot generation.
This module provides an OPTIONAL overlay for parallel execution.

DESIGN PHILOSOPHY:
- Parallel is an overlay, not a replacement
- Sequential code stays intact and is the default
- Single toggle to enable/disable everything
- Automatic graceful fallback on any error
- Zero changes to existing plotting functions

PUBLIC API:
- run_parallel_formation_plots(): Execute parallel plot generation
- ParallelExecutionError: Raised when parallel fails, triggers fallback
- should_use_parallel(): Check if parallel should be used
- get_parallel_config(): Get current parallel configuration

USAGE:
    from geotechnical_plotting.parallel_processing import (
        run_parallel_formation_plots,
        ParallelExecutionError,
    )

    try:
        results, summary = run_parallel_formation_plots(...)
    except ParallelExecutionError:
        # Fall back to sequential processing
        pass

REMOVAL:
To completely remove parallel processing:
1. Delete this folder (parallel_processing/)
2. Remove conditional import from orchestrator.py (~15 lines)
3. Remove parallel config from shared_config.py (~20 lines)

This module can be safely deleted without affecting sequential operation.
"""

# ═══════════════════════════════════════════════════════════════════════════
# 📦 MODULE VERSION AND METADATA
# ═══════════════════════════════════════════════════════════════════════════

__version__ = "1.0.0"
__author__ = "SESRO GIR Geotechnical Team"

# ═══════════════════════════════════════════════════════════════════════════
# 🔧 PUBLIC API EXPORTS
# ═══════════════════════════════════════════════════════════════════════════

# Configuration and validation functions
from .parallel_config import (
    DEFAULT_PARALLEL_CONFIG,
    validate_parallel_environment,
    get_effective_worker_count,
    should_use_parallel,
    get_parallel_config,
    get_parallel_diagnostics,
    print_parallel_status,
)

# Phase 2: Parallel orchestration and worker functions
from .parallel_orchestrator import (
    run_parallel_formation_plots,
    ParallelExecutionError,
)
from .parallel_worker import worker_generate_formation_plots


# ═══════════════════════════════════════════════════════════════════════════
# 📦 MODULE EXPORTS
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    # Exception class
    "ParallelExecutionError",
    # Configuration
    "DEFAULT_PARALLEL_CONFIG",
    "validate_parallel_environment",
    "get_effective_worker_count",
    "should_use_parallel",
    "get_parallel_config",
    "get_parallel_diagnostics",
    "print_parallel_status",
    # Phase 2: Orchestration
    "run_parallel_formation_plots",
    # Phase 2: Worker
    "worker_generate_formation_plots",
]
