#!/bin/bash
# =============================================================================
# Setup Script — SDN Path Tracing Project
# =============================================================================
# This script:
#   1. Finds your POX installation
#   2. Copies path_tracer.py into POX's ext/ directory
#   3. Verifies Mininet and OVS are available
#   4. Makes all scripts executable
#   5. Prints the commands needed to start the demo
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROLLER="$SCRIPT_DIR/path_tracer.py"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║        SDN Path Tracing — Setup Script              ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── 1. Find POX installation ──────────────────────────────────────────────────
echo "[1/5] Locating POX controller..."

POX_DIR=""
CANDIDATES=(
    "$HOME/pox"
    "/usr/local/pox"
    "/opt/pox"
    "$(find /home -maxdepth 3 -name 'pox.py' 2>/dev/null | head -1 | xargs dirname 2>/dev/null || true)"
)

for dir in "${CANDIDATES[@]}"; do
    if [ -n "$dir" ] && [ -f "$dir/pox.py" ]; then
        POX_DIR="$dir"
        break
    fi
done

if [ -z "$POX_DIR" ]; then
    echo ""
    echo "  [!] POX not found in standard locations."
    echo "      Installing POX now..."
    echo ""
    cd "$HOME"
    git clone https://github.com/noxrepo/pox.git
    POX_DIR="$HOME/pox"
    echo "  [OK] POX cloned to $POX_DIR"
else
    echo "  [OK] Found POX at: $POX_DIR"
fi

# ── 2. Copy controller to POX ext/ ────────────────────────────────────────────
echo ""
echo "[2/5] Installing controller into POX..."

POX_EXT="$POX_DIR/ext"
mkdir -p "$POX_EXT"

cp "$CONTROLLER" "$POX_EXT/path_tracer.py"
echo "  [OK] Copied path_tracer.py -> $POX_EXT/path_tracer.py"

# ── 3. Check dependencies ─────────────────────────────────────────────────────
echo ""
echo "[3/5] Checking dependencies..."

check_cmd() {
    if command -v "$1" &>/dev/null; then
        echo "  [OK] $1 found"
    else
        echo "  [!!] $1 NOT found — please install it"
    fi
}

check_cmd mn          # Mininet
check_cmd ovs-vsctl   # Open vSwitch
check_cmd ovs-ofctl   # OVS OpenFlow control
check_cmd python      # Python (for POX and topology.py)
check_cmd python3     # Python 3 (for show_paths.py)
check_cmd ping
check_cmd iperf

# ── 4. Set permissions ─────────────────────────────────────────────────────────
echo ""
echo "[4/5] Setting file permissions..."
chmod +x "$SCRIPT_DIR/topology.py"
chmod +x "$SCRIPT_DIR/show_paths.py"
chmod +x "$SCRIPT_DIR/flow_table.sh"
chmod +x "$SCRIPT_DIR/tests/scenario1_basic_trace.sh"
chmod +x "$SCRIPT_DIR/tests/scenario2_link_failure.sh"
echo "  [OK] All scripts marked executable"

# ── 5. Write convenience run scripts ──────────────────────────────────────────
echo ""
echo "[5/5] Creating run helper scripts..."

cat > "$SCRIPT_DIR/run_controller.sh" << EOF
#!/bin/bash
# Start the POX controller with path tracing
echo "[*] Starting POX Path Tracer Controller..."
echo "    Press Ctrl-C to stop"
echo ""
cd "$POX_DIR"
python pox.py log.level --DEBUG openflow.discovery path_tracer
EOF
chmod +x "$SCRIPT_DIR/run_controller.sh"
echo "  [OK] run_controller.sh created"

cat > "$SCRIPT_DIR/run_topology.sh" << EOF
#!/bin/bash
# Start the Mininet diamond topology
echo "[*] Starting Mininet topology..."
echo "    Make sure the controller is already running!"
echo ""
sudo python "$SCRIPT_DIR/topology.py"
EOF
chmod +x "$SCRIPT_DIR/run_topology.sh"
echo "  [OK] run_topology.sh created"

# ── Final Instructions ─────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    SETUP COMPLETE!                          ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║                                                              ║"
echo "║  STEP 1 — Open Terminal A. Start the controller:            ║"
echo "║    bash $SCRIPT_DIR/run_controller.sh"
echo "║                                                              ║"
echo "║  STEP 2 — Open Terminal B. Start Mininet:                   ║"
echo "║    bash $SCRIPT_DIR/run_topology.sh"
echo "║                                                              ║"
echo "║  STEP 3 — Inside Mininet CLI, run tests:                    ║"
echo "║    mininet> pingall                                          ║"
echo "║    mininet> h1 ping -c 5 h3                                 ║"
echo "║    mininet> h1 iperf h3                                     ║"
echo "║                                                              ║"
echo "║  STEP 4 — Open Terminal C. View paths:                      ║"
echo "║    python $SCRIPT_DIR/show_paths.py --watch"
echo "║                                                              ║"
echo "║  STEP 5 — View flow tables:                                 ║"
echo "║    bash $SCRIPT_DIR/flow_table.sh --watch"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  POX location  : $POX_DIR"
echo "  Controller at : $POX_EXT/path_tracer.py"
echo ""
