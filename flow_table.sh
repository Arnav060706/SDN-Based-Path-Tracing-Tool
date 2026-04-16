#!/bin/bash
# =============================================================================
# Flow Table Viewer
# =============================================================================
# Dumps the OpenFlow flow tables from every switch in the topology.
# Run this from any terminal (does not need to be inside Mininet CLI).
#
# Usage:
#   bash flow_table.sh            # One-shot dump
#   bash flow_table.sh --watch    # Refresh every 2 s (Ctrl-C to stop)
# =============================================================================

SWITCHES="s1 s2 s3 s4"
SEPARATOR="─────────────────────────────────────────────────────────"

dump_all() {
    echo ""
    echo "┌─────────────────────────────────────────────────────┐"
    echo "│        OPENFLOW FLOW TABLES  ($(date '+%H:%M:%S'))          │"
    echo "└─────────────────────────────────────────────────────┘"

    for sw in $SWITCHES; do
        echo ""
        echo "  ■ Switch: $sw"
        echo "  $SEPARATOR"
        output=$(sudo ovs-ofctl dump-flows "$sw" 2>/dev/null)
        if [ $? -ne 0 ]; then
            echo "    [!] Cannot reach $sw — is Mininet running?"
            continue
        fi
        count=$(echo "$output" | grep -c "actions" || true)
        if [ "$count" -eq 0 ]; then
            echo "    (no flow rules installed)"
        else
            echo "$output" | grep "actions" | while IFS= read -r line; do
                # Extract key fields for a compact display
                priority=$(echo "$line" | grep -oP 'priority=\K[0-9]+' || echo "?")
                dl_src=$(echo "$line"   | grep -oP 'dl_src=\K[^ ,]+' || echo "*")
                dl_dst=$(echo "$line"   | grep -oP 'dl_dst=\K[^ ,]+' || echo "*")
                actions=$(echo "$line"  | grep -oP 'actions=\K.*'    || echo "?")
                n_packets=$(echo "$line"| grep -oP 'n_packets=\K[0-9]+' || echo "0")
                echo "    prio=$priority | src=$dl_src | dst=$dl_dst | $actions | pkts=$n_packets"
            done
        fi
    done
    echo ""
}

if [ "$1" = "--watch" ]; then
    echo "[*] Watching flow tables... (Ctrl-C to stop)"
    while true; do
        clear
        dump_all
        sleep 2
    done
else
    dump_all
fi
