from __future__ import annotations

import time
from typing import Iterable

from agent.data import JobRepository
from agent.matcher import JobMatcher
from agent.model import RoleClassifier
from agent.skills import SkillExtractor


class JobMatchAgent:
    """Controllable workflow that matches a resume against a local JD corpus."""

    def __init__(
        self,
        jobs: Iterable[dict] | None = None,
        skill_extractor: SkillExtractor | None = None,
        role_classifier: RoleClassifier | None = None,
    ):
        self.repository = JobRepository()
        self.skill_extractor = skill_extractor or SkillExtractor()
        self.role_classifier = role_classifier or RoleClassifier()
        self.jobs = list(jobs) if jobs is not None else self.repository.jobs

    def analyze(
        self,
        resume_text: str,
        role_families: list[str] | None = None,
        top_n: int = 10,
        custom_jd_text: str = "",
        cities: list[str] | None = None,
        employment_types: list[str] | None = None,
        max_experience_years: int | None = None,
        freshness_window: str = "2y",
        confirmed_skills: list[str] | None = None,
        confirmed_custom_role: str = "",
    ) -> dict:
        started = time.perf_counter()
        cleaned_resume = (resume_text or "").strip()
        if len(cleaned_resume) < 20:
            raise ValueError(
                "请输入至少 20 个字符的简历内容，或上传 PDF/DOCX/TXT 文件。"
            )
        if freshness_window not in {"1y", "2y", "all"}:
            raise ValueError("发布时间筛选参数无效。")
        if max_experience_years is not None and max_experience_years < 0:
            raise ValueError("经验年限不能为负数。")

        valid_roles = set(self.skill_extractor.families)
        selected = set(role_families or valid_roles) & valid_roles
        if not selected:
            raise ValueError("请至少选择一个岗位方向。")

        jobs = JobRepository.filter_jobs(
            self.jobs,
            role_families=selected,
            cities=set(cities or []),
            employment_types=set(employment_types or []),
            max_experience_years=max_experience_years,
            freshness_window=freshness_window,
        )
        filter_advice = []
        if len(jobs) < 3:
            if employment_types:
                filter_advice.append(
                    "当前招聘类型筛选后岗位较少，可尝试同时查看校招或社招岗位。"
                )
            if max_experience_years is not None:
                filter_advice.append(
                    "当前经验年限筛选较严格，可放宽经验条件后再比较。"
                )
            if freshness_window == "1y":
                filter_advice.append(
                    "近一年岗位较少，可切换到近两年或全部有效数据。"
                )
            if cities:
                filter_advice.append("当前城市范围较窄，可尝试取消城市限制。")
        matcher = JobMatcher(
            self.skill_extractor,
            self.role_classifier,
            jobs,
            negative_feedback_counts=self.repository.negative_feedback_counts(),
        )
        confirmed = [
            key for key in (confirmed_skills or []) if key in self.skill_extractor.by_key
        ]
        result = matcher.rank(
            cleaned_resume,
            top_n=top_n,
            confirmed_skills=confirmed,
        )
        custom_analysis = matcher.analyze_custom_jd(
            cleaned_resume,
            (custom_jd_text or "").strip(),
            confirmed_skills=confirmed,
            confirmed_role=confirmed_custom_role,
        )

        role_readiness = {
            family: self.skill_extractor.core_readiness(
                family,
                set(result["profile"]),
            )
            for family in sorted(selected)
        }
        result.update(
            {
                "role_families": sorted(selected),
                "role_family_names": {
                    key: self.skill_extractor.families[key]["name"]
                    for key in sorted(selected)
                },
                "role_readiness": role_readiness,
                "custom_jd": custom_analysis,
                "job_count": len(jobs),
                "filters": {
                    "cities": sorted(cities or []),
                    "employment_types": sorted(employment_types or []),
                    "max_experience_years": max_experience_years,
                    "freshness_window": freshness_window,
                },
                "confirmed_skills": confirmed,
                "filter_advice": filter_advice,
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
                "disclaimer": (
                    "匹配分表示简历与岗位要求的覆盖程度，不是录用概率。"
                    "“简历中未找到”不等于“不会”，请结合真实经历确认。"
                ),
            }
        )
        return result
