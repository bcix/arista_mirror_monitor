# arista_mirror_monitor

Arista EOS supports mirroring to GRE tunnel. This feature may be used
instead of logging in ACLs. By doing so, the content of logs may be
customised. For details, especially the platform specific limitations
consult the [TOI](https://www.arista.com/en/support/toi/eos-4-32-0f/16893-mirroring-to-gre-tunnel).

At BCIX we are running on DCS-7280R3 series switches using VXLAN/EVPN
and L2 subinterfaces. This combination has turned out to work well.

## Mapping GRE key to interfaces

The switches deliver all necessary information about ingress interfaces
in the GRE key. The encoded port IDs are using internal identifiers.

- Front panel interfaces use their SysPhyPort as in
  `show platform fap mapping`.
- Port-channels use the LagId in `show platform fap lag` and have
  bit 15 set.
- L2 subinterfaces can be identified by the upper two octets of the
  GRE key which is populated with the GlemIndex from
  `show platform fap subinterface mapping l2`.

The first is at least platform specific -- all switches of the same kind
running the same version of EOS seem to share the same mapping. All
others are assigned upon interface creation.

To correctly identify interfaces, it's important to have up-to-date
runtime state.

## Configuration of the switch

### Monitor session

```
monitor session deny_monitor destination tunnel mode gre source <local IP> destination <target IP>
```

### ACL

```
mac access-list Example
   counters per-entry
   20 remark !! Deny other broadcast and multicast
   21 deny any 01:00:00:00:00:00 fe:ff:ff:ff:ff:ff mirror session deny_monitor
```

### Mapping updater

```
event-handler upload_int_mapping
   action bash bash /mnt/flash/upload_int_mapping.sh <user>@<SFTP server> <VRF> <target directory>
   delay 1
   repeat interval 60
   asynchronous
   !
   trigger on-logging
      poll interval 20
      regex %SYS-5-CONFIG_I|%SYS-5-CONFIG_SESSION_COMMIT_SUCCESS|%SYS-5-CONFIG_REPLACE_SUCCESS|%SYS-6-SYSTEM_INFO
```

Additionally you'll need the script `/mnt/flash/upload_int_mapping.sh`
on the device.

## The monitoring host

### SFTP service

Add a config file in `/etc/sshd_config.d/` containing the following:

```
# only allow SFTP using pubkey
PasswordAuthentication no
KbdInteractiveAuthentication no

Match User upload
  ChrootDirectory /data/upload
  ForceCommand internal-sftp
  AllowTcpForwarding no
  X11Forwarding no
```

And restart ssh server (Ubuntu 26.04):
```
systemctl daemon-reload
systemctl restart ssh.socket
```

### Create upload user

```
sudo useradd -m -s /usr/sbin/nologin upload
sudo mkdir ~upload/.ssh
sudo touch ~upload/.ssh/authorized_keys
sudo chown -R upload:upload ~upload/.ssh
sudo chmod -R go-rwx ~upload/.ssh
sudo mkdir -p /data/upload/files
sudo chown upload /data/upload/files
sudo mkdir -p /data/upload/home/upload
```

### Update SSH keys

The Switches are supposed to upload their mappings using their
individual SSH hostkeys as identity. Thus we need to update the list
of authorized keys regularly.

The script `/home/upload/update_ssh_pubkeys.sh` shall be installed,
made executable and scheduled to run. E.g.

```
chmod +x /home/upload/update_ssh_pubkeys.sh
echo '6 * * * * /home/upload/update_ssh_pubkeys.sh' | crontab -u upload -
```

### Deny Monitor Daemon

The scripts `deny-monitor.py` and `deny-monitor.sh` shall be installed
in `/usr/local/bin`. To execute those, you may use the SystemD unit
`deny-monitor.service` -- copy it to `/etc/systemd/system`.

To activate the daemon:
```
systemctl daemon-reload
systemctl enabled deny-monitor.service
systemctl start deny-monitor.service
```

### Trigger on mapping changes

As soon as a switch updates its mapping file, the Monitor Daemon should
be reloaded. This can be achieved by using inotify by means of SystemD
path units.

Copy `mapping-monitor.path` and `mapping-monitor.service` to
`/etc/systemd/system` and activate those.

```
systemctl daemon-reload
systemctl enabled mapping-monitor.{service,path}
systemctl start mapping-monitor.path
```

## How it all fits together

1. Upon configuration changes (and thus potential interface mapping
   changes) EOS will trigger the event handler.
2. This will cause an update of the mapping file on the monitor host.
3. Changes to mapping files will trigger the Deny Monitor daemon to
   re-read those files.
4. Based on the updated mappings the GRE encapsulated packets will
   be interpreted and logged to a syslog target.
