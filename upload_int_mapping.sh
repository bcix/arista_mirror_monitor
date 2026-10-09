#!/bin/bash

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
