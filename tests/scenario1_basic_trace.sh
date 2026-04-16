#!/bin/bash
# =============================================================================
# SCENARIO 1 — Basic Path Tracing (Normal Traffic)
# =============================================================================
# PURPOSE:
#   Demonstrate that the controller correctly traces and logs the path
#   taken by packets between multiple host pairs.
#
# WHAT WE TEST:
#   • h1 -> h3   (crosses s1 -> s2 -> s4,  upper path)
#   • h2 -> h4   (same path, different hosts)
#   • h1 -> h2   (same switch, no inter-switch hops)
#
# HOW TO RUN:
#   Inside the Mininet CLI:
#       mininet> sh bash tests/scenario1_basic_trace.sh
#   OR from a separate terminal:
#       sudo python topology.py      (keep this open)
#       # Then inside the CLI that opens:
#       mininet> sh bash ~/sdn-path-tracer/tests/scenario1_basic_trace.sh
#
# EXPECTED OUTPUT:
#   • All pings succeed (0% packet loss)
#   • Controller log shows PATH TRACED blocks for each flow
#   • show_paths.py lists flows with correct hop counts
# =============================================================================

set -e  # Exit on first error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo ""
echo "┌──────────────────────────────────────────────────┐"
echo "│  SCENARIO 1: Basic Path Tracing                  │"
echo "└──────────────────────────────────────────────────┘"
echo ""

# ── 1. Check that Mininet is running ─────────────────────────────────────────
if ! pgrep -x "python" > /dev/null; then
    echo "[!] Mininet does not appear to be running."
    echo "    Start topology.py first, then run this script from the Mininet CLI."
    exit 1
fi

# ── 2. Show flow tables BEFORE any traffic ────────────────────────────────────
echo "--- Flow tables BEFORE test ---"
for sw in s1 s2 s3 s4; do
    echo ""
    echo "  Switch $sw:"
    sudo ovs-ofctl dump-flows "$sw" 2>/dev/null | grep -v "NXST_FLOW" || echo "    (empty)"
done

echo ""
echo "--- Running ping tests ---"

# ── 3. PING TEST A: h1 -> h3  (crosses s1 -> s2 -> s4) ───────────────────────
echo ""
echo "[TEST A]  h1  -->  h3  (expected path: s1 -> s2 -> s4)"
sudo mn --test pingall 2>/dev/null || true
# Since we are inside the CLI, we use the 'ping' command via mnexec
# This script is designed to be called from within Mininet's bash context.
ping -c 4 -I 10.0.0.1 10.0.0.3 2>/dev/null && echo "  [PASS] h1 -> h3 reachable" || echo "  [WARN] Ping via script context failed (run manually inside Mininet)"

echo ""
echo "[TEST B]  h2  -->  h4  (expected path: s1 -> s2 -> s4)"
ping -c 4 -I 10.0.0.2 10.0.0.4 2>/dev/null && echo "  [PASS] h2 -> h4 reachable" || echo "  [WARN] Ping via script context failed (run manually inside Mininet)"

echo ""
echo "[TEST C]  h1  -->  h2  (same switch, path: s1 only)"
ping -c 4 -I 10.0.0.1 10.0.0.2 2>/dev/null && echo "  [PASS] h1 -> h2 reachable" || echo "  [WARN] Ping via script context failed (run manually inside Mininet)"

# ── 4. Show flow tables AFTER traffic ─────────────────────────────────────────
echo ""
echo "--- Flow tables AFTER test ---"
for sw in s1 s2 s3 s4; do
    echo ""
    echo "  Switch $sw:"
    sudo ovs-ofctl dump-flows "$sw" 2>/dev/null | grep -v "NXST_FLOW" | \
        awk '{printf "    %s\n", $0}' || echo "    (empty)"
done

# ── 5. Display recorded paths ──────────────────────────────────────────────────
echo ""
echo "--- Paths recorded by controller ---"
python "$PROJECT_DIR/show_paths.py"

echo ""
echo "[SCENARIO 1 COMPLETE]"
echo "  Check the POX controller terminal for PATH TRACED output."
echo ""
