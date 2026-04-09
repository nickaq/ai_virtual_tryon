#!/usr/bin/env python3
"""
Experiment 04: Quality Gate Ablation
Forces a bad affine alignment (or uses complex images) to demonstrate
how the Quality Gate rejects outputs with a score < 0.70.
"""
import asyncio
from runner import ExperimentRunner, scan_and_run

async def main():
    print("Starting Experiment 04: Quality Gate Ablation")
    # Using affine because it's more likely to fail complex poses, 
    # triggering the Quality Gate retry or failure mechanism.
    runner = ExperimentRunner(
        experiment_id="exp_04_quality_gate_ablation",
        warp_mode="affine",
        refinement_mode="none",
        max_retries=0
    )
    # The runner logs the `passed` and `overall_score` flags to metrics.csv
    await scan_and_run(runner)
    print("Experiment completed. Check metrics.csv to see the rejected jobs.")

if __name__ == "__main__":
    asyncio.run(main())
