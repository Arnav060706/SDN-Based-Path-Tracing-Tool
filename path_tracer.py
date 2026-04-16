#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
File: path_tracer.py
Description: Implements the SDN controller logic for tracing
             packet paths across the network. Uses flow rules
             and packet inspection to determine routing paths.

SDN Path Tracing Tool - POX Controller
=======================================
Tracks and displays the exact path taken by packets through the SDN network.

How it works:
  1. openflow.discovery sends LLDP probes to build a topology map (adjacency graph)
  2. When a new packet arrives (packet_in), we learn the source host's location
  3. When both src and dst hosts are known, we compute the shortest path via BFS
  4. Flow rules are installed at EVERY switch along that path
  5. The path is logged to console AND written to /tmp/sdn_paths.json

Usage:
  - Copy this file to:  ~/pox/ext/path_tracer.py
  - Run controller with: python ~/pox/pox.py openflow.discovery path_tracer

Author: SDN Path Tracing Project
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpid_to_str
from pox.lib.revent import *
from pox.lib.packet.ethernet import ethernet
from pox.lib.recoco import Timer
from collections import defaultdict
import time
import json

log = core.getLogger()

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL STATE TABLES
# ─────────────────────────────────────────────────────────────────────────────

# Topology adjacency map built from LLDP discovery
# adjacency[sw_A_dpid][sw_B_dpid] = port_on_A_that_connects_to_B
adjacency = defaultdict(lambda: defaultdict(lambda: None))

# Host location table: learned from packet_in events
# host_locations[mac_address] = (switch_dpid, port_number)
host_locations = {}

# Active switch connections
# switches[dpid] = openflow_connection_object
switches = {}

# Recorded flow paths (used for periodic display and JSON export)
# paths_log["src_mac->dst_mac"] = { 'path': [...], 'hops': N, 'timestamp': '...' }
paths_log = {}

# Where to save path data for the show_paths.py utility
PATH_LOG_FILE = "/tmp/sdn_paths.json"


# ─────────────────────────────────────────────────────────────────────────────
# TOPOLOGY & ROUTING HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def bfs_shortest_path(src_dpid, dst_dpid):
    """
    Find the shortest path between two switches using Breadth-First Search.

    We traverse the adjacency graph (built from LLDP discovery).
    BFS guarantees the minimum hop-count path.

    Args:
        src_dpid (int): DPID of the switch where the source host is attached
        dst_dpid (int): DPID of the switch where the destination host is attached

    Returns:
        list[int]: Ordered list of switch DPIDs from src to dst, or None if unreachable
    """
    if src_dpid == dst_dpid:
        return [src_dpid]   # Source and destination on the same switch

    visited = {src_dpid}
    queue = [[src_dpid]]    # Each element is a list = a candidate path

    while queue:
        current_path = queue.pop(0)   # BFS: pop from front
        current_sw = current_path[-1]

        # Explore all neighbours of current_sw
        for neighbor_dpid, port in adjacency[current_sw].items():
            if port is None or neighbor_dpid in visited:
                continue  # Skip unreachable or already-visited nodes

            new_path = current_path + [neighbor_dpid]

            if neighbor_dpid == dst_dpid:
                return new_path  # ✓ Found the destination!

            visited.add(neighbor_dpid)
            queue.append(new_path)

    return None  # No path found (network might be partitioned)


def is_host_port(dpid, port):
    """
    Decide whether a switch port faces a HOST (not another switch).

    openflow.discovery uses LLDP to populate the adjacency map with all
    INTER-SWITCH links.  Any port NOT in adjacency[dpid] is therefore a
    HOST-facing port (or not yet discovered).

    We use this to avoid learning the MAC address of a switch interface
    as if it were a host.

    Args:
        dpid (int): Switch datapath ID
        port (int): Port number on that switch

    Returns:
        bool: True if the port faces a host, False if it connects to a switch
    """
    for _neighbor, adj_port in adjacency[dpid].items():
        if adj_port == port:
            return False  # Port is in adjacency → connects to another switch
    return True  # Not found → host-facing port


