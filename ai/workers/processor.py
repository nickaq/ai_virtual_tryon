"""Background job processor."""
import asyncio
import traceback
from typing import Optional

from .job_queue import job_queue
from backend.models.job import Job, JobStatus, ErrorCode
from ai.services import image_loader, segmentation, pose_detector, garment_prep, alignment, quality_control, diffusion, storage


async def process_job(job: Job) -> bool:
    """
    Process a single try-on job through the complete pipeline.
    
    Args:
        job: Job to process
        
    Returns:
        True if successful, False if failed
    """
    try:
        print(f"Processing job {job.job_id}...")
        
        # Update status to processing
        job.mark_processing()
        await job_queue.update_job(job)
        
        # STEP 1 — VALIDATION
        print(f"  STEP 1: Validation & Loading...")
        person_image, _ = await image_loader.load_and_normalize(
            image_url=job.user_image_url,
            image_path=job.user_image_path
        )
        garment_image, _ = await image_loader.load_and_normalize(
            image_url=job.product_image_url,
            image_path=job.product_image_path
        )
        
        # STEP 2 — HUMAN ANALYSIS
        print(f"  STEP 2: Human Analysis (Pose Detection)...")
        # Use pose_hint if available (mock check). Fallback to standard.
        person_keypoints = pose_detector.detect_pose(person_image, person_mask=None)
        
        # STEP 3 — SEGMENTATION
        print(f"  STEP 3: Segmentation...")
        masks = segmentation.segment_person(person_image, person_keypoints)
        person_mask = masks['person']
        torso_mask = masks['torso']
        arms_mask = masks['arms']
        
        # Re-detect pose with person mask as fallback if poorly found initially
        if len(person_keypoints) < 2:
            person_keypoints = pose_detector.detect_pose(person_image, person_mask)
            
        # STEP 4 — CLOTHING PROCESSING
        print(f"  STEP 4: Clothing Processing...")
        garment_rgba, garment_mask, garment_anchors = garment_prep.prepare_garment(
            garment_image,
            garment_type=job.cloth_category
        )
        
        # STEP 5 & 6 — GEOMETRIC ALIGNMENT & OCCLUSION HANDLING
        print(f"  STEP 5 & 6: Geometric Alignment & Occlusion Handling...")
        draft_composite, transformed_garment_mask, transform_params = alignment.align_and_composite(
            person_image=person_image,
            person_keypoints=person_keypoints,
            garment_image=garment_rgba,
            garment_mask=garment_mask,
            garment_anchors=garment_anchors,
            torso_mask=torso_mask,
            arms_mask=arms_mask
        )
        
        geometric_score, _ = quality_control.quality_control(
            garment_anchors=garment_anchors,
            person_keypoints=person_keypoints,
            garment_mask=transformed_garment_mask,
            person_mask=person_mask,
            transform_params=transform_params
        )
        
        # STEP 7 — COMPOSITING
        print(f"  STEP 7: Compositing coarse tryon image...")
        coarse_tryon_image = draft_composite
        final_result = coarse_tryon_image
        final_score = geometric_score
        
        if job.generation_mode == "fast":
            print(f"  Generation mode is 'fast'. Skipping diffusion...")
        else:
            # STEP 8 & 9 — DIFFUSION REFINEMENT & QUALITY EVALUATION
            print(f"  STEP 8: Diffusion Refinement & STEP 9: Quality Evaluation...")
            attempts = 0
            quality_passed = False
            
            while attempts <= job.max_retries and not quality_passed:
                attempts += 1
                try:
                    # Dynamically adjust realism level/strength parameters on retry
                    current_realism = min(5, job.realism_level + (attempts - 1))
                    print(f"    Attempt {attempts}: Calling Local Diffusion (realism={current_realism})...")
                    
                    candidate_result = await diffusion.refine_image_with_diffusion(
                        person_image=person_image,
                        garment_image=garment_image,
                        draft_composite=coarse_tryon_image,
                        preserve_face=job.preserve_face,
                        preserve_background=job.preserve_background,
                        realism_level=current_realism,
                        garment_type=job.cloth_category
                    )
                    
                    # Evaluate result
                    score, passed = quality_control.evaluate_final_result(
                        original_image=person_image,
                        final_image=candidate_result,
                        person_mask=person_mask,
                        geometric_score=geometric_score
                    )
                    
                    print(f"    Quality Evaluation Score: {score:.3f} (Passed: {passed})")
                    final_result = candidate_result
                    final_score = score
                    
                    if passed:
                        quality_passed = True
                    else:
                        print(f"    Quality check failed. Retrying if limits allow...")
                        
                except diffusion.DiffusionAPIError as e:
                    print(f"    Attempt {attempts} failed: {e.message}")
                    if attempts > job.max_retries:
                        print("    Max retries reached, falling back to coarse composite.")
        
        # STEP 10 — STORAGE
        print(f"  STEP 10: Saving final image to storage...")
        result_url = storage.save_result(job.job_id, final_result)
        
        debug_artifacts = storage.save_debug_artifacts(
            job_id=job.job_id,
            person_mask=person_mask,
            torso_mask=torso_mask,
            garment_mask=transformed_garment_mask,
            draft_composite=coarse_tryon_image,
            keypoints=person_keypoints
        )
        job.debug_artifacts = debug_artifacts
        
        # STEP 11 — RESPONSE
        print(f"  STEP 11: Finalizing response status...")
        job.mark_done(result_url, final_score)
        await job_queue.update_job(job)
        
        print(f"Job {job.job_id} completed successfully!")
        return True
        
    except image_loader.ImageLoadError as e:
        job.mark_failed(e.error_code, e.message)
        await job_queue.update_job(job)
        print(f"Job {job.job_id} failed: {e.message}")
        return False
        
    except segmentation.SegmentationError as e:
        job.mark_failed(e.error_code, e.message)
        await job_queue.update_job(job)
        print(f"Job {job.job_id} failed: {e.message}")
        return False
        
    except pose_detector.PoseDetectionError as e:
        job.mark_failed(e.error_code, e.message)
        await job_queue.update_job(job)
        print(f"Job {job.job_id} failed: {e.message}")
        return False
        
    except garment_prep.GarmentPrepError as e:
        job.mark_failed(e.error_code, e.message)
        await job_queue.update_job(job)
        print(f"Job {job.job_id} failed: {e.message}")
        return False
        
    except alignment.AlignmentError as e:
        job.mark_failed(e.error_code, e.message)
        await job_queue.update_job(job)
        print(f"Job {job.job_id} failed: {e.message}")
        return False
        
    except quality_control.QualityCheckError as e:
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
        # Catch-all for unexpected errors
        error_msg = f"Unexpected error: {str(e)}\n{traceback.format_exc()}"
        job.mark_failed(ErrorCode.UNKNOWN_ERROR, error_msg)
        await job_queue.update_job(job)
        print(f"Job {job.job_id} failed with unexpected error: {error_msg}")
        return False


async def worker_loop():
    """
    Background worker that continuously processes jobs from the queue.
    """
    print("Worker started, waiting for jobs...")
    
    while True:
        try:
            # Get next job from queue
            job_id = await job_queue.get_next_job()
            
            if job_id is None:
                # No jobs, wait a bit
                await asyncio.sleep(0.1)
                continue
            
            # Get job data
            job = await job_queue.get_job(job_id)
            
            if job is None:
                print(f"Warning: Job {job_id} not found in storage")
                continue
            
            # Process the job
            await process_job(job)
            
        except Exception as e:
            print(f"Worker error: {e}\n{traceback.format_exc()}")
            await asyncio.sleep(1)


def start_worker():
    """Start the background worker in a new task."""
    asyncio.create_task(worker_loop())
