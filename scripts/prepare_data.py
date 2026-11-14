from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.skills import SkillExtractor


RAW_PATH = PROJECT_ROOT / "data" / "jobs_raw.jsonl"
AUDIT_PATH = PROJECT_ROOT / "data" / "job_status_audit.jsonl"
CLEAN_PATH = PROJECT_ROOT / "data" / "jobs_clean.jsonl"
REPORT_PATH = PROJECT_ROOT / "models" / "data_quality_report.json"
SNAPSHOT_DATE = date(2026, 11, 6)

CHINESE_DIGITS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}

KNOWN_CITIES = [
    "北京",
    "上海",
    "广州",
    "深圳",
    "杭州",
    "成都",
    "武汉",
    "南京",
    "西安",
    "苏州",
    "天津",
    "重庆",
    "厦门",
    "济南",
    "青岛",
    "合肥",
    "长沙",
    "珠海",
    "郑州",
    "无锡",
    "佛山",
    "东莞",
    "大连",
    "福州",
    "中山",
    "常州",
    "潍坊",
    "淄博",
]


def parse_chinese_number(value: str) -> int | None:
    if value.isdigit():
        return int(value)
    if value == "十":
        return 10
    if "十" in value:
        left, _, right = value.partition("十")
        tens = CHINESE_DIGITS.get(left, 1) if left else 1
        ones = CHINESE_DIGITS.get(right, 0) if right else 0
        return tens * 10 + ones
    if len(value) == 1 and value in CHINESE_DIGITS:
        return CHINESE_DIGITS[value]
    return None


def parse_experience_years(value: str) -> int | None:
    value = (value or "").strip()
    if not value or any(
        marker in value for marker in ["不限", "应届", "在校", "经验不要求", "无经验"]
    ):
        return 0 if value else None
    match = re.search(r"(\d+|[一二两三四五六七八九十])\s*年", value)
    if not match:
        return None
    return parse_chinese_number(match.group(1))


def parse_date(value: str) -> date | None:
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", value or "")
    if not match:
        return None
    try:
        return datetime.strptime(match.group(0), "%Y-%m-%d").date()
    except ValueError:
        return None


def clean_requirements(value: str) -> str:
    return re.sub(r"^[\s：:，,；;、]+", "", value or "")


def normalize_city(value: str) -> tuple[str, str]:
    original = (value or "").strip()
    matches = [city for city in KNOWN_CITIES if city in original]
    if matches:
        normalized = "、".join(dict.fromkeys(matches))
        return normalized, original
    if any(marker in original for marker in ["未", "明确", "通常", "待定"]):
        return "", original
    return original, original


def main():
    if not RAW_PATH.exists():
        RAW_PATH.write_bytes(CLEAN_PATH.read_bytes() if CLEAN_PATH.exists() else b"")
    rows = [
        json.loads(line)
        for line in RAW_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    audits = {}
    if AUDIT_PATH.exists():
        audits = {
            item["jd_id"]: item
            for item in (
                json.loads(line)
                for line in AUDIT_PATH.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        }
    seen_keys = set()
    seen_urls = set()
    cleaned = []
    duplicate_ids = []
    multi_role_ids = []
    skill_extractor = SkillExtractor(PROJECT_ROOT / "config" / "skills.json")

    for row in rows:
        record = dict(row)
        flags = []
        audit = audits.get(record.get("jd_id"), {})
        record["active_status"] = audit.get("active_status", "unknown")
        record["last_link_checked_at"] = audit.get("checked_at", "")
        record["link_audit_note"] = audit.get("audit_note", "")
        record["requirements"] = clean_requirements(record.get("requirements", ""))
        record["preferred_qualifications"] = clean_requirements(
            record.get("preferred_qualifications", "")
        )
        extracted_skills = skill_extractor.extract_job(record)
        record["tech_stack_keywords"] = ", ".join(
            sorted(item["name"] for item in extracted_skills.values())
        )
        record["required_years_min"] = parse_experience_years(
            record.get("experience_requirement", "")
        )

        city, city_original = normalize_city(record.get("city", ""))
        record["city"] = city
        record["city_original"] = city_original
        if city.endswith(("省", "自治区")):
            record["city_precision"] = "province"
            flags.append("province_only")
        elif "/" in city or "、" in city:
            record["city_precision"] = "multiple"
        elif city:
            record["city_precision"] = "city"
        else:
            record["city_precision"] = "unknown"
            flags.append("city_missing")

        published = parse_date(record.get("published_at", ""))
        if published is None:
            record["freshness_status"] = "unknown"
            flags.append("date_missing")
        else:
            age_days = (SNAPSHOT_DATE - published).days
            if age_days <= 365:
                record["freshness_status"] = "fresh"
            elif age_days <= 730:
                record["freshness_status"] = "recent"
            else:
                record["freshness_status"] = "stale"
                flags.append("stale_over_2y")

        title = record.get("job_title", "")
        if len(title) > 80 or title.count("/") >= 4 or title.count("工程师") >= 4:
            record["quality_status"] = "exclude"
            flags.append("multi_role_title")
            multi_role_ids.append(record.get("jd_id"))
        else:
            record["quality_status"] = "ok"

        title_key = (
            record.get("company", "").strip().lower(),
            title.strip().lower(),
            city.strip().lower(),
        )
        url_key = record.get("source_url", "")
        if all(title_key) and title_key in seen_keys:
            record["quality_status"] = "exclude"
            flags.append("duplicate_title_company_city")
            duplicate_ids.append(record.get("jd_id"))
        elif url_key and url_key in seen_urls:
            record["quality_status"] = "exclude"
            flags.append("duplicate_source_url")
            duplicate_ids.append(record.get("jd_id"))

        if all(title_key):
            seen_keys.add(title_key)
        if url_key:
            seen_urls.add(url_key)
        record["quality_flags"] = sorted(set(flags))
        if record["active_status"] == "expired":
            record["quality_status"] = "exclude"
            record["quality_flags"] = sorted(
                set(record["quality_flags"] + ["expired_posting"])
            )
        record["is_matchable"] = record["quality_status"] == "ok"
        cleaned.append(record)

    CLEAN_PATH.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in cleaned) + "\n",
        encoding="utf-8",
    )
    report = {
        "raw_records": len(rows),
        "clean_records": len(cleaned),
        "matchable_records": sum(record["is_matchable"] for record in cleaned),
        "role_counts": dict(Counter(record["role_family"] for record in cleaned)),
        "freshness_counts": dict(
            Counter(record["freshness_status"] for record in cleaned)
        ),
        "quality_status_counts": dict(
            Counter(record["quality_status"] for record in cleaned)
        ),
        "active_status_counts": dict(
            Counter(record["active_status"] for record in cleaned)
        ),
        "duplicate_ids": sorted(filter(None, duplicate_ids)),
        "multi_role_ids": sorted(filter(None, multi_role_ids)),
        "removed_leading_punctuation": sum(
            bool(re.match(r"^[：:，,；;、]", row.get("requirements", "")))
            for row in rows
        ),
        "missing_preferred_qualifications": sum(
            not row.get("preferred_qualifications") for row in rows
        ),
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
