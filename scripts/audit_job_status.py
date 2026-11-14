from __future__ import annotations

import concurrent.futures
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = PROJECT_ROOT / "data" / "jobs_raw.jsonl"
OUTPUT_PATH = PROJECT_ROOT / "data" / "job_status_audit.jsonl"
EXPIRED_MARKERS = (
    "该招聘信息已过期",
    "招聘信息已过期",
    "职位已下线",
    "岗位已关闭",
    "该职位已失效",
    "职位不存在",
)


def audit_url(job: dict) -> dict:
    original_url = job.get("source_url", "")
    url = original_url
    if "career.hebut.edu.cn/home/correcruit/content/" in url:
        url = url.replace("/home/correcruit/", "/correcruit/")

    result = {
        "jd_id": job["jd_id"],
        "source_url": original_url,
        "audit_url": url,
        "checked_at": date.today().isoformat(),
        "http_status": None,
        "active_status": "unknown",
        "audit_note": "",
    }
    if not url.startswith(("http://", "https://")):
        result["audit_note"] = "no_public_url"
        return result

    session = requests.Session()
    session.trust_env = False
    try:
        response = session.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            allow_redirects=True,
            timeout=12,
        )
        result["http_status"] = response.status_code
        result["final_url"] = response.url
        parsed = urlparse(response.url)
        if any(
            marker in parsed.path.lower()
            for marker in ["captcha", "security", "login"]
        ):
            result["active_status"] = "unknown"
            result["audit_note"] = "redirected_to_login_or_security_page"
            return result
        if response.status_code >= 400:
            result["active_status"] = "expired"
            result["audit_note"] = "http_error"
            return result
        text = response.text[:500000]
        marker = next((item for item in EXPIRED_MARKERS if item in text), "")
        if marker:
            result["active_status"] = "expired"
            result["audit_note"] = marker
        elif url.startswith("https://careers.tencent.com/"):
            result["active_status"] = "active"
            result["audit_note"] = "company_official_page"
        elif len(text.strip()) < 1000:
            result["active_status"] = "unknown"
            result["audit_note"] = "page_too_short"
        else:
            result["active_status"] = "active"
            result["audit_note"] = "page_reachable"
    except requests.RequestException as exc:
        result["audit_note"] = f"request_error:{type(exc).__name__}"
    return result


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    jobs = [
        json.loads(line)
        for line in RAW_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(audit_url, jobs))
    OUTPUT_PATH.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in results) + "\n",
        encoding="utf-8",
    )
    print("Status counts", Counter(item["active_status"] for item in results))
    print("Notes", Counter(item["audit_note"] for item in results).most_common(12))


if __name__ == "__main__":
    main()
