$ErrorActionPreference = "Stop"

$needsPrepare = -not (Test-Path "data/jobs_clean.jsonl")
if (-not $needsPrepare -and (Test-Path "data/jobs_raw.jsonl")) {
    $needsPrepare = (Get-Item "data/jobs_raw.jsonl").LastWriteTime -gt (Get-Item "data/jobs_clean.jsonl").LastWriteTime
}
if ($needsPrepare) {
    python scripts/prepare_data.py
}

$needsTrain = -not (Test-Path "models/role_classifier.joblib")
if (-not $needsTrain) {
    $needsTrain = (Get-Item "data/jobs_clean.jsonl").LastWriteTime -gt (Get-Item "models/role_classifier.joblib").LastWriteTime
}
if ($needsTrain) {
    python scripts/train_model.py
}

python app.py

