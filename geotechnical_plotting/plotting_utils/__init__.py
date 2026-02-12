#!/usr/bin/env python3
"""
SESRO Geotechnical Plotting - Plotting Utilities Module
========================================================

Visualization utilities for geotechnical plotting:
- Plotly interactive HTML plots
- Matplotlib static PNG plots
- Shared plotting utilities
"""

# Plotly utilities
from .plotly_utils import (
    generate_depth_plot,
    generate_xy_plot,
    generate_psd_plot as generate_plotly_psd_plot,
    # Unified functions (Phase 2 & 3 unification)
    get_plot_layout,
    create_hover_text,
    # FAQ panel generation
    generate_faq_panel_html,
    FAQ_PANEL_CONFIG,
    # Unified injection builder
    build_combined_injection_and_faq,
    DEFAULT_FAQ_ITEMS,
)

# Matplotlib utilities
from .matplotlib_utils import (
    generate_depth_plot as generate_matplotlib_depth_plot,
    generate_xy_plot as generate_matplotlib_xy_plot,
    generate_manually_modified_depth_plot,
    generate_psd_plot as generate_matplotlib_psd_plot,
)

# Shared plotting utilities
from .shared_plotting_utils import (
    create_investigation_color_mapping,
    sanitize_filename,
    # Plot type helpers (Phase 1 unification)
    get_axis_parameters,
    resolve_manual_data_paths,
    get_plotly_figure_size,
    get_matplotlib_figure_size,
)

__all__ = [
    # Plotly
    "generate_depth_plot",
    "generate_xy_plot",
    "generate_plotly_psd_plot",
    # Unified Plotly functions (recommended)
    "get_plot_layout",
    "create_hover_text",
    # FAQ panel
    "generate_faq_panel_html",
    "FAQ_PANEL_CONFIG",
    # Matplotlib
    "generate_matplotlib_depth_plot",
    "generate_matplotlib_xy_plot",
    "generate_manually_modified_depth_plot",
    "generate_matplotlib_psd_plot",
    # Shared
    "create_investigation_color_mapping",
    "sanitize_filename",
    "get_axis_parameters",
    "resolve_manual_data_paths",
    "get_plotly_figure_size",
    "get_matplotlib_figure_size",
]
