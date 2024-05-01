#!/bin/bash

# Set noninteractive mode
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a
export NEEDRESTART_SUSPEND=1

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

check_mnemonic() {
    if [ -z "$MNEMONIC" ]; then
        echo "MNEMONIC variable is not set. Exiting"
        echo "Please set the MNEMONIC variable to the mnemonic of the wallet"
        echo "Example: export MNEMONIC='word1 word2 word3 ...'"
        exit 1
    fi
}

# Function to install Docker
install_docker() {
    if ! command_exists docker; then
        echo "Installing Docker"
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
        sudo -E apt update
        sudo -E apt install docker-ce -y
        sudo systemctl start docker
        sudo systemctl enable docker
        sudo usermod -aG docker "$USER"
    else
        echo "Docker is already installed"
    fi
}

# Function to install Node.js and PM2
install_node_pm2() {
    if ! command_exists nvm; then
        echo "Installing Node.js and PM2"
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
        source ~/.nvm/nvm.sh
        nvm install --lts
        npm install -g pm2
    else
        echo "NVM is already installed"
    fi
}

# Function to clone and set up HIP Subnet
setup_hip_subnet() {
    echo "Setting up HIP Subnet"
    cd ~ || exit
    if [ ! -d "HIP-Subnet" ]; then
        git clone https://github.com/HIP-Labs/HIP-Subnet
    else
        cd HIP-Subnet || exit
        git reset --hard
        git checkout main
        git pull
        cd ..
    fi
}

# Function to install Python 3.10 and set up virtual environment
setup_python() {
    echo "Installing Python 3.10"
    sudo add-apt-repository ppa:deadsnakes/ppa -y
    sudo-E apt update
    sudo -E apt install -y python3.10 python3.10-venv python3.10-dev
    sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1
}

# Define setup_wallet() function
setup_miner() {
    if ! command_exists btcli; then
        echo "Btcli not found. Exiting"
        exit 1
    else
        # if MNEMONIC variable is not set, throw an error
        check_mnemonic
        btcli wallet regen_coldkey --wallet.name default --wallet.hotkey default --subtensor.network test --no_password --no_prompt  --mnemonic $MNEMONIC
        btcli wallet regen_hotkey  --wallet.name default --wallet.hotkey default --subtensor.network test --no_password --no_prompt  --mnemonic $MNEMONIC
        btcli subnet register --wallet.name default --wallet.hotkey default --subtensor.network test --no_prompt --netuid 134
    fi
}

# Main script
check_mnemonic
echo "Setting up Subtensor Testnet"
echo "Installing dependencies"
sudo -E apt update
sudo -E apt install -y apt-transport-https ca-certificates curl software-properties-common tmux

install_docker

# Make sure the user is in the docker group
docker compose down --volumes

install_node_pm2

echo "Running Subtensor Testnet in Docker"
cd ~ || exit

git clone https://github.com/opentensor/subtensor.git
cd subtensor || exit
git checkout main
sudo ./scripts/run/subtensor.sh -e docker --network testnet --node-type lite
setup_hip_subnet

cd ~/HIP-Subnet || exit
setup_python

echo "Creating virtual environment and installing HIP Subnet"
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .

setup_miner

echo "HIP Subnet setup complete"
echo "Running HIP Subnet"
echo "Run the following command:"
echo "cd ~/HIP-Subnet && source venv/bin/activate"
echo "Now ensure the wallet is configured and run the following commands:"
echo "pm2 start ecosystem.config.js"
