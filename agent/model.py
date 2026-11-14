from __future__ import annotations

from pathlib import Path

import joblib


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "role_classifier.joblib"


def job_text(job: dict) -> str:
    return "\n".join(
        [
            job.get("responsibilities", ""),
            job.get("requirements", ""),
            job.get("preferred_qualifications", ""),
        ]
    )


class RoleClassifier:
    def __init__(self, model_path: Path | str = DEFAULT_MODEL_PATH):
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Role model not found: {path}. Run `python scripts/train_model.py`."
            )
        self.pipeline = joblib.load(path)

    def predict(self, text: str) -> dict:
        probabilities = self.pipeline.predict_proba([text])[0]
        classes = [
            str(class_name)
            for class_name in self.pipeline.named_steps["classifier"].classes_
        ]
        ranked = sorted(
            zip(classes, probabilities),
            key=lambda item: item[1],
            reverse=True,
        )
        role, confidence = ranked[0]
        return {
            "role_family": role,
            "confidence": round(float(confidence), 4),
            "probabilities": {
                class_name: round(float(probability), 4)
                for class_name, probability in ranked
            },
            "low_confidence": bool(confidence < 0.45),
        }
