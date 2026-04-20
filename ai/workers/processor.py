"""Job processor — IDM-VTON pipeline.

Simplified pipeline:
  Step 1: Load & validate images
  Step 2: Preprocess person (DensePose + human parsing + agnostic mask)
  Step 3: Run IDM-VTON inference
  Step 4: Post-check (face identity, artifacts, background)
  Step 5: Save result
"""
import asyncio
import traceback
import cv2
import numpy as np
from PIL import Image
from typing import Optional

from .job_queue import job_queue
from backend.models.job import Job, JobStatus, ErrorCode
from ai.services import image_loader, storage
from ai.services.preprocessing import preprocess_person, PreprocessingError
from ai.services.vton_inference import try_on, VTONInferenceError, VTON_WIDTH, VTON_HEIGHT
from ai.services.postcheck import run_postchecks


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

        # ── STEP 2: Preprocess person ────────────────────────────────
        category = job.cloth_category or "upper_body"
        print(f"  Step 2: Preprocessing person (category={category})...")

        densepose_image, agnostic_mask, parsing_map = await preprocess_person(
            person_pil, category=category
        )

        # ── STEP 3: VTON inference ───────────────────────────────────
        print(f"  Step 3: Running IDM-VTON inference...")
        result_pil = await try_on(
            person_image=person_pil,
            garment_image=garment_pil,
            densepose_image=densepose_image,
            agnostic_mask=agnostic_mask,
            category=category,
            num_inference_steps=30,
            guidance_scale=2.0,
            seed=42,
        )

        # Convert result back to BGR numpy
        result_np = cv2.cvtColor(np.array(result_pil), cv2.COLOR_RGB2BGR)

        # Resize result back to original person image dimensions
        orig_h, orig_w = person_image_np.shape[:2]
        if result_np.shape[:2] != (orig_h, orig_w):
            result_np = cv2.resize(result_np, (orig_w, orig_h), interpolation=cv2.INTER_LANCZOS4)

        # ── STEP 4: Post-check ───────────────────────────────────────
        print("  Step 4: Running post-checks...")
        report = run_postchecks(
            original_image=person_image_np,
            result_image=result_np,
            parsing_map=parsing_map,
        )
        print(f"  Post-check score: {report.overall_score:.3f} (passed={report.passed})")
        if report.failure_reasons:
            for reason in report.failure_reasons:
                print(f"    Warning: {reason}")

        final_score = report.overall_score

        # ── STEP 5: Save result ──────────────────────────────────────
        print("  Step 5: Saving result...")
        result_url = storage.save_result(job.job_id, result_np)

        # Save debug artifacts
        debug_artifacts = {}
        try:
            debug_artifacts = storage.save_debug_artifacts(
                job_id=job.job_id,
                person_mask=np.array(agnostic_mask),
                torso_mask=None,
                garment_mask=None,
                draft_composite=result_np,
                keypoints={},
                quality_report=report.to_dict(),
            )
        except Exception as e:
            print(f"  Warning: Could not save debug artifacts: {e}")

        job.debug_artifacts = debug_artifacts

        # ── Done ─────────────────────────────────────────────────────
        job.mark_done(result_url, final_score)
        await job_queue.update_job(job)
        print(f"Job {job.job_id} completed successfully! Score: {final_score:.3f}")
        return True

    except image_loader.ImageLoadError as e:
        job.mark_failed(e.error_code, e.message)
        await job_queue.update_job(job)
        print(f"Job {job.job_id} failed: {e.message}")
        return False

    except PreprocessingError as e:
        job.mark_failed(e.error_code, e.message)
        await job_queue.update_job(job)
        print(f"Job {job.job_id} failed: {e.message}")
        return False

    except VTONInferenceError as e:
        job.mark_failed(e.error_code, e.message)
        await job_queue.update_job(job)
        print(f"Job {job.job_id} failed: {e.message}")
        return False

    except storage.StorageError as e:
        job.mark_failed(e.error_code, e.message)
        await job_queue.update_job(job)
        print(f"Job {job.job_id} failed: {e.message}")
        return False

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}\n{traceback.format_exc()}"
        job.mark_failed(ErrorCode.UNKNOWN_ERROR, error_msg)
        await job_queue.update_job(job)
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
