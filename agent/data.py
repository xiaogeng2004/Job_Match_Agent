from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JOBS_PATH = PROJECT_ROOT / "data" / "jobs_clean.jsonl"


class JobRepository:
    def __init__(self, path: Path | str = DEFAULT_JOBS_PATH):
        self.path = Path(path)
        self.jobs = self._load()

    def _load(self) -> list[dict]:
        jobs = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    jobs.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Invalid JSONL at {self.path}:{line_number}: {exc}"
                    ) from exc
        return jobs

    @staticmethod
    def filter_jobs(
        jobs: list[dict],
        role_families: set[str],
        cities: set[str] | None = None,
        employment_types: set[str] | None = None,
        max_experience_years: int | None = None,
        freshness_window: str = "2y",
    ) -> list[dict]:
        cities = {city.strip().lower() for city in cities or set() if city.strip()}
        employment_types = {
            employment.strip().lower()
            for employment in employment_types or set()
            if employment.strip()
        }
        jobs = [job for job in jobs if job.get("is_matchable", True)]
        if role_families:
            jobs = [job for job in jobs if job["role_family"] in role_families]
        if cities:
            jobs = [
                job
                for job in jobs
                if any(city in job.get("city", "").lower() for city in cities)
            ]
        if employment_types:
            jobs = [
                job
                for job in jobs
                if any(
                    employment in job.get("employment_type", "").lower()
                    or (
                        employment == "实习"
                        and "校招/实习" in job.get("employment_type", "")
                    )
                    for employment in employment_types
                )
            ]
        if max_experience_years is not None:
            jobs = [
                job
                for job in jobs
                if job.get("required_years_min") is not None
                and job["required_years_min"] <= max_experience_years
            ]
        if freshness_window == "1y":
            jobs = [
                job for job in jobs if job.get("freshness_status") == "fresh"
            ]
        elif freshness_window == "2y":
            jobs = [
                job
                for job in jobs
                if job.get("freshness_status") in {"fresh", "recent"}
            ]
        return jobs

    def filter(
        self,
        role_families: set[str],
        cities: set[str] | None = None,
        employment_types: set[str] | None = None,
        max_experience_years: int | None = None,
        freshness_window: str = "2y",
    ) -> list[dict]:
        return self.filter_jobs(
            self.jobs,
            role_families=role_families,
            cities=cities,
            employment_types=employment_types,
            max_experience_years=max_experience_years,
            freshness_window=freshness_window,
        )

    def negative_feedback_counts(self) -> dict[str, int]:
        path = PROJECT_ROOT / "data" / "feedback.jsonl"
        counts: dict[str, int] = {}
        if not path.exists():
            return counts
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("feedback_type") != "job_not_relevant":
                continue
            job_id = str(record.get("jd_id", ""))
            if job_id:
                counts[job_id] = counts.get(job_id, 0) + 1
        return counts

