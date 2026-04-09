#!/usr/bin/env python3
"""
Experiment 03: TPS + Diffusion
Tests the full pipeline using TPS warping and Stable Diffusion refinement.
This represents the proposed diploma architecture.
"""
import asyncio
from runner import ExperimentRunner, scan_and_run

async def main():
    print("Starting Experiment 03: TPS + Diffusion")
    runner = ExperimentRunner(
        experiment_id="exp_03_tps_plus_diffusion",
        warp_mode="tps",
        refinement_mode="img2img",  # or inpainting depending on settings
        max_retries=2
    )
    await scan_and_run(runner)
    print("Experiment completed.")

if __name__ == "__main__":
    asyncio.run(main())
