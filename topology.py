#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Diamond Topology for SDN Path Tracing
======================================
Creates a diamond-shaped network that gives TWO possible paths between
the left cluster (h1, h2) and the right cluster (h3, h4).

                h1  h2
                 \  /
                  s1
                 /  \
               s2    s3
                 \  /
                  s4
                 /  \
                h3  h4

Two inter-switch paths between s1 and s4:
  Path A (upper): s1 --> s2 --> s4   (BFS will find this by default)
  Path B (lower): s1 --> s3 --> s4   (used after link failure on Path A)

This topology lets us:
  • Show basic path tracing (Scenario 1)
  • Demonstrate re-routing after a link failure (Scenario 2)

Usage:
    sudo python topology.py
    (Start the POX controller FIRST in a separate terminal)
"""

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink


class DiamondTopo(Topo):
    """
    Diamond-shaped 4-switch, 4-host topology.

    Port assignments (auto-assigned by Mininet, shown for reference):
        s1: port1=h1, port2=h2, port3=s2, port4=s3
        s2: port1=s1, port2=s4
        s3: port1=s1, port2=s4
        s4: port1=s2, port2=s3, port3=h3, port4=h4
    """

    def build(self):
        # ── Hosts ──────────────────────────────────────────────────────────────
        # Explicit MAC addresses make Wireshark captures easier to read
        h1 = self.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
        h2 = self.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
        h3 = self.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03')
        h4 = self.addHost('h4', ip='10.0.0.4/24', mac='00:00:00:00:00:04')

        # ── Switches ───────────────────────────────────────────────────────────
        s1 = self.addSwitch('s1')   # Left aggregation switch
        s2 = self.addSwitch('s2')   # Upper core switch
        s3 = self.addSwitch('s3')   # Lower core switch
        s4 = self.addSwitch('s4')   # Right aggregation switch

        # ── Host-to-Switch Links ───────────────────────────────────────────────
        # bw=10 sets 10 Mbit/s bandwidth (used in iperf tests)
        self.addLink(h1, s1, bw=10)
        self.addLink(h2, s1, bw=10)
        self.addLink(h3, s4, bw=10)
        self.addLink(h4, s4, bw=10)

        # ── Inter-Switch Links (diamond structure) ─────────────────────────────
        self.addLink(s1, s2, bw=10)   # Upper arm
        self.addLink(s2, s4, bw=10)   # Upper arm (continued)
        self.addLink(s1, s3, bw=10)   # Lower arm
        self.addLink(s3, s4, bw=10)   # Lower arm (continued)


def run():
    """Instantiate and start the Mininet network."""
    info("*** Building Diamond Topology\n")

    topo = DiamondTopo()

    net = Mininet(
        topo       = topo,
        # RemoteController connects to POX running on localhost:6633
        controller = lambda name: RemoteController(name, ip='127.0.0.1', port=6633),
        switch     = OVSSwitch,
        link       = TCLink,     # Traffic Control links (enables bw/delay settings)
        autoSetMacs = False       # We set MACs explicitly above
    )

    info("*** Starting network\n")
    net.start()

    # ── Pretty-print the topology ──────────────────────────────────────────────
    info("\n")
    info("╔═══════════════════════════════════════════════════════════╗\n")
    info("║               Diamond Topology Active                     ║\n")
    info("║                                                           ║\n")
    info("║   h1 (10.0.0.1) ─┐                    ┌─ h3 (10.0.0.3)  ║\n")
    info("║                  s1 ─── s2 ─── (upper) ┤                 ║\n")
    info("║   h2 (10.0.0.2) ─┘    ╲              s4                  ║\n")
    info("║                        s3 ─── (lower) ┤                  ║\n")
    info("║                                        └─ h4 (10.0.0.4)  ║\n")
    info("╚═══════════════════════════════════════════════════════════╝\n")
    info("\n")
    info("  Two paths from s1 to s4:\n")
    info("    PATH A (upper): s1 -> s2 -> s4   [BFS default]\n")
    info("    PATH B (lower): s1 -> s3 -> s4   [after link failure]\n")
    info("\n")
    info("  Controller must be running: python pox.py openflow.discovery path_tracer\n")
    info("\n")

    # Drop into Mininet interactive CLI
    CLI(net)

    info("*** Stopping network\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
