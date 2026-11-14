from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import (
    StratifiedGroupKFold,
    StratifiedKFold,
    cross_val_predict,
)
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "jobs_clean.jsonl"
MODEL_PATH = PROJECT_ROOT / "models" / "role_classifier.joblib"
METRICS_PATH = PROJECT_ROOT / "models" / "metrics.json"
MIN_SAMPLES_PER_CLASS = 5
MAX_PER_COMPANY_ROLE = 4


def load_dataset() -> tuple[list[str], list[str], list[str]]:
    texts = []
    labels = []
    groups = []
    with DATA_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            job = json.loads(line)
            if not job.get("is_matchable", True):
                continue
            texts.append(
                "\n".join(
                    [
                        job.get("responsibilities", ""),
                        job.get("requirements", ""),
                        job.get("preferred_qualifications", ""),
                    ]
                )
            )
            labels.append(job["role_family"])
            groups.append(job.get("company", "") or f"source:{job.get('source_name', '')}")
    return texts, labels, groups


def build_pipeline(classifier) -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(2, 5),
                    min_df=1,
                    max_features=30000,
                    sublinear_tf=True,
                ),
            ),
            ("classifier", classifier),
        ]
    )


def balance_training_sample(
    texts: list[str],
    labels: list[str],
    groups: list[str],
) -> tuple[list[str], list[str], list[str]]:
    buckets: dict[tuple[str, str], list[int]] = {}
    for index, (label, group) in enumerate(zip(labels, groups)):
        buckets.setdefault((group, label), []).append(index)
    selected_indices = []
    sampler = random.Random(42)
    for indices in buckets.values():
        selected_indices.extend(
            sampler.sample(indices, min(MAX_PER_COMPANY_ROLE, len(indices)))
        )
    selected_indices.sort()
    return (
        [texts[index] for index in selected_indices],
        [labels[index] for index in selected_indices],
        [groups[index] for index in selected_indices],
    )


def evaluate_model(
    name: str,
    pipeline: Pipeline,
    texts,
    labels,
    class_names,
    groups,
    grouped: bool,
) -> dict:
    if grouped:
        folds = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
        predicted = cross_val_predict(
            pipeline,
            texts,
            labels,
            cv=folds,
            groups=groups,
        )
    else:
        folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        predicted = cross_val_predict(pipeline, texts, labels, cv=folds)
    report = classification_report(
        labels,
        predicted,
        labels=class_names,
        output_dict=True,
        zero_division=0,
    )
    return {
        "model": name,
        "accuracy": round(accuracy_score(labels, predicted), 4),
        "macro_f1": round(
            f1_score(labels, predicted, average="macro", zero_division=0),
            4,
        ),
        "weighted_f1": round(
            f1_score(labels, predicted, average="weighted", zero_division=0),
            4,
        ),
        "classification_report": report,
        "confusion_matrix": confusion_matrix(
            labels,
            predicted,
            labels=class_names,
        ).tolist(),
    }


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    texts, labels, groups = load_dataset()
    original_size = len(texts)
    texts, labels, groups = balance_training_sample(texts, labels, groups)
    counts = Counter(labels)
    class_names = sorted(
        label for label, count in counts.items() if count >= MIN_SAMPLES_PER_CLASS
    )
    excluded = {
        label: count
        for label, count in sorted(counts.items())
        if count < MIN_SAMPLES_PER_CLASS
    }
    filtered = [
        (text, label)
        for text, label in zip(texts, labels)
        if label in class_names
    ]
    texts = [item[0] for item in filtered]
    labels = [item[1] for item in filtered]

    baseline = build_pipeline(MultinomialNB())
    main_model = build_pipeline(
        LogisticRegression(
            max_iter=3000,
            class_weight="balanced",
            random_state=42,
        )
    )

    baseline_metrics = evaluate_model(
        "tfidf_naive_bayes",
        baseline,
        texts,
        labels,
        class_names,
        groups,
        grouped=True,
    )
    main_metrics = evaluate_model(
        "tfidf_logistic_regression",
        main_model,
        texts,
        labels,
        class_names,
        groups,
        grouped=True,
    )
    random_baseline = evaluate_model(
        "tfidf_naive_bayes",
        build_pipeline(MultinomialNB()),
        texts,
        labels,
        class_names,
        groups,
        grouped=False,
    )
    random_main = evaluate_model(
        "tfidf_logistic_regression",
        build_pipeline(
            LogisticRegression(
                max_iter=3000,
                class_weight="balanced",
                random_state=42,
            )
        ),
        texts,
        labels,
        class_names,
        groups,
        grouped=False,
    )
    main_model.fit(texts, labels)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(main_model, MODEL_PATH)

    payload = {
        "dataset_size": len(texts),
        "library_size": original_size,
        "raw_training_size": original_size,
        "max_samples_per_company_role": MAX_PER_COMPANY_ROLE,
        "labels": class_names,
        "excluded_classes": excluded,
        "minimum_samples_per_class": MIN_SAMPLES_PER_CLASS,
        "validation": "grouped 5-fold cross-validation by company",
        "baseline": baseline_metrics,
        "main_model": main_metrics,
        "random_validation_reference": {
            "baseline": random_baseline,
            "main_model": random_main,
        },
    }
    METRICS_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"\nSaved model to {MODEL_PATH}")
    print(f"Saved metrics to {METRICS_PATH}")


if __name__ == "__main__":
    main()
