from __future__ import annotations

import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT.parent
ARCHIVE_PATH = OUTPUT_ROOT / "job_match_agent_repository.zip"
EXCLUDED_PARTS = {".deps", "__pycache__", ".git", ".pytest_cache", "work"}
EXCLUDED_FILES = {
    "data/feedback.jsonl",
    "tests/feedback_test.jsonl",
}


def main():
    with zipfile.ZipFile(
        ARCHIVE_PATH,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in sorted(PROJECT_ROOT.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(PROJECT_ROOT)
            if any(part in EXCLUDED_PARTS for part in relative.parts):
                continue
            if relative.as_posix() in EXCLUDED_FILES:
                continue
            if path.suffix in {".pyc", ".pyo", ".log"}:
                continue
            archive.write(path, relative.as_posix())
    print(ARCHIVE_PATH)
    print(f"size={ARCHIVE_PATH.stat().st_size}")


if __name__ == "__main__":
    main()