def flood_packet(event, reason=""):
    """
    Send a packet_out with FLOOD action to all ports except the input port.
    Used when the destination is unknown or for broadcast traffic.
    """
    if reason:
        log.debug("[FLOOD] %s" % reason)
    msg = of.ofp_packet_out()
    msg.in_port = event.port
    msg.data = event.ofp            # Re-serialize the original packet
    msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
    event.connection.send(msg)


# ─────────────────────────────────────────────────────────────────────────────
# PATH LOGGING
# ─────────────────────────────────────────────────────────────────────────────

def record_and_display_path(src_mac, dst_mac, path):
    """
    Pretty-print the discovered path to the controller log and
    write it to PATH_LOG_FILE for the show_paths.py utility.

    Args:
        src_mac (EthAddr): Source MAC address
        dst_mac (EthAddr): Destination MAC address
        path (list[int]): Ordered list of switch DPIDs
    """
    path_names = [dpid_to_str(d) for d in path]
    path_str   = " -> ".join(path_names)
    timestamp  = time.strftime('%Y-%m-%d %H:%M:%S')

    # ── Console display ───────────────────────────────────────────────────────
    log.info("")
    log.info("┌──────────────────────────────────────────────────┐")
    log.info("│              *** PATH TRACED ***                 │")
    log.info("├──────────────────────────────────────────────────┤")
    log.info("│  Src MAC  : %-36s │" % str(src_mac))
    log.info("│  Dst MAC  : %-36s │" % str(dst_mac))
    log.info("│  Time     : %-36s │" % timestamp)
    log.info("│  Hops     : %-36s │" % len(path))
    log.info("│  Path     : %-36s │" % path_str)
    log.info("└──────────────────────────────────────────────────┘")
    log.info("")

    # ── JSON export ───────────────────────────────────────────────────────────
    key = "%s->%s" % (str(src_mac), str(dst_mac))
    paths_log[key] = {
        'src_mac'   : str(src_mac),
        'dst_mac'   : str(dst_mac),
        'path'      : path_names,
        'hops'      : len(path),
        'timestamp' : timestamp
    }
    try:
        with open(PATH_LOG_FILE, 'w') as f:
            json.dump(paths_log, f, indent=2)
    except Exception as e:
        log.warning("Could not write path log: %s" % str(e))


# ─────────────────────────────────────────────────────────────────────────────
# FLOW RULE INSTALLATION
# ─────────────────────────────────────────────────────────────────────────────

def install_flow_rules(path, src_mac, dst_mac, trigger_event):
    """
    Install OpenFlow flow rules at EVERY switch along the computed path.

    For each switch:
      - Match fields : Ethernet src MAC + dst MAC
      - Action       : Output to the port leading to the NEXT hop
      - Priority     : 100  (overrides default table-miss entries)
      - idle_timeout : 30 s (rule removed if no traffic for 30 s)
      - hard_timeout : 120 s (rule always removed after 2 min)

    Special case: At the switch that sent the original packet_in event,
    we attach msg.data = trigger_event.ofp so that the buffered packet
    is forwarded immediately when the rule is installed.

    Args:
        path          (list[int])  : Ordered switch DPIDs
        src_mac       (EthAddr)    : Source MAC
        dst_mac       (EthAddr)    : Destination MAC
        trigger_event (PacketIn)   : The original packet_in event
    """
    record_and_display_path(src_mac, dst_mac, path)

    for i, current_sw in enumerate(path):

        # ── Determine where to send traffic FROM this switch ──────────────────
        if i < len(path) - 1:
            # Not the last switch: send to the next switch in path
            next_sw   = path[i + 1]
            out_port  = adjacency[current_sw][next_sw]
            hop_label = "switch %s" % dpid_to_str(next_sw)
        else:
            # Last switch: deliver directly to destination host
            _, out_port = host_locations[dst_mac]
            hop_label   = "host %s" % str(dst_mac)

        if out_port is None:
            log.error("  [!] No port found at %s for next hop" % dpid_to_str(current_sw))
            continue

        if current_sw not in switches:
            log.warning("  [!] Switch %s not connected, skipping" % dpid_to_str(current_sw))
            continue

        # ── Build the ofp_flow_mod message ────────────────────────────────────
        msg = of.ofp_flow_mod()
        msg.match          = of.ofp_match()
        msg.match.dl_src   = src_mac         # Match on source MAC
        msg.match.dl_dst   = dst_mac         # Match on destination MAC
        msg.priority       = 100             # Higher priority than default (0)
        msg.idle_timeout   = 30              # Remove if idle for 30 s
        msg.hard_timeout   = 120             # Absolute max lifetime: 120 s
        msg.actions.append(of.ofp_action_output(port=out_port))

        # If this is the switch that triggered the packet_in,
        # include the original packet data so it is forwarded immediately.
        if current_sw == trigger_event.dpid:
            msg.data = trigger_event.ofp

        switches[current_sw].send(msg)
        log.info("  [RULE] %-20s port %2d  -->  %s" % (
            dpid_to_str(current_sw), out_port, hop_label))


