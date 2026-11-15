#!/usr/bin/env bash
set -euo pipefail
sudo apt update
sudo apt install -y mininet openvswitch-switch iperf3 python3.10 python3.10-venv
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
