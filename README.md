# NAUbackup / VmBackup
Copyright (C) 2009-2015, Northern Arizona University (NAU)
Information Technology Services, Academic Computing SCAN division.
Use of this software is "as-is".  NAU takes no responsibility
for the results of making use of this or related programs and any data
directly or indirectly affected.

**Title:** a XenServer simple backup script

**Package Contents:** README.md (this file), VmBackup.py, example.cfg

## Version History:
 - v2.1 2014/08/22 Added email status option
 - v2.0 2014/04/09 New VmBackup version (supersedes all previous NAUbackup versions)

**DO NOT RUN THIS SCRIPT UNLESS YOU ARE COMFORTABLE WITH THESE ACTIONS.**

 - To accomplish the vm backup this script uses the following xe commands: (a) vm-snapshot, (b) template-param-set, (c) vm-export, (d) vm-uninstall, where vm-uninstall is against the snapshot uuid.

## Contents
 - Overview
 - Command Line Usage
 - Command Line Parameters
 - NFS Setup
 - CIFS (SMB) Setup
 - Configuration File Options
 - Script Installation Instructions
 - Additional Features
 - VM Restore
 - Pool Restore

## Overview
 - The VmBackup.py script is run from a XenServer host and utilizes the native
   XenServer `xe vm-export` command to backup either Linux or Windows VMs.
 - The vm-export is actually run after a vm-snapshot has occurred
   and this allows for backup while the VM is up and running.
 - These backup command techniques were originally discovered from anonymous
   Internet sources, then modified and developed into this python code.
 - During the backup of specified VMs, this script collects additional VM
   metadata using the Citrix XenServer XenAPI. This additional information
   can be useful during VM restore situations.
 - Backups can be run from multiple XenServer hosts and from multiple pools and
   all be written to a common area, if desired. That way, local as well as pooled
   SRs can be handled.
 - In addition to any scheduled cron backups, the VmBackup.py script can be run manually
   as desired. However, it is important to keep in mind that the backup process does use
   important DOM0 resources, so running a backup during heavy workloads should be avoided.
 - The SR where VDI is located requires sufficient free space to hold a complete
   snapshot of a VM. The temporary snapshots created during the backup process are deleted
   after the vm-export has completed.
 - Optionally, if pool_db_backup=1 then the pool state backup occurs via
   the `xe pool-dump-database` command.
 - Optionally, compression of the vm-export file can be performed in the background
   after each VM backup is completed by an independent user supplied cron job.
 - Optionally, status email can be sent by configuring optional VmBackup.py variables.

## Command Line Usage

Typical Usage w/ config file for multiple vm backups:

    ./VmBackup.py <password> <config-file-path> [compress=True|False] [allow_extra_keys=True|False]

Alternate Usage w/ vm name for single vm backup:

    ./VmBackup.py <password> <vm-name> [compress=True|False] [allow_extra_keys=True|False]

Crontab example (most easily implemented as user 'root' with the command "crontab -e"):

    10 0 * * 6 /usr/bin/env python /snapshots/NAUbackup/VmBackup.py password /snapshots/NAUbackup/example.cfg >> /snapshots/NAUbackup/logs/VmBackup.log 2>&1

### Password ###
Provide the password for the user `root`. Make sure to set it in single quotes, e.g.  `'yourPassword'`.


### Command Line Parameters
 - *compress=True*          -> will trigger the 'xe vm-export compress=true' option during backup.
 - *compress=False*         -> (default) no immediate backup compression.
 - *allow_extra_keys=True*  -> Other scripts may read the same config file with some extra params,
                           if this is the case then ignore extra configuration params.
 - *allow_extra_keys=False* -> (default) If extra keys exist, then an error will occur.

## Configuration File Options (see example.cfg):
 1. Take Xen Pool DB backup: 0=No, 1=Yes (default to 0=No)
   pool_db_backup=0
 2. How many backups to keep for each vm (default to 4)
   max_backups=4
 3. Backup Directory path (required)
   backup_dir=/path/to/backupspace
 4. name-label of vm to backup. (required - one vm per line)
   vm-export=my-vm-name
   vm-export=my-second-vm
   vm-export=my-third-vm

