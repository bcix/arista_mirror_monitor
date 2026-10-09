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

AUTHFILE=/home/upload/.ssh/authorized_keys
OXIDIZED_URL="${1:-https://oxidized.bcix.de}"

if [ ! -f "${AUTHFILE}" ]; then
    echo "${AUTHFILE} must exist" >&2
    exit 1
fi

# get list of devices from oxidized and SSH hostkeys
curl -s "${OXIDIZED_URL}/nodes.json" | \
    jq -r '.[] | .name | select(startswith("edge"))' | \
    ssh-keyscan -f - -t ed25519 2>/dev/null | \
while read host type pubkey; do
    [ "${host}" = '#' ] && continue
    line="${type} ${pubkey} ${host}"
    grep -qxF "${line}" "${AUTHFILE}" || echo "${line}" >> ${AUTHFILE}
done
