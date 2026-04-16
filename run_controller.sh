#!/bin/bash
# Start the POX controller with path tracing
echo "[*] Starting POX Path Tracer Controller..."
echo "    Press Ctrl-C to stop"
echo ""
cd "/home/arnav/pox"
python pox.py log.level --DEBUG openflow.discovery path_tracer
