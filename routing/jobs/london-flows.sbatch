#!/bin/bash
#SBATCH --job-name=london-flows
#SBATCH --account=project_2022768
#SBATCH --partition=small
#SBATCH --time=01:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=384
#SBATCH --mem=700G
#SBATCH --output=/scratch/project_2022768/%u/locomizer/logs/%x-%j.out

# Step 1 of routing/london_routing.ipynb only: the home -> work hexagon pairs of the London panel users
# from the two level-8 user-day tables (38 + 44 GB, about 360 GB of RAM, ~10 min on a full node).
# Writes results/GBR/london_2024-05_2024-06/routing/od_h3_8.parquet and stops before the routing.
# Submit from roihu-cpu.csc.fi, from ~/locomizer_signals:  sbatch routing/jobs/london-flows.sbatch
set -euo pipefail
module load python-geo
export LOCO_RUN_FLOWS=1 LOCO_RUN_ROUTING=0
cd ~/locomizer_signals/routing
jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=-1 \
    --output "/scratch/project_2022768/${USER}/locomizer/logs/london_routing_flows_${SLURM_JOB_ID}.ipynb" london_routing.ipynb
