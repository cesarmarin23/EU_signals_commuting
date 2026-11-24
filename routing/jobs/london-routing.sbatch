#!/bin/bash
#SBATCH --job-name=london-routing
#SBATCH --account=project_2010423
#SBATCH --partition=small
#SBATCH --time=06:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --output=/scratch/project_2010423/carbon-advantage/logs/%x-%j.out

# Steps 2-8 of routing/london_routing.ipynb: routing points, England street network, the four street
# modes, BODS + gb-transit timetables, the transit network and the summaries. Executes the notebook
# in place. First run: LOCO_SMOKE=1 routes only the strongest pairs (network builds + a timing check).
# Submit from roihu-cpu.csc.fi, from ~/locomizer_signals:  sbatch routing/jobs/london-routing.sbatch
set -euo pipefail
module load python-geo
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export CAFEIN_SAMPLEDATA_DIR=/scratch/project_2010423/cafein-sampledata
export LOCO_RUN_FLOWS=0 LOCO_RUN_ROUTING=1 LOCO_SMOKE="${LOCO_SMOKE:-1}"
cd ~/locomizer_signals/routing
jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=-1 --allow-errors london_routing.ipynb
