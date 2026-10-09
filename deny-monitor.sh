#!/bin/bash
#
# This file is part of the arista_mirror_monitor distribution
# (https://github.com/bcix/arista_mirror_monitor).
# Copyright (c) 2026 BCIX Management GmbH, André Grüneberg
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

# make the python script the main process
exec "${0%/*}/deny-monitor.py" < <( tcpdump -p -nl -i vxlan0 -w - --packet-buffered proto 47 )
