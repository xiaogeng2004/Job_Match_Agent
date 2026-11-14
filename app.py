from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from agent.core import JobMatchAgent
from agent.documents import extract_text_from_upload, privacy_flags


PROJECT_ROOT = Path(__file__).resolve().parent
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
FEEDBACK_PATH = PROJECT_ROOT / "data" / "feedback.jsonl"
FEEDBACK_LOCK = threading.Lock()


def get_agent() -> JobMatchAgent:
    if not hasattr(app, "_job_match_agent"):
        app._job_match_agent = JobMatchAgent()
    return app._job_match_agent


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    agent = get_agent()
    matchable_jobs = [job for job in agent.jobs if job.get("is_matchable", True)]
    return jsonify(
        {
            "status": "ok",
            "jobs": len(matchable_jobs),
            "total_jobs": len(agent.jobs),
            "roles": sorted(agent.skill_extractor.families),
            "skills": len(agent.skill_extractor.skills),
            "cities": sorted(
                {
                    city.strip()
                    for job in matchable_jobs
                    for city in re.split(r"[/、,，]", job.get("city", ""))
                    if city.strip()
                }
            ),
        }
    )


@app.get("/api/metrics")
def metrics():
    path = PROJECT_ROOT / "models" / "metrics.json"
    if not path.exists():
        return jsonify({"error": "模型指标尚未生成。"}), 404
    return jsonify(json.loads(path.read_text(encoding="utf-8")))


@app.get("/api/ranking-metrics")
def ranking_metrics():
    path = PROJECT_ROOT / "models" / "ranking_metrics.json"
    if not path.exists():
        return jsonify({"error": "排序指标尚未生成。"}), 404
    return jsonify(json.loads(path.read_text(encoding="utf-8")))


@app.get("/api/jobs")
def browse_jobs():
    agent = get_agent()
    roles = set(request.args.getlist("roles"))
    city_values = set(request.args.getlist("cities"))
    employment_types = set(request.args.getlist("employment_types"))
    max_experience_raw = request.args.get("max_experience_years", "").strip()
    freshness_window = request.args.get("freshness_window", "2y")
    try:
        max_experience_years = (
            int(max_experience_raw) if max_experience_raw else None
        )
        page = max(1, int(request.args.get("page", "1")))
        page_size = max(1, min(50, int(request.args.get("page_size", "20"))))
    except ValueError:
        return jsonify({"error": "分页或经验参数格式错误。"}), 400

    jobs = agent.repository.filter_jobs(
        agent.jobs,
        role_families=roles,
        cities=city_values,
        employment_types=employment_types,
        max_experience_years=max_experience_years,
        freshness_window=freshness_window,
    )
    jobs.sort(
        key=lambda item: (
            item.get("published_at", ""),
            item.get("job_title", ""),
        ),
        reverse=True,
    )
    total = len(jobs)
    start = (page - 1) * page_size
    page_items = jobs[start : start + page_size]
    return jsonify(
        {
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": start + page_size < total,
            "jobs": [
                {
                    "jd_id": job["jd_id"],
                    "job_title": job.get("job_title", ""),
                    "company": job.get("company", ""),
                    "city": job.get("city", ""),
                    "role_family": job.get("role_family", ""),
                    "role_family_zh": job.get("role_family_zh", ""),
                    "employment_type": job.get("employment_type", ""),
                    "published_at": job.get("published_at", ""),
                    "freshness_status": job.get("freshness_status", "unknown"),
                    "active_status": job.get("active_status", "unknown"),
                    "source_url": job.get("source_url", ""),
                }
                for job in page_items
            ],
        }
    )


@app.post("/api/analyze")
def analyze():
    try:
        roles = request.form.getlist("roles")
        if len(roles) == 1 and "," in roles[0]:
            roles = [item.strip() for item in roles[0].split(",") if item.strip()]

        resume_text = (request.form.get("resume_text") or "").strip()
        uploaded = request.files.get("resume_file")
        if not resume_text and uploaded and uploaded.filename:
            resume_text = extract_text_from_upload(uploaded)

        if not resume_text:
            raise ValueError("请粘贴简历文本或上传 PDF/DOCX/TXT 文件。")

        top_n = int(request.form.get("top_n", "10"))
        custom_jd_text = request.form.get("custom_jd_text", "")
        max_experience_raw = request.form.get("max_experience_years", "").strip()
        max_experience_years = (
            int(max_experience_raw) if max_experience_raw else None
        )
        result = get_agent().analyze(
            resume_text=resume_text,
            role_families=roles,
            top_n=top_n,
            custom_jd_text=custom_jd_text,
            cities=request.form.getlist("cities"),
            employment_types=request.form.getlist("employment_types"),
            max_experience_years=max_experience_years,
            freshness_window=request.form.get("freshness_window", "2y"),
            confirmed_skills=request.form.getlist("confirmed_skills"),
            confirmed_custom_role=request.form.get(
                "confirmed_custom_role",
                "",
            ),
        )
        result["privacy_warnings"] = privacy_flags(resume_text)
        return jsonify(result)
    except (ValueError, FileNotFoundError) as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        app.logger.exception("Unexpected analysis error")
        return jsonify({"error": "分析失败，请检查输入后重试。"}), 500


@app.post("/api/feedback")
def feedback():
    payload = request.get_json(silent=True) or {}
    feedback_type = str(payload.get("feedback_type", "")).strip()
    if feedback_type not in {"job_not_relevant", "skill_confirmed", "role_corrected"}:
        return jsonify({"error": "不支持的反馈类型。"}), 400
    record = {
        "received_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "feedback_type": feedback_type,
        "jd_id": str(payload.get("jd_id", ""))[:100],
        "skill_key": str(payload.get("skill_key", ""))[:100],
        "corrected_role": str(payload.get("corrected_role", ""))[:100],
    }
    with FEEDBACK_LOCK:
        with FEEDBACK_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return jsonify({"saved": True})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)

