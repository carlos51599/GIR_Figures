"""
SharePoint Output Folder Structure Generator - Combined Output Only

ARCHITECTURAL OVERVIEW:
Responsibility: Creates SharePoint-ready folder structure organizing all output files by formation and output type.
                Generates combined output merging HTML plots, PNG plots, manually excluded PNGs, and investigation summary CSVs.

Key Interactions:
- Input: Scans Output folder for various file types in specific directory patterns
- Output: Creates Sharepoint Output Combined folder with formation-based organization
- Configuration: Uses CONFIG dictionary with output type definitions and toggle controls

Navigation Guide:
1. Configuration Section - Define output types, source patterns, and toggle controls
2. Logging Setup - Configure file and console logging
3. Discovery Functions - File discovery for HTML, PNG, manually excluded, and CSV files
4. Structure Creation - Folder creation and file copying for combined output
5. Main Execution - Orchestrate discovery and structure creation

For Navigation: Use VS Code outline (Ctrl+Shift+O) to jump between sections.

CONFIGURATION ARCHITECTURE:
- Single source of truth: All configuration in CONFIG dictionary
- Coordination boundaries: Main function extracts config values
- Primitive injection: Functions accept explicit typed parameters
- Zero hidden dependencies: All behavior predictable from signatures
- Full testability: Functions accept primitives, no config mocking required
"""

import shutil
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
import logging

# ═══════════════════════════════════════════════════════════════════════════
# 🔧 CONFIGURATION SECTION
# ═══════════════════════════════════════════════════════════════════════════

CONFIG = {
    "base_path": r"C:\Users\dea29431\OneDrive - Rsk Group Limited\Documents\Geotech\SESRO\SESRO GIR\Figures",
    "output_folder": "Output",
    "log_file": "logs/sharepoint_structure_combined.log",
    "sharepoint_folder": "SharePoint Combined",
    # MODIFICATION POINT: Toggle controls for different file types in combined output
    "include_html_plots": True,  # Include HTML plots
    "include_with_outliers": True,  # Include PNG with outliers
    "include_manually_excluded": True,  # Include manually excluded/modified PNGs
    "include_investigation_summary": True,  # Include investigation_summary.csv per formation
    # ═══════════════════════════════════════════════════════════════════════
    # OUTPUT TYPES CONFIGURATION
    # ═══════════════════════════════════════════════════════════════════════
    "output_types": [
        "ALine",
        "Calculated_CV",
        "CoefficientConsolidationvsCellPressure",
        "CoefficientVolumeCompressibility",
        "Cohesion",
        "DrainedStiffnessEprime",
        "EffectiveAngleFriction",
        "In Situ Horizontal Stress",
        "Initial Shear Modulus",
        "MoistureContent",
        "ParticleSizeDistribution",
        "PlasticityIndex",
        "UndrainedShearStrength",
        "UndrainedStiffnessEu",
        "UnitWeightBulk",
    ],
}


# ═══════════════════════════════════════════════════════════════════════════
# 🛠️ LOGGING SETUP
# ═══════════════════════════════════════════════════════════════════════════


