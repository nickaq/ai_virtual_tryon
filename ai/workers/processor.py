"""Job processor — IDM-VTON pipeline.

Simplified pipeline:
  Step 1: Load & validate images
  Step 2: Preprocess person (DensePose + human parsing + agnostic mask)
  Step 3: Run IDM-VTON inference
  Step 4: Post-check (face identity, artifacts, background)
  Step 5: Save result
"""
import asyncio
import functools
import os
import traceback
import cv2
import numpy as np
from PIL import Image
from typing import Optional, List, Tuple

from .job_queue import job_queue
from backend.models.job import Job, JobStatus, ErrorCode
from ai.services import image_loader, storage
from ai.services.preprocessing import preprocess_person, PreprocessingError
from ai.services.vton_inference import try_on, VTONInferenceError, VTON_WIDTH, VTON_HEIGHT
from ai.services.postcheck import run_postchecks
from ai.services.compositing import seam_blend
from ai.services.garment_score import garment_preservation_score
from ai.services.preflight import run_preflight
from ai.services.sr_garment import enhance_garment_region, VTON_GARMENT_SR
from ai.services import failure_logger


# ── Reranking / fallback config ───────────────────────────────────────
# Number of diffusion samples generated per job; best one wins.
VTON_NUM_SAMPLES = int(os.environ.get("VTON_NUM_SAMPLES", "1"))
# Composite score below which we run a single fallback attempt.
VTON_MIN_SCORE = float(os.environ.get("VTON_MIN_SCORE", "0.55"))
# Seam blending parameters.
VTON_SEAM_FEATHER_PX = int(os.environ.get("VTON_SEAM_FEATHER_PX", "11"))
VTON_SEAM_ERODE_PX = int(os.environ.get("VTON_SEAM_ERODE_PX", "2"))
# Weight of garment-preservation score inside the composite rank score.
VTON_GARMENT_WEIGHT = float(os.environ.get("VTON_GARMENT_WEIGHT", "0.5"))


async def _generate_and_score(
    *,
    person_pil: Image.Image,
    garment_pil: Image.Image,
    densepose_image: Image.Image,
    agnostic_mask: Image.Image,
    category: str,
    person_image_np: np.ndarray,
    garment_image_np: np.ndarray,
    parsing_map: np.ndarray,
    seed: int,
    num_inference_steps: int = 30,
    guidance_scale: float = 2.0,
) -> Tuple[np.ndarray, float, dict]:
    """Run a single VTON sample, seam-blend, and compute a composite score.

    Returns `(result_bgr, composite_score, debug_info)`.
    """
    result_pil = await try_on(
        person_image=person_pil,
        garment_image=garment_pil,
        densepose_image=densepose_image,
        agnostic_mask=agnostic_mask,
        category=category,
        num_inference_steps=num_inference_steps,
        guidance_scale=guidance_scale,
        seed=seed,
    )

    # Result → BGR, same resolution as the original person.
    result_np = cv2.cvtColor(np.array(result_pil), cv2.COLOR_RGB2BGR)
    orig_h, orig_w = person_image_np.shape[:2]
    if result_np.shape[:2] != (orig_h, orig_w):
        result_np = cv2.resize(result_np, (orig_w, orig_h), interpolation=cv2.INTER_LANCZOS4)

    # Seam-blend so face / hair / background stay byte-identical to the original.
    blended = seam_blend(
        original_bgr=person_image_np,
        generated_bgr=result_np,
        agnostic_mask=agnostic_mask,
        feather_px=VTON_SEAM_FEATHER_PX,
        erode_px=VTON_SEAM_ERODE_PX,
        match_colors=True,
    )

    report = run_postchecks(
        original_image=person_image_np,
        result_image=blended,
        parsing_map=parsing_map,
    )
    garment = garment_preservation_score(
        reference_garment=garment_image_np,
        generated_image=blended,
        parsing_map=parsing_map,
        category=category,
    )

    composite = (
        (1.0 - VTON_GARMENT_WEIGHT) * report.overall_score
        + VTON_GARMENT_WEIGHT * garment["score"]
    )
    debug = {
        "seed": seed,
        "guidance_scale": guidance_scale,
        "postcheck": report.to_dict(),
        "garment_score": garment,
        "composite_score": round(composite, 4),
    }
    return blended, composite, debug


