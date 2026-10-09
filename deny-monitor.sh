#!/bin/bash

# make the python script the main process
exec "${0%/*}/deny-monitor.py" < <( tcpdump -p -nl -i vxlan0 -w - --packet-buffered proto 47 )
