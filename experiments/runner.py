"""
Common runner framework for diploma experiments.
"""
import asyncio
import csv
import json
import uuid
import shutil
from pathlib import Path

# Fix python path for imports
import sys
PROJ_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJ_ROOT))

from backend.models.job import Job, JobStatus
from ai.workers.processor import process_job

EXP_DIR = PROJ_ROOT / "experiments"
RESULTS_DIR = EXP_DIR / "results"
DATA_DIR = EXP_DIR / "data"

# Create standard directories
RESULTS_DIR.mkdir(exist_ok=True, parents=True)
DATA_DIR.mkdir(exist_ok=True, parents=True)


class ExperimentRunner:
    """Runs a batch of image pairs through the AI pipeline in a specific configuration."""
    
    def __init__(self, experiment_id: str, warp_mode: str, refinement_mode: str, max_retries: int = 0):
        self.experiment_id = experiment_id
        self.warp_mode = warp_mode
        self.refinement_mode = refinement_mode
        self.max_retries = max_retries
        
        self.exp_results_dir = RESULTS_DIR / self.experiment_id
        self.exp_results_dir.mkdir(exist_ok=True, parents=True)
        
        self.csv_path = self.exp_results_dir / "metrics.csv"
        self._init_csv()

    def _init_csv(self):
        with open(self.csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'job_id', 'status', 'geometric_score', 'overall_score', 'passed',
                'neckline_score', 'shoulder_score', 'overlap_score', 'scale_score',
                'retry_recommended', 'error_msg'
            ])

    async def run_pair(self, user_img_path: str, product_img_path: str, cloth_category: str = "upper_body"):
        job_id = f"exp_{self.experiment_id}_{uuid.uuid4().hex[:8]}"
        print(f"\n[{self.experiment_id}] Processing pair -> Job: {job_id}")
        
        # Determine if we should skip diffusion (fast mode)
        gen_mode = "fast" if self.refinement_mode == "none" else "quality"
        ref_mode = "img2img" if self.refinement_mode == "none" else self.refinement_mode
        
        job = Job(
            job_id=job_id,
            user_image_path=str(user_img_path),
            product_image_path=str(product_img_path),
            cloth_category=cloth_category,
            generation_mode=gen_mode,
            warp_mode=self.warp_mode,
            refinement_mode=ref_mode,
            max_retries=self.max_retries,
            preserve_face=True,
            preserve_background=True
        )
        
        await process_job(job)
        
        # Save output image nicely to exp directory
        if job.status == JobStatus.DONE:
            result_path = PROJ_ROOT / job.result_image_url.lstrip('/')
            if result_path.exists():
                shutil.copy(result_path, self.exp_results_dir / f"{job_id}_result.png")
                
        self._log_metrics(job)
        return job

    def _log_metrics(self, job: Job):
        metrics = {
            'geometric_score': None,
            'passed': job.status == JobStatus.DONE,
            'overall_score': job.quality_score,
            'neckline_score': None,
            'shoulder_score': None,
            'overlap_score': None,
            'scale_score': None,
            'retry_recommended': False,
            'error_msg': job.error_message
        }
        
        # Read the debug artifact for geometric score
        if job.debug_artifacts and 'quality_report' in job.debug_artifacts:
            qr_path = PROJ_ROOT / job.debug_artifacts['quality_report'].lstrip('/')
            if qr_path.exists():
                with open(qr_path) as f:
                    qr = json.load(f)
                metrics['geometric_score'] = qr.get('overall_score')
                metrics['retry_recommended'] = qr.get('retry_recommended', False)
                
                checks = qr.get('checks', {})
                metrics['neckline_score'] = checks.get('neckline_alignment', {}).get('score')
                metrics['shoulder_score'] = checks.get('shoulder_angle', {}).get('score')
                metrics['overlap_score'] = checks.get('overlap', {}).get('score')
                metrics['scale_score'] = checks.get('scale', {}).get('score')
                
        # Write to CSV
        with open(self.csv_path, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                job.job_id, job.status, metrics['geometric_score'], metrics['overall_score'],
                metrics['passed'], metrics['neckline_score'], metrics['shoulder_score'],
                metrics['overlap_score'], metrics['scale_score'], metrics['retry_recommended'],
                metrics['error_msg']
            ])

async def generate_mock_data():
    """Generates empty files if data/ is empty to prevent crashes during setup testing."""
    if not list(DATA_DIR.glob("*.jpg")) and not list(DATA_DIR.glob("*.png")):
        print("Creating mock test data...")
        import numpy as np
        import cv2
        user = np.ones((512, 512, 3), dtype=np.uint8) * 200
        prod = np.ones((512, 512, 3), dtype=np.uint8) * 100
        cv2.imwrite(str(DATA_DIR / "sample_user.jpg"), user)
        cv2.imwrite(str(DATA_DIR / "sample_product.jpg"), prod)

async def scan_and_run(runner: ExperimentRunner):
    """Scans the data directory for pairs (person_*.jpg, garment_*.jpg) and runs them."""
    await generate_mock_data()
    
    users = sorted(list(DATA_DIR.glob("*user*.jpg")) + list(DATA_DIR.glob("*user*.png")))
    prods = sorted(list(DATA_DIR.glob("*product*.jpg")) + list(DATA_DIR.glob("*product*.png")))
    
    if not users or not prods:
        print("No test pairs found in data directory. Please add test images.")
        return
        
    # Just run the first available pairs (up to min length)
    for u, p in zip(users, prods):
        await runner.run_pair(u, p)
