#!/bin/bash
tcpdump -p -nl -i vxlan0 -w - --packet-buffered proto 47 | "${0%/*}/deny-monitor.py"
