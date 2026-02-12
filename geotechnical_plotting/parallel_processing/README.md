# Parallel Processing Module

## Overview

This module provides **optional** Joblib-based parallel processing for the SESRO geotechnical plotting pipeline. It is designed as an **overlay** that can be completely removed without affecting the existing sequential operation.

## Design Philosophy

```
┌─────────────────────────────────────────────────────────────────┐
│                     CORE DESIGN PRINCIPLES                      │
├─────────────────────────────────────────────────────────────────┤
│  1. PARALLEL IS AN OVERLAY    Sequential code stays untouched  │
│  2. SINGLE TOGGLE             One config flag controls all     │
│  3. AUTOMATIC FALLBACK        Any error → sequential mode      │
│  4. ZERO PLOTTING CHANGES     matplotlib/plotly utils intact   │
│  5. COMPLETE REMOVABILITY     Delete folder → system works     │
└─────────────────────────────────────────────────────────────────┘
```

## Module Structure

```
parallel_processing/
├── __init__.py              # Public API (2-3 functions exported)
├── parallel_config.py       # Configuration and validation
├── parallel_worker.py       # Isolated worker function (Phase 2)
├── parallel_orchestrator.py # Job dispatch and collection (Phase 2)
└── README.md               # This documentation
```

## Quick Start

### Enabling Parallel Processing

In your parameter script, add the override to your CONFIG:

```python
from geotechnical_plotting import build_config_from_defaults

CONFIG = build_config_from_defaults(
    parameter_name="MoistureContent",
    display_name="Moisture Content (%)",
    csv_source_settings=CSV_SOURCE_SETTINGS,
    # Enable parallel processing
    parallel_processing_override={
        "enabled": True,  # Turn on parallel
        "max_workers": 4,  # Optional: limit workers
    },
)
```

### Checking Parallel Status

```python
from geotechnical_plotting.parallel_processing import (
    should_use_parallel,
    validate_parallel_environment,
)

# Check if parallel would be used
can_use, reason = should_use_parallel(num_formations=10, config=parallel_config)
print(f"Parallel: {can_use} - {reason}")

# Check environment validity
env_valid, env_reason = validate_parallel_environment()
print(f"Environment: {env_valid} - {env_reason}")
```

## Configuration Options

| Option                          | Default  | Description                                             |
| ------------------------------- | -------- | ------------------------------------------------------- |
| `enabled`                       | `False`  | Master toggle - must be True to use parallel            |
| `max_workers`                   | `-1`     | -1=auto (CPU count), -2=CPU count-1, or explicit number |
| `min_formations_for_parallel`   | `3`      | Minimum formations to trigger parallel mode             |
| `timeout_per_formation_seconds` | `300`    | Max time per formation (5 minutes)                      |
| `backend`                       | `"loky"` | Joblib backend (loky is safest for matplotlib)          |
| `fallback_on_error`             | `True`   | Auto-fallback to sequential on any error                |
| `verbose`                       | `10`     | Joblib verbosity level (0-50)                           |

## Safety Mechanisms

### Automatic Fallback

The module automatically falls back to sequential processing when:

1. **Config disabled**: `enabled: False` in config
2. **Environment invalid**: Jupyter, single CPU, missing joblib
3. **Too few formations**: Below `min_formations_for_parallel` threshold
4. **Runtime errors**: Any exception during parallel execution

### Environment Detection

The system automatically detects unsuitable environments:

| Environment      | Detection              | Action           |
| ---------------- | ---------------------- | ---------------- |
| Jupyter Notebook | `get_ipython()` check  | Disable parallel |
| Single CPU       | `os.cpu_count()` check | Disable parallel |
| Missing joblib   | Import error           | Disable parallel |

## Rollback / Removal

### Quick Disable (No Code Changes)

```python
CONFIG = build_config_from_defaults(
    # ...
    parallel_processing_override={"enabled": False},
)
```

### Complete Removal

1. Delete this folder:
   ```bash
   rm -rf geotechnical_plotting/parallel_processing/
   ```

2. Remove from `orchestrator.py` (~15 lines):
   ```python
   # Delete these lines:
   try:
       from .parallel_processing import ...
       PARALLEL_AVAILABLE = True
   except ImportError:
       PARALLEL_AVAILABLE = False
   ```

3. Remove from `shared_config.py` (~20 lines):
   - Delete `DEFAULT_PARALLEL_PROCESSING` constant
   - Remove `parallel_processing_override` parameter from builder

**Total: ~50 lines removed, system returns to pre-parallel state.**

## Troubleshooting

### Parallel Not Activating

1. Check `enabled: True` in config
2. Verify formation count meets threshold
3. Run environment validation:
   ```python
   from geotechnical_plotting.parallel_processing import validate_parallel_environment
   valid, reason = validate_parallel_environment()
   print(f"Valid: {valid}, Reason: {reason}")
   ```

### matplotlib Errors in Workers

If you see matplotlib thread/process errors:
- The worker module forces `matplotlib.use('Agg')` before any imports
- If issues persist, disable parallel: `enabled: False`

### Memory Issues

Reduce worker count:
```python
parallel_processing_override={
    "enabled": True,
    "max_workers": 2,  # Fewer workers = less memory
}
```

## Development Notes

### Adding New Features

1. All parallel code MUST stay in this folder
2. Workers MUST be stateless pure functions
3. All data to workers MUST be serializable (use `.to_dict('records')`)
4. Workers MUST call `matplotlib.use('Agg')` before any matplotlib import
5. Workers MUST call `plt.close('all')` after plot generation

### Testing

Run the test suite to verify parallel/sequential equivalence:

```bash
python -m pytest tests/test_parallel_*.py -v
```

## Version History

| Version | Date    | Changes                                        |
| ------- | ------- | ---------------------------------------------- |
| 1.0.0   | 2024-12 | Initial implementation - config and validation |
| 1.1.0   | TBD     | Worker and orchestrator (Phase 2)              |

---

*SESRO GIR Geotechnical Plotting Pipeline*
