#!/usr/bin/env python3
"""
Experiment 02: TPS Only
Tests the pipeline using the new TPS warp module but without diffusion refinement.
This isolates the contribution of the TPS warping geometry.
"""
import asyncio
from runner import ExperimentRunner, scan_and_run

async def main():
    print("Starting Experiment 02: TPS Only")
    runner = ExperimentRunner(
        experiment_id="exp_02_tps_only",
        warp_mode="tps",
        refinement_mode="none",
        max_retries=0
    )
    await scan_and_run(runner)
    print("Experiment completed.")

if __name__ == "__main__":
    asyncio.run(main())
