#!/bin/bash
#SBATCH --job-name=setup_virutal_Env
#SBATCH --output=install-%j.out
#SBATCH --error=install-%j.err
#SBATCH --partition=24CPUNodes
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8

# loading modules
module load Python/3.12.2

echo "Creating env"
python -m venv /projects/iris/hhamdoud/venv
source /projects/iris/hhamdoud/venv/bin/activate

echo "Installing Env Packages"
pip install --upgrade pip

pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install --target=/projects/iris/hhamdoud/venv/lib/python3.9/site-packages -r _requirements.txt
echo "Finshed Setting up Env"