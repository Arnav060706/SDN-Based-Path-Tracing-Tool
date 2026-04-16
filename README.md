# SDN Path Tracing Tool (Mininet + POX)

> **Project:** Orange Problem — SDN Mininet-based Simulation  
> **Controller:** POX (OpenFlow 1.0)  
> **Topology:** Diamond (4 switches, 4 hosts, 2 redundant paths)

---

## Problem Statement

This project implements an **SDN-based Path Tracing Tool** that:

- Identifies and displays the **exact path** taken by packets through the network
- Tracks **OpenFlow flow rules** as they are installed at each switch
- Validates the traced path using **ping**, **iperf**, and **ovs-ofctl** tests
- Demonstrates **automatic re-routing** when a link fails

Traditional networks provide no visibility into the forwarding path. With SDN and OpenFlow, the controller has a global view of the topology and can intercept, trace, and log every new flow — making the forwarding path fully transparent and observable.

---

## Network Topology

```
        h1 (10.0.0.1)   h2 (10.0.0.2)
                  \       /
                   s1 (DPID=1)
                  /         \
      s2 (DPID=2)            s3 (DPID=3)
         [upper]                [lower]
                  \         /
                   s4 (DPID=4)
                  /         \
        h3 (10.0.0.3)   h4 (10.0.0.4)
```

| Element | Detail |
|---------|--------|
| Hosts | h1–h4, IPs: 10.0.0.1–10.0.0.4 |
| Switches | s1 (left), s2 (upper), s3 (lower), s4 (right) |
| Path A (upper) | s1 → s2 → s4 |
| Path B (lower) | s1 → s3 → s4 |
| Link bandwidth | 10 Mbit/s (TCLink) |

Two redundant paths between s1 and s4 enable path-tracing and link-failure demonstrations.

---

## Design Choices & Justification

### Why POX?
POX is a Python-based OpenFlow controller that is lightweight, well-documented, and includes a built-in `openflow.discovery` component that uses LLDP to automatically discover inter-switch links. This removes the need to hardcode the topology inside the controller — the controller learns it dynamically.

### Why a Diamond Topology?
A linear topology has only one path, making path tracing uninteresting. A diamond gives two equal-length paths, allowing:
1. Verification that BFS selects a consistent path (Path A by default)
2. Demonstration of failover to Path B when Path A's link is broken

### Flow Rule Design
```
Match:   Ethernet src-MAC + dst-MAC
Action:  Output to specific port (computed from BFS path)
Priority: 100  (overrides default table-miss)
Idle timeout: 30 s  (removed if no traffic)
Hard timeout: 120 s (always removed after 2 min)
```
Using **MAC-level matching** keeps the rules simple and independent of IP routing. Idle + hard timeouts prevent stale rules from blocking re-routing after topology changes.

---

## Setup & Execution

### Prerequisites

```bash
# Mininet (assumed already installed)
mn --version

# Open vSwitch
ovs-vsctl --version

# Python 2.7 (for POX)
python --version

# Python 3 (for show_paths.py utility)
python3 --version
```

### Step 1 — Clone the Repository

```bash
git clone https://github.com/Arnav060706/SDN-Based-Path-Tracing-Tool.git
cd SDN-Based-Path-Tracing-Tool
```

### Step 2 — Run Setup

The setup script installs POX (if missing), copies the controller into the right place, and creates convenience launchers:

```bash
bash setup.sh
```

This will print the exact paths used and confirm all dependencies.

### Step 3 — Start the Controller (Terminal A)

```bash
bash run_controller.sh
```

Internally this runs:
```bash
cd ~/pox
python pox.py log.level --DEBUG openflow.discovery path_tracer
```

Wait until you see:
```
[*] PathTracerController ready
```

### Step 4 — Start Mininet (Terminal B)

```bash
bash run_topology.sh
```

This opens the Mininet interactive CLI. You should see all 4 switches connect in Terminal A.

### Step 5 — Run Basic Test (inside Mininet CLI)

```
mininet> pingall
mininet> h1 ping -c 5 h3
mininet> h2 ping -c 5 h4
```

**Expected Controller Output:**
```
┌──────────────────────────────────────────────────┐
│              *** PATH TRACED ***                 │
├──────────────────────────────────────────────────┤
│  Src MAC  : 00:00:00:00:00:01                    │
│  Dst MAC  : 00:00:00:00:00:03                    │
│  Time     : 2024-01-01 10:00:00                  │
│  Hops     : 3                                    │
│  Path     : 00-00-00-00-00-01 -> 00-00-00-00-00-02 -> 00-00-00-00-00-04 │
└──────────────────────────────────────────────────┘
```

### Step 6 — View Traced Paths (Terminal C)

```bash
# One-shot view
python show_paths.py

# Auto-refreshing view
python show_paths.py --watch
```

### Step 7 — View Flow Tables (Terminal C)

```bash
# One-shot
bash flow_table.sh

# Auto-refreshing
bash flow_table.sh --watch

# Manual per-switch
sudo ovs-ofctl dump-flows s1
sudo ovs-ofctl dump-flows s2
sudo ovs-ofctl dump-flows s4
```

---

## Test Scenarios

### Scenario 1 — Basic Path Tracing (Normal Traffic)

**Objective:** Verify the controller traces and installs correct paths for multiple host pairs.

**Commands (inside Mininet CLI):**
```
mininet> h1 ping -c 5 h3       # h1 -> h3, expected: s1->s2->s4
mininet> h2 ping -c 5 h4       # h2 -> h4, expected: s1->s2->s4
mininet> h1 ping -c 5 h2       # same switch (s1), no inter-switch hops
mininet> h1 iperf h3           # throughput test along traced path
```