## NFS Setup
  - The NFS server holding the backup storage area will need to export its directory to
    each and every XenServer that will create backups. An entry in /etc/exports should
    appear similar to this:

    `/snapshots myxenserver1.mycompany.org(rw,sync,no_root_squash)`

  - In addition, rpcbind, mountd, lockd, statd and possibly also rquotad access should be
    granted to the NFS server from all XenServer hosts (for example, via tcpwrapper settings
    on the NFS server).
  - There should be no need to alter any settings on any of the XenServers unless if firewalls
    are utilized anywere within the network chain, appropriate tunneling should be enabled as
    required.

## CIFS (SMB) Setup
  - Similar to NFS, a CIFS storage area to hold the backup storage will need to be configured on
    either a Windows server or CIFS-compatible storage device and the corresponding mount area made
    available to all the XenServer hosts. In this case, the variable DEFAULT_BACKUP_DIR in the
    VmBackup.py script should be modified according to the instructions given within that file.
  - Again, since XenServer natively supports CIFS connections, no firewall modifications should be
    necessary on the XenServer end.

## Installation
 1. Copy VmBackup.py to a XenServer local execution path.
 2. From www.citrix.com/downloads - download the XenServer Software Development Kit
     then copy file XenAPI.py into the same directory where VmBackup.py exists.
 3. Setup a %BACKUP_DIR% path (typically NFS) for VM backup storage.
 4. Edit the example configuration file for the appropriate settings.
 5. Review VmBackup.py code.
     - review comments at beginning of script.
     - customize hard coded default values to suit your environment.
     - if desired, enable optional status email. This requires user configure / uncomment code lines in VmBackup.py.
 6. Command line run VmBackup.py from XenServer host against test VM's
     - then do some test VM restores to verify operation.
     - then edit crontab for regular execution cycles.

## Feature Discussion
 - A typical VmBackup.py run with vm-export specified creates a unique
   VM backup directory %BACKUP_DIR%/vm-name/date-time/. This VM backup directory
   contains (a) the vm backup xva file and (b) additional VM metadata.

## Additional Features
 - If running script from cron, then consider redirect to output file as the
   backup script output can be verbose and quite useful for error situations.
 - For each VM that is backed up it creates a unique backup directory
   *%BACKUP_DIR%/vm-name/date-time/*.
 - Associated VM metadata is stored in text files inside the
   *%BACKUP_DIR%/vm-name/date-time/* location.
 - The oldest %BACKUP_DIR%/vm-name/date-time/ entries are deleted when the number of
   backups for a vm exceeds `%MAX_BACKUPS%`.
 - Before each new VM backup begins then a check is made to ensure that the last
   VM backup was successful. If it was not successful then the previous backup directory
   will be deleted so that `%MAX_BACKUPS%` will not delete older 'successful' backups.
 - If the script is run with a config file, then extra logging occurs in the
   status_log file. This file is good for a bird's eye view of the backup run and
   optionally can be used by other scripts for additional processing requirements.

## Optional Features
 - VmBackup.py does not include email status by default since there is another component of NAUbackup that calls VmBackup and handles email from that framework.
 - To configure email in VmBackup.py then follow the comments in the script to configure and uncomment out the desired send_email lines.

## Restore
### VM Restore
To restore VM from backup, use the `xe vm-import` command. Use `xe help vm-import` for parameter options. In particular, attention should be paid to the "preserve" option, which if specified as `preserve=true` will re-create as many of the original settings as possible, including in particular the network and MAC addresses.

### Pool Restore
In the situation where the pool is corrupt and no hosts will start in the pool then it may be necessary to restore and rebuild the XenServer pool. This decision should be carefully reviewed with advice from Citrix Support. Consult the Citrix XenServer Administrator's Guide chapter 8 and review sections that discuss the 'xe pool-restore-database' command.


##  Troubleshooting ###
### XenAPI authentication failed
Console output:
```
['SESSION_AUTHENTICATION_FAILED', 'root', 'Authentication failure']
ERROR - XenAPI authentication error
```
Possible reasons:
- The password you provided as CLI-parameter is wrong. Provide the password for the `root` user.
- The password contains a special character, e.g. "@" and prevents correct parsing.
Provide the password in single quotes, e.g. `./VmBackup 'rootPasswordForTheXenHost' ...`
