"""
=============================================================================
  DATA MECHANIC - TENSILE TEST TOOLKIT
  Understand the science behind your data.
=============================================================================

HOW TO USE
  1. Change the settings below if you need to (the defaults work as they are).
  2. Save this file.
  3. Press Run (the ▶ button at the top right in VS Code).
  4. Your results appear in the OUTPUT folder.

You may need to edit THIS file for your data.
The analysis itself is done by tensile_engine.py - you don't need to open it.
=============================================================================
"""

# ---------------------------------------------------------------------------
# 1. WHERE ARE YOUR FILES?
# ---------------------------------------------------------------------------

# Folder with your test files and the specimens.xlsx sheet.
#   "example_data"  -> the practice data that comes with the toolkit
#   "my_data"       -> put your own test files here
# You can also give a full path. Copy it from File Explorer and keep the r:
#   r"D:\My Thesis\Tensile Tests"

DATA_FOLDER = "example_data"

# Folder where results and figures are saved (created automatically).


OUTPUT_FOLDER = "output"


# ---------------------------------------------------------------------------
# 2. HOW WAS STRAIN MEASURED?
# ---------------------------------------------------------------------------

# "sheet"         -> use the strain_source column in specimens.xlsx (normal choice)
# "extensometer"  -> use extensometer strain for every specimen
# "crosshead"     -> use machine crosshead movement (modulus will NOT be reliable)


STRAIN_SOURCE = "as in specimens.xlsx" #Leave this unchanged


# ---------------------------------------------------------------------------
# 3. FIGURE SETTINGS
# ---------------------------------------------------------------------------

# Title inside the figure. None = no title.
# Tip: journals usually put the title in the caption, not inside the figure.

TITLE = None                      # e.g. "Engineering stress-strain curves"

# Axis labels and text size

X_LABEL = "Engineering strain (%)"
Y_LABEL = "Engineering stress (MPa)"
FONT_SIZE = 9

# Legend position: "lower right", "upper left", "upper right", "lower left",
#                  "center right", or "best" (Python chooses)

LEGEND_POSITION = "lower right"

# Line colours. None = automatic, or list your own, one per specimen:
#   ["black", "tab:blue", "tab:red", "tab:green"]

COLOURS = None

# Line thickness (1 = thin, 2 = thick)

LINE_WIDTH = 1.0

# Light background grid: True = on, False = off

SHOW_GRID = False

# Axis range. None = automatic, or (start, end).
#   X_LIMITS = (0, 1)  zooms into the first 1 % strain (the elastic part)

X_LIMITS = None
Y_LIMITS = None

# Figure size in inches (width, height). 3.5 inches = one journal column.

FIGURE_SIZE = (3.5, 2.6)

# File name of the figure. End it in .png for an image,
# or .pdf / .svg if a journal asks for vector graphics.

FIGURE_FILE = "stress_strain.png"

# Resolution in dots per inch. 300 suits most journals; 600 for line art.

DPI = 300


# ===========================================================================
# Nothing to change below this line.
# ===========================================================================
import tensile_engine

tensile_engine.run({name: value for name, value in globals().items() if name.isupper()})
