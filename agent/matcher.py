from __future__ import annotations

import re
from typing import Iterable

from sklearn.metrics.pairwise import cosine_similarity

from agent.model import RoleClassifier, job_text
from agent.skills import SkillExtractor


class JobMatcher:
    def __init__(
        self,
        skill_extractor: SkillExtractor,
        role_classifier: RoleClassifier,
        jobs: Iterable[dict],
        negative_feedback_counts: dict[str, int] | None = None,
    ):
        self.skill_extractor = skill_extractor
        self.role_classifier = role_classifier
        self.jobs = list(jobs)
        self.negative_feedback_counts = negative_feedback_counts or {}

    @staticmethod
    def _coverage(matched: set[str], required: set[str]) -> float:
        if not required:
            return 0.0
        return len(matched & required) / len(required)

    def _skill_payload(self, keys: set[str]) -> list[dict]:
        return [
            {
                "key": key,
                "name": self.skill_extractor.by_key[key].name,
                "category": self.skill_extractor.by_key[key].category,
            }
            for key in sorted(keys)
            if key in self.skill_extractor.by_key
        ]

    @staticmethod
    def _diversify_by_company(
        jobs: list[dict],
        limit: int,
        max_per_company: int = 2,
    ) -> list[dict]:
        selected = []
        deferred = []
        company_counts: dict[str, int] = {}
        for job in jobs:
            company = job.get("company", "")
            count = company_counts.get(company, 0)
            if count < max_per_company:
                selected.append(job)
                company_counts[company] = count + 1
                if len(selected) >= limit:
                    return selected
            else:
                deferred.append(job)
        for job in deferred:
            if len(selected) >= limit:
                break
            selected.append(job)
        return selected

    def _predict_role(self, text: str) -> dict:
        ml_prediction = self.role_classifier.predict(text)
        rule_prediction = self.skill_extractor.rule_role_prediction(text)
        if rule_prediction and (
            rule_prediction["role_family"] == ml_prediction["role_family"]
            or ml_prediction["confidence"] < 0.45
        ):
            return {
                **rule_prediction,
                "ml_role": ml_prediction["role_family"],
                "ml_confidence": ml_prediction["confidence"],
                "probabilities": ml_prediction["probabilities"],
                "low_confidence": False,
                "decision_method": "hybrid_model_and_rules",
            }
        return {
            **ml_prediction,
            "decision_method": "supervised_model",
            "rule_role": (
                rule_prediction["role_family"] if rule_prediction else None
            ),
        }

    def rank(
        self,
        resume_text: str,
        top_n: int = 10,
        confirmed_skills: Iterable[str] | None = None,
    ) -> dict:
        profile = self.skill_extractor.extract_profile(resume_text)
        for key in confirmed_skills or []:
            skill = self.skill_extractor.by_key.get(key)
            if skill:
                profile[key] = {
                    "key": skill.key,
                    "name": skill.name,
                    "category": skill.category,
                    "technical": skill.technical,
                    "count": 1,
                    "evidence": ["用户手动确认具备该技能"],
                    "confirmed": True,
                }
        profile_keys = set(profile)
        if not self.jobs:
            return {"profile": profile, "jobs": [], "trace": []}

        all_text = [job_text(job) for job in self.jobs]
        vectorizer = self.role_classifier.pipeline.named_steps["tfidf"]
        job_vectors = vectorizer.transform(all_text)
        resume_vector = vectorizer.transform([resume_text])
        similarities = cosine_similarity(resume_vector, job_vectors)[0]

        ranked = []
        for index, job in enumerate(self.jobs):
            family = job["role_family"]
            job_skills = self.skill_extractor.extract_job(job)
            required = {
                key
                for key, value in job_skills.items()
                if value["importance"] == "required" and value["technical"]
            }
            preferred = {
                key
                for key, value in job_skills.items()
                if value["importance"] == "preferred" and value["technical"]
            }
            required_coverage = self._coverage(profile_keys, required)
            preferred_coverage = (
                self._coverage(profile_keys, preferred) if preferred else None
            )
            matched = required & profile_keys
            missing = required - profile_keys
            preferred_gaps = preferred - profile_keys
            hit_strength = min(1.0, len(matched) / 4)
            core = self.skill_extractor.core_readiness(family, profile_keys)
            similarity = float(similarities[index])
            role_prediction = self._predict_role(all_text[index])
            role_alignment = role_prediction["probabilities"].get(family, 0.0)
            weighted_components = [
                (required_coverage, 0.15),
                (hit_strength, 0.60),
                (core["coverage"], 0.05),
                (similarity, 0.05),
                (role_alignment, 0.10),
            ]
            if preferred_coverage is not None:
                weighted_components.append((preferred_coverage, 0.05))
            weight_total = sum(weight for _, weight in weighted_components)
            score = sum(
                value * weight for value, weight in weighted_components
            ) / weight_total
            if core["coverage"] < 0.5:
                score *= 0.78
            negative_feedback = self.negative_feedback_counts.get(job["jd_id"], 0)
            if negative_feedback:
                score *= max(0.70, 1.0 - 0.10 * negative_feedback)

            ranked.append(
                {
                    "jd_id": job["jd_id"],
                    "job_title": job["job_title"],
                    "company": job.get("company", ""),
                    "city": job.get("city", ""),
                    "employment_type": job.get("employment_type", ""),
                    "required_years_min": job.get("required_years_min"),
                    "freshness_status": job.get("freshness_status", "unknown"),
                    "active_status": job.get("active_status", "unknown"),
                    "role_family": family,
                    "role_family_zh": job["role_family_zh"],
                    "model_role": role_prediction["role_family"],
                    "model_confidence": role_prediction["confidence"],
                    "score": round(score * 100, 1),
                    "required_coverage": round(required_coverage * 100, 1),
                    "preferred_coverage": (
                        round(preferred_coverage * 100, 1)
                        if preferred_coverage is not None
                        else None
                    ),
                    "core_coverage": round(core["coverage"] * 100, 1),
                    "text_similarity": round(similarity * 100, 1),
                    "hit_strength": round(hit_strength * 100, 1),
                    "model_alignment": round(role_alignment * 100, 1),
                    "model_decision": role_prediction.get("decision_method", ""),
                    "negative_feedback_count": negative_feedback,
                    "matched_skills": self._skill_payload(matched),
                    "missing_skills": self._skill_payload(missing),
                    "preferred_gaps": self._skill_payload(preferred_gaps),
                    "core_groups": core["groups"],
                    "source_url": job.get("source_url", ""),
                    "published_at": job.get("published_at", ""),
                    "requirements_evidence": {
                        key: job_skills[key]["evidence"]
                        for key in missing
                        if key in job_skills
                    },
                }
            )

        ranked.sort(key=lambda item: item["score"], reverse=True)
        ranked = self._diversify_by_company(
            ranked,
            limit=max(1, min(top_n, 20)),
        )
        return {
            "profile": profile,
            "jobs": ranked,
            "trace": [
                "从简历中提取技能与原文证据",
                f"在本地岗位库中检索 {len(self.jobs)} 条岗位",
                "使用岗位分类模型检查岗位方向",
                "计算必备技能、加分技能、核心能力和文本相似度",
                "按匹配得分排序并生成差距说明",
                "限制单一公司占位，增加来源多样性",
                "应用历史岗位不相关反馈进行降权",
            ],
        }

    def analyze_custom_jd(
        self,
        resume_text: str,
        jd_text: str,
        confirmed_skills: Iterable[str] | None = None,
        confirmed_role: str = "",
    ) -> dict | None:
        if not jd_text.strip():
            return None

        profile = self.skill_extractor.extract_profile(resume_text)
        for key in confirmed_skills or []:
            skill = self.skill_extractor.by_key.get(key)
            if skill:
                profile[key] = {
                    "key": skill.key,
                    "name": skill.name,
                    "category": skill.category,
                    "technical": skill.technical,
                    "count": 1,
                    "evidence": ["用户手动确认具备该技能"],
                    "confirmed": True,
                }
        profile_keys = set(profile)
        prediction = self._predict_role(jd_text)
        if confirmed_role in self.skill_extractor.families:
            prediction = {
                "role_family": confirmed_role,
                "confidence": 1.0,
                "probabilities": prediction.get("probabilities", {}),
                "low_confidence": False,
                "decision_method": "user_confirmation",
            }
        family = prediction["role_family"]
        responsibility_match = re.split(
            r"任职要求|岗位要求|职位要求",
            jd_text,
            maxsplit=1,
        )
        responsibilities = (
            re.sub(
                r"^(?:岗位职责|职位职责|工作职责)[：:]\s*",
                "",
                responsibility_match[0],
            ).strip()
            if len(responsibility_match) > 1
            else ""
        )
        requirements = (
            responsibility_match[1].strip()
            if len(responsibility_match) > 1
            else jd_text
        )
        job = {
            "responsibilities": responsibilities,
            "requirements": requirements,
            "preferred_qualifications": "",
        }
        job_skills = self.skill_extractor.extract_job(job)
        required = {
            key
            for key, value in job_skills.items()
            if value["importance"] == "required" and value["technical"]
        }
        matched = required & profile_keys
        missing = required - profile_keys
        core = self.skill_extractor.core_readiness(family, profile_keys)
        return {
            "prediction": prediction,
            "role_family_zh": self.skill_extractor.families[family]["name"],
            "matched_skills": self._skill_payload(matched),
            "missing_skills": self._skill_payload(missing),
            "core_readiness": core,
            "requirement_coverage": round(
                self._coverage(profile_keys, required) * 100, 1
            ),
        }

