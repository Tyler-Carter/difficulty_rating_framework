from pathlib import Path

# Resolved at import time relative to the package root
_PGK_ROOT = Path(__file__).parent.parent.parent # project root


BASE_FILES_DIR:     Path = _PGK_ROOT / "base_files"
JSON_OUTPUT_DIR:    Path = _PGK_ROOT / "json_output"
TEXT_OUTPUT_DIR:    Path = _PGK_ROOT / "text_output"

# ----------------------------------------------------------------------------
# Playtesting parameters (see docs/outline.md "Requires playtesting" sections)
# ----------------------------------------------------------------------------
CTS_MULTIPLIER:         float = 10.7    # = 5 + 0.58 + 4.41 + 0.67 (derived in outline)
AUTOFIRE_ATK_PENALTY:   int   = 3       # -3 to attack pool for HPW autofire branch
DSR_WEIGHT:             float = 5.0     # Scales E_DSR to HP-equivalent units

# ----------------------------------------------------------------------------
# AAC cap - prevents military-grade SP from collapsing tier separation
# ----------------------------------------------------------------------------
AAC_SP_CAP: int = 18
