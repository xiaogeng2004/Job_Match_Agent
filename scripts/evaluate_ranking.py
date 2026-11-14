from __future__ import annotations

import csv
import json
import math
import random
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.core import JobMatchAgent
from agent.data import JobRepository
from agent.model import job_text


PERSONAS_PATH = PROJECT_ROOT / "data" / "evaluation_personas.json"
OUTPUT_PATH = PROJECT_ROOT / "models" / "ranking_metrics.json"
REVIEW_PATH = PROJECT_ROOT / "models" / "relevance_review_template.csv"
REVIEWED_PATH = PROJECT_ROOT / "models" / "relevance_review_v1.csv"


def dcg(relevances: list[int]) -> float:
    return sum(
        (2**relevance - 1) / math.log2(index + 2)
        for index, relevance in enumerate(relevances)
    )


def ndcg_at_k(ranked_ids: list[str], labels: dict[str, int], k: int) -> float:
    actual = [labels.get(job_id, 0) for job_id in ranked_ids[:k]]
    ideal = sorted(labels.values(), reverse=True)[:k]
    ideal_score = dcg(ideal)
    return dcg(actual) / ideal_score if ideal_score else 0.0


def precision_at_k(ranked_ids: list[str], labels: dict[str, int], k: int) -> float:
    hits = sum(labels.get(job_id, 0) >= 1 for job_id in ranked_ids[:k])
    return hits / k


def recall_at_k(ranked_ids: list[str], labels: dict[str, int], k: int) -> float:
    relevant = {job_id for job_id, grade in labels.items() if grade >= 1}
    if not relevant:
        return 0.0
    return len(set(ranked_ids[:k]) & relevant) / len(relevant)


