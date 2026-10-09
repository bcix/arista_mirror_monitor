#!/usr/bin/env python3

from scapy.all import *
import scapy.contrib.erspan as erspan
import sys
import logging
import logging.handlers
import socket
import time
import json
import gzip
from pathlib import Path
import signal

AGG_SECONDS = 60
LOG_HOSTS = { "loghost01.bcix.de": 514 }
mapping_path = Path("/data/upload/files")

# storage for switch mappings
switch_mappings = {}

def read_mappings():
    global switch_mappings
    global mapping_path

    # get sorted list of switch interface mapping files
    json_files = list(mapping_path.glob("*.json.gz"))
    json_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    for file_path in json_files:
        try:
            with gzip.open(file_path, "r") as f:
                data = json.loads(f.read().decode("utf-8"))

                ip = data["interfaces"]["Loopback0"]["interfaceAddressBrief"]["ipAddr"]["address"]
                if ip in switch_mappings: # only use file with latest info
                    continue

                switch_mappings[ip] = { "name": data["hostname"] }

                # front panel interfaces
                for intmap in data["aradMappings"]:
                    for intid, intinfo in intmap["portMappings"].items():
                        switch_mappings[ip][int(intid)] = intinfo["interface"]
                # lags with bit 15 set
                for lagname, laginfo in data["aradLags"]["Fap0"]["lags"].items():
                    switch_mappings[ip][0x8000+int(laginfo["id"])] = lagname
                # L2 subinterfaces use glemIndex in high word
                for siname, siinfo in data["subInterfaces"].items():
                    for pi, piinfo in siinfo["parentInterfaces"].items():
                        switch_mappings[ip][int(piinfo["glemIndex"]) << 16] = siname
        except (json.JSONDecodeError, IOError, KeyError) as e:
            print(f"Error reading {file_path.name}: {e}")


def portname(switch_info, grekey: int):
    try:
        if grekey >= 0x10000:
            return switch_info[grekey & 0xffff0000]
        else:
            return switch_info[grekey]
    except KeyError:
        return f"unknown (0x{grekey:02x})"

class LogAggregator:
    # Aggregates logs per window, but prints first occurence in window

    def __init__(self):
        # Constructor
        self.log = logging.getLogger('deny_monitor')
        self.log.setLevel(logging.INFO)
        for host, port in LOG_HOSTS.items():
            handler = logging.handlers.SysLogHandler(address = (host, port), socktype=socket.SOCK_DGRAM)
            self.log.addHandler(handler)
        self.cur_timekey = int(time.time() / AGG_SECONDS)
        self.cur_msgs = {}

    def info(self, line):
        timekey = int(time.time() / AGG_SECONDS)
        if self.cur_timekey != timekey:
            # aggregation window changed
            self.flush()
            self.cur_timekey = timekey

        if line not in self.cur_msgs:
            # first time
            self.log.info(line)
            self.cur_msgs[line] = 1
        else:
            # count within aggregation window
            self.cur_msgs[line] += 1

    def flush(self):
        # Flush the messages in last aggregation window
        if not self.cur_msgs:
            return
        for line, count in self.cur_msgs.items():
            if count > 1:
                self.log.info(f"{line}; repeated {count} times within last {AGG_SECONDS}s window")
        self.cur_msgs.clear()

def handle_sighup(signum, frame):
    print(f"SIGHUP received! Triggering reload...", file=sys.stderr)
    load_config()

def handle_packet(packet):
    global switch_mappings

    # ignore everything not containing GRE/ERSPAN 
    if not packet.haslayer(erspan.ERSPAN):
        return None

    switch_info = switch_mappings.get(packet[IP].src, { "name": "unknown" })
    switch = switch_info["name"]
    grekey = packet[GRE].key
    port_id = grekey % 0x10000
    inner = packet[erspan.ERSPAN].payload
    if isinstance(inner, Ether):
        src = inner[Ether].src
        dst = inner[Ether].dst

        if inner.haslayer(Dot1Q):
            vlan = inner[Dot1Q].vlan
            other = inner.sprintf("Ethertype: %Dot1Q.type%")
        else:
            vlan = "-"
            other = inner.sprintf("Ethertype: %Ether.type%")

        if "SLOW" in other and port_id & 0x8000 > 0:
            # we can ignore LACP on LAGs
            return None
        if "LLDP" in other:
            # LLDP is ok
            return None
    elif isinstance(inner, Dot3):
        src = inner[Dot3].src
        dst = inner[Dot3].dst
        vlan = "-"
        other = "802.3"
    else:
        print(inner.show())
        return "Unknown L2 protocol received"

    if inner.haslayer(STP):
        other = "Spanning Tree Protocol"
    elif inner.haslayer(SNAP):
        if inner[SNAP].OUI == 0xc and inner[SNAP].code == 0x2000:
            other = "CDP"
        else:
            other = inner.sprintf("SNAP: %SNAP.OUI%, code: %SNAP.code%")
    elif inner.haslayer(IPv6):
        ip6l = inner[IPv6]
        src += f"/{ip6l.src}"
        dst += f"/{ip6l.dst}"
        icmpv6type = None
        for lay in ip6l.layers():
            if "ICMPv6" in lay.__name__:
                icmpv6type = lay.__name__
                break
        if icmpv6type != None:
            icmpl = ip6l[icmpv6type]
            typename = icmp6types.get(icmpl.type, "Unknown")
            other = f"ICMPv6 {typename} ({icmpl.type})"
            if hasattr(icmpl, "tgt"):
                other += f", Target: {icmpl.tgt}"
    elif inner.haslayer(IP):
        src += f"/{inner[IP].src}"
        dst += f"/{inner[IP].dst}"
    elif inner.haslayer(ARP):
        arpl = inner[ARP]
        src += f"/{arpl.psrc}"
        dst += f"/{arpl.pdst}"
        other = arpl.sprintf("ARP %ARP.op% (%r,ARP.op%)")

    if inner.haslayer(TCP):
        other = f"TCP {inner[TCP].sport} -> {inner[TCP].dport}"
    elif inner.haslayer(UDP):
        other = f"UDP {inner[UDP].sport} -> {inner[UDP].dport}"

    sw_int = portname(switch_info, grekey)
    return f"Switch: {switch}, {sw_int}, {src} -> {dst}, VLAN: {vlan}, {other}"



if __name__=="__main__":
    log = LogAggregator()
    read_mappings()
    # register SIGHUP handler
    signal.signal(signal.SIGHUP, handle_sighup)

    try:
        # PcapReader reads binary stream from stdin
        with PcapReader(sys.stdin.buffer) as pcap_stream:
            for packet in pcap_stream:
                msg = handle_packet(packet)
                if msg:
                    log.info(msg)
                
    except KeyboardInterrupt:
        # Cleanup on Ctrl-C
        log.flush()
        sys.exit(0)
    except Exception as e:
        log.info(f"Error reading PCAP stream: {e}")
        log.flush()
        print(f"Error reading PCAP stream: {e}", file=sys.stderr)
