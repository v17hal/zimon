"""Generate ZIMON_Documentation.pdf from ZIMON_Documentation.md using fpdf2."""

import os
import re
from fpdf import FPDF
from fpdf.enums import XPos, YPos

# ── Unicode → ASCII substitutions (keeps Latin-1 fonts working) ──────────────
_UNICODE_MAP = {
    "—": "-",    # em dash
    "–": "-",    # en dash
    "‘": "'",    # left single quote
    "’": "'",    # right single quote
    "“": '"',    # left double quote
    "”": '"',    # right double quote
    "•": "*",    # bullet
    "…": "...",  # ellipsis
    " ": " ",    # non-breaking space
    "→": "->",   # right arrow
    "←": "<-",   # left arrow
    "°": " deg", # degree
    # Status indicators
    "✅": "[YES]",   # ✅
    "❌": "[NO]",    # ❌
    "⚠": "[!]",     # ⚠
    "️": "",        # variation selector (strip)
    "\U0001f4c1": "",    # 📁 folder (strip)
    "\U0001f321": "",    # 🌡 thermometer (strip)
    "►": ">",       # ► play button
    "◼": "[stop]",  # ■ stop
    "↺": "[replay]",# ↺
    "⏭": "|>>",     # ⏭
    "⏸": "||",      # ⏸
    "▶": ">",       # ▶
    "\U0001f514": "",    # 🔔 bell (strip)
    "\U0001f50a": "",    # 🔊 speaker (strip)
    "✓": "[OK]",    # ✓
}

def _clean(text: str) -> str:
    """Replace all non-Latin-1 chars with ASCII equivalents."""
    for src, dst in _UNICODE_MAP.items():
        text = text.replace(src, dst)
    # Strip any remaining non-latin-1 characters
    return text.encode("latin-1", errors="ignore").decode("latin-1")

# ── Colour palette ────────────────────────────────────────────────────────────
C_NAVY       = (13,  35,  95)    # #0d235f  — headings
C_INDIGO     = (79,  70, 229)    # #4f46e5  — h2 accent
C_PURPLE_LT  = (224, 231, 255)   # #e0e7ff  — h2 bg band
C_TEXT       = (30,  41,  59)    # #1e293b  — body
C_MUTED      = (100,116,139)     # #64748b  — muted / table header text
C_CODE_BG    = (241,245,249)     # #f1f5f9  — code block bg
C_CODE_TEXT  = (51,  65,  85)    # #334155  — code text
C_BORDER     = (226,232,240)     # #e2e8f0  — lines / borders
C_WHITE      = (255,255,255)
C_GREEN      = (22, 163,  74)    # #16a34a
C_ORANGE     = (234, 88,  12)    # #ea580c
C_TH_BG      = (248,250,252)     # #f8fafc  — table header bg
C_TR_ALT     = (249,250,251)     # alternating row tint

# ── PDF class ─────────────────────────────────────────────────────────────────

