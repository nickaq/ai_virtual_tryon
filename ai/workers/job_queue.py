"""In-memory job queue management."""
import asyncio
from typing import Dict, Optional
from datetime import datetime

from backend.models.job import Job, JobStatus


class JobQueue:
    """Thread-safe in-memory job queue."""
    
    def __init__(self):
        self.jobs: Dict[str, Job] = {}
        self.queue: asyncio.Queue = asyncio.Queue()
        self.lock = asyncio.Lock()
    
    async def submit_job(self, job: Job) -> str:
        """
        Submit a new job to the queue.
        
        Args:
            job: Job to submit
            
        Returns:
            Job ID
        """
        async with self.lock:
            self.jobs[job.job_id] = job
            await self.queue.put(job.job_id)
        
        return job.job_id
    
    async def get_next_job(self) -> Optional[str]:
        """
        Get next job ID from queue.
        
        Returns:
            Job ID or None if queue is empty
        """
        try:
            job_id = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            return job_id
        except asyncio.TimeoutError:
            return None
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get job by ID.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job or None if not found
        """
        async with self.lock:
            return self.jobs.get(job_id)
    
    async def update_job(self, job: Job):
        """
        Update job in storage.
        
        Args:
            job: Updated job
        """
        async with self.lock:
            job.updated_at = datetime.utcnow()
            self.jobs[job.job_id] = job
    
    async def requeue_job(self, job_id: str):
        """
        Requeue a job (for retries).
        
        Args:
            job_id: Job identifier
        """
        await self.queue.put(job_id)
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get queue statistics.
        
        Returns:
            Dictionary with queue stats
        """
        stats = {
            'total': len(self.jobs),
            'queued': 0,
            'processing': 0,
            'done': 0,
            'failed': 0
        }
        
        for job in self.jobs.values():
            if job.status == JobStatus.QUEUED:
                stats['queued'] += 1
            elif job.status == JobStatus.PROCESSING:
                stats['processing'] += 1
            elif job.status == JobStatus.DONE:
                stats['done'] += 1
            elif job.status == JobStatus.FAILED:
                stats['failed'] += 1
        
        return stats


# Global job queue instance
job_queue = JobQueue()