async def process_job(job: Job) -> bool:
    """
    Process a single virtual try-on job using IDM-VTON.

    Args:
        job: Job to process

    Returns:
        True if successful, False on error
    """
    try:
        print(f"Processing job {job.job_id}...")
        job.mark_processing()
        await job_queue.update_job(job)

        # ── STEP 1: Load images ──────────────────────────────────────
        print("  Step 1: Loading images...")
        person_image_np, _ = await image_loader.load_and_normalize(
            image_url=job.user_image_url,
            image_path=job.user_image_path,
        )
        garment_image_np, _ = await image_loader.load_and_normalize(
            image_url=job.product_image_url,
            image_path=job.product_image_path,
        )

        # Convert BGR→RGB PIL for VTON pipeline
        person_pil = Image.fromarray(cv2.cvtColor(person_image_np, cv2.COLOR_BGR2RGB))
        garment_pil = Image.fromarray(cv2.cvtColor(garment_image_np, cv2.COLOR_BGR2RGB))

        # ── STEP 1b: Preflight input quality gates ───────────────────
        print("  Step 1b: Running preflight input quality gates...")
        preflight = await asyncio.get_running_loop().run_in_executor(
            None, run_preflight, person_image_np
        )
        print(f"    preflight: {preflight.summary}")
        if not preflight.passed:
            msg = f"Input quality check failed: {preflight.summary}"
            job.mark_failed(preflight.error_code or ErrorCode.INPUT_QUALITY_FAILED, msg)
            await job_queue.update_job(job)
            failure_logger.log_failure(
                job,
                error_code=preflight.error_code or ErrorCode.INPUT_QUALITY_FAILED,
                message=msg,
                stage="preflight",
                person_image=person_image_np,
                garment_image=garment_image_np,
                extra={"preflight": preflight.to_dict()},
            )
            print(f"Job {job.job_id} rejected at preflight: {msg}")
            return False

        # ── STEP 2: Preprocess person ────────────────────────────────
        category = job.cloth_category or "upper_body"
        print(f"  Step 2: Preprocessing person (category={category})...")

        densepose_image, agnostic_mask, parsing_map = await preprocess_person(
            person_pil, category=category
        )

        # ── STEP 3: VTON inference with multi-sample reranking ──────
        n = max(1, VTON_NUM_SAMPLES)
        print(f"  Step 3: Running IDM-VTON inference ({n} sample(s))...")
        base_seeds = [42 + i * 101 for i in range(n)]

        candidates: List[Tuple[np.ndarray, float, dict]] = []
        for i, seed in enumerate(base_seeds):
            print(f"    Sample {i + 1}/{n} (seed={seed})...")
            try:
                cand = await _generate_and_score(
                    person_pil=person_pil,
                    garment_pil=garment_pil,
                    densepose_image=densepose_image,
                    agnostic_mask=agnostic_mask,
                    category=category,
                    person_image_np=person_image_np,
                    garment_image_np=garment_image_np,
                    parsing_map=parsing_map,
                    seed=seed,
                )
            except VTONInferenceError:
                raise
            except Exception as e:
                print(f"      Sample {i + 1} failed: {e}")
                continue
            candidates.append(cand)
            print(
                f"      composite={cand[2]['composite_score']:.3f}"
                f" postcheck={cand[2]['postcheck']['overall_score']:.3f}"
                f" garment={cand[2]['garment_score']['score']:.3f}"
            )

        if not candidates:
            raise VTONInferenceError("All VTON samples failed")

        candidates.sort(key=lambda c: c[1], reverse=True)
        result_np, final_score, best_debug = candidates[0]
        parsing_map_result = parsing_map

        # ── STEP 3b: Low-confidence fallback ─────────────────────────
        if final_score < VTON_MIN_SCORE:
            print(
                f"  Step 3b: best score {final_score:.3f} < {VTON_MIN_SCORE},"
                f" running fallback attempt..."
            )
            try:
                fb = await _generate_and_score(
                    person_pil=person_pil,
                    garment_pil=garment_pil,
                    densepose_image=densepose_image,
                    agnostic_mask=agnostic_mask,
                    category=category,
                    person_image_np=person_image_np,
                    garment_image_np=garment_image_np,
                    parsing_map=parsing_map,
                    seed=base_seeds[0] + 997,
                    num_inference_steps=40,
                    guidance_scale=2.5,
                )
                if fb[1] > final_score:
                    result_np, final_score, best_debug = fb
                    print(f"    fallback improved score → {final_score:.3f}")
                else:
                    print(f"    fallback did not improve (={fb[1]:.3f}), keeping best")
            except Exception as e:
                print(f"    fallback failed: {e}")

        # ── STEP 4: Post-check reporting ─────────────────────────────
        print("  Step 4: Best-sample post-check summary:")
        report_dict = best_debug["postcheck"]
        print(f"    overall={report_dict['overall_score']:.3f} passed={report_dict['passed']}")
        for name, c in report_dict["checks"].items():
            if not c["passed"]:
                print(f"    Warning: {name}: {c['reason']}")

        # ── STEP 4b: Garment-only super-resolution (optional) ────────
        if VTON_GARMENT_SR:
            print("  Step 4b: Enhancing garment region (SR)...")
            try:
                result_np = await asyncio.get_running_loop().run_in_executor(
                    None,
                    functools.partial(
                        enhance_garment_region,
                        result_np,
                        parsing_map_result,
                        np.array(agnostic_mask),
                        category,
                    ),
                )
            except Exception as e:
                print(f"    garment SR failed: {e}; using un-enhanced result")

        # ── STEP 5: Save result ──────────────────────────────────────
        print("  Step 5: Saving result...")
        result_url = storage.save_result(job.job_id, result_np)

        # Save debug artifacts
        debug_artifacts = {}
        try:
            quality_report = {
                **best_debug["postcheck"],
                "garment_score": best_debug["garment_score"],
                "composite_score": best_debug["composite_score"],
                "selected_seed": best_debug["seed"],
                "num_samples": n,
            }
            debug_artifacts = storage.save_debug_artifacts(
                job_id=job.job_id,
                person_mask=np.array(agnostic_mask),
                torso_mask=None,
                garment_mask=None,
                draft_composite=result_np,
                keypoints={},
                quality_report=quality_report,
            )
        except Exception as e:
            print(f"  Warning: Could not save debug artifacts: {e}")

        job.debug_artifacts = debug_artifacts

        # ── Done ─────────────────────────────────────────────────────
        job.mark_done(result_url, final_score)
        await job_queue.update_job(job)
        print(f"Job {job.job_id} completed successfully! Score: {final_score:.3f}")

        # Low-confidence bucket for retraining loop (§9).
        if final_score < VTON_MIN_SCORE:
            failure_logger.log_low_confidence(
                job,
                score=final_score,
                threshold=VTON_MIN_SCORE,
                person_image=person_image_np,
                garment_image=garment_image_np,
                result_image=result_np,
                extra={
                    "postcheck": best_debug["postcheck"],
                    "garment_score": best_debug["garment_score"],
                },
            )
        return True

    except image_loader.ImageLoadError as e:
        job.mark_failed(e.error_code, e.message)
        await job_queue.update_job(job)
        failure_logger.log_failure(
            job, error_code=e.error_code, message=e.message, stage="load"
        )
        print(f"Job {job.job_id} failed: {e.message}")
        return False

    except PreprocessingError as e:
        job.mark_failed(e.error_code, e.message)
        await job_queue.update_job(job)
        failure_logger.log_failure(
            job,
            error_code=e.error_code,
            message=e.message,
            stage="preprocess",
            person_image=locals().get("person_image_np"),
            garment_image=locals().get("garment_image_np"),
        )
        print(f"Job {job.job_id} failed: {e.message}")
        return False

    except VTONInferenceError as e:
        job.mark_failed(e.error_code, e.message)
        await job_queue.update_job(job)
        failure_logger.log_failure(
            job,
            error_code=e.error_code,
            message=e.message,
            stage="vton",
            person_image=locals().get("person_image_np"),
            garment_image=locals().get("garment_image_np"),
        )
        print(f"Job {job.job_id} failed: {e.message}")
        return False

    except storage.StorageError as e:
        job.mark_failed(e.error_code, e.message)
        await job_queue.update_job(job)
        failure_logger.log_failure(
            job, error_code=e.error_code, message=e.message, stage="storage"
        )
        print(f"Job {job.job_id} failed: {e.message}")
        return False

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}\n{traceback.format_exc()}"
        job.mark_failed(ErrorCode.UNKNOWN_ERROR, error_msg)
        await job_queue.update_job(job)
        failure_logger.log_failure(
            job,
            error_code=ErrorCode.UNKNOWN_ERROR,
            message=error_msg,
            stage="unknown",
            person_image=locals().get("person_image_np"),
            garment_image=locals().get("garment_image_np"),
        )
        print(f"Job {job.job_id} failed unexpectedly: {error_msg}")
        return False


async def worker_loop():
    """Background worker that continuously processes jobs from the queue."""
    print("Worker started, waiting for jobs...")

    while True:
        try:
            job_id = await job_queue.get_next_job()

            if job_id is None:
                await asyncio.sleep(0.1)
                continue

            job = await job_queue.get_job(job_id)

            if job is None:
                print(f"Warning: Job {job_id} not found in queue")
                continue

            await process_job(job)

        except Exception as e:
            print(f"Worker error: {e}\n{traceback.format_exc()}")
            await asyncio.sleep(1)


def start_worker():
    """Start the background worker as an asyncio task."""
    asyncio.create_task(worker_loop())
