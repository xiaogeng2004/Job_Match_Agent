from __future__ import annotations

import html
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / ".deps"))

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    Image as ReportLabImage,
    LongTable,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)


FONT = "STSong-Light"
IMAGE_PATTERN = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$")


def add_page_number(canvas, document):
    canvas.saveState()
    canvas.setFont(FONT, 8)
    canvas.setFillColor(colors.black)
    canvas.drawCentredString(
        A4[0] / 2,
        1.2 * cm,
        str(document.page),
    )
    canvas.restoreState()


def parse_markdown(lines, base_dir: Path):
    story = []
    index = 0
    title = lines[0].lstrip("# ").strip()
    story.append(Paragraph(html.escape(title), STYLES["Title"]))
    story.append(Spacer(1, 1.2 * cm))
    index = 1
    while index < len(lines):
        line = lines[index].rstrip()
        if not line:
            index += 1
            continue
        if line.startswith("课程：") or line.startswith("姓名：") or line.startswith(
            "学号："
        ) or line.startswith("组员") or line.startswith("日期："):
            story.append(Paragraph(html.escape(line.rstrip()), STYLES["CoverMeta"]))
            index += 1
            continue
        if line == "## 摘要":
            story.append(PageBreak())
        if line.startswith("## "):
            story.append(Paragraph(html.escape(line[3:]), STYLES["Heading1"]))
            index += 1
            continue
        if line.startswith("### "):
            story.append(Paragraph(html.escape(line[4:]), STYLES["Heading2"]))
            index += 1
            continue
        if line.startswith("```"):
            index += 1
            code_lines = []
            while index < len(lines) and not lines[index].startswith("```"):
                code_lines.append(lines[index])
                index += 1
            story.append(
                Preformatted(
                    "\n".join(code_lines),
                    STYLES["Code"],
                )
            )
            index += 1
            continue
        image_match = IMAGE_PATTERN.match(line)
        if image_match:
            caption, relative_path = image_match.groups()
            image_path = (base_dir / relative_path).resolve()
            image = ReportLabImage(str(image_path))
            max_width = A4[0] - 4 * cm
            max_height = 9.5 * cm
            scale = min(
                1.0,
                max_width / image.drawWidth,
                max_height / image.drawHeight,
            )
            image.drawWidth *= scale
            image.drawHeight *= scale
            image.hAlign = "CENTER"
            story.extend(
                [
                    Spacer(1, 0.15 * cm),
                    image,
                    Paragraph(html.escape(caption), STYLES["Caption"]),
                    Spacer(1, 0.25 * cm),
                ]
            )
            index += 1
            continue
        if line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].startswith("|"):
                cells = [
                    cell.strip()
                    for cell in lines[index].strip().strip("|").split("|")
                ]
                if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                    rows.append(cells)
                index += 1
            if rows:
                width = len(rows[0])
                columns = (A4[0] - 4 * cm) / width
                table = LongTable(
                    [
                        [
                            Paragraph(html.escape(cell), STYLES["Table"])
                            for cell in row
                        ]
                        for row in rows
                    ],
                    colWidths=[columns] * width,
                    repeatRows=1,
                )
                table.setStyle(
                    TableStyle(
                        [
                            (
                                "BACKGROUND",
                                (0, 0),
                                (-1, 0),
                                colors.HexColor("#E6E5DE"),
                            ),
                            (
                                "GRID",
                                (0, 0),
                                (-1, -1),
                                0.4,
                                colors.HexColor("#BFC1BC"),
                            ),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ]
                    )
                )
                story.extend([table, Spacer(1, 0.3 * cm)])
            continue
        if re.match(r"^\d+\.\s", line):
            story.append(
                Paragraph(
                    html.escape(re.sub(r"^\d+\.\s*", "", line)),
                    STYLES["List"],
                    bulletText=f"{line.split('.', 1)[0]}.",
                )
            )
            index += 1
            continue
        if line.startswith("- "):
            story.append(
                Paragraph(
                    html.escape(line[2:]),
                    STYLES["List"],
                    bulletText="•",
                )
            )
            index += 1
            continue
        story.append(Paragraph(html.escape(line.rstrip()), STYLES["Body"]))
        index += 1
    return story


pdfmetrics.registerFont(UnicodeCIDFont(FONT))
base = getSampleStyleSheet()
STYLES = {
    "Title": ParagraphStyle(
        "PaperTitle",
        parent=base["Title"],
        fontName=FONT,
        fontSize=20,
        leading=30,
        alignment=TA_CENTER,
        textColor=colors.black,
        spaceAfter=24,
    ),
    "CoverMeta": ParagraphStyle(
        "CoverMeta",
        parent=base["BodyText"],
        fontName=FONT,
        fontSize=11,
        leading=22,
        alignment=TA_CENTER,
        textColor=colors.black,
    ),
    "Heading1": ParagraphStyle(
        "Heading1",
        parent=base["Heading1"],
        fontName=FONT,
        fontSize=15,
        leading=23,
        textColor=colors.black,
        spaceBefore=14,
        spaceAfter=8,
    ),
    "Heading2": ParagraphStyle(
        "Heading2",
        parent=base["Heading2"],
        fontName=FONT,
        fontSize=12,
        leading=19,
        textColor=colors.black,
        spaceBefore=10,
        spaceAfter=6,
    ),
    "Body": ParagraphStyle(
        "Body",
        parent=base["BodyText"],
        fontName=FONT,
        fontSize=10.5,
        leading=18,
        alignment=TA_JUSTIFY,
        firstLineIndent=21,
        spaceAfter=5,
        textColor=colors.black,
    ),
    "List": ParagraphStyle(
        "List",
        parent=base["BodyText"],
        fontName=FONT,
        fontSize=10.5,
        leading=17,
        leftIndent=18,
        firstLineIndent=0,
        spaceAfter=3,
        textColor=colors.black,
    ),
    "Table": ParagraphStyle(
        "Table",
        parent=base["BodyText"],
        fontName=FONT,
        fontSize=8.5,
        leading=12,
        textColor=colors.black,
    ),
    "Code": ParagraphStyle(
        "Code",
        parent=base["Code"],
        fontName=FONT,
        fontSize=8.5,
        leading=12,
        leftIndent=12,
        backColor=colors.HexColor("#F2F1EB"),
        borderPadding=6,
        textColor=colors.black,
    ),
    "Caption": ParagraphStyle(
        "Caption",
        parent=base["BodyText"],
        fontName=FONT,
        fontSize=8.5,
        leading=13,
        alignment=TA_CENTER,
        textColor=colors.black,
        spaceBefore=4,
        spaceAfter=2,
    ),
}


def build(source: Path, output: Path):
    text = source.read_text(encoding="utf-8")
    story = parse_markdown(text.splitlines(), source.parent)
    document = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="面向多类技术岗位的简历匹配与技能差距分析 Agent",
        author="________",
    )
    document.build(
        story,
        onFirstPage=add_page_number,
        onLaterPages=add_page_number,
    )
    print(output)


if __name__ == "__main__":
    source = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else PROJECT_ROOT / "reports" / "项目报告.md"
    )
    output = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else PROJECT_ROOT / "reports" / "项目报告_待填写个人信息.pdf"
    )
    build(source, output)
