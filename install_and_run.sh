#!/bin/bash

# ==========================================
# Color Variables for Terminal Output
# ==========================================
RED='\033[0;31m'
GREEN='\033[0;32m'
PURPLE='\033[0;35m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# ==========================================
# ASCII Banner
# ==========================================
clear
echo -e "${PURPLE}${BOLD}"
cat << "EOF"
 _   _       _   _ _   _ _______________  _____  ___________ 
| \ | |     | | | | \ | |___  /_   _| _ \|  __ \|  ___| ___ \
|  \| |_____| | | |  \| |  / /  | | | |_) | |  \/ |__ | |_/ /
| . ` |_____| | | | . ` | / /   | | |  __/| | __|  __||    / 
| |\  |     | |_| | |\  |/ /____| | | |   | |_\ \ |___| |\ \ 
\_| \_/      \___/\_| \_/\_____/\_/ \_|   |____/\____/\_| \_|
                                                             
EOF
echo -e "${GREEN}       Recursive Extraction Engine v2.0${NC}"
echo -e "${PURPLE}   Developed by Noufal NS | Byte Craft Labs${NC}\n"
echo -e "=========================================================${NC}\n"

# ==========================================
# Configuration Variables
# ==========================================
APP_SCRIPT="nunzipper.py" # <-- Change this if your python file is named differently
VENV_DIR="venv"

# ==========================================
# System Checks & Installation
# ==========================================

# 1. Check if Python3 is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR] Python3 could not be found. Please install Python3 and try again.${NC}"
    exit 1
fi

# 2. Check if the application script exists
if [ ! -f "$APP_SCRIPT" ]; then
    echo -e "${RED}[ERROR] Application script '$APP_SCRIPT' not found in this directory.${NC}"
    echo -e "Please ensure the script is named correctly or update the APP_SCRIPT variable in this bash file."
    exit 1
fi

# 3. Virtual Environment Setup
echo -e "${BLUE}[*] Checking virtual environment...${NC}"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${GREEN}[+] Creating new virtual environment '${VENV_DIR}'...${NC}"
    python3 -m venv $VENV_DIR
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR] Failed to create virtual environment. Ensure 'python3-venv' is installed.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}[+] Virtual environment already exists.${NC}"
fi

# 4. Activate Virtual Environment
source $VENV_DIR/bin/activate

# 5. Install Dependencies
if [ -f "requirements.txt" ]; then
    echo -e "${BLUE}[*] Verifying dependencies from requirements.txt...${NC}"
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
    echo -e "${GREEN}[+] Dependencies are up to date.${NC}"
else
    echo -e "${RED}[WARNING] requirements.txt not found! Skipping dependency installation.${NC}"
    # Fallback install just in case
    pip install customtkinter>=5.2.0 -q
fi

# ==========================================
# Launch Application
# ==========================================
echo -e "\n${GREEN}${BOLD}▶ ENGAGING N-UNZIPPER...${NC}\n"

# Run the python script
python3 "$APP_SCRIPT"

# Deactivate the virtual environment upon exit
deactivate
echo -e "\n${BLUE}[*] Application closed. Environment deactivated.${NC}"
