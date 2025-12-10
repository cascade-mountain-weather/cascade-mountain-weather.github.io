# !/bin/bash

# set working directory
cd /c/Users/dlhogan/'OneDrive - UW'/Documents/GitHub/Cascski-Alpine-Insights/cascade-mountain-weather.github.io/scripts/

# activate conda environment
source ~/miniforge3/etc/profile.d/conda.sh
conda activate DGZefficiency

# run the forecast evaluation script
echo "Running forecast evaluation script..."
python build_fx_evaluation.py

# update the website
echo "Updating evaluation page..."
python populate_evaluation_html.py