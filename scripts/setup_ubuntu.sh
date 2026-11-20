#!/usr/bin/env bash
set -euo pipefail
sudo apt-get -o Acquire::Retries=1 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update
sudo apt-get -y install mininet openvswitch-switch iperf3 python3.10 python3.10-venv
sudo service openvswitch-switch start

python3.10 -m venv .venv
.venv/bin/python -m pip install "pip<24"
.venv/bin/python -m pip install "setuptools<58" wheel
.venv/bin/python -m pip install "eventlet==0.33.3" pytest
.venv/bin/python -m pip install --no-build-isolation "ryu==4.34"

# Ryu 4.34 imports a sentinel removed from newer Eventlet releases.
eventlet_wsgi=".venv/lib/python3.10/site-packages/eventlet/wsgi.py"
if ! grep -q '^ALREADY_HANDLED = object()$' "$eventlet_wsgi"; then
    printf '\nALREADY_HANDLED = object()\n' >> "$eventlet_wsgi"
fi

.venv/bin/python -m pip install -r requirements.txt
.venv/bin/ryu-manager --version
