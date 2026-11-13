# Data Mechanic – Tensile Test Toolkit

*Understand the science behind your data.*

Turn raw tensile test files into a results table, an Excel file and a thesis-ready figure, without writing any code.

---

## Install Python and libraries: first time only

1. Install **Python** from python.org. During installation, tick **"Add Python to PATH"**.
2. Install **VS Code** from code.visualstudio.com, then add its **Python** extension.
3. In VS Code, open a terminal (**Terminal → New Terminal**) and paste:

   ```
   pip install numpy pandas matplotlib openpyxl
   ```

---

## Every time you need to use your data

### Instructions to use the toolkit

1. **Copy your test files** into the `my_data` folder.
2. **Fill in `my_data/specimens.xlsx`**: the Instructions tab explains everything; type one row per test file in the Specimens tab.
3. In VS Code, **File → Open Folder → DataMechanic_Tensile_Toolkit**, then open **`run_analysis.py`**.
4. In the file, change `DATA_FOLDER = "example_data"` to `DATA_FOLDER = "my_data"`.
5. Press the **Run** icon (▶ at the top right).
6. Once the run is successful, results are stored in the **`output`** folder.
7. Open the **`output`** folder to see: `results.xlsx`, `results.csv`, `summary.csv` and `stress_strain.png`.

### Test the toolkit

To try the toolkit first, skip steps 1, 2 and 4: it runs on the example data as it is.

---

## Filling in specimens.xlsx

Every data folder has its own `specimens.xlsx`, describing only the files in that folder. The testing machine doesn't create it; you fill it in. Keep the file name and don't rename the Specimens tab.

Check the **Instructions** sheet in the specimens.xlsx file.

| Column | What to enter |
|---|---|
| file | Exact file name, including `.csv` |
| specimen_id | A short name, e.g. S1 |
| width_mm, thickness_mm | Measured specimen dimensions in mm |
| gauge_length_mm | Extensometer gauge length in mm |
| strain_source | `extensometer` (recommended) or `crosshead` from the dropdown |
| material | Any description |

---

## Your test files

Each test must be a **CSV file** (comma-separated). The toolkit was written for Instron Bluehill exports, but works with any machine whose file has the following details:

| Column | Name must contain | Units it understands |
|---|---|---|
| Time | `Time` | s, min |
| Force | `Load` or `Force` | N, kN, lbf |
| Crosshead movement | `Extension`, `Displacement` or `Crosshead` | mm, in |
| Extensometer strain (if used) | `Strain 1` or `Extensometer` | %, mm/mm |

Units can be in a separate row below the column names, e.g. `(s)`, `(N)`, `(mm)`, or in brackets after the name, e.g. `Load (kN)`. Information lines above the column names are fine; the toolkit skips them.

### Files from a different machine

1. **Export as CSV.** If your machine gives an Excel (.xlsx), text (.txt) or tab-separated file, open it in Excel and use **File → Save As → CSV (Comma delimited)**.
2. **Check the column names.** If they're different (for example `Stroke`, `Position` or `Kraft`), make a **copy** of the file and rename those headings to the names above, e.g. `Stroke (mm)` → `Extension (mm)`. Keep your original file unchanged.
3. **Check the units.** Make sure each column has a unit from the table, either in brackets or in a units row.
4. **Check decimal points.** Numbers must use a full stop as the decimal mark (`12.5`, not `12,5`). Some European software uses commas; change the export setting or the Excel region setting.
5. **Run again.** If something is still wrong, the toolkit stops and tells you which file and what it couldn't find.

> [!TIP]
> **Still stuck?** Share the first 20 lines of your file (remove any private details) in the comments or on GitHub, and support for that machine can be added.

---

## What you get

| Result | What it tells you |
|---|---|
| Young's modulus (GPa) | Stiffness |
| 0.2% proof stress (MPa) | Where permanent deformation begins |
| Ultimate tensile strength (MPa) | Maximum strength |
| Plastic strain at fracture, from curve (%) | Ductility. This is not "elongation after fracture" in testing standards, which is measured on the broken specimen. |

The summary gives mean ± SD, rounded for reporting (e.g. 275 ± 2 MPa).

---

## Changing the figure

All figure settings are in `run_analysis.py` under **FIGURE SETTINGS**, each with a note: title, labels, font size, legend position, colours, line thickness, grid, axis range, size, file name (`.png` or `.pdf`) and resolution. Change, save, and press Run again.

---

## Warnings and what to do

If something is missing (a folder, a file, a column), the toolkit stops and tells you exactly what to fix.

### ⚠️ Strain from crosshead

**What it means:** Strain was calculated from machine movement, not measured on the specimen. Common when a lab has no extensometer.

**What to look for:** Nothing to inspect: it applies to every crosshead test.

UTS is independent of the strain measurement method, provided force and specimen dimensions are measured correctly. Proof stress may be affected by the strain measurement method. Modulus and strain-derived ductility measurements from crosshead data should not be treated as reliable material properties without appropriate calibration.

**What to do:**
- **Reliable:** UTS.
- **Approximate:** proof stress.
- **Not reliable:** modulus and strains, so don't report them.
- For ductility, measure elongation after fracture from gauge marks on the broken specimen.

### ⚠️ Elastic part not very straight

**What it means:** The points used to calculate the modulus don't lie on a straight line, so E is uncertain.

**What to look for:** Zoom into the start of the curve (set `X_LIMITS = (0, 1)`). Look for:
- a step or kink: the specimen slipped in the grips
- a slowly curving start: specimen seating or a slightly bent specimen
- scattered points: noisy data

**What to do:**
- Check the specimen dimensions and strain source in the sheet.
- If one specimen slipped, don't report its modulus, but its strength values can still be used.
- For future tests: check alignment and grip pressure, and apply a small preload.
- Don't change the fitting range just to remove the warning.

### ⚠️ Maximum stress looks like a spike

**What it means:** The highest stress is a single reading clearly above the readings around it, rather than a smooth peak.

**What to look for:** Zoom into the peak of the curve. A single point sticking up above a smooth curve is usually an electrical or data glitch. A smooth, rounded peak is real.

**What to do:**
- If it's a glitch: make a copy of the raw file, delete that one reading in the copy, note it in your records, and run again. Keep the original file unchanged.
- If the peak is smooth: the warning can be ignored.
- Never delete readings just because a value seems too high.

### ⚠️ No sudden load drop found

**What it means:** The curve ends without the sharp drop that normally marks fracture.

**What to look for:** Check the broken specimen and the test record. Did the specimen actually break? Did the machine stop early because of an end-of-test setting? Was the file cut short when exported?

**What to do:**
- If the specimen broke but recording stopped just before: UTS and proof stress are fine, but don't report strain at fracture.
- If it didn't break: report it as "test stopped before fracture".
- For future tests: check the machine's end-of-test settings.

### ⚠️ Only a few readings in the elastic fit

**What it means:** Fewer than 20 data points fall in the straight part of the curve, so the modulus is less precise.

**What to look for:** Look at how sparse the points are at the start of the curve.

**What to do:**
- The results can still be used, but treat the modulus with caution.
- For future tests: increase the data recording rate in the test method.

---

## Good to know

> [!NOTE]
> The example data is **simulated** and labelled as such. **It is not from a real test.**

- You will never need to open `tensile_engine.py`. It contains the analysis, with comments for anyone curious.
- Licence: MIT (free to use and share; keep the copyright notice).