class ZimonPDF(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_margins(18, 22, 18)
        self.set_auto_page_break(auto=True, margin=20)
        self._toc: list[tuple[int,str,int]] = []   # (level, title, page)

    def normalize_text(self, text: str) -> str:
        """Auto-clean Unicode before fpdf encodes it."""
        return super().normalize_text(_clean(text))

    # ── Header / footer ───────────────────────────────────────────────────────

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*C_MUTED)
        self.cell(0, 8, "ZIMON — Project Documentation", align="L",
                  new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.cell(0, 8, f"Page {self.page_no()}", align="R",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*C_BORDER)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

    def footer(self):
        if self.page_no() == 1:
            return
        self.set_y(-14)
        self.set_draw_color(*C_BORDER)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*C_MUTED)
        self.cell(0, 6,
                  _clean("Zebrafish Integrated Motion & Optical Neuroanalysis Chamber  |  v2.0.0"),
                  align="C")

    # ── Cover page ────────────────────────────────────────────────────────────

    def cover_page(self):
        self.add_page()
        # Background gradient band
        self.set_fill_color(*C_NAVY)
        self.rect(0, 0, self.w, 90, style="F")

        # Logo text
        self.set_y(28)
        self.set_font("Helvetica", "B", 52)
        self.set_text_color(*C_WHITE)
        self.cell(0, 20, "ZIMON", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_font("Helvetica", "", 12)
        self.set_text_color(180, 200, 240)
        self.cell(0, 8, "Zebrafish Integrated Motion & Optical Neuroanalysis Chamber",
                  align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Subtitle band
        self.set_y(95)
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(*C_NAVY)
        self.cell(0, 12, "Complete Project Documentation", align="C",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_font("Helvetica", "", 11)
        self.set_text_color(*C_MUTED)
        self.cell(0, 8, "Version 2.0.0  |  Desktop Application (Windows 10/11 64-bit)",
                  align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Divider
        self.ln(6)
        self.set_draw_color(*C_INDIGO)
        self.set_line_width(0.8)
        mid = self.w / 2
        self.line(mid - 40, self.get_y(), mid + 40, self.get_y())
        self.set_line_width(0.2)
        self.ln(10)

        # Info box
        self._info_row("Document covers",  "Installation · Features · Hardware · File Structure · Installer")
        self._info_row("Hardware support",  "Arduino · FLIR Camera · Basler Camera · USB Webcam")
        self._info_row("Tech stack",        "Python 3.12 · PyQt6 · OpenCV · SQLite · PyInstaller")
        self._info_row("Prepared",          "May 2026")

        # Footer note on cover
        self.set_y(-30)
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(*C_MUTED)
        self.cell(0, 6,
                  "Confidential — prepared for laboratory use",
                  align="C")

    def _info_row(self, label: str, value: str):
        x = self.l_margin
        self.set_x(x + 20)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*C_NAVY)
        self.cell(52, 7, label + ":", new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*C_TEXT)
        self.cell(0, 7, value, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── Heading renderers ─────────────────────────────────────────────────────

    def h1(self, text: str):
        self._toc.append((1, text, self.page_no()))
        self.ln(6)
        # Full-width navy bar
        self.set_fill_color(*C_NAVY)
        self.set_text_color(*C_WHITE)
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, f"  {text}", fill=True,
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(4)
        self.set_text_color(*C_TEXT)

    def h2(self, text: str):
        self._toc.append((2, text, self.page_no()))
        self.ln(4)
        self.set_fill_color(*C_PURPLE_LT)
        self.set_text_color(*C_INDIGO)
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 8, f"  {text}", fill=True,
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)
        self.set_text_color(*C_TEXT)

    def h3(self, text: str):
        self.ln(3)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*C_NAVY)
        self.cell(0, 7, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        # Underline
        y = self.get_y()
        self.set_draw_color(*C_INDIGO)
        self.set_line_width(0.4)
        self.line(self.l_margin, y, self.l_margin + 60, y)
        self.set_line_width(0.2)
        self.ln(2)
        self.set_text_color(*C_TEXT)

    def h4(self, text: str):
        self.ln(2)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*C_NAVY)
        self.cell(0, 6, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)
        self.set_text_color(*C_TEXT)

    # ── Body text ─────────────────────────────────────────────────────────────

    def body(self, text: str):
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(*C_TEXT)
        # Strip inline code backticks for now
        text = re.sub(r'`([^`]+)`', r'\1', text)
        self.multi_cell(0, 5.5, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def bullet(self, text: str, level: int = 0):
        indent = 6 + level * 5
        bullet_char = "•" if level == 0 else "–"
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(*C_TEXT)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        # Bold text between ** **
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        x0 = self.l_margin + indent
        self.set_x(x0)
        self.cell(5, 5.5, bullet_char,
                  new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.multi_cell(
            self.w - self.r_margin - x0 - 5,
            5.5, text,
            new_x=XPos.LMARGIN, new_y=YPos.NEXT
        )

    def code_block(self, lines: list[str]):
        self.ln(2)
        self.set_fill_color(*C_CODE_BG)
        self.set_draw_color(*C_BORDER)
        self.set_font("Courier", "", 8)
        self.set_text_color(*C_CODE_TEXT)
        pad = 4
        content = "\n".join(lines)
        x0 = self.l_margin
        w  = self.w - self.l_margin - self.r_margin
        # Draw background rect
        line_h = 4.5
        n_lines = len(lines)
        box_h = n_lines * line_h + pad * 2
        self.rect(x0, self.get_y(), w, box_h, style="FD")
        self.set_y(self.get_y() + pad)
        for line in lines:
            self.set_x(x0 + pad)
            self.cell(w - pad*2, line_h, line,
                      new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(3)
        self.set_text_color(*C_TEXT)

    # ── Table renderer ────────────────────────────────────────────────────────

    def table(self, headers: list[str], rows: list[list[str]]):
        self.ln(2)
        usable_w = self.w - self.l_margin - self.r_margin

        # Auto-size columns
        n = len(headers)
        if n == 0:
            return

        # Rough heuristic: first col narrow if it's "Feature"/"Button" etc.
        if n == 2:
            col_w = [usable_w * 0.38, usable_w * 0.62]
        elif n == 3:
            col_w = [usable_w * 0.25, usable_w * 0.40, usable_w * 0.35]
        elif n == 4:
            col_w = [usable_w * 0.18, usable_w * 0.28, usable_w * 0.28, usable_w * 0.26]
        else:
            each = usable_w / n
            col_w = [each] * n

        row_h = 5.5
        font_size = 8.5

        def draw_row(cells, is_header=False, alt=False):
            y0 = self.get_y()
            # Check page break
            if y0 + row_h * 3 > self.h - self.b_margin:
                self.add_page()
                y0 = self.get_y()

            if is_header:
                self.set_fill_color(*C_TH_BG)
                self.set_text_color(*C_MUTED)
                self.set_font("Helvetica", "B", font_size - 0.5)
            elif alt:
                self.set_fill_color(*C_TR_ALT)
                self.set_text_color(*C_TEXT)
                self.set_font("Helvetica", "", font_size)
            else:
                self.set_fill_color(*C_WHITE)
                self.set_text_color(*C_TEXT)
                self.set_font("Helvetica", "", font_size)

            self.set_draw_color(*C_BORDER)
            x0 = self.l_margin

            # Calculate actual row height (multi-cell wrapping)
            max_lines = 1
            for i, cell_text in enumerate(cells[:n]):
                words = cell_text
                if col_w[i] > 0:
                    approx = len(words) * (font_size * 0.45) / col_w[i]
                    max_lines = max(max_lines, int(approx) + 1)
            actual_h = row_h * min(max_lines, 4)

            # Draw each cell
            for i, cell_text in enumerate(cells[:n]):
                self.set_xy(x0, y0)
                # Status cell colouring
                if not is_header:
                    t = cell_text.strip()
                    if t.startswith("✅"):
                        self.set_text_color(*C_GREEN)
                    elif t.startswith("⚠️") or t.startswith("⚠"):
                        self.set_text_color(*C_ORANGE)
                    elif t.startswith("❌"):
                        self.set_text_color(220, 38, 38)
                    else:
                        self.set_text_color(*C_TEXT if not is_header else C_MUTED)
                self.multi_cell(col_w[i], row_h, cell_text,
                                border=1, fill=True, align="L",
                                new_x=XPos.RIGHT, new_y=YPos.TOP,
                                max_line_height=row_h)
                x0 += col_w[i]

            self.set_xy(self.l_margin, y0 + actual_h)

        draw_row(headers, is_header=True)
        for idx, row in enumerate(rows):
            padded = list(row) + [""] * (n - len(row))
            draw_row(padded[:n], alt=(idx % 2 == 1))

        self.ln(3)
        self.set_text_color(*C_TEXT)

    # ── Horizontal rule ───────────────────────────────────────────────────────

    def hr(self):
        self.ln(2)
        self.set_draw_color(*C_BORDER)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    # ── Block quote / note ────────────────────────────────────────────────────

    def blockquote(self, text: str):
        self.ln(1)
        x0 = self.l_margin
        self.set_fill_color(255, 251, 235)   # amber-50
        self.set_draw_color(251, 191, 36)    # amber-400
        self.set_line_width(0.8)
        w = self.w - x0 - self.r_margin
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(120, 53, 15)     # amber-900
        n_lines = max(1, len(text) // 80 + 1)
        bh = n_lines * 5 + 6
        self.rect(x0, self.get_y(), w, bh, style="FD")
        self.set_xy(x0 + 4, self.get_y() + 3)
        self.multi_cell(w - 8, 5, f"⚠  {text}",
                        new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_line_width(0.2)
        self.ln(2)
        self.set_text_color(*C_TEXT)


# ── Markdown parser → PDF ─────────────────────────────────────────────────────

def parse_md_to_pdf(md_path: str, pdf_path: str):
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    pdf = ZimonPDF()
    pdf.cover_page()
    pdf.add_page()

    i = 0
    in_code = False
    code_lines: list[str] = []
    in_table = False
    table_headers: list[str] = []
    table_rows: list[list[str]] = []

    def flush_table():
        nonlocal in_table, table_headers, table_rows
        if in_table and table_headers:
            pdf.table(table_headers, table_rows)
        in_table = False
        table_headers = []
        table_rows = []

    def flush_code():
        nonlocal in_code, code_lines
        if in_code and code_lines:
            pdf.code_block(code_lines)
        in_code = False
        code_lines = []

    while i < len(lines):
        raw = lines[i].rstrip("\n")
        stripped = raw.strip()

        # ── Code fence ──────────────────────────────────────────────────────
        if stripped.startswith("```"):
            if not in_code:
                in_code = True
                code_lines = []
            else:
                flush_code()
            i += 1
            continue

        if in_code:
            code_lines.append(raw)
            i += 1
            continue

        # ── Table row ───────────────────────────────────────────────────────
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped[1:-1].split("|")]
            # Separator row
            if all(re.match(r'^[-:]+$', c) for c in cells if c):
                i += 1
                continue
            if not in_table:
                in_table = True
                table_headers = cells
                table_rows = []
            else:
                table_rows.append(cells)
            i += 1
            continue
        else:
            flush_table()

        # ── Heading ──────────────────────────────────────────────────────────
        if stripped.startswith("#### "):
            pdf.h4(stripped[5:])
        elif stripped.startswith("### "):
            pdf.h3(stripped[4:])
        elif stripped.startswith("## "):
            text = stripped[3:]
            # Remove markdown anchor
            text = re.sub(r'\s*\{#[^}]+\}', '', text).strip()
            pdf.h2(text)
        elif stripped.startswith("# "):
            pdf.h1(stripped[2:])

        # ── Horizontal rule ──────────────────────────────────────────────────
        elif stripped in ("---", "***", "___") or re.match(r'^-{3,}$', stripped):
            pdf.hr()

        # ── Blockquote ───────────────────────────────────────────────────────
        elif stripped.startswith("> "):
            pdf.blockquote(stripped[2:])

        # ── Bullet list ──────────────────────────────────────────────────────
        elif re.match(r'^(\s*)[-*+] ', raw):
            level = (len(raw) - len(raw.lstrip())) // 2
            text = re.match(r'^\s*[-*+] (.+)', raw).group(1)
            # Strip bold markers
            text = re.sub(r'\*\*([^*]+)\*\*', lambda m: m.group(1), text)
            pdf.bullet(text, level)

        # ── Numbered list ────────────────────────────────────────────────────
        elif re.match(r'^\d+\. ', stripped):
            text = re.sub(r'^\d+\.\s+', '', stripped)
            text = re.sub(r'\*\*([^*]+)\*\*', lambda m: m.group(1), text)
            pdf.bullet(text, 0)

        # ── Empty line ───────────────────────────────────────────────────────
        elif not stripped:
            if not in_table:
                pdf.ln(2)

        # ── Body paragraph ───────────────────────────────────────────────────
        else:
            text = stripped
            # Strip bold, italic, links for body
            text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
            text = re.sub(r'\*([^*]+)\*', r'\1', text)
            text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
            text = re.sub(r'`([^`]+)`', r'\1', text)
            if text:
                pdf.body(text)

        i += 1

    flush_table()
    flush_code()

    pdf.output(pdf_path)
    print(f"PDF created: {pdf_path}  ({os.path.getsize(pdf_path)//1024} KB)")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    md   = os.path.join(base, "ZIMON_Documentation.md")
    out  = os.path.join(base, "ZIMON_Documentation.pdf")
    parse_md_to_pdf(md, out)
