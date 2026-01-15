#!/bin/bash
# This script sets up the environment and runs the Python bot.

# Get the absolute path to the directory containing this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Define the path to the python executable in the virtual environment
PYTHON_EXEC="$DIR/.venv/bin/python3"

# Define the path to the main script
MAIN_SCRIPT="$DIR/main.py"

# Run the main script using the virtual environment's interpreter
"$PYTHON_EXEC" "$MAIN_SCRIPT" "$@"

