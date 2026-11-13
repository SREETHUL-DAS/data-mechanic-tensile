"""
=============================================================================
  DATA MECHANIC - TENSILE ENGINE
  You don't need to open or change this file.
  To run the toolkit, open run_analysis.py and press Run.
=============================================================================

For the curious: what this file does, step by step
  1. Reads each raw test file (Instron / Bluehill-style CSV export):
     skips the information lines at the top, finds the Time and Load/Force
     columns, reads the units and converts to N, mm and mm/mm.
  2. Engineering stress = force / original area.
     Strain = extensometer reading, or crosshead extension / gauge length.
  3. Young's modulus = slope of a straight line fitted between 10 % and 40 %
     of the maximum stress. This range is fixed in advance (a stated default),
     never adjusted to get a preferred value.
  4. The start of the strain axis is moved to where the fitted line crosses
     zero stress (removes initial slack in the grips).
  5. 0.2 % proof stress = where the curve meets a line parallel to the
     elastic slope, offset by 0.2 % strain. The curve must stay below the
     line for 5 points, so one noisy reading cannot fool it.
  6. UTS = highest measured stress. Candidate fracture = first sudden load
     drop after the UTS. Plastic strain at fracture = strain at that point
     minus the elastic part that recovers.
  7. Mean and standard deviation, a results table, an Excel file and a figure.
  8. Plain-language warnings whenever a result needs caution.

Licence: MIT
"""
import io
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent

UNIT_FACTORS = {  # converts to N, mm, s, mm/mm
    "n": 1.0, "kn": 1e3, "lbf": 4.44822,
    "mm": 1.0, "in": 25.4,
    "s": 1.0, "sec": 1.0, "min": 60.0,
    "%": 0.01, "mm/mm": 1.0,
}
ALIASES = {
    "time": ["time"],
    "force": ["load", "force"],
    "extension": ["extension", "displacement", "crosshead"],
    "ext_strain": ["strain 1", "extensometer", "dic strain"],
}
FIT_WINDOW = (0.10, 0.40)   # modulus fit range, fraction of maximum stress
OFFSET = 0.002              # 0.2 % offset


# ------------------------------------------------------------------ reading
def _cells(line):
    return [c.strip().strip('"').strip() for c in line.split(",")]


def read_raw_file(path):
    """Read one raw test file and return force, extension and strain columns."""
    path = Path(path)
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    hdr = None
    for i, line in enumerate(lines):
        low = [c.lower() for c in _cells(line)]
        if any(c.startswith("time") for c in low) and any(("load" in c) or ("force" in c) for c in low):
            hdr = i
            break
    if hdr is None:
        raise ValueError(f"{path.name}: could not find a header row containing Time and Load (or Force).")

    names = _cells(lines[hdr])
    unit_row = _cells(lines[hdr + 1])
    if all(u.startswith("(") or u == "" for u in unit_row):
        units = [u.strip("()").lower() for u in unit_row]
        start = hdr + 2
    else:  # units inside the header, e.g. "Load (kN)"
        units = [n.split("(")[-1].rstrip(")").lower() if "(" in n else "" for n in names]
        start = hdr + 1

    df = pd.read_csv(io.StringIO("\n".join(lines[start:])), header=None).iloc[:, : len(names)]
    df.columns = names
    out = {}
    for key, keys in ALIASES.items():
        for col, unit in zip(names, units):
            if any(k in col.lower() for k in keys) and key not in out:
                if unit == "" and key == "time":
                    factor = 1.0  # time is not used in any calculation
                elif unit == "":
                    raise ValueError(
                        f"{path.name}: column '{col}' has no unit. Add one in brackets, "
                        f"e.g. '{col} (N)', or in a units row below the column names.")
                elif unit not in UNIT_FACTORS:
                    raise ValueError(
                        f"{path.name}: unknown unit '{unit}' in column '{col}'. "
                        f"Units understood: {', '.join(UNIT_FACTORS)}.")
                else:
                    factor = UNIT_FACTORS[unit]
                out[key] = pd.to_numeric(df[col], errors="coerce").to_numpy() * factor
    if "force" not in out:
        raise ValueError(f"{path.name}: no Load or Force column found.")
    data = pd.DataFrame(out).dropna()
    data.attrs["simulated"] = "SIMULATED" in "\n".join(lines[:hdr]).upper()
    return data


# ------------------------------------------------------------------ analysis
def analyse_specimen(data, area, gauge_length, source="extensometer",
                     window=FIT_WINDOW, offset=OFFSET, run=5):
    """Properties of one specimen plus a list of plain-language warnings."""
    warnings = []
    stress = data["force"].to_numpy() / area
    if source == "extensometer":
        if "ext_strain" not in data:
            raise ValueError("no extensometer strain column in the file. "
                             "Set strain_source to crosshead in specimens.xlsx.")
        strain = data["ext_strain"].to_numpy()
    elif source == "crosshead":
        if "extension" not in data:
            raise ValueError("no Extension column in the file.")
        strain = data["extension"].to_numpy() / gauge_length
        warnings.append("Strain from crosshead: modulus is not reliable and strains are "
                        "overestimated. Use extensometer data for E if available.")
    else:
        raise ValueError(f"strain source must be extensometer or crosshead, not '{source}'.")

    # UTS = measured maximum; a smoothed curve is used only to spot a possible spike
    i_uts = int(np.argmax(stress))
    uts = float(stress[i_uts])
    smooth = pd.Series(stress).rolling(5, center=True, min_periods=1).median().to_numpy()
    if uts > 1.01 * smooth.max():
        warnings.append("Maximum stress looks like a single-point spike - check the raw curve.")

    # candidate fracture: first sudden drop (> 10 % of UTS between readings) after UTS
    drops = np.where(np.diff(stress[i_uts:]) < -0.10 * uts)[0]
    if drops.size:
        i_frac = i_uts + int(drops[0])
    else:
        i_frac = len(stress) - 1
        warnings.append("No sudden load drop found - the test may have stopped before fracture.")

    # modulus: straight-line fit on the first rise through the window
    lo, hi = window[0] * uts, window[1] * uts
    i_hi = int(np.argmax(stress > hi))
    mask = np.zeros_like(stress, dtype=bool)
    mask[:i_hi] = stress[:i_hi] >= lo
    n_fit = int(mask.sum())
    if n_fit < 10:
        raise RuntimeError(f"only {n_fit} readings in the elastic part - the sampling rate is too low.")
    if n_fit < 20:
        warnings.append(f"Only {n_fit} readings in the elastic fit - use a higher sampling rate next time.")
    E, b = np.polyfit(strain[mask], stress[mask], 1)
    resid = stress[mask] - (E * strain[mask] + b)
    r2 = 1 - resid.var() / stress[mask].var()
    if r2 < 0.995:
        warnings.append(f"Elastic part is not very straight (R² = {r2:.3f}) - modulus is uncertain.")
    strain_c = strain - (-b / E)  # start strain where the elastic line crosses zero

    # 0.2 % proof stress
    d = stress - E * (strain_c - offset)
    k = next((j for j in range(i_hi, len(d) - run) if np.all(d[j: j + run] < 0)), None)
    if k is None:
        raise RuntimeError("the curve never crosses the 0.2 % offset line - check the data.")
    f = d[k - 1] / (d[k - 1] - d[k])
    rp02 = stress[k - 1] + f * (stress[k] - stress[k - 1])

    e_frac, s_frac = strain_c[i_frac], stress[i_frac]
    return {
        "E_GPa": E / 1000.0,
        "Rp02_MPa": rp02,
        "UTS_MPa": uts,
        "uniform_strain_%": 100 * strain_c[i_uts],
        "strain_at_fracture_%": 100 * e_frac,
        "plastic_strain_at_fracture_%": 100 * (e_frac - s_frac / E),
        "E_fit_points": n_fit,
        "E_fit_R2": r2,
        "warnings": warnings,
        "_strain": strain_c[: i_frac + 1],
        "_stress": stress[: i_frac + 1],
    }


# ------------------------------------------------------------------ report
REPORT = {  # column: (label, decimals) for thesis-style reporting
    "E_GPa": ("Young's modulus (GPa)", 1),
    "Rp02_MPa": ("0.2% proof stress (MPa)", 0),
    "UTS_MPa": ("Ultimate tensile strength (MPa)", 0),
    "uniform_strain_%": ("Uniform strain (%)", 1),
    "plastic_strain_at_fracture_%": ("Plastic strain at fracture, from curve (%)", 1),
}


def _folder(path_text):
    p = Path(path_text)
    return p if p.is_absolute() else HERE / p


def _stop(message):
    print("\n" + "=" * 70 + "\nCANNOT CONTINUE\n" + message + "\n" + "=" * 70)
    raise SystemExit(1)


REQUIRED = ["file", "specimen_id", "width_mm", "thickness_mm", "gauge_length_mm", "strain_source"]


def read_specimen_sheet(data_folder):
    """Read specimens.xlsx (sheet 'Specimens'), or specimens.csv, from the data folder."""
    data_folder = Path(data_folder)
    xlsx, csv = data_folder / "specimens.xlsx", data_folder / "specimens.csv"
    if xlsx.exists():
        try:
            sheet = pd.read_excel(xlsx, sheet_name="Specimens")
        except ValueError:
            _stop(f"specimens.xlsx in {data_folder.name} has no sheet called 'Specimens'.\n"
                  "Don't rename that sheet.")
        except ImportError:
            _stop("Reading Excel needs one extra library. In the terminal, run once:\n"
                  "  pip install openpyxl")
    elif csv.exists():
        sheet = pd.read_csv(csv)
    else:
        _stop(f"No specimens.xlsx found in:\n  {data_folder}\n"
              "Every data folder needs its own specimens.xlsx (copy the one from my_data).")
    sheet.columns = [str(c).strip() for c in sheet.columns]
    missing = [c for c in REQUIRED if c not in sheet.columns]
    if missing:
        _stop(f"The specimen sheet is missing these columns: {', '.join(missing)}.\n"
              "Don't change the column headings.")
    sheet = sheet.dropna(subset=["file"])
    sheet = sheet[sheet["file"].astype(str).str.strip() != ""]
    if sheet.empty:
        _stop(f"No specimens are listed in the sheet in {data_folder.name}.\n"
              "Open specimens.xlsx, fill in one row per test file, and save.")
    blanks = sheet[REQUIRED].isna().any(axis=1)
    if blanks.any():
        rows = ", ".join(str(sheet.loc[i, "file"]) for i in sheet.index[blanks])
        _stop(f"Some cells are empty for: {rows}.\nFill in every column for each test file.")
    return sheet


def analyse_folder(data_folder, strain_source="sheet"):
    data_folder = Path(data_folder)
    if not data_folder.exists():
        _stop(f"The data folder does not exist:\n  {data_folder}\n"
              "Check DATA_FOLDER in run_analysis.py.")
    sheet = read_specimen_sheet(data_folder)

    rows, curves, simulated = [], {}, False
    for _, s in sheet.iterrows():
        f = data_folder / str(s["file"]).strip()
        if not f.exists():
            _stop(f"The specimen sheet lists '{s['file']}', but that file is not in:\n  {data_folder}\n"
                  "Check the file name (including .csv) in the sheet.")
        choice = str(strain_source).strip().lower()
        if choice in ("sheet", "as in specimens.xlsx"):
            src = str(s["strain_source"]).strip().lower()
        elif choice in ("extensometer", "crosshead"):
            src = choice
        else:
            _stop(f"STRAIN_SOURCE in run_analysis.py is '{strain_source}'.\n"
                  'Use "as in specimens.xlsx", "extensometer" or "crosshead".')
        try:
            data = read_raw_file(f)
            r = analyse_specimen(data, s["width_mm"] * s["thickness_mm"], s["gauge_length_mm"], src)
        except (ValueError, RuntimeError) as err:
            _stop(f"Problem with specimen {s['specimen_id']} ({f.name}):\n  {err}")
        simulated |= data.attrs.get("simulated", False)
        curves[str(s["specimen_id"])] = (r.pop("_strain"), r.pop("_stress"))
        r["warnings"] = " | ".join(r["warnings"])
        rows.append({"specimen": s["specimen_id"], "strain_source": src, **r})

    table = pd.DataFrame(rows)
    n = len(table)
    summary = pd.DataFrame({
        "property": [REPORT[c][0] for c in REPORT],
        "mean": [round(table[c].mean(), d) for c, (_, d) in REPORT.items()],
        "SD": [round(table[c].std(ddof=1), d) if n > 1 else np.nan for c, (_, d) in REPORT.items()],
        "report_as": [f"{table[c].mean():.{d}f} ± {table[c].std(ddof=1):.{d}f}" if n > 1
                      else f"{table[c].mean():.{d}f}" for c, (_, d) in REPORT.items()],
    })
    return table, summary, curves, simulated


def make_figure(curves, path, s, simulated):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": s["FONT_SIZE"], "axes.linewidth": 0.8})
    fig, ax = plt.subplots(figsize=s["FIGURE_SIZE"])
    colours = s["COLOURS"]
    for i, (sid, (e, st)) in enumerate(curves.items()):
        ax.plot(e * 100, st, lw=s["LINE_WIDTH"], label=sid,
                color=colours[i % len(colours)] if colours else None)
    if s["TITLE"]:
        ax.set_title(s["TITLE"], fontsize=s["FONT_SIZE"] + 2)
    ax.set_xlabel(s["X_LABEL"], fontsize=s["FONT_SIZE"])
    ax.set_ylabel(s["Y_LABEL"], fontsize=s["FONT_SIZE"])
    ax.legend(loc=s["LEGEND_POSITION"], fontsize=s["FONT_SIZE"] - 2, frameon=False)
    if s["SHOW_GRID"]:
        ax.grid(True, alpha=0.3)
    ax.set_xlim(s["X_LIMITS"] if s["X_LIMITS"] else (0, None))
    ax.set_ylim(s["Y_LIMITS"] if s["Y_LIMITS"] else (0, None))
    if simulated:
        ax.text(0.98, 0.98, "SIMULATED DATA", transform=ax.transAxes,
                ha="right", va="top", fontsize=6, color="0.4")
    fig.tight_layout()
    fig.savefig(path, dpi=s["DPI"])
    png = io.BytesIO()
    fig.savefig(png, format="png", dpi=200)  # copy for the Excel summary
    plt.close(fig)
    png.seek(0)
    return png


def write_excel(path, table, summary, figure_png, data_folder, simulated):
    """Formatted results.xlsx: Summary sheet (with the figure) + Specimens sheet."""
    from datetime import date

    from openpyxl import Workbook
    from openpyxl.drawing.image import Image as XLImage
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    navy, grey = "1F4E79", "595959"
    head_fill = PatternFill("solid", fgColor=navy)
    band = PatternFill("solid", fgColor="F2F2F2")
    thin = Side(style="thin", color="BFBFBF")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    F = "Arial"

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.sheet_view.showGridLines = False
    for col, w in zip("ABCDE", (3, 44, 12, 10, 16)):
        ws.column_dimensions[col].width = w

    ws["B2"] = "Data Mechanic – Tensile test results"
    ws["B2"].font = Font(name=F, size=16, bold=True, color=navy)
    ws["B3"] = (f"Data folder: {data_folder.name}   ·   n = {len(table)} specimens   ·   "
                f"Strain source: {', '.join(sorted(table['strain_source'].unique()))}   ·   "
                f"Analysed: {date.today():%d %b %Y}")
    ws["B3"].font = Font(name=F, size=9, color=grey)
    if simulated:
        ws["B4"] = "SIMULATED DATA – not from a real test"
        ws["B4"].font = Font(name=F, size=9, bold=True, color="C00000")

    top = 6
    for j, h in enumerate(["Property", "Mean", "SD", "Report as"], start=2):
        c = ws.cell(row=top, column=j, value=h)
        c.font = Font(name=F, bold=True, color="FFFFFF")
        c.fill = head_fill
        c.border = box
        c.alignment = Alignment(horizontal="left" if j == 2 else "center")
    for i, ((_, (_, d)), (_, r)) in enumerate(zip(REPORT.items(), summary.iterrows())):
        row = top + 1 + i
        fmt = "0" if d == 0 else "0." + "0" * d
        values = [r["property"], r["mean"], r["SD"], r["report_as"]]
        for j, v in enumerate(values, start=2):
            c = ws.cell(row=row, column=j, value=None if pd.isna(v) else v)
            c.font = Font(name=F, bold=(j == 5))
            c.border = box
            if i % 2:
                c.fill = band
            if j in (3, 4):
                c.number_format = fmt
            c.alignment = Alignment(horizontal="left" if j == 2 else "center")

    row = top + len(REPORT) + 2
    n_warn = int((table["warnings"] != "").sum())
    ws.cell(row=row, column=2,
            value="No warnings." if n_warn == 0 else
            f"{n_warn} specimen(s) have warnings – see the Specimens sheet.").font = Font(
        name=F, bold=True, color="375623" if n_warn == 0 else "C00000")
    notes = [
        "Mean ± standard deviation of all specimens.",
        f"Modulus: straight-line fit between {int(FIT_WINDOW[0]*100)} % and "
        f"{int(FIT_WINDOW[1]*100)} % of the maximum stress (toolkit default).",
        "Proof stress: 0.2 % offset method.  UTS: highest measured engineering stress.",
        "Plastic strain at fracture is taken from the curve. It is not 'elongation after "
        "fracture', which is measured on the broken specimen.",
    ]
    for k, t in enumerate(notes):
        c = ws.cell(row=row + 2 + k, column=2, value=t)
        c.font = Font(name=F, size=9, color=grey)

    img = XLImage(figure_png)
    scale = 520 / img.width
    img.width, img.height = 520, int(img.height * scale)
    ws.add_image(img, "G2")
    ws.page_setup.orientation = "landscape"  # prints on one page
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 1

    # Specimens sheet
    sp = wb.create_sheet("Specimens")
    sp.freeze_panes = "A2"
    labels = {"specimen": "Specimen", "strain_source": "Strain source", "E_GPa": "E (GPa)",
              "Rp02_MPa": "Rp0.2 (MPa)", "UTS_MPa": "UTS (MPa)",
              "uniform_strain_%": "Uniform strain (%)", "strain_at_fracture_%": "Strain at fracture (%)",
              "plastic_strain_at_fracture_%": "Plastic strain at fracture (%)",
              "E_fit_points": "E fit points", "E_fit_R2": "E fit R²", "warnings": "Warnings"}
    formats = {"E_GPa": "0.00", "Rp02_MPa": "0.0", "UTS_MPa": "0.0", "uniform_strain_%": "0.00",
               "strain_at_fracture_%": "0.00", "plastic_strain_at_fracture_%": "0.00",
               "E_fit_points": "0", "E_fit_R2": "0.0000"}
    cols = list(table.columns)
    for j, col in enumerate(cols, start=1):
        c = sp.cell(row=1, column=j, value=labels.get(col, col))
        c.font = Font(name=F, bold=True, color="FFFFFF")
        c.fill = head_fill
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = box
        sp.column_dimensions[c.column_letter].width = 60 if col == "warnings" else 14
    sp.row_dimensions[1].height = 32
    for i, (_, r) in enumerate(table.iterrows(), start=2):
        for j, col in enumerate(cols, start=1):
            v = r[col]
            c = sp.cell(row=i, column=j, value=None if (not isinstance(v, str) and pd.isna(v)) else v)
            c.font = Font(name=F)
            c.border = box
            if col in formats:
                c.number_format = formats[col]
            c.alignment = Alignment(horizontal="left" if col == "warnings" else "center",
                                    vertical="top", wrap_text=(col == "warnings"))
            if i % 2 == 1:
                c.fill = band
    sp.page_setup.orientation = "landscape"
    sp.sheet_properties.pageSetUpPr.fitToPage = True
    sp.page_setup.fitToWidth, sp.page_setup.fitToHeight = 1, 0
    wb.save(path)


