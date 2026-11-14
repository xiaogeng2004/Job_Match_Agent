import unittest
from io import BytesIO
from pathlib import Path
from collections import Counter

import app as app_module
from agent.core import JobMatchAgent
from agent.matcher import JobMatcher


app = app_module.app

RESUME = """
计算机科学与技术专业，熟悉 Python、SQL、pandas、scikit-learn、Flask、Linux 和 Git。
项目中使用逻辑回归完成用户流失预测，并负责数据清洗、特征工程和模型评估。
使用 Flask 开发过 REST API。
"""


def make_text_pdf(text: str) -> bytes:
    """Create a minimal single-page PDF for the PDF upload test."""
    safe_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({safe_text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"\nendstream"
        ),
    ]
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, payload in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(payload)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


class AgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agent = JobMatchAgent()

    def test_skill_extraction(self):
        profile = self.agent.skill_extractor.extract_profile(RESUME)
        self.assertIn("python", profile)
        self.assertIn("sql_database", profile)
        self.assertIn("machine_learning", profile)
        self.assertIn("backend_api", profile)
        self.assertTrue(profile["python"]["evidence"])

    def test_frontend_and_data_terms_do_not_trigger_algorithm_or_backend(self):
        frontend = self.agent.skill_extractor.extract_profile(
            "使用 React 和 TypeScript 开发前端页面，并调用 REST API。"
        )
        self.assertNotIn("backend_api", frontend)
        analysis = self.agent.skill_extractor.extract_profile(
            "负责搜索广告业务的数据分析和报表。"
        )
        self.assertNotIn("nlp_cv", analysis)

    def test_analysis_returns_ranked_jobs(self):
        result = self.agent.analyze(
            RESUME,
            role_families=["backend", "algorithm"],
            top_n=5,
        )
        self.assertEqual(len(result["jobs"]), 5)
        self.assertEqual(
            {job["role_family"] for job in result["jobs"]},
            {"backend", "algorithm"},
        )
        scores = [job["score"] for job in result["jobs"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_short_resume_is_rejected(self):
        with self.assertRaises(ValueError):
            self.agent.analyze("Python", role_families=["algorithm"])

    def test_custom_jd_analysis(self):
        jd = "负责后端服务开发，要求熟悉 Java、Spring、MySQL 和 Linux。"
        result = self.agent.analyze(
            RESUME,
            role_families=["backend", "algorithm"],
            custom_jd_text=jd,
        )
        self.assertEqual(result["custom_jd"]["prediction"]["role_family"], "backend")

    def test_new_role_rule_fallback(self):
        jd = "负责数据仓库和 ETL 开发，使用 Spark、Flink 和 Hive 构建离线与实时数仓。"
        result = self.agent.analyze(
            RESUME,
            role_families=["data_engineering"],
            custom_jd_text=jd,
        )
        self.assertEqual(
            result["custom_jd"]["prediction"]["role_family"],
            "data_engineering",
        )
        self.assertEqual(len(result["jobs"]), 10)

    def test_custom_role_can_be_confirmed(self):
        jd = "负责数据平台和指标分析。"
        result = self.agent.analyze(
            RESUME,
            role_families=["data_analysis"],
            custom_jd_text=jd,
            confirmed_custom_role="data_analysis",
        )
        self.assertEqual(
            result["custom_jd"]["prediction"]["decision_method"],
            "user_confirmation",
        )

    def test_filters_and_confirmed_skill(self):
        result = self.agent.analyze(
            RESUME,
            role_families=["data_analysis"],
            employment_types=["实习"],
            max_experience_years=0,
            freshness_window="2y",
            confirmed_skills=["data_visualization"],
        )
        self.assertGreaterEqual(result["job_count"], 1)
        self.assertTrue(result["profile"]["data_visualization"]["confirmed"])
        self.assertTrue(
            all(
                job["employment_type"] == "实习"
                for job in result["jobs"]
            )
        )

    def test_company_diversity_and_feedback_penalty(self):
        result = self.agent.analyze(
            RESUME,
            role_families=["backend", "algorithm"],
            top_n=10,
        )
        companies = Counter(job["company"] for job in result["jobs"])
        self.assertLessEqual(max(companies.values()), 2)

        jobs = self.agent.repository.filter_jobs(
            self.agent.jobs,
            role_families={"backend", "algorithm"},
            freshness_window="2y",
        )
        baseline = JobMatcher(
            self.agent.skill_extractor,
            self.agent.role_classifier,
            jobs,
        ).rank(RESUME, top_n=20)
        target_id = baseline["jobs"][5]["jd_id"]
        baseline_score = baseline["jobs"][5]["score"]
        penalized = JobMatcher(
            self.agent.skill_extractor,
            self.agent.role_classifier,
            jobs,
            negative_feedback_counts={target_id: 2},
        ).rank(RESUME, top_n=20)
        penalized_job = next(
            (job for job in penalized["jobs"] if job["jd_id"] == target_id),
            None,
        )
        self.assertIsNotNone(penalized_job)
        self.assertLess(penalized_job["score"], baseline_score)
        self.assertEqual(penalized_job["negative_feedback_count"], 2)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config.update(TESTING=True)
        cls.client = app.test_client()

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["jobs"], 222)
        self.assertEqual(body["total_jobs"], 307)
        self.assertEqual(len(body["roles"]), 8)
        self.assertGreaterEqual(body["skills"], 40)

    def test_browse_jobs_endpoint(self):
        response = self.client.get(
            "/api/jobs",
            query_string={
                "roles": ["backend", "frontend"],
                "page": 1,
                "page_size": 5,
                "freshness_window": "2y",
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertLessEqual(len(body["jobs"]), 5)
        self.assertGreaterEqual(body["total"], len(body["jobs"]))

    def test_analyze_endpoint(self):
        response = self.client.post(
            "/api/analyze",
            data={
                "resume_text": RESUME,
                "roles": ["backend", "algorithm"],
                "top_n": "3",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()["jobs"]), 3)

    def test_pdf_resume_upload(self):
        pdf_bytes = make_text_pdf(
            "Python SQL pandas Flask Linux Git machine learning REST API"
        )
        response = self.client.post(
            "/api/analyze",
            data={
                "resume_file": (BytesIO(pdf_bytes), "resume.pdf"),
                "roles": ["backend", "algorithm"],
                "top_n": "3",
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("python", response.get_json()["profile"])

    def test_pdf_without_text_is_rejected(self):
        pdf_bytes = make_text_pdf("")
        response = self.client.post(
            "/api/analyze",
            data={
                "resume_file": (BytesIO(pdf_bytes), "scanned.pdf"),
                "roles": ["backend"],
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("扫描件", response.get_json()["error"])

    def test_feedback_endpoint(self):
        original_path = app_module.FEEDBACK_PATH
        test_path = Path(__file__).with_name("feedback_test.jsonl")
        test_path.unlink(missing_ok=True)
        app_module.FEEDBACK_PATH = test_path
        try:
            response = self.client.post(
                "/api/feedback",
                json={
                    "feedback_type": "job_not_relevant",
                    "jd_id": "TEST-JOB",
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(test_path.exists())
            self.assertIn("TEST-JOB", test_path.read_text(encoding="utf-8"))
        finally:
            app_module.FEEDBACK_PATH = original_path
            test_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