def evaluate_rankings(
    rankings: dict[str, list[str]],
    labels_by_query: dict[str, dict[str, int]],
    eligible_queries: set[str],
):
    results = {}
    for method, _ in rankings.items():
        precision_values = []
        recall_values = []
        ndcg_values = []
        for query_id, ranked_ids in rankings[method].items():
            if query_id not in eligible_queries:
                continue
            labels = labels_by_query[query_id]
            precision_values.append(precision_at_k(ranked_ids, labels, 3))
            recall_values.append(recall_at_k(ranked_ids, labels, 5))
            ndcg_values.append(ndcg_at_k(ranked_ids, labels, 5))
        results[method] = {
            "precision_at_3": round(float(np.mean(precision_values)), 4),
            "recall_at_5": round(float(np.mean(recall_values)), 4),
            "ndcg_at_5": round(float(np.mean(ndcg_values)), 4),
        }
    return results


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    personas = json.loads(PERSONAS_PATH.read_text(encoding="utf-8"))
    agent = JobMatchAgent()
    vectorizer = agent.role_classifier.pipeline.named_steps["tfidf"]
    reviewed_labels = {}
    if REVIEWED_PATH.exists():
        with REVIEWED_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("reviewer_grade", "").strip():
                    reviewed_labels[(row["query_id"], row["jd_id"])] = int(
                        row["reviewer_grade"]
                    )

    rankings = {"keyword": {}, "tfidf": {}, "agent_hybrid": {}}
    labels_by_query = {}
    query_summaries = []
    eligible_queries = set()
    review_pool = []
    reviewed_pair_count = 0

    for persona in personas:
        roles = {persona["role_family"]}
        jobs = JobRepository.filter_jobs(
            agent.jobs,
            role_families=roles,
            employment_types=set(persona.get("employment_types", [])),
            max_experience_years=persona.get("max_experience_years"),
            freshness_window="2y",
        )
        target_skills = set(persona["target_skills"])
        overlap_by_job = {}
        labels = {}
        for job in jobs:
            job_skills = agent.skill_extractor.extract_job(job)
            required_keys = {
                key
                for key, value in job_skills.items()
                if value["importance"] == "required" and value["technical"]
            }
            overlap = len(target_skills & set(job_skills))
            required_coverage = (
                len(target_skills & required_keys) / len(required_keys)
                if required_keys
                else 0.0
            )
            overlap_by_job[job["jd_id"]] = overlap
            labels[job["jd_id"]] = (
                2
                if overlap >= 2 and required_coverage >= 0.25
                else (1 if overlap >= 1 and required_coverage >= 0.10 else 0)
            )
            if len(jobs) >= 5:
                review_pool.append(
                    {
                        "query_id": persona["id"],
                        "role_family": persona["role_family"],
                        "jd_id": job["jd_id"],
                        "job_title": job.get("job_title", ""),
                        "company": job.get("company", ""),
                        "city": job.get("city", ""),
                        "employment_type": job.get("employment_type", ""),
                        "target_skills": ", ".join(sorted(target_skills)),
                        "auto_grade": labels[job["jd_id"]],
                        "reviewer_grade": "",
                        "reviewer_notes": "",
                    }
                )

        labels_by_query[persona["id"]] = labels
        reviewed_count = 0
        for (query_id, job_id), grade in reviewed_labels.items():
            if query_id == persona["id"] and job_id in labels:
                labels[job_id] = grade
                reviewed_count += 1
        reviewed_pair_count += reviewed_count
        if len(jobs) >= 5:
            eligible_queries.add(persona["id"])
        rankings["keyword"][persona["id"]] = [
            job["jd_id"]
            for job in sorted(
                jobs,
                key=lambda job: (
                    overlap_by_job[job["jd_id"]],
                    job.get("published_at", ""),
                ),
                reverse=True,
            )
        ]

        if jobs:
            job_vectors = vectorizer.transform([job_text(job) for job in jobs])
            resume_vector = vectorizer.transform([persona["resume_text"]])
            similarities = cosine_similarity(resume_vector, job_vectors)[0]
            tfidf_order = np.argsort(-similarities)
            rankings["tfidf"][persona["id"]] = [
                jobs[index]["jd_id"] for index in tfidf_order
            ]
        else:
            rankings["tfidf"][persona["id"]] = []

        result = agent.analyze(
            persona["resume_text"],
            role_families=list(roles),
            top_n=20,
            employment_types=persona.get("employment_types", []),
            max_experience_years=persona.get("max_experience_years"),
            freshness_window="2y",
        )
        rankings["agent_hybrid"][persona["id"]] = [
            job["jd_id"] for job in result["jobs"]
        ]
        query_summaries.append(
            {
                "query_id": persona["id"],
                "role_family": persona["role_family"],
                "candidate_count": len(jobs),
                "relevant_count": sum(grade >= 1 for grade in labels.values()),
                "agent_top_5": rankings["agent_hybrid"][persona["id"]][:5],
            }
        )

    metrics = evaluate_rankings(rankings, labels_by_query, eligible_queries)
    output = {
        "query_count": len(personas),
        "eligible_query_count": len(eligible_queries),
        "reviewed_pair_count": reviewed_pair_count,
        "excluded_small_candidate_queries": sorted(
            {persona["id"] for persona in personas} - eligible_queries
        ),
        "label_method": (
            "skill_overlap_silver_labels_with_ai_assisted_review"
            if reviewed_labels
            else "silver_rule_from_target_skill_overlap"
        ),
        "label_grades": {
            "2": "至少命中 2 个目标技能，且必备技能覆盖不低于 25%",
            "1": "至少命中 1 个目标技能，且必备技能覆盖不低于 10%",
            "0": "未命中目标技能"
        },
        "metrics": metrics,
        "queries": query_summaries,
        "limitations": [
            "相关性标签由目标技能覆盖规则生成，不是完全独立的人工 gold set。",
            "抽样结果经过 AI 辅助复核，但仍应由团队成员确认真实求职者偏好。"
        ]
    }
    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    review_size = min(len(review_pool), max(20, round(len(review_pool) * 0.2)))
    review_rows = random.Random(42).sample(review_pool, review_size)
    with REVIEW_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(review_rows[0]))
        writer.writeheader()
        writer.writerows(review_rows)
    output["manual_review_sample"] = {
        "path": str(REVIEW_PATH),
        "rows": review_size,
    }
    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
