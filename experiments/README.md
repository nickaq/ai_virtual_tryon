# AI Virtual Try-On — Diploma Experiments

This directory contains the experimental suite used for the Ablation Study in the diploma thesis. These scripts process test image pairs through the pipeline under different configurations to demonstrate the impact of individual architectural contributions (like TPS warping and Diffusion).

## Directory Structure

- `data/` — Put your test image pairs here. Name them `exp_user_01.jpg` and `exp_product_01.jpg` (or any sequence that groups them alphabetically).
- `results/` — Generated automatically. Contains output images and a `metrics.csv` table for each experiment.
- `runner.py` — The core framework that parses images and executes the pipeline locally.

## Experiments

Run these tests sequentially from the root of the project using python:

### 1. Affine Baseline
Shows the limitations of standard global transformations.
```bash
python experiments/exp_01_affine_baseline.py
```

### 2. TPS Only
Isolates the contribution of the proprietary Thin-Plate Spline module. Highlights non-linear body wrapping without generative artifacts.
```bash
python experiments/exp_02_tps_only.py
```

### 3. TPS + Diffusion (Proposed Architecture)
The full pipeline. TPS provides geometric structural integrity, while local diffusion refines the texture and lighting.
```bash
python experiments/exp_03_tps_plus_diffusion.py
```

### 4. Quality Gate Ablation
Forces edge cases through the pipeline to demonstrate the rejection rate of poor alignments (score < 0.70).
```bash
python experiments/exp_04_quality_gate_ablation.py
```

## Metrics Collection

After running the experiments, check `experiments/results/exp_.../metrics.csv`.
The table will contain the following data for your thesis:

| job_id | status | geometric_score | overall_score | passed | neckline_score | shoulder_score | overlap_score | scale_score | retry_recommended | error_msg |
|--------|--------|-----------------|---------------|--------|----------------|----------------|---------------|-------------|-------------------|-----------|
| ...    | ...    | ...             | ...           | ...    | ...            | ...            | ...           | ...         | ...               | ...       |

You can copy this directly into Excel/Google Sheets to generate your diploma charts.
