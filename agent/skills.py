from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "skills.json"

REQUIREMENT_SPLIT = re.compile(r"[\n\r。；;]+")
PREFERRED_MARKERS = ("优先", "加分", "更佳", "者佳", "有经验者优先", "熟悉者优先")


@dataclass(frozen=True)
class Skill:
    key: str
    name: str
    category: str
    technical: bool
    patterns: tuple[re.Pattern[str], ...]


class SkillExtractor:
    """Deterministic skill extractor with evidence spans."""

    def __init__(self, config_path: Path | str = DEFAULT_CONFIG_PATH):
        config = json.loads(Path(config_path).read_text(encoding="utf-8"))
        self.families = config["families"]
        self.role_patterns = {
            family: tuple(
                re.compile(pattern, re.IGNORECASE)
                for pattern in details.get("role_patterns", [])
            )
            for family, details in self.families.items()
        }
        self.skills = [
            Skill(
                key=item["key"],
                name=item["name"],
                category=item["category"],
                technical=item["technical"],
                patterns=tuple(re.compile(pattern) for pattern in item["patterns"]),
            )
            for item in config["skills"]
        ]
        self.by_key = {skill.key: skill for skill in self.skills}

    @staticmethod
    def _sentences(text: str) -> list[str]:
        return [
            sentence.strip(" \t\n\r-•·")
            for sentence in REQUIREMENT_SPLIT.split(text or "")
            if sentence.strip(" \t\n\r-•·")
        ]

    def _matching_skills(self, sentence: str) -> Iterable[Skill]:
        for skill in self.skills:
            if any(pattern.search(sentence) for pattern in skill.patterns):
                yield skill

    def extract_profile(self, text: str) -> dict[str, dict]:
        """Extract skills from resume text and keep concise evidence."""
        found: dict[str, dict] = {}
        for sentence in self._sentences(text):
            for skill in self._matching_skills(sentence):
                entry = found.setdefault(
                    skill.key,
                    {
                        "key": skill.key,
                        "name": skill.name,
                        "category": skill.category,
                        "technical": skill.technical,
                        "count": 0,
                        "evidence": [],
                    },
                )
                entry["count"] += 1
                evidence = sentence[:180]
                if evidence not in entry["evidence"] and len(entry["evidence"]) < 2:
                    entry["evidence"].append(evidence)
        return found

    def extract_job(self, job: dict) -> dict:
        """Extract required, preferred, and contextual skills from one JD."""
        results: dict[str, dict] = {}
        priority = {"context": 1, "preferred": 2, "required": 3}

        def add(skill: Skill, importance: str, sentence: str):
            current = results.get(skill.key)
            if current is None or priority[importance] > priority[current["importance"]]:
                results[skill.key] = {
                    "key": skill.key,
                    "name": skill.name,
                    "category": skill.category,
                    "technical": skill.technical,
                    "importance": importance,
                    "evidence": [],
                }
            evidence = sentence[:180]
            if evidence not in results[skill.key]["evidence"] and len(
                results[skill.key]["evidence"]
            ) < 2:
                results[skill.key]["evidence"].append(evidence)

        for sentence in self._sentences(job.get("responsibilities", "")):
            for skill in self._matching_skills(sentence):
                add(skill, "context", sentence)

        for sentence in self._sentences(job.get("requirements", "")):
            importance = (
                "preferred"
                if any(marker in sentence for marker in PREFERRED_MARKERS)
                else "required"
            )
            for skill in self._matching_skills(sentence):
                add(skill, importance, sentence)

        for sentence in self._sentences(job.get("preferred_qualifications", "")):
            for skill in self._matching_skills(sentence):
                add(skill, "preferred", sentence)

        return results

    def core_readiness(self, family: str, profile_keys: set[str]) -> dict:
        family_config = self.families[family]
        groups = []
        for group in family_config["core_groups"]:
            matched = [key for key in group["any"] if key in profile_keys]
            groups.append(
                {
                    "name": group["name"],
                    "met": bool(matched),
                    "matched_skills": [
                        self.by_key[key].name for key in matched if key in self.by_key
                    ],
                }
            )
        coverage = sum(group["met"] for group in groups) / len(groups)
        return {"coverage": coverage, "groups": groups}

    def rule_role_prediction(self, text: str) -> dict | None:
        """Fallback for newly added roles that do not yet have enough training data."""
        specialized = [
            "data_analysis",
            "data_engineering",
            "test_development",
            "cloud_native_sre",
        ]
        ranked = []
        for family in specialized:
            matches = []
            for pattern in self.role_patterns.get(family, ()):
                match = pattern.search(text or "")
                if match:
                    matches.append(match.group(0))
            ranked.append((len(matches), family, sorted(set(matches))))
        count, family, matches = max(ranked, key=lambda item: item[0])
        if count < 2:
            return None
        return {
            "role_family": family,
            "confidence": round(min(0.92, 0.55 + 0.1 * count), 4),
            "matched_terms": matches,
            "decision_method": "specialized_role_rules",
        }

