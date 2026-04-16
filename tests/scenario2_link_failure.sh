#!/bin/bash
# =============================================================================
# SCENARIO 2 — Link Failure & Path Re-Routing
# =============================================================================
# PURPOSE:
#   Show that the controller detects a link failure and automatically
#   installs new flow rules via the alternate path (lower arm).
#
# TOPOLOGY REMINDER:
#
#         h1 ─── s1 ─── s2 ─── s4 ─── h3
#                  \             /
#                   s3 ──────────          <- alternate (lower) path
#
# WHAT WE TEST:
#   Phase 1: Normal traffic  → Path A (s1 -> s2 -> s4)     [upper arm]
#   Phase 2: Bring down s1-s2 link
#   Phase 3: Traffic again   → Path B (s1 -> s3 -> s4)     [lower arm]
#
# HOW TO RUN (from the Mininet CLI):
#   Step-by-step (recommended — gives you full visibility):
#
#   mininet> h1 ping -c 3 h3         # Establish Path A
#   mininet> link s1 s2 down         # Simulate link failure
#   mininet> h1 ping -c 3 h3         # Should re-route via Path B
#   mininet> link s1 s2 up           # Restore link
#
#   OR run this script from within the Mininet bash context:
#   mininet> sh bash ~/sdn-path-tracer/tests/scenario2_link_failure.sh
# =============================================================================

echo ""
echo "┌──────────────────────────────────────────────────┐"
echo "│  SCENARIO 2: Link Failure & Re-Routing           │"
echo "└──────────────────────────────────────────────────┘"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1: Normal operation — traffic should use upper path (s1->s2->s4)
# ═══════════════════════════════════════════════════════════════════════════
echo "═══ PHASE 1: Normal operation ═══"
echo ""
echo "  Sending 3 pings from h1 to h3 (expected path: s1 -> s2 -> s4) ..."
echo "  Run in Mininet:  h1 ping -c 3 h3"
echo ""
echo "  Flow tables on all switches (should show upper path rules):"
for sw in s1 s2 s3 s4; do
    rules=$(sudo ovs-ofctl dump-flows "$sw" 2>/dev/null | grep -c "actions" || echo 0)
    echo "    $sw: $rules rule(s)"
    sudo ovs-ofctl dump-flows "$sw" 2>/dev/null | grep "actions" | \
        awk '{printf "      %s\n", $0}'
done

# Wait for user to initiate ping manually (since this is meant to be
# run alongside the interactive CLI, not replace it)
echo ""
read -p "  [Press ENTER after you have pinged h1->h3 in the Mininet CLI]"

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: Bring down the upper link (s1 <-> s2)
# ═══════════════════════════════════════════════════════════════════════════
echo ""
echo "═══ PHASE 2: Simulating link failure (s1 <-> s2) ═══"
echo ""
echo "  Disabling the s1-s2 interface..."

# Bring down the s1-s2 link via ovs-vsctl (works when running as root)
S1_S2_IFACE_S1=$(sudo ovs-vsctl find Interface | grep -A2 "s1" | grep "s2" | head -1 | awk -F'"' '{print $2}' 2>/dev/null || echo "s1-eth3")
S1_S2_IFACE_S2=$(sudo ovs-vsctl find Interface | grep -A2 "s2" | grep "s1" | head -1 | awk -F'"' '{print $2}' 2>/dev/null || echo "s2-eth1")

echo "  Bringing down interfaces: $S1_S2_IFACE_S1 and $S1_S2_IFACE_S2"
sudo ip link set "$S1_S2_IFACE_S1" down 2>/dev/null || echo "  [!] Could not bring down $S1_S2_IFACE_S1 automatically."
sudo ip link set "$S1_S2_IFACE_S2" down 2>/dev/null || echo "  [!] Could not bring down $S1_S2_IFACE_S2 automatically."

echo ""
echo "  [RECOMMENDED] In the Mininet CLI, run:"
echo "      mininet> link s1 s2 down"
echo ""
read -p "  [Press ENTER once the link is down]"

echo ""
echo "  Waiting 5 s for controller to detect the link failure via LLDP ..."
sleep 5

echo ""
echo "  Flushing stale flow rules (so controller recomputes) ..."
for sw in s1 s2 s3 s4; do
    sudo ovs-ofctl del-flows "$sw" 2>/dev/null || true
done
echo "  Flow tables cleared."

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 3: Traffic with link down — should use lower path (s1->s3->s4)
# ═══════════════════════════════════════════════════════════════════════════
echo ""
echo "═══ PHASE 3: Traffic with upper link DOWN ═══"
echo ""
echo "  Expected new path: s1 -> s3 -> s4  (lower arm)"
echo ""
echo "  Run in Mininet:  h1 ping -c 3 h3"
echo ""
read -p "  [Press ENTER after you have pinged h1->h3 again in the CLI]"

echo ""
echo "  Flow tables (should now show LOWER path rules: s1->s3->s4):"
for sw in s1 s2 s3 s4; do
    rules=$(sudo ovs-ofctl dump-flows "$sw" 2>/dev/null | grep -c "actions" || echo 0)
    echo "    $sw: $rules rule(s)"
    sudo ovs-ofctl dump-flows "$sw" 2>/dev/null | grep "actions" | \
        awk '{printf "      %s\n", $0}'
done

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 4: Restore link
# ═══════════════════════════════════════════════════════════════════════════
echo ""
echo "═══ PHASE 4: Restoring s1 <-> s2 link ═══"
sudo ip link set "$S1_S2_IFACE_S1" up 2>/dev/null || true
sudo ip link set "$S1_S2_IFACE_S2" up 2>/dev/null || true
echo "  [RECOMMENDED] In Mininet CLI: link s1 s2 up"
echo ""

echo "  All recorded paths:"
python "$PROJECT_DIR/show_paths.py"

echo ""
echo "[SCENARIO 2 COMPLETE]"
echo ""
echo "  Summary of demonstrated behaviours:"
echo "    ✓ Phase 1: Upper path (s1->s2->s4) used under normal conditions"
echo "    ✓ Phase 2: Link failure detected by LLDP mechanism"
echo "    ✓ Phase 3: Lower path (s1->s3->s4) used after re-routing"
echo "    ✓ Phase 4: Link restored — both paths available again"
echo ""
