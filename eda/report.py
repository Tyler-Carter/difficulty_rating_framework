from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


class MarkdownReport:
    """Streaming Markdown assembler with a small, opinionated section vocabulary.

    Each `add_*` call appends text or block content. `add_table()` writes both
    a Markdown table for inline reading AND a sibling CSV file linked from the
    text — the CSV is the source of truth, the Markdown table is the preview.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lines: list[str] = []
        self._csv_dir = self.path.parent / "tables"
        self._csv_dir.mkdir(exist_ok=True)
        self._section_index = 0

    def add_title(self, title: str, subtitle: str | None = None) -> None:
        self._lines.append(f"# {title}\n")
        if subtitle:
            self._lines.append(f"_{subtitle}_\n")
        self._lines.append("")

    def add_section(self, title: str, *, subtitle: str | None = None) -> None:
        self._section_index += 1
        self._lines.append(f"\n## {self._section_index}. {title}\n")
        if subtitle:
            self._lines.append(f"> {subtitle}\n")

    def add_subsection(self, title: str) -> None:
        self._lines.append(f"\n### {title}\n")

    def add_paragraph(self, text: str) -> None:
        self._lines.append(text + "\n")

    def add_bullets(self, items: list[str]) -> None:
        for item in items:
            self._lines.append(f"- {item}")
        self._lines.append("")

    def add_kv(self, mapping: dict[str, Any]) -> None:
        for k, v in mapping.items():
            self._lines.append(f"- **{k}**: {v}")
        self._lines.append("")

    def add_table(self, df: pd.DataFrame, *, name: str,
                  caption: str | None = None,
                  max_rows_inline: int = 25,
                  float_format: str = "{:.3f}") -> None:
        csv_path = self._csv_dir / f"{name}.csv"
        df.to_csv(csv_path)
        rel = csv_path.relative_to(self.path.parent).as_posix()

        if caption:
            self._lines.append(f"_{caption}_\n")

        self._lines.append(_to_markdown_table(df.head(max_rows_inline), float_format))
        if len(df) > max_rows_inline:
            self._lines.append(f"\n_...showing first {max_rows_inline} of {len(df)} rows. "
                               f"Full table: [{rel}]({rel})_")
        else:
            self._lines.append(f"\n_Source: [{rel}]({rel})_")
        self._lines.append("")

    def add_image(self, image_path: Path, *, alt: str, caption: str | None = None) -> None:
        rel = image_path.relative_to(self.path.parent).as_posix()
        self._lines.append(f"\n![{alt}]({rel})\n")
        if caption:
            self._lines.append(f"_{caption}_\n")

    def add_integrity_block(self, checks: list[tuple[str, bool, str]]) -> None:
        for name, ok, detail in checks:
            mark = "PASS" if ok else "FAIL"
            self._lines.append(f"- **[{mark}]** {name} — {detail}")
        self._lines.append("")

    def add_recommendations(self, recs: list[dict]) -> None:
        """Render a prioritized recommendation list as full narrative blocks.

        Groups recs by priority (P1=CRITICAL first, P0=OK last). Each rec gets
        a labeled subsection heading plus Issue / Root Cause / Action / Expected
        sub-fields.
        """
        _ICON   = {"CRITICAL": "❌", "WARNING": "⚠️", "MONITOR": "🔍", "OK": "✅"}
        _LABEL  = {
            1: "Priority 1 — Critical (Fix Before Use)",
            2: "Priority 2 — Warning (Address Before Relying on Ratings)",
            3: "Priority 3 — Monitor (No Immediate Action)",
            0: "Confirmed Healthy",
        }
        seen_groups: set[int] = set()
        for rec in recs:
            p = rec["priority"]
            if p not in seen_groups:
                self.add_subsection(_LABEL[p])
                seen_groups.add(p)
            icon  = _ICON.get(rec["status"], "")
            self._lines.append(f"\n#### {icon} {rec['title']}\n")
            self._lines.append(f"**Issue:** {rec['issue']}\n")
            self._lines.append(f"**Root cause:** {rec['root_cause']}\n")
            self._lines.append("**Action:**")
            for step in rec["action"]:
                self._lines.append(f"- {step}")
            self._lines.append("")
            self._lines.append(f"**Expected outcome:** {rec['expected']}\n")

    def write(self) -> Path:
        self.path.write_text("\n".join(self._lines), encoding="utf-8")
        return self.path


def _fmt_cell(v, float_format: str) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, float):
        return float_format.format(v)
    return str(v)


def _to_markdown_table(df: pd.DataFrame, float_format: str = "{:.3f}") -> str:
    """Render a DataFrame as a GitHub-flavored Markdown table without tabulate."""
    if df.empty:
        return "_(empty)_"

    # Promote the index into column 0 so the index label is visible.
    work = df.reset_index()
    cols = [str(c) for c in work.columns]
    rows = [[_fmt_cell(v, float_format) for v in row] for row in work.itertuples(index=False, name=None)]

    widths = [max(len(cols[i]), max((len(r[i]) for r in rows), default=0)) for i in range(len(cols))]
    fmt = lambda cells: "| " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(cells)) + " |"

    out = [fmt(cols), "| " + " | ".join("-" * w for w in widths) + " |"]
    out.extend(fmt(r) for r in rows)
    return "\n".join(out)
