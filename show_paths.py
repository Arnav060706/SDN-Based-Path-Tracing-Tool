#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SDN Path Display Utility
========================
Reads the flow-path log written by the POX controller and displays it
in a human-readable table.  Optionally watches for updates in real time.

The controller writes /tmp/sdn_paths.json every time a new path is traced.

Usage:
    python show_paths.py            # One-shot display
    python show_paths.py --watch    # Refresh every 3 s (Ctrl-C to stop)
"""

import json
import os
import sys
import time

PATH_LOG_FILE = "/tmp/sdn_paths.json"
SEPARATOR     = "=" * 72


def display():
    """Read the JSON log and pretty-print all recorded paths."""
    if not os.path.exists(PATH_LOG_FILE):
        print("\n[!] No path data found.")
        print("    Is the POX controller running?")
        print("    Expected file: %s\n" % PATH_LOG_FILE)
        return

    try:
        with open(PATH_LOG_FILE) as f:
            data = json.load(f)
    except (ValueError, IOError) as e:
        print("[!] Could not read log file: %s" % e)
        return

    if not data:
        print("\n[*] No flows traced yet.")
        print("    Try: mininet> h1 ping h3\n")
        return

    print("\n" + SEPARATOR)
    print("          SDN PATH TRACING TOOL -- RECORDED FLOWS")
    print(SEPARATOR)
    print("  %-18s  %-18s  %-5s  %-20s" % (
        "SRC MAC", "DST MAC", "HOPS", "PATH"))
    print("-" * 72)

    for _key, info in sorted(data.items()):
        path_str = " -> ".join(info['path'])
        print("  %-18s  %-18s  %-5d  %-20s" % (
            info['src_mac'], info['dst_mac'], info['hops'], path_str))
        print("  %-18s  %-18s  Time: %s" % ("", "", info['timestamp']))
        print("-" * 72)

    print("  Total flows traced: %d" % len(data))
    print(SEPARATOR + "\n")


if __name__ == '__main__':
    if '--watch' in sys.argv:
        print("[*] Watching for path updates... (Ctrl-C to stop)")
        try:
            while True:
                os.system('clear')
                print("[Last updated: %s]" % time.strftime('%H:%M:%S'))
                display()
                time.sleep(3)
        except KeyboardInterrupt:
            print("\n[*] Stopped.")
    else:
        display()
