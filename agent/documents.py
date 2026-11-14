from __future__ import annotations

import io
import re
import sys
from pathlib import Path

from docx import Document
from werkzeug.datastructures import FileStorage


MAX_FILE_BYTES = 2 * 1024 * 1024
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def extract_text_from_upload(file: FileStorage) -> str:
    filename = (file.filename or "").lower()
    payload = file.read()
    if len(payload) > MAX_FILE_BYTES:
        raise ValueError("文件超过 2 MB，请精简后再上传。")
    if not payload:
        raise ValueError("上传文件为空。")

    if filename.endswith(".docx"):
        document = Document(io.BytesIO(payload))
        parts = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        return "\n".join(part for part in parts if part.strip())

    if filename.endswith(".txt"):
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return payload.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("TXT 文件编码无法识别，请另存为 UTF-8 后重试。")

    if filename.endswith(".pdf"):
        local_deps = PROJECT_ROOT / ".deps"
        if local_deps.exists() and str(local_deps) not in sys.path:
            sys.path.insert(0, str(local_deps))
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError(
                "缺少 PDF 解析依赖，请先运行 `python -m pip install -r requirements.txt`。"
            ) from exc

        try:
            reader = PdfReader(io.BytesIO(payload))
            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception as exc:
                    raise ValueError(
                        "PDF 已加密，无法读取。请上传未加密版本。"
                    ) from exc
            pages = [(page.extract_text() or "").strip() for page in reader.pages]
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("PDF 文件损坏或格式不受支持，请重新导出后重试。") from exc

        text = "\n".join(page for page in pages if page)
        if not text:
            raise ValueError(
                "PDF 中没有可提取的文字，可能是扫描件。请先进行 OCR，或直接粘贴简历文本。"
            )
        return text

    raise ValueError("仅支持 PDF、DOCX 和 TXT 文件，也可以直接粘贴简历文本。")


def privacy_flags(text: str) -> list[str]:
    flags = []
    if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text):
        flags.append("检测到可能的手机号，结果只在当前请求内存中处理，不会保存。")
    if re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text):
        flags.append("检测到可能的邮箱，结果只在当前请求内存中处理，不会保存。")
    return flags