# ─────────────────────────────────────────────────────────────────────────────
# CONTROLLER CLASS
# ─────────────────────────────────────────────────────────────────────────────

class PathTracerController(EventMixin):
    """
    Main POX controller component.

    Event handlers:
      _handle_ConnectionUp   : Switch connects  --> register it, clear its table
      _handle_ConnectionDown : Switch disconnects --> remove from state
      _handle_LinkEvent      : LLDP link found  --> update adjacency map
      _handle_PacketIn       : Packet arrives   --> learn host, trace path, install rules
    """

    def __init__(self):
        self.listenTo(core.openflow)

        if core.hasComponent("openflow_discovery"):
            self.listenTo(core.openflow_discovery)
            log.info("[OK] openflow_discovery component attached")
        else:
            log.error("[!!] openflow_discovery NOT loaded!")
            log.error("     Run: python pox.py openflow.discovery path_tracer")

        log.info("[*] PathTracerController ready")

    # ── Switch lifecycle ──────────────────────────────────────────────────────

    def _handle_ConnectionUp(self, event):
        """
        A switch just connected.
        We register it and wipe its flow table for a clean slate.
        """
        switches[event.dpid] = event.connection

        # Delete ALL existing flow rules (OFPFC_DELETE matches everything)
        msg = of.ofp_flow_mod(command=of.OFPFC_DELETE)
        event.connection.send(msg)

        log.info("[+] Switch UP:   DPID = %s  (table cleared)" % dpid_to_str(event.dpid))

    def _handle_ConnectionDown(self, event):
        """
        A switch disconnected.
        Remove it from our state tables and invalidate adjacency entries.
        """
        dpid = event.dpid

        if dpid in switches:
            del switches[dpid]
        if dpid in adjacency:
            del adjacency[dpid]
        # Remove back-edges pointing to the disconnected switch
        for sw in adjacency:
            if dpid in adjacency[sw]:
                adjacency[sw][dpid] = None

        log.info("[-] Switch DOWN: DPID = %s" % dpid_to_str(dpid))

    # ── Topology discovery ────────────────────────────────────────────────────

    def _handle_LinkEvent(self, event):
        """
        openflow.discovery fires this when it observes a link via LLDP.

        Each LLDP packet carries the originating switch's DPID and port.
        When another switch receives and reports it as packet_in, the
        discovery module records the link and fires a LinkEvent.

        We use this to populate the adjacency map.
        """
        link  = event.link
        dpid1, port1 = link.dpid1, link.port1
        dpid2, port2 = link.dpid2, link.port2

        if event.added:
            # Bidirectional adjacency
            adjacency[dpid1][dpid2] = port1
            adjacency[dpid2][dpid1] = port2
            log.info("[LINK+] %s:p%d  <-->  %s:p%d" % (
                dpid_to_str(dpid1), port1, dpid_to_str(dpid2), port2))

        elif event.removed:
            adjacency[dpid1][dpid2] = None
            adjacency[dpid2][dpid1] = None
            log.info("[LINK-] %s  <X>  %s  (link DOWN)" % (
                dpid_to_str(dpid1), dpid_to_str(dpid2)))

            # Invalidate cached paths that used this now-broken link
            broken = [k for k, v in paths_log.items()
                      if dpid_to_str(dpid1) in v['path'] and dpid_to_str(dpid2) in v['path']]
            for k in broken:
                log.info("[REROUTE] Path '%s' invalidated -- will recompute on next packet" % k)
                del paths_log[k]

    # ── Packet processing ─────────────────────────────────────────────────────

    def _handle_PacketIn(self, event):
        """
        Core logic: called every time the controller receives a packet.

        Step-by-step:
          1. Ignore LLDP probes (they belong to the discovery module)
          2. Learn the source host's location (MAC -> switch+port)
          3. Flood broadcasts/ARP (destination MAC is FF:FF:FF:FF:FF:FF)
          4. Flood if destination host is still unknown
          5. BFS to compute the shortest path
          6. Install flow rules along that path + forward the buffered packet
        """
        packet   = event.parsed
        if not packet.parsed:
            log.warning("Incomplete packet, ignoring")
            return

        dpid     = event.dpid
        in_port  = event.port
        src_mac  = packet.src
        dst_mac  = packet.dst

        # ── Step 1: Skip LLDP ─────────────────────────────────────────────────
        # LLDP packets are internal to the discovery mechanism; don't forward them
        if packet.type == ethernet.LLDP_TYPE:
            return

        # ── Step 2: Learn source host location ───────────────────────────────
        # Only record hosts on HOST-facing ports (skip switch-to-switch ports)
        if is_host_port(dpid, in_port):
            if src_mac not in host_locations:
                host_locations[src_mac] = (dpid, in_port)
                log.info("[HOST] Learned: %s at switch %s port %d" % (
                    src_mac, dpid_to_str(dpid), in_port))

        # ── Step 3: Broadcast / multicast (ARP requests go here) ─────────────
        # We must flood ARP so hosts can discover each other's MAC addresses
        if dst_mac.is_broadcast or dst_mac.is_multicast:
            flood_packet(event, "Broadcast from %s" % src_mac)
            return

        # ── Step 4: Unknown destination ───────────────────────────────────────
        if dst_mac not in host_locations:
            flood_packet(event, "Dest %s unknown, flooding" % dst_mac)
            return

        # ── Step 5: Compute BFS path ──────────────────────────────────────────
        src_info = host_locations.get(src_mac)
        if src_info is None:
            flood_packet(event, "Source location unknown, flooding")
            return

        src_dpid         = src_info[0]
        dst_dpid, _      = host_locations[dst_mac]

        path = bfs_shortest_path(src_dpid, dst_dpid)

        if path is None:
            log.warning("[PATH] No route found -- flooding as last resort")
            flood_packet(event)
            return

        # ── Step 6: Install flows + forward first packet ──────────────────────
        install_flow_rules(path, src_mac, dst_mac, event)


