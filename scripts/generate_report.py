from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT_ROOT / "reports" / "项目报告.md"
DOCX_OUTPUT = PROJECT_ROOT / "reports" / "项目报告_待填写个人信息.docx"
IMAGE_PATTERN = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$")


def set_run_font(run, name="Microsoft YaHei", size=11, bold=None):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor(0, 0, 0)
    if bold is not None:
        run.bold = bold


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = "PAGE"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(begin)
    run._r.append(instruction)
    run._r.append(end)
    set_run_font(run, size=9)


def add_table(document, rows):
    if not rows:
        return
    width = max(len(row) for row in rows)
    table = document.add_table(rows=len(rows), cols=width)
    table.style = "Table Grid"
    for row_index, values in enumerate(rows):
        for column_index in range(width):
            text = values[column_index] if column_index < len(values) else ""
            cell = table.cell(row_index, column_index)
            cell.text = " " if not text else text
            for paragraph in cell.paragraphs:
                paragraph.alignment = (
                    WD_ALIGN_PARAGRAPH.CENTER
                    if column_index > 0
                    else WD_ALIGN_PARAGRAPH.LEFT
                )
                for run in paragraph.runs:
                    set_run_font(run, size=9, bold=row_index == 0)
    document.add_paragraph()


def main():
    text = SOURCE.read_text(encoding="utf-8")
    lines = text.splitlines()
    document = Document()
    section = document.sections[0]
    section.top_margin = Cm(2.2)
    section.bottom_margin = Cm(2.2)
    section.left_margin = Cm(2.4)
    section.right_margin = Cm(2.4)

    normal = document.styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.font.size = Pt(11)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(6)

    add_page_number(section.footer.paragraphs[0])
    title = lines[0].lstrip("# ").strip()
    title_paragraph = document.add_paragraph()
    title_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_paragraph.add_run(title)
    set_run_font(title_run, size=20, bold=True)
    title_paragraph.paragraph_format.space_after = Pt(24)

    index = 1
    while index < len(lines):
        line = lines[index].rstrip()
        if not line:
            index += 1
            continue
        if line.startswith("课程：") or line.startswith("姓名：") or line.startswith(
            "学号："
        ) or line.startswith("组员") or line.startswith("日期："):
            paragraph = document.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = paragraph.add_run(line.rstrip())
            set_run_font(run, size=11)
            index += 1
            continue
        if line == "## 摘要":
            document.add_page_break()
        if line.startswith("## "):
            paragraph = document.add_heading(level=1)
            run = paragraph.add_run(line[3:].strip())
            set_run_font(run, size=15, bold=True)
            index += 1
            continue
        if line.startswith("### "):
            paragraph = document.add_heading(level=2)
            run = paragraph.add_run(line[4:].strip())
            set_run_font(run, size=12, bold=True)
            index += 1
            continue
        if line.startswith("```"):
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                paragraph = document.add_paragraph()
                paragraph.paragraph_format.left_indent = Cm(0.5)
                run = paragraph.add_run(lines[index])
                set_run_font(run, name="Consolas", size=9)
                index += 1
            index += 1
            continue
        image_match = IMAGE_PATTERN.match(line)
        if image_match:
            caption, relative_path = image_match.groups()
            image_path = (SOURCE.parent / relative_path).resolve()
            picture_paragraph = document.add_paragraph()
            picture_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            picture_paragraph.add_run().add_picture(str(image_path), width=Cm(15.4))
            caption_paragraph = document.add_paragraph()
            caption_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            caption_run = caption_paragraph.add_run(caption)
            set_run_font(caption_run, size=9)
            caption_run.italic = True
            index += 1
            continue
        if line.startswith("|"):
            table_lines = []
            while index < len(lines) and lines[index].startswith("|"):
                row = [
                    cell.strip()
                    for cell in lines[index].strip().strip("|").split("|")
                ]
                if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in row):
                    table_lines.append(row)
                index += 1
            add_table(document, table_lines)
            continue
        if re.match(r"^\d+\.\s", line):
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.left_indent = Cm(0.74)
            paragraph.paragraph_format.first_line_indent = Cm(-0.4)
            run = paragraph.add_run(line)
            set_run_font(run)
            index += 1
            continue
        if line.startswith("- "):
            paragraph = document.add_paragraph(style="List Bullet")
            run = paragraph.add_run(line[2:])
            set_run_font(run)
            index += 1
            continue
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.first_line_indent = Cm(0.74)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = paragraph.add_run(line.replace("  ", ""))
        set_run_font(run)
        index += 1

    DOCX_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document.save(DOCX_OUTPUT)
    print(DOCX_OUTPUT)


if __name__ == "__main__":
    main()
