#!/usr/bin/env python3
"""
SESRO Geotechnical Plotting Package
=====================================

Shared module architecture for all geotechnical parameter plotting scripts.
Reduces code duplication from ~5,000 lines per script to ~100-250 lines.

ARCHITECTURAL OVERVIEW:

Responsibility:
Provides unified plotting framework for geotechnical parameter visualization.
Consolidates common functionality across 15+ plotting scripts including data
loading, formation processing, outlier detection, and plot generation.

Package Structure:
- shared_config.py: Configuration builder and PlotConfig dataclass
- data_pipeline.py: Data loading, formation processing, outlier detection
- manual_data.py: Manual outlier/addition handling
- orchestrator.py: Main pipeline orchestration
- data_export_utils/: Investigation summaries and data tracking
- plotting_utils/: Matplotlib and Plotly visualization
- Plotting Scripts/: Parameter-specific plotting scripts

USAGE EXAMPLE:

```python
from geotechnical_plotting import run_parameter_plotting_pipeline
from geotechnical_plotting.shared_config import build_config_from_defaults

CONFIG = build_config_from_defaults(...)

if __name__ == "__main__":
    run_parameter_plotting_pipeline(CONFIG)
```
"""

# ═══════════════════════════════════════════════════════════════════════════
# 📦 PACKAGE VERSION AND METADATA
# ═══════════════════════════════════════════════════════════════════════════

__version__ = "2.0.0"
__author__ = "SESRO GIR Geotechnical Team"

# ═══════════════════════════════════════════════════════════════════════════
# 🔧 CONFIGURATION EXPORTS
# ═══════════════════════════════════════════════════════════════════════════

from .shared_config import (
    # Unified builder (recommended)
    build_config,
    # Specialized builders (backwards compatible)
    build_config_from_defaults,
    build_dual_param_config_from_defaults,
    # Constants
    DEFAULT_EXCLUDE_PREFIXES,
    DEFAULT_INVESTIGATION_COLORS,
    DEFAULT_COLUMN_VARIATIONS,
)

# ═══════════════════════════════════════════════════════════════════════════
# 💾 DATA PIPELINE EXPORTS
# ═══════════════════════════════════════════════════════════════════════════

from .data_pipeline import (
    # Parameter mapping
    extract_parameter_mappings,
    # CSV loading
    find_column_in_dataframe,
    standardize_location_columns,
    filter_location_ids,
    load_csv_data,
    load_parameter_data,
    # Formation processing
    add_strata_description,
    create_enhanced_geological_strata_column,
    classify_weathering_state,
    classify_rtd_subformation,
    create_enhanced_formation_code,
    # Formation grouping
    group_data_by_formation_unified,
    # Investigation
    load_location_details,
    add_investigation_column,
    create_investigation_color_mapping,
    # Empirical calculations
    apply_empirical_calculations,
    # Unified data
    prepare_unified_data_objects,
    # Outlier detection
    detect_outliers_standard_iqr,
    detect_outliers_per_csv,
    filter_outliers_from_formations,
    # Threshold filtering (Script-Specific Filtering Phase)
    apply_cell_pressure_threshold_filtering,
    apply_formation_parameter_threshold_filtering,
    apply_test_type_threshold_filtering,
    # Excel export
    export_highlighted_excel,
)

# ═══════════════════════════════════════════════════════════════════════════
# 🔍 MANUAL DATA EXPORTS
# ═══════════════════════════════════════════════════════════════════════════

from .manual_data import (
    # Manual outliers
    load_manual_outliers,
    mark_manual_outliers,
    print_manual_outlier_summary,
    # Manual additions
    load_manual_additions,
    mark_manual_additions,
    print_manual_addition_summary,
    # CSV export
    export_manual_data_changes_csv,
)

# ═══════════════════════════════════════════════════════════════════════════
# 🎨 PLOTTING EXPORTS
# ═══════════════════════════════════════════════════════════════════════════

from .plotting_utils import (
    generate_depth_plot,
    generate_manually_modified_depth_plot,
    create_investigation_color_mapping,
    sanitize_filename,
)

# ═══════════════════════════════════════════════════════════════════════════
# 📊 DATA EXPORT EXPORTS
# ═══════════════════════════════════════════════════════════════════════════

from .data_export_utils import (
    generate_investigation_summary,
    extract_investigation_sources,
    export_investigation_csv,
    should_generate_output,
    should_generate_data_export,
    track_filtered_data,
)

# ═══════════════════════════════════════════════════════════════════════════
# ⚡ ORCHESTRATION PIPELINE
# ═══════════════════════════════════════════════════════════════════════════

from .orchestrator import (
    # Unified pipeline (recommended)
    run_plotting_pipeline,
    # Specialized pipelines (backwards compatible)
    run_parameter_plotting_pipeline,
    run_dual_parameter_plotting_pipeline,
    run_psd_plotting_pipeline,
)


# ═══════════════════════════════════════════════════════════════════════════
# 📋 PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    # Version
    "__version__",
    # Configuration (unified)
    "build_config",
    # Configuration (specialized - backwards compatible)
    "build_config_from_defaults",
    "build_dual_param_config_from_defaults",
    "DEFAULT_EXCLUDE_PREFIXES",
    "DEFAULT_INVESTIGATION_COLORS",
    "DEFAULT_COLUMN_VARIATIONS",
    # Data pipeline
    "extract_parameter_mappings",
    "find_column_in_dataframe",
    "standardize_location_columns",
    "filter_location_ids",
    "load_csv_data",
    "load_parameter_data",
    "add_strata_description",
    "create_enhanced_geological_strata_column",
    "classify_weathering_state",
    "classify_rtd_subformation",
    "create_enhanced_formation_code",
    # Formation grouping
    "group_data_by_formation_unified",
    "load_location_details",
    "add_investigation_column",
    "create_investigation_color_mapping",
    "apply_empirical_calculations",
    "prepare_unified_data_objects",
    "detect_outliers_standard_iqr",
    "detect_outliers_per_csv",
    "filter_outliers_from_formations",
    # Threshold filtering (Script-Specific Filtering Phase)
    "apply_cell_pressure_threshold_filtering",
    "apply_formation_parameter_threshold_filtering",
    "apply_test_type_threshold_filtering",
    "export_highlighted_excel",
    # Manual data
    "load_manual_outliers",
    "mark_manual_outliers",
    "print_manual_outlier_summary",
    "load_manual_additions",
    "mark_manual_additions",
    "print_manual_addition_summary",
    "export_manual_data_changes_csv",
    # Plotting
    "generate_depth_plot",
    "generate_manually_modified_depth_plot",
    "sanitize_filename",
    # Data export
    "generate_investigation_summary",
    "extract_investigation_sources",
    "export_investigation_csv",
    "should_generate_output",
    "should_generate_data_export",
    "track_filtered_data",
    # Orchestration (unified)
    "run_plotting_pipeline",
    # Orchestration (specialized - backwards compatible)
    "run_parameter_plotting_pipeline",
    "run_dual_parameter_plotting_pipeline",
    "run_psd_plotting_pipeline",
]