# ─────────────────────────────────────────────────────────────────────────────
# PERIODIC PATH SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def periodic_summary():
    """Print a compact summary of all currently known flow paths every 20 s."""
    if not paths_log:
        return
    log.info("")
    log.info("═══════════════ ACTIVE FLOW PATH SUMMARY ════════════════")
    for key, info in paths_log.items():
        log.info("  %-17s -> %-17s  |  %s  (%d hops)" % (
            info['src_mac'], info['dst_mac'],
            " -> ".join(info['path']), info['hops']))
    log.info("═════════════════════════════════════════════════════════")
    log.info("")


# ─────────────────────────────────────────────────────────────────────────────
# POX ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def launch():
    """
    POX calls this function when loading the module.

    Must be run together with openflow.discovery:
        python pox.py openflow.discovery path_tracer
    """
    log.info("")
    log.info("╔══════════════════════════════════════════════╗")
    log.info("║    SDN PATH TRACING TOOL  v1.0               ║")
    log.info("║    Controller : POX + OpenFlow 1.0           ║")
    log.info("║    Path log   : /tmp/sdn_paths.json          ║")
    log.info("╚══════════════════════════════════════════════╝")
    log.info("")

    core.registerNew(PathTracerController)

    # Fire periodic_summary every 20 seconds
    Timer(20, periodic_summary, recurring=True)