**Expected Results:**

| Test | Result | Path |
|------|--------|------|
| h1 → h3 ping | 0% packet loss | s1 → s2 → s4 |
| h2 → h4 ping | 0% packet loss | s1 → s2 → s4 |
| h1 → h2 ping | 0% packet loss | s1 only |
| h1 iperf h3  | ~10 Mbit/s    | s1 → s2 → s4 |

**Validation:**
```bash
# Flow rules should appear at s1, s2, s4 but NOT s3 (not on the path)
sudo ovs-ofctl dump-flows s3   # Should be empty
sudo ovs-ofctl dump-flows s2   # Should have rules for h1<->h3 traffic
```

---

### Scenario 2 — Link Failure & Re-Routing

**Objective:** Demonstrate that the controller detects a link failure and automatically re-routes via the alternate path.

**Step-by-step (inside Mininet CLI):**

```
# Phase 1: Establish traffic on Path A (upper)
mininet> h1 ping -c 3 h3
```
```
# Phase 2: Simulate link failure
mininet> link s1 s2 down
```
```
# Phase 3: Flush stale rules (force re-computation)
mininet> sh sudo ovs-ofctl del-flows s1
mininet> sh sudo ovs-ofctl del-flows s2
mininet> sh sudo ovs-ofctl del-flows s3
mininet> sh sudo ovs-ofctl del-flows s4
```
```
# Phase 4: Traffic should re-route via Path B (lower)
mininet> h1 ping -c 3 h3
```
```
# Phase 5: Restore the link
mininet> link s1 s2 up
```

**Expected Results:**

| Phase | Expected Path | Description |
|-------|--------------|-------------|
| Phase 1 | s1 → s2 → s4 | Upper path (normal) |
| Phase 2 | — | Link s1-s2 goes down |
| Phase 4 | s1 → s3 → s4 | Lower path (failover) |
| Phase 5 | s1 → s2 → s4 | Upper path restored |

**Validation:**
```bash
# After Phase 4, s3 should have flow rules (it wasn't on Path A)
sudo ovs-ofctl dump-flows s3   # Should now have rules
sudo ovs-ofctl dump-flows s2   # Should be empty (link down)
```

---

## Performance Observations

### Latency Measurement (ping)
```bash
# Inside Mininet CLI
mininet> h1 ping -c 20 h3
```
Expected RTT: < 5 ms (Mininet virtual links).

### Throughput Measurement (iperf)
```bash
# Inside Mininet CLI (h3 is server, h1 is client)
mininet> h3 iperf -s &
mininet> h1 iperf -c 10.0.0.3 -t 10
```
Expected throughput: ~10 Mbit/s (bounded by TCLink `bw=10`).

### Packet Count Verification
```bash
# After running pings, check packet counters in flow tables
sudo ovs-ofctl dump-flows s1 | grep n_packets
```
The `n_packets` counter on each flow rule confirms traffic is following the installed path.

---

## SDN Logic — Controller Behaviour Explained

### Controller Startup
1. POX loads `openflow.discovery` which starts sending LLDP probes out every switch port
2. `path_tracer.py` listens for `LinkEvent` from the discovery module
3. As LLDP probes travel between switches, `LinkEvent`s fire and the adjacency map is populated

### Packet Processing (packet_in)
```
New packet arrives at switch
        │
        ▼
Is it LLDP? ──yes──> Ignore (used by discovery)
        │ no
        ▼
Learn source host location (MAC → switch + port)
        │
        ▼
Is dst MAC broadcast? ──yes──> Flood (ARP requests need this)
        │ no
        ▼
Is dst host known? ──no──> Flood (will learn on reply)
        │ yes
        ▼
BFS: src_switch → dst_switch
        │
        ▼
Install flow rules at EVERY switch on path
        │
        ▼
Log path to console + /tmp/sdn_paths.json
        │
        ▼
Forward buffered packet (included in flow_mod at trigger switch)
```

### Flow Rule Installation
Each switch on the path receives:
```
MATCH:   dl_src = <src_mac>, dl_dst = <dst_mac>
ACTION:  output(port=<next_hop_port>)
FLAGS:   priority=100, idle_timeout=30, hard_timeout=120
```

---

## Repository Structure

```
sdn-path-tracer/
├── path_tracer.py              # POX controller (copy to ~/pox/ext/)
├── topology.py                 # Mininet diamond topology
├── show_paths.py               # Path display utility
├── flow_table.sh               # Flow table viewer
├── setup.sh                    # One-time setup script
├── run_controller.sh           # Start POX (generated by setup.sh)
├── run_topology.sh             # Start Mininet (generated by setup.sh)
└── tests/
    ├── scenario1_basic_trace.sh    # Scenario 1: basic path tracing
    └── scenario2_link_failure.sh   # Scenario 2: link failure & re-routing
```

---

# References
 
1. Lantz, B., Heller, B., & McKeown, N. (2010). *A Network in a Laptop: Rapid Prototyping for Software-Defined Networks.* HotNets-IX. https://dl.acm.org/doi/10.1145/1868447.1868466
2. POX Documentation — https://noxrepo.github.io/pox-doc/html/
3. OpenFlow Switch Specification v1.0 — https://opennetworking.org/wp-content/uploads/2013/04/openflow-spec-v1.0.0.pdf
4. Mininet Documentation — http://mininet.org/
5. Open vSwitch Documentation — https://www.openvswitch.org/
6. Feamster, N., Rexford, J., & Zegura, E. (2014). *The Road to SDN.* ACM Queue. https://dl.acm.org/doi/10.1145/2602204.2602219
 