def setup_logging(log_file_path: str) -> logging.Logger:
    """
    Configure logging with file and console handlers.

    Args:
        log_file_path: Path to log file

    Returns:
        Configured logger instance
    """
    log_path = Path(log_file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("sharepoint_combined")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    # File handler
    file_handler = logging.FileHandler(log_file_path, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# ═══════════════════════════════════════════════════════════════════════════
# 🔍 DISCOVERY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def discover_files_by_pattern(
    output_base: Path,
    output_types: List[str],
    source_pattern: str,
    file_extension: str,
    logger: logging.Logger,
) -> Dict[str, Dict[str, Path]]:
    """
    Discover files organized by output type and formation (single pattern).

    Args:
        output_base: Base path to Output folder
        output_types: List of output type folder names
        source_pattern: Subdirectory pattern to search
        file_extension: File extension to search for (e.g., '*.html', '*.png')
        logger: Logger instance

    Returns:
        Dictionary mapping output_type -> {formation_name: file_path}
    """
    discovered: Dict[str, Dict[str, Path]] = {}

    for output_type in output_types:
        source_dir = output_base / output_type / source_pattern

        if not source_dir.exists():
            continue

        files = list(source_dir.glob(file_extension))

        if files:
            discovered[output_type] = {}
            for file_path in files:
                formation_name = file_path.stem
                discovered[output_type][formation_name] = file_path

    return discovered


def discover_manually_excluded_files(
    output_base: Path,
    output_types: List[str],
    logger: logging.Logger,
) -> Dict[str, Dict[str, List[Tuple[Path, str]]]]:
    """
    Discover manually excluded/modified PNG files from multiple source directories.

    Args:
        output_base: Base path to Output folder
        output_types: List of output type folder names
        logger: Logger instance

    Returns:
        Dictionary mapping output_type -> formation -> [(file_path, suffix)]
    """
    discovered: Dict[str, Dict[str, List[Tuple[Path, str]]]] = {}
    source_patterns = [
        ("investigation_series/manually_identified_excluded", "_manually_excluded"),
        ("investigation_series/manually_modified", "_manually_modified"),
    ]

    for output_type in output_types:
        for source_pattern, suffix in source_patterns:
            source_dir = output_base / output_type / source_pattern

            if not source_dir.exists():
                continue

            files = list(source_dir.glob("*.png"))

            if files:
                if output_type not in discovered:
                    discovered[output_type] = {}

                for file_path in files:
                    formation_name = file_path.stem
                    if formation_name not in discovered[output_type]:
                        discovered[output_type][formation_name] = []
                    discovered[output_type][formation_name].append((file_path, suffix))

    return discovered


def discover_investigation_summary_csvs(
    output_base: Path,
    output_types: List[str],
    logger: logging.Logger,
) -> Dict[str, Path]:
    """
    Discover investigation_summary.csv files by output type.

    Args:
        output_base: Base path to Output folder
        output_types: List of output type folder names
        logger: Logger instance

    Returns:
        Dictionary mapping output_type -> csv_file_path
    """
    discovered: Dict[str, Path] = {}

    for output_type in output_types:
        source_dir = output_base / output_type / "data"
        csv_file = source_dir / "investigation_summary.csv"

        if csv_file.exists():
            discovered[output_type] = csv_file

    return discovered


# ═══════════════════════════════════════════════════════════════════════════
# 🏗️ STRUCTURE CREATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def create_combined_structure(
    sharepoint_base: Path,
    html_files: Dict[str, Dict[str, Path]],
    png_files: Dict[str, Dict[str, Path]],
    manually_excluded_files: Dict[str, Dict[str, List[Tuple[Path, str]]]],
    csv_files: Dict[str, Path],
    logger: logging.Logger,
) -> Dict[str, int]:
    """
    Create combined SharePoint folder structure organized by formation.

    Structure: {sharepoint_base}/{formation}/{output_type}/[files + investigation_summary.csv]

    Args:
        sharepoint_base: Base path for SharePoint Output folder
        html_files: Dict mapping output_type -> formation -> html_file_path
        png_files: Dict mapping output_type -> formation -> png_file_path
        manually_excluded_files: Dict mapping output_type -> formation -> [(file_path, suffix)]
        csv_files: Dict mapping output_type -> csv_file_path
        logger: Logger instance

    Returns:
        Statistics dictionary with counts
    """
    stats = {"formations_created": 0, "folders_created": 0, "files_copied": 0}

    # Collect all unique formations across all output types
    all_formations: Set[str] = set()
    for output_type_files in html_files.values():
        all_formations.update(output_type_files.keys())
    for output_type_files in png_files.values():
        all_formations.update(output_type_files.keys())
    for output_type_files in manually_excluded_files.values():
        all_formations.update(output_type_files.keys())

    logger.info(f"📊 Found {len(all_formations)} unique formations")

    # Create formation folders and copy all files
    for formation in sorted(all_formations):
        formation_folder = sharepoint_base / formation
        formation_folder.mkdir(parents=True, exist_ok=True)
        stats["formations_created"] += 1

        # Collect all output types for this formation
        output_types_for_formation = set()
        for output_type, formations in html_files.items():
            if formation in formations:
                output_types_for_formation.add(output_type)
        for output_type, formations in png_files.items():
            if formation in formations:
                output_types_for_formation.add(output_type)
        for output_type, formations in manually_excluded_files.items():
            if formation in formations:
                output_types_for_formation.add(output_type)

        # Create output type folders and copy files
        for output_type in sorted(output_types_for_formation):
            output_type_folder = formation_folder / output_type
            output_type_folder.mkdir(parents=True, exist_ok=True)
            stats["folders_created"] += 1

            # Copy HTML file if exists
            if output_type in html_files and formation in html_files[output_type]:
                source_file = html_files[output_type][formation]
                dest_file = output_type_folder / source_file.name
                shutil.copy2(source_file, dest_file)
                stats["files_copied"] += 1

            # Copy PNG file if exists
            if output_type in png_files and formation in png_files[output_type]:
                source_file = png_files[output_type][formation]
                dest_file = output_type_folder / source_file.name
                shutil.copy2(source_file, dest_file)
                stats["files_copied"] += 1

            # Copy manually excluded files if exist
            if (
                output_type in manually_excluded_files
                and formation in manually_excluded_files[output_type]
            ):
                for source_file, suffix in manually_excluded_files[output_type][
                    formation
                ]:
                    dest_name = f"{source_file.stem}{suffix}{source_file.suffix}"
                    dest_file = output_type_folder / dest_name
                    shutil.copy2(source_file, dest_file)
                    stats["files_copied"] += 1

            # Copy investigation_summary.csv if exists for this output type
            if output_type in csv_files:
                source_csv = csv_files[output_type]
                dest_csv = (
                    output_type_folder / f"investigation_summary_{output_type}.csv"
                )
                shutil.copy2(source_csv, dest_csv)
                stats["files_copied"] += 1

    return stats


