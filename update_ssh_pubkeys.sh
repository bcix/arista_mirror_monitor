#!/bin/bash

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
