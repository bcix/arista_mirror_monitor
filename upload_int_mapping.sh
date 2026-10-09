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

SFTP_HOST="${1}"
VRF="${2:-default}"
SFTP_DIR="${3:-/files}"
if [ "${VRF}" != 'default' ]; then
	VRF="ns-${VRF}"
fi

OUTFILE="/tmp/mapping_$(hostname).json.gz"
(
        FastCli -M -p 15 -c 'show hostname | json' | sed '$ s/}/,/'
        FastCli -M -p 15 -c 'show ip int lo0 | json' | sed '1 d; $ s/}/,/'
        FastCli -M -p 15 -c 'show platform fap mapping | json' | sed '1 d; $ s/}/,/'
        FastCli -M -p 15 -c 'show platform fap lag | json' | sed '1 d; $ s/}/,/'
        FastCli -M -p 15 -c 'show platform fap subinterface mapping l2 | json' | sed '1 d'
) | gzip -9 > "${OUTFILE}"
sudo ip netns exec "${VRF}" sftp -i /persist/secure/ssh_host_ed25519_key -b - "${SFTP_HOST}" <<< "PUT ${OUTFILE} ${SFTP_DIR}"