def run(settings):
    """Called by run_analysis.py with all the settings."""
    data_folder = _folder(settings["DATA_FOLDER"])
    out = _folder(settings["OUTPUT_FOLDER"])
    table, summary, curves, simulated = analyse_folder(data_folder, settings["STRAIN_SOURCE"])
    out.mkdir(parents=True, exist_ok=True)

    print(f"\nAnalysed {len(table)} specimens from {data_folder.name}"
          + ("   [SIMULATED DATA]" if simulated else ""))
    cols = ["specimen", "E_GPa", "Rp02_MPa", "UTS_MPa", "plastic_strain_at_fracture_%"]
    print(table[cols].rename(columns={
        "E_GPa": "E (GPa)", "Rp02_MPa": "Rp0.2 (MPa)", "UTS_MPa": "UTS (MPa)",
        "plastic_strain_at_fracture_%": "Strain at fracture (%)"}).round(1).to_string(index=False))
    print(f"\nRESULTS (mean ± SD, n = {len(table)})")
    for _, r in summary.iterrows():
        print(f"  {r['property']:<44}{r['report_as']}")

    warn = table[table["warnings"] != ""]
    if warn.empty:
        print("\nNo warnings.")
    else:
        print("\nWARNINGS:")
        for _, w in warn.iterrows():
            print(f"  {w['specimen']}: {w['warnings']}")

    table = table.round({"E_GPa": 2, "Rp02_MPa": 1, "UTS_MPa": 1, "uniform_strain_%": 2,
                         "strain_at_fracture_%": 2, "plastic_strain_at_fracture_%": 2, "E_fit_R2": 4})
    table.to_csv(out / "results.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(out / "summary.csv", index=False, encoding="utf-8-sig")
    saved = ["results.csv", "summary.csv"]
    figure_png = make_figure(curves, out / settings["FIGURE_FILE"], settings, simulated)
    saved.append(settings["FIGURE_FILE"])
    try:
        write_excel(out / "results.xlsx", table, summary, figure_png, data_folder, simulated)
        saved.append("results.xlsx")
    except ImportError:
        print("\n(Excel file skipped: run  pip install openpyxl  once to enable it.)")
    except PermissionError:
        print("\n(Excel file not saved: close results.xlsx in Excel and run again.)")
    print(f"\nSaved {', '.join(saved)} in:\n  {out}")