# ═══════════════════════════════════════════════════════════════════════════
# 🚀 MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════════════


def main() -> None:
    """Main orchestrator function."""
    # Extract configuration values (Coordination boundary)
    base_path = Path(CONFIG["base_path"])
    output_folder = CONFIG["output_folder"]
    log_file = CONFIG["log_file"]
    sharepoint_folder = CONFIG["sharepoint_folder"]
    output_types = CONFIG["output_types"]
    include_html = CONFIG["include_html_plots"]
    include_png = CONFIG["include_with_outliers"]
    include_manually_excluded = CONFIG["include_manually_excluded"]
    include_csv = CONFIG["include_investigation_summary"]

    # Setup logging
    logger = setup_logging(log_file)

    logger.info("=" * 70)
    logger.info("🚀 SharePoint Combined Output Structure Generator Started")
    logger.info("=" * 70)
    logger.info(f"📁 Base Path: {base_path}")
    logger.info("")
    logger.info("📋 Output Configuration:")
    logger.info(f"   Include HTML Plots: {'✅' if include_html else '❌'}")
    logger.info(f"   Include PNG with Outliers: {'✅' if include_png else '❌'}")
    logger.info(
        f"   Include Manually Excluded: {'✅' if include_manually_excluded else '❌'}"
    )
    logger.info(f"   Include Investigation Summary: {'✅' if include_csv else '❌'}")
    logger.info("")

    # Define paths
    output_base = base_path / output_folder
    sharepoint_base = base_path / sharepoint_folder

    # Check if output folder exists
    if not output_base.exists():
        logger.error(f"❌ Output folder not found: {output_base}")
        return

    # Create SharePoint base folder
    sharepoint_base.mkdir(parents=True, exist_ok=True)

    logger.info("-" * 70)
    logger.info("🔍 Discovering Files...")
    logger.info("-" * 70)

    # Discover files based on configuration
    html_files: Dict[str, Dict[str, Path]] = {}
    png_files: Dict[str, Dict[str, Path]] = {}
    manually_excluded_files: Dict[str, Dict[str, List[Tuple[Path, str]]]] = {}
    csv_files: Dict[str, Path] = {}

    if include_html:
        html_files = discover_files_by_pattern(
            output_base,
            output_types,
            "investigation_series/html_interactive/with_outliers",
            "*.html",
            logger,
        )
        logger.info(
            f"   📊 HTML Plots: {sum(len(f) for f in html_files.values())} files"
        )

    if include_png:
        png_files = discover_files_by_pattern(
            output_base,
            output_types,
            "investigation_series/with_outliers",
            "*.png",
            logger,
        )
        logger.info(
            f"   📊 PNG with Outliers: {sum(len(f) for f in png_files.values())} files"
        )

    if include_manually_excluded:
        manually_excluded_files = discover_manually_excluded_files(
            output_base,
            output_types,
            logger,
        )
        total_manually_excluded = sum(
            len(files)
            for formation_files in manually_excluded_files.values()
            for files in formation_files.values()
        )
        logger.info(f"   📊 Manually Excluded: {total_manually_excluded} files")

    if include_csv:
        csv_files = discover_investigation_summary_csvs(
            output_base,
            output_types,
            logger,
        )
        logger.info(f"   📊 Investigation Summary CSVs: {len(csv_files)} files")

    # Check if any files were discovered
    if (
        not html_files
        and not png_files
        and not manually_excluded_files
        and not csv_files
    ):
        logger.warning("⚠️ No files discovered. Nothing to process.")
        return

    logger.info("")
    logger.info("-" * 70)
    logger.info("🏗️ Creating Combined Structure...")
    logger.info("-" * 70)

    # Create combined structure
    stats = create_combined_structure(
        sharepoint_base,
        html_files,
        png_files,
        manually_excluded_files,
        csv_files,
        logger,
    )

    logger.info(f"✅ Copied {stats['files_copied']} files")
    logger.info("")

    # Print summary
    logger.info("=" * 70)
    logger.info("✅ SHAREPOINT STRUCTURE CREATION COMPLETE")
    logger.info("=" * 70)
    logger.info(
        f"📊 Summary: {stats['formations_created']} formations, "
        f"{stats['folders_created']} folders, {stats['files_copied']} files"
    )
    logger.info(f"📁 Output Location: {sharepoint_base}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
