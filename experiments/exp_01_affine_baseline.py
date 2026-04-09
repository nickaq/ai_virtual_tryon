#!/usr/bin/env python3
"""
Experiment 01: Affine Baseline
Tests the pipeline using classic affine warp and no diffusion refinement.
"""
import asyncio
from runner import ExperimentRunner, scan_and_run

async def main():
    print("Starting Experiment 01: Affine Baseline")
    runner = ExperimentRunner(
        experiment_id="exp_01_affine_baseline",
        warp_mode="affine",
        refinement_mode="none",
        max_retries=0
    )
    await scan_and_run(runner)
    print("Experiment completed.")

if __name__ == "__main__":
    asyncio.run(main())
