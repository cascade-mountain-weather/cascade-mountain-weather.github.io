# !/bin/bash
echo "Make sure you run this within the scripts/ directory of the repository."

# check if user wants to use the DGZefficiency conda environment
echo "Using DGZefficiency conda environment for forecast evaluation."
# ask if this should be changed and get user input with y/n prompt
read -p "Do you want to change? (y/n): " choice
if [[ "$choice" != "n" ]]; then
    # allow user to add input their conda environment name
    read -p "Enter the name of the conda environment you want to use: " env_name
    # activate the user-specified conda environment
    source ~/miniforge3/etc/profile.d/conda.sh
    conda activate $env_name
    # if this exits tell them that source location must be change in the script
    if [ $? -ne 0 ]; then
        echo "Failed to activate conda environment. Please check the source location in the script."
        echo "Simply activate your environment manually and re-run the script."
        exit 1
    fi
else
    echo "Continuing with DGZefficiency conda environment."
    # activate conda environment
    source ~/miniforge3/etc/profile.d/conda.sh
    conda activate DGZefficiency
fi

# run the forecast evaluation script
# fill in with first two arsguments: snow level min and max (in feet)
arg1=$1
arg2=$2
echo "Running forecast evaluation script..."
python build_fx_evaluation.py $arg1 $arg2

# update the website
echo "Updating evaluation page..."
python populate_evaluation_html.py