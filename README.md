# SESRO GIR Geotechnical Plotting

Automated geotechnical plotting pipeline for the SESRO Ground Investigation Report. Generates interactive Plotly HTML and static Matplotlib PNG plots from Openground lab/field test data.

## How It Works

1. The plotting script specifies a parameter name. The system reads `Parameter_CSV_Mapping.csv` to find which Openground CSVs contain that parameter.
2. Raw CSVs are loaded, columns standardised, and Location Details joined for investigation metadata.
3. Most CSVs are in the Reports/Geology section of OpenGround with the execption of PSD data, Pressuremeter data and Location Details. Remember to first filter to the GIR location group.
4. Data is grouped by geological formation (Kimmeridge Clay, Gault Clay, RTD, etc.) with weathering splits where applicable.
5. IQR-based outlier detection runs but does not apply filtering, then `Data to Remove.xlsx` / `Data to Add.xlsx` are applied for manual curation.
6. Plotly (interactive HTML) and Matplotlib (static PNG) plots are generated per formation.

**Warning**

* There are several layers of filtering active, global, plot specific and formation specific. Review these.

## Key Files

| File / Folder                                       | Purpose                                                                                                                                                      |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `geotechnical_plotting/Plotting Scripts/`           | **Plot scripts** -- one config-only script per geotechnical parameter; each can be run individually to generate plots for that parameter                     |
| `Openground CSVs/`                                  | **Source data** -- 19 CSV files exported from Openground (classification, triaxial, CPT, PSD, vane tests, etc.)                                              |
| `Parameter_CSV_Mapping.csv`                         | **Parameter mapping** -- maps each geotechnical parameter to the CSV file(s) and column(s) that contain it                                                   |
| `Data to Remove.xlsx`                               | **Manual outlier list** -- Excel workbook with per-parameter sheets listing data points to exclude from plots (matched by Location ID + value + depth)       |
| `Data to Add.xlsx`                                  | **Manual addition list** -- Excel workbook with per-parameter sheets listing data points to manually include in plots                                        |
| `create_sharepoint_structure_combined.py`           | **SharePoint exporter** -- scans `Output/` and copies HTML plots, PNGs, and summary CSVs into a formation-based folder structure ready for SharePoint upload |
| `geotechnical_plotting/run_all_plotting_scripts.py` | **Batch runner** -- executes all plotting scripts sequentially or in parallel with CPU-based worker calculation, progress tracking, and summary reporting    |

## Running Plots

**All parameters at once:**

```bash
python geotechnical_plotting/run_all_plotting_scripts.py
```

This runs every script in `Plotting Scripts/` with parallel support and progress tracking.

**Individual parameter:**

```bash
python "geotechnical_plotting/Plotting Scripts/MCvsDepth.py"
python "geotechnical_plotting/Plotting Scripts/UndrainedShearStrength.py"
python "geotechnical_plotting/Plotting Scripts/PSD.py"
```

Each script in `geotechnical_plotting/Plotting Scripts/` is self-contained and can be run independently.

Output goes to `Output/<ParameterName>/` as Plotly HTML, Matplotlib PNG, and summary CSVs.

## Dependencies

Python 3.8+ with pandas, numpy, plotly, matplotlib, openpyxl, and joblib.
