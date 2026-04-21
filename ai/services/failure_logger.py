"""Structured error logger + retraining-loop bucket.

Writes one JSON line per failed/low-confidence job to
`<storage>/failures/failures.jsonl`, and copies the input images into
`<storage>/failures/<bucket>/<job_id>/` for later inspection, hard-negative
mining and (optionally) retraining.

Buckets correspond to `ErrorCode` values so we can aggregate "what is our
model currently failing at" with a simple `jq` over the jsonl.

All operations are best-effort: we never let logging raise and break the
job pipeline.
"""
from __future__ import annotations

import json
import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

import cv2
import numpy as np

from backend.config import settings
from backend.models.job import Job, ErrorCode


def _failures_root() -> Path:
    root = settings.storage_path / "failures"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _jsonl_path() -> Path:
    return _failures_root() / "failures.jsonl"


def _bucket_dir(error_code: str, job_id: str) -> Path:
    d = _failures_root() / error_code / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_copy(src: Optional[str], dst: Path) -> Optional[str]:
    if not src:
        return None
    try:
        p = Path(src)
        if not p.exists():
            return None
        shutil.copy2(p, dst)
        return str(dst)
    except Exception:
        return None


def _safe_write_image(img: Optional[np.ndarray], dst: Path) -> Optional[str]:
    if img is None:
        return None
    try:
        cv2.imwrite(str(dst), img)
        return str(dst)
    except Exception:
        return None


def log_failure(
    job: Job,
    *,
    error_code: ErrorCode | str,
    message: str,
    stage: str,
    person_image: Optional[np.ndarray] = None,
    garment_image: Optional[np.ndarray] = None,
    extra: Optional[dict] = None,
) -> None:
    """Append a structured failure record and snapshot inputs for retraining.

    Args:
        job: The `Job` that failed.
        error_code: ErrorCode (enum or its string value).
        message: Human-readable error message.
        stage: Pipeline stage where failure occurred
            (e.g. ``"preflight"``, ``"preprocess"``, ``"vton"``,
            ``"postcheck"``, ``"storage"``, ``"unknown"``).
        person_image: Loaded person image (BGR uint8). Saved for triage.
        garment_image: Loaded garment image (BGR uint8). Saved for triage.
        extra: Arbitrary JSON-safe extra context (scores, reasons, etc.).
    """
    try:
        code_str = error_code.value if isinstance(error_code, ErrorCode) else str(error_code)
        bucket = _bucket_dir(code_str, job.job_id)

        person_saved = _safe_write_image(person_image, bucket / "person.png")
        if person_saved is None:
            person_saved = _safe_copy(job.user_image_path, bucket / "person_input")
        garment_saved = _safe_write_image(garment_image, bucket / "garment.png")
        if garment_saved is None:
            garment_saved = _safe_copy(job.product_image_path, bucket / "garment_input")

        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "job_id": job.job_id,
            "stage": stage,
            "error_code": code_str,
            "message": message[:2000],
            "product_id": job.product_id,
            "cloth_category": job.cloth_category,
            "retry_count": job.retry_count,
            "user_image_url": job.user_image_url,
            "product_image_url": job.product_image_url,
            "snapshot_person": person_saved,
            "snapshot_garment": garment_saved,
            "extra": extra or {},
        }

        with _jsonl_path().open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception:
        # Absolutely never let logging break the worker.
        traceback.print_exc()


def log_low_confidence(
    job: Job,
    *,
    score: float,
    threshold: float,
    person_image: Optional[np.ndarray] = None,
    garment_image: Optional[np.ndarray] = None,
    result_image: Optional[np.ndarray] = None,
    extra: Optional[dict] = None,
) -> None:
    """Log a DONE job whose quality score is below a review threshold.

    These jobs succeed from the user's perspective but should be surfaced
    to the retraining loop as hard cases.
    """
    try:
        code = "LOW_CONFIDENCE"
        bucket = _bucket_dir(code, job.job_id)
        _safe_write_image(person_image, bucket / "person.png")
        _safe_write_image(garment_image, bucket / "garment.png")
        _safe_write_image(result_image, bucket / "result.png")

        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "job_id": job.job_id,
            "stage": "done_low_confidence",
            "error_code": code,
            "message": f"score {score:.3f} < {threshold:.3f}",
            "product_id": job.product_id,
            "cloth_category": job.cloth_category,
            "score": score,
            "threshold": threshold,
            "extra": extra or {},
        }
        with _jsonl_path().open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception:
        traceback.print_exc()


def summarize(limit: int = 10_000) -> dict:
    """Return a simple histogram over the last N records — handy for
    dashboards and health endpoints."""
    path = _jsonl_path()
    if not path.exists():
        return {"total": 0, "by_error_code": {}, "by_stage": {}}
    counts_err: dict[str, int] = {}
    counts_stage: dict[str, int] = {}
    total = 0
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f.readlines()[-limit:]:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                total += 1
                counts_err[rec.get("error_code", "?")] = (
                    counts_err.get(rec.get("error_code", "?"), 0) + 1
                )
                counts_stage[rec.get("stage", "?")] = (
                    counts_stage.get(rec.get("stage", "?"), 0) + 1
                )
    except Exception:
        traceback.print_exc()
    return {"total": total, "by_error_code": counts_err, "by_stage": counts_stage}
