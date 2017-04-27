Copyright (C) 2016  Northern Arizona University

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

**Title:** NAUbackup / VmBackup - a XenServer vm-export and vdi-export Backup Script

**Package Contents:** README.md (this file), VmBackup.py, example.cfg

## Version History:
 - v3.2 2017/04/03 Adding metadata-export backup options
 - v3.1 2016/11/26 Replaced prefix wildcard option with python regex wildcards.
 - v3.0 2016/03/04 Added vdi-export and VM prefix wildcards.
 - v2.1 2014/08/22 Added email status option.
 - v2.0 2014/04/09 New VmBackup version supersedes all previous NAU Backup releases.

**DO NOT RUN THIS SCRIPT UNLESS YOU ARE COMFORTABLE WITH THESE ACTIONS.**
 
- For vm-export: (a) `xe vm-snapshot`, (b) `xe template-param-set`, (c) `xe vm-export`, (d) `xe vm-uninstall` on the vm-snapshot.
- For vdi-export: (a) `xe vdi-snapshot`, (b) `xe vdi-param-set`, (c) `xe vdi-export`, (d) `xe vdi-destroy` on the vdi-snapshot.

## Overview
 - The VmBackup.py script is run from a XenServer host and utilizes the native `xe vm-export` and `xe vdi-export` commands to backup both Linux and Windows VMs. 
 - The vm-export or vdi-export is run after a respective vm-snapshot or vdi-snapshot occurs, which allows for the export to execute while the VM is up and running.
 - These backup command techniques were originally discovered from anonymous Internet sources, then modified and developed into this python code. The new vdi-export feature was developed from information found at http://wiki.xensource.com/wiki/Disk_import/export_APIs
 - During the backup of specified VMs, this script collects additional VM metadata using the XenServer XenAPI. This additional information can be useful during VM restore situations and is stored in each individual VM backup location.
 - Typically, VmBackup.py is implemented through scheduled crontab entries or can be run manually on a XenServer ssh session. It is important to keep in mind that the backup process does use critical DOM0 resources, so running a backup during heavy workloads should be avoided.
 - The SRs where one or more VDIs are located require sufficient free space to hold a complete snapshot of a VM. The temporary snapshots that are created during the backup process are deleted after the vm-export has completed.
 - If the config-file pool_db_backup=1 is specified, then the pool state backup occurs via the `xe pool-dump-database` command. 
 - Optionally, a completion status email can be sent by configuring VmBackup.py variables that are provided in the code, see the Quick Start Checklist section.

## Release 3.2 Summary
 - Adding a new parameter to put in the config file: **metadata-export**. This option should be used like **vm-export** or **vdi-export** but will only backup metadata and will create an **xva** file using *xe vm-export vm=vmname filename="filename" metadata=true*.
 - When **vdi-export** ran it also create an **xva** file with metadata following the same process as **metadata-export**.

## Release 3.1 Summary

 - Deprecated **VM prefix wildcard** option for vm-export and vm-import (see regex option below). The syntax was vm-export=PROD* and vdi-export=PRD-with-many-disks* but note that python regex will interpret this _differently_ than a Linux shell "grep" command. More details are given below.

 - New **VM regex wildcard** options for vm-export, vdi-export as well as exclude lists. This is an even more powerful feature if you utilize a VM naming convention. Exclude choices are equally applied to all VMs, regardless if intended for vdi-export or vm-export. WARNING: The prefix wildcard will _not_ be interpreted quite the same as before, hence older configuration files will need to be modified! See the regex section containing caveats and examples further below. Individual names deemed to be non-wildcard variations are handled as simple strings, just like before.

 - New **regex syntax checking** built in. With the potential complexity of regex operators, the script is parsed for regex errors which are flagged and cause the script to exit. Full parsing and reporting is still performed for the "preview" option.

 - New check that the target backup destination folder is writable at the onset.

 - New option to configure email to use SMTP START/TLS user account authentication for email delivery.
 
 - New introduction of the DEFAULT_STATUS_LOG parameter, allowing a user-defined log file path definition.

## Release 3.0 Summary

These new features have been added:

 - New configuration option **vdi-export=vm_name** which utilizes the `xe vdi-export` command for just the /dev/xvda boot disk of the given vm_name.

   - **The vdi-export is for special purpose backup situations** - a VM with a /dev/xvda boot disk and several other user data disks xvdb, xvdc, xvdd, ... that are so "large" that it is not practical to vm-export the whole VM. When the vdi-export option is used, then any subsequent restore would require separate a backup and restore product of the user data disks, such as the NetBackup commercial product.

   - The `xe vdi-export` and `xe vdi-import` commands are a relatively new XenServer function and as such the XenServer usage documentation is still evolving. **If you choose to use the vdi-export option, then it is imperative that you verify the restore process with your particular VM's in your environment.** This feature has been available for quite a few releases, however it has only been verified on XenServer 6.5 and the early versions of XenServer Dundee.

 - New **VM prefix wildcard** option for both vm-export and vdi-export. This is a powerful feature if you utilize a VM prefix naming convention. Syntax examples include: vm-export=PROD* and vdi-export=PRD-with-many-disks*
 - New configuration **exclude=vm_name** option to filter out VMs from the vm-export and vdi-export VM selection list. Currently, the exclude parameter must specify a specific vm_name and can not be a VM prefix wildcard.
 - New command line **preview** option. This will show all config parameters, VMs have been selected for vm-export and vdi-export. If there are any configuration errors then they will be flagged.
 - New command line **vm-selector** options include vm-export, vdi-export, and VM prefix wildcard options.
 - VM export and VDI export now supports **VM names with spaces**. 
   - Note all vm-export, vdi-export, exclude and VM-selectors continue to be **case sensitive**.
 - The command line password can now be obscured into a password file. See "VmBackup.py help" on how to use and create the password file.
 - The internal email option is updated to fix some previous errors. See the next section for additional information.


## Quick Start Checklist

1. VmBackup will require lots of file storage. Set up a storage server with an exported VM backup share. By default VmBackup.py uses /snapshots, which can be modified. Frequently NFS is used for the storage server, with many installation and configuration sources available on the web. An optional SMB/CIFS method can be enabled through comments in the script.
2. For all of the XenServers in a given pool, mount the new /snapshots share. 
3. Finish creating a share directory structure that meets your needs. Here are the VmBackup.py default subdirectories which can be changed:
   - /snapshots/BACKUPS - this is for all VM backups
   - /snapshots/NAUbackup - this is for the VmBackup.py script, any config files, and the status.log summary file.
   - /snapshots/NAUbackup/logs - this is for redirecting your cronjob VmBackup.py output.
4. Download VmBackup.py, example.cfg, README.md to your execution location, such as /snapshots/NAUbackup
5. Inspect and customize the comments in page one of the VmBackup.py code. Here are some of the changes you may want to configure:
 - Find text HARD CODED DEFAULTS - these values are in effect anytime you run VmBackup.py with a command line vm-selector. Many of these code defaults can also be overridden in the config-file.
 - Find text OPTIONAL - if you want an automatic email to be sent at end of VmBackup then follow the instructions for the label MAIL_ENABLE. 
6. Install the XenServer Software Development Kit from www.citrix.com/downloads - download the XenServer and copy file XenAPI.py into the same directory where VmBackup.py exists.
   - To verfy XenApi, execute VmBackup with a valid password and some simple vm-name.
   - Example: ./VmBackup.py password vm-name preview 
   - Note: if password has any special characters, then escape with back slash: ./VmBackup.py pass\$word vm-name
7. Follow some VmBackup usage examples in the next section and try some examples with your VMs. Initially use the `preview` option, followed by a non-preview execution to actually see the VM export process. If you have a test XenServer environment, then utilize this for test verification.
8. VM Recovery testing is an important part of the setup, see later section. Become familiar with the /snapshots/BACKUPS/vm-name directory structure and file contents, also in later section. After backing up some VMs then restore them on a test system and verify VM functionality.
9. Plan your backup strategy, such as weekly, bi-monthly, monthly frequencies. How many copies of each backup do you want to keep? How long do your backup configurations take to execute and does this fit in with your XenServer processing priorities?
10. Execute your plan which typically involves setting up a XenServer crontab schedule, see later section.

## Usage Examples

### VmBackup.py Command Usage

#### Basic usage:

	./VmBackup.py
	
	Usage:
	./VmBackup.py  <password> <config-file|vm-selector> [preview] [other optional params]
	
	Also: VmBackup.py help    - for additional parameter usage
	  or: VmBackup.py config  - for config-file parameter usage
	  or: VmBackup.py example - for some simple example usage


#### Detail usage:

	./VmBackup.py help
  
	Usage-help:
	./VmBackup.py  <password|password-file> <config-file|vm-selector> [preview] [other optional params]

	required params:
  		<password|password-file> - xenserver password or obscured password stored in password-file
  		<config-file|vm-selector> - several options:
    		config-file - a common choice for production crontab execution
    		vm-selector - a single vm name or vm prefix wildcard that defaults to vm-export
    			note with vm-selector then config defaults are set from VmBackup.py default constantants
    		vm-export=vm-selector  - explicit vm-export
    		vdi-export=vm-selector - explicit vdi-export

	optional params:
  		[preview] - preview/validate VmBackup config parameters and xenserver password
  		[compress=True|False] - only for vm-export functions automatic compression (default: False)
  		[ignore_extra_keys=True|False] - some config files may have extra params (default: False)

	alternate form - create-password-file:
	./VmBackup.py  <password> create-password-file=filename

  		create-password-file=filename - create an obscured password file with the specified password
  		note - password filename is relative to current path or absolute path.


#### Config-file parameter usage:

	./VmBackup.py config
	
	Usage-config-file:

	# Example config file for VmBackup.py

	#### high level VmBackup settings ################
	#### note - if any of these are not specified ####
	####   then VmBackup uses default constants   ####

	# Take Xen Pool DB backup: 0=No, 1=Yes (script default to 0=No)
	pool_db_backup=0

	# How many backups to keep for each vm (script default to 4)
	max_backups=3

	# Note: All directories must already exist and have the correct
	# ownership and access protections set

	#Backup Directory path (script default /snapshots/BACKUPS)
	backup_dir=/path/to/backupspace

	#Log file Directory path
	# (script default /snapshots/NAUbackup/status.log)
	status_log=/path/to/backupspace/logs/status.log

	# applicable if vdi-export is used
	# vdi_export_format either raw or vhd (script default to raw)
	vdi_export_format=raw

	#### specific VMs backup settings ####

	#### ALL excludes must currently be defined BEFORE any VM selections ####
	# exclude selected VMs from VM wildcards
	exclude=PROD-WinDomainController
	exclude=DEV-DestructiveTest 
	exclude=TEMP-.*

	# vm-export VM name-label of vm to backup. One per line - notice :max_backups override.
	vm-export=my-vm-name
	vm-export=my-second-vm
	vm-export=my-third-vm:3

	# special vdi-export - only backs up first disk. See README Documenation!
	vdi-export=my-vm-name

	# vm-export using VM prefix wildcard - notice DEV.* has :max_backups overide
	# and note the necessary ".*" syntax needed to replicaite the "*" wildcard
	# syntax used in V3.0 and now deprecated. More detailed examples will
	# be discussed elsewhere
	vm-export=PROD.*
	vm-export=DEV.*:2
	# metadata-export using the same regex principle than vm-export
 	metadata-export=WEB.*

#### Some simple examples:

	./VmBackup.py example
	
	Usage-examples:

	# config file
	./VmBackup.py password weekend.cfg

	# single VM name, which is case sensitive
	./VmBackup.py password DEV-mySql

	# single VM name using vdi-export instead of vm-export
	./VmBackup.py password vdi-export=DEV-mySql

	# single VM name with spaces in name
	./VmBackup.py password "DEV mySql"

	# VM prefix wildcard - which may be more than one VM
	./VmBackup.py password DEV-my.*

	# all VMs in pool (the earlier "*" syntax is no longer valid)
	./VmBackup.py password .*
	
	Alternate form - create-password-file:
	# create password file from command line password
	./VmBackup.py password create-password-file=/root/VmBackup.pass

	# use password file + config file
	./VmBackup.py /root/VmBackup.pass monthly.cfg

### Preview Example #1 - VmBackup.py with vm-selector
 
 Preview is useful after config-file changes for production crontab backups that will run later.
 
**Example with errors present:**

	./VmBackup.py password DEV-mySql preview
	
	2016-01-29-(10:33:49) - VmBackup.py running with these settings:
	2016-01-29-(10:33:49) -   backup_dir        = /snapshots/BACKUPS
	2016-01-29-(10:33:49) -   status_log        = /snapshots/NAUbackup/status.log
	2016-01-29-(10:33:49) -   compress          = False
	2016-01-29-(10:33:49) -   max_backups       = 4
	2016-01-29-(10:33:49) -   vdi_export_format = raw
	2016-01-29-(10:33:49) -   pool_db_backup    = 0
	2016-01-29-(10:33:49) -   exclude (cnt)= 0
	2016-01-29-(10:33:49) -   exclude:
	2016-01-29-(10:33:49) -   vdi-export (cnt)= 0
	2016-01-29-(10:33:49) -   vdi-export:
	2016-01-29-(10:33:49) -   vm-export (cnt)= 1
	2016-01-29-(10:33:49) -   vm-export: DEV-mySql
	2016-01-29-(10:33:49) - ERROR - vm(s) List does not exist: DEV-mySql

**Example with errors resolved:**

	./VmBackup.py password "DEV mySql" preview
	
	2016-01-29-(10:33:49) - VmBackup.py running with these settings:
	2016-01-29-(10:33:49) -   backup_dir        = /snapshots/BACKUPS
	2016-01-29-(10:33:49) -   status_log        = /snapshots/NAUbackup/status.log
	2016-01-29-(10:33:49) -   compress          = False
	2016-01-29-(10:33:49) -   max_backups       = 4
	2016-01-29-(10:33:49) -   vdi_export_format = raw
	2016-01-29-(10:33:49) -   pool_db_backup    = 0
	2016-01-29-(10:33:49) -   exclude (cnt)= 0
	2016-01-29-(10:33:49) -   exclude:
	2016-01-29-(10:33:49) -   vdi-export (cnt)= 0
	2016-01-29-(10:33:49) -   vdi-export:
	2016-01-29-(10:33:49) -   vm-export (cnt)= 1
	2016-01-29-(10:33:49) -   vm-export: DEV mySql
	2016-01-29-(10:33:49) - SUCCESS preview parameters


### Preview Example #2 - VmBackup.py with config-file

Notice the besides preview error checking, the VM list scope is also shown.

**Example with configuration errors present:**

	cat weekend.cfg	
	
	# Weekend VMs - with VM name errors
	max_backups=4
	backup_dir=/snapshots/BACKUPS
	#
	vdi-export=PROD-CentOS7.large-user-disks
	vm-export=PROD.*
	vm-export=DEV-RH.*:3
	exclude=PROD-ubuntu12.benchmark

	./VmBackup.py password weekend.cfg preview
	
	2016-01-29-(10:58:59) - VmBackup.py running with these settings:
	2016-01-29-(10:58:59) -   backup_dir        = /snapshots/BACKUPS
	2016-01-29-(10:58:59) -   status_log        = /snapshots/NAUbackup/status.log
	2016-01-29-(10:58:59) -   compress          = False
	2016-01-29-(10:58:59) -   max_backups       = 4
	2016-01-29-(10:58:59) -   vdi_export_format = raw
	2016-01-29-(10:58:59) -   pool_db_backup    = 0
	2016-01-29-(10:58:59) -   exclude (cnt)= 1
	2016-01-29-(10:58:59) -   exclude: PROD-ubuntu12.xs66
	2016-01-29-(10:58:59) -   vdi-export (cnt)= 1
	2016-01-29-(10:58:59) -   vdi-export: PROD-CentOS7.large-user-disks
	2016-01-29-(10:58:59) -   vm-export (cnt)= 6
	2016-01-29-(10:58:59) -   vm-export: PROD-ubuntu14, PROD-ubuntu12-benchmark, PROD-CentOS7-large-user-disks, DEV-RH6:3, DEV-RH7:3, PROD-WinSvr
	2016-01-29-(10:58:59) - ERROR - vm(s) List does not exist: PROD-CentOS7.large-user-disks
	2016-01-29-(10:58:59) - ERROR - vm(s) Exclude does not exist: PROD-ubuntu12.benchmark

**Example with configuration errors resolved:**

	cat weekend.cfg
	
	# Weekend VMs - with VM name's fixed
	max_backups=4
	backup_dir=/snapshots/BACKUPS
	#
	vdi-export=PROD-CentOS7-large-user-disks
	vm-export=PROD.*
	vm-export=DEV-RH.*:3
	exclude=PROD-ubuntu12-benchmark

	./VmBackup.py password weekend.cfg preview
	
	2016-01-29-(11:02:17) - VmBackup.py running with these settings:
	2016-01-29-(11:02:17) -   backup_dir        = /snapshots/BACKUPS
	2016-01-29-(11:02:17) -   status_log        = /snapshots/NAUbackup/status.log
	2016-01-29-(11:02:17) -   compress          = False
	2016-01-29-(11:02:17) -   max_backups       = 4
	2016-01-29-(11:02:17) -   vdi_export_format = raw
	2016-01-29-(11:02:17) -   pool_db_backup    = 0
	2016-01-29-(11:02:17) -   exclude (cnt)= 1
	2016-01-29-(11:02:17) -   exclude: PROD-ubuntu12-benchmark
	2016-01-29-(11:02:17) -   vdi-export (cnt)= 1
	2016-01-29-(11:02:17) -   vdi-export: PROD-CentOS7-large-user-disks
	2016-01-29-(11:02:17) -   vm-export (cnt)= 4
	2016-01-29-(11:02:17) -   vm-export: PROD-ubuntu14, DEV-RH6:3, DEV-RH7:3, PROD-WinSvr
	2016-01-29-(11:02:17) - SUCCESS preview parameters


### Important Details About Python REGEX Syntax and Configuration File Differences

Handling of wildcard VMs has been expanded to incorporate the native python regex library of regular expressions. WARNING: The syntax is slightly different from what is processed with the Linux family of grep commands. Note in particular that the earlier wildcard prefix option in V3.0 using a single trailing asterisk "\*" will behave _differently_ under V3.1 and hence any older scripts should have such occurences changed instead to ".\*" to retain the same behavior! Failing to do so may result in unexpected results. This is because in python, a string followed by "*" causes the resulting regular expression to match zero or more repetitions of the preceding regular expression, as many repetitions as are possible. For example, ab* will match "a", "ab", or "a" followed by any number of "b" characters. Therefore, if you had PRD-a* before, this will now match PRD-a, PRD-aa, PRD-aaaSomething, as well as PRD- but _also_ PRD-Test, PRD-123 and anything else starting with PRD- since zero occurences of the "a" after the "-" are matched. To avoid this, PRD-a.* should be used, instead, indicating in this case PRD-a followed by any single character (".") zero or more("*") times.

Note that the current implementation uses the re.match function which by design is expected to be front-anachored. You can explicitly preface a search string with the "^" operator, if desired, but it is already implied and the results will be the same.

A VM name is considered to be a simple (non-wildcard) name, provided that it contains only combinations of any of the following: letters (upper as well as lower case), numerals 0 through 9, the space charachter, hyphens (dashes), and underscore characters. These will _no_t be handled using regex operations!

Here are some examples of regex selections. Note that if a vdi-export definition is encouteded in the configuration file before a matching vm-export definition, the vdi-export will take precedence. Recall also that exclude definitions must appear first in the script before any VDI or VM definitions and will be appled to all vdi-export and vm-export rules.

	# exclude simple host names (non-wildcard instances)
	exclude=DEV-phishing-test
	exclude=PRD-PRINTER1

	# exclude using end-of-string - handled as a regex expression
	exclude=PRD-PRINT$

	# exclude PRD-a as well as PRD-a followed by anything (note the use of ".*" instead of "*")
	exclude=PRD-a.*

	# exclude DEV-V followed by anything followed by TEMP and anding in TEMP (end-of-string)
	exclude=DEV-V.*TEMP$

	# back up just the root VDI of DEV-web3
	vdi-export=DEV-web3

	# the same as above, except retain seven copies
	vdi-export=DEV-web3:7

	# back up just the root VDI for anything strting with DEV followed by anything, followed
	# by either the string "TEST" or the string "test" followed by anything else
	vdi-export=DEV-.*(TEST|test).*

	# The same as above, except using the string "Test" or "test"
	vdi-export=DEV-.*[Tt]est.*

	# back up VMs ending with the string SAVE and keeping five versions
	vm-export=.*SAVE$:5

	# back up VMs starting with PRD- and ending with print4 or print5 and save five versions
	vm-export=PRD-.*print[4-5]$:5

	# back up VMs starting with PRD- and ending with print6, print7 or print8 and save ten versions
	vm-export=PRD-.*print[6-8]$:10

	# back up VMs starting with PRD- and ending with print followed by any number(s) and ending
	# in that same string of numbers and save eight versions
	vm-export=PRD-.*print[\d{1,}]$:8

Note that there are numerous combinations that may possily conflict with each other or potentially overlap. It is strongly encouraged to use the "preview" option to review the configuration output before putting into service.


### Python REGEX Syntax Errors

In the even of a regex error, the script will deliberately fail as otherwise, results may be unpredictable and/or undesirabrle. Regex errors will be shown when using the preview option, and it is recommended to check the syntax ahead of implementing any scripts into actual use. For example, if instead of vm-export=PRD-[aA].* you had created a line reading vm-export=PRD-[aA.* (with a missing square bracket), the resulting error message would include output similar to this:

2016-11-03-(12:34:02) - ***ERROR - invalid regex: vm-export=PRD-[aA.*
.
.
.
2016-11-03-(12:34:04) - ERROR regex errors found (see above)  - WARNINGS found (see above)

You should then correct any such errors. Because of the rich number of options available, typos still can be interperted as perfectly valid regex syntax, hence again, a preview of the results is stronly encouraged. A good source on python regex syntax can be found at: https://docs.python.org/2/library/re.html


### Common cronjob Example

Typically you will want to run the cron with an input config file and redirected output file in case any run time errors occur.

	10 0 * * 6 /usr/bin/python /snapshots/NAUbackup/VmBackup.py password \
	/snapshots/NAUbackup/example.cfg >> /snapshots/NAUbackup/logs/VmBackup.log 2>&1

Provide the password for the user `root`. If it contains special characters, make sure to set it in single quotes, e.g. `'your*Password'`.

### VM selection and max_backups operations

The vm-export and vdi-export each have an associated process list where each entry is of the form vm-name:max_backups. The :max_backups is optional, and if specified then is the maximum number of backups to maintain for this vm-name. Otherwise, the global max_backups is in effect for the given vm-name. At the completion of every successful VM vm-export/vdi-operation, the oldest backup(s) are deleted using the in effect vm-name:max_backups value.

The following VM selection operations apply to both the vm-export and vdi-export; (1) load all single vm-name:max_backups with no wildcard into the associated process list, (2) for any VM-regex:max_backups, query the XenServer and load each applicable vm-name into the associated process list and do not replace the VMs from step 1, then finally (3) remove any excluded VMs (both simple and regex-based) from the process list VMs. By using the `preview` option then the scope of the given VmBackup run is clearly defined.

For any individual VmBackup.py run, then any single VM should preferably not be in both vm-export and vdi-export process lists, otherwise confusion or a potential error could occur; a VM found in a vdi-export list will take precedence over a matching entry in a vm-export list. The convention is that a VM is backed up with a vm-export or a vdi-export, but not both. If at some point in time a VM grows in number of /dev/xvdX disks where it is required to switch from vm-export to vdi-export, then the same /snapshots/BACKUPS/vm-name structure continues. Since in this case the backups are ordered by date with a mix of vdi-export and older vm-export backups, then eventually the vm-export backups will be deleted. One technique to save any of the older vm-exports from automatically deleting is to simply rename /snapshots/BACKSUPS/vm-name to /snapshots/BACKSUPS/vm-name_xva at time of the conversion to vdi-export.
 

### VM Backup Directory Structure

The VM backup directory has this format %BACKUP_DIR%/vm-name/date-time/ and each VM backup directory contains the vm backup file plus additional VM metadata. 

Each successful backup directory is marked by a touched file of `success` and in some special cases may include `success_other-actions`. These situations may be reviewed in the VmBackup code.

The number of VM backups saved is based upon the config max_backups value. For example, if max_backups=3 and when the forth successful backup completes, then the oldest backup directory date-time will be deleted.

As each new VM backup begins, then a check is made to ensure that the last VM backup was successful. If it was not successful then the previous failed backup directory will be deleted.

#### VM Backup File Types
The vm backup file has one of three possible formats, (a) vm-name.vxa which is created from a vm-export command, (b) vm-name.raw which is created from vdi-export and vdi-export-form=raw, or (c) vm-name.vhd which is created from vdi-export and vdi-export-form=vhd.

#### Additional VM Metadata
For each backup directory, there is a dump of selected XenServer VM metadata. This information can be useful in certain recovery situations.

* vm.cfg - includes name_label, name_description, memory_dynamic_max, VCPUs_max, VCPUs_at_startup, os_version, orig_uuid
* DISK-xvda (for each attached disk)
	* vbd.cfg - includes userdevice, bootable, mode, type, unplugable, empty, orig_uuid
	* vdi.cfg - includes name_label, name_description, virtual_size, type, sharable, read_only, orig_uuid, orig_sr_uuid 
* VIFs (for each attached VIF)
  * vif-0.cfg - includes device, network_name_label, MTU, MAC, other_config, orig_uuid


## Restore
### VM Restore from the vm-export backup
Use the `xe vm-import` command. See `xe help vm-import` for parameter options. In particular, attention should be paid to the "preserve" option, which if specified as `preserve=true` will re-create as many of the original settings as possible, such as the associated VM UUID values along with the network and MAC addresses.

### VDI Restore from the vdi-export backup
Use the `xe vdi-import` command. See `xe help vdi-import` for parameter options. However, the current Citrix documentation is lacking and the best vdi-import examples can be found at http://wiki.xensource.com/wiki/Disk_import/export_APIs

**For each Xenserver installation where the choice is made to use the vdi-export backup mechanism, then it is imperative that you test a VM restore procedure for your specific Xenserver VM envirionment**

An outline of what has worked for us is provided:

1. Create a new VM with no attached virtual disks. This can be obtained a number of ways. One method is to restore another VM of the exact same OS version as the candidate VM you need to restore and remove all virtual disks that from the new VM you have just restored. Also review and set the VM memory, cpu, and network requirements.
2. Create a new VDI with the same size as the original /dev/xvda boot disk. The size can be found in the %BACKUP_DIR%/vm-name/date-time/DISK-xvda/vdi.cfg virtual_size=xxxxxxxx value.
	- NEW_VDI_UUID=$(xe vdi-create name-label=your-name sr-uuid=your-sr-uuid type=system virtual-size=xxxxxxxx)
	- echo $NEW_VDI_UUID
3. Restore from your vdi-export file which will either be format=raw or format=vhd. For the following example we use a raw vdi-export.
	- xe vdi-import uuid=$NEW_VDI_UUID filename=path-of-your-vdi-backup.raw format=raw
	- If any error messages then analyze the issue.
4. From XenCenter attach the new restored VDI to the new candidate VM and try to boot the VM up. **Note if the original VM were production and still live, then you will need to beware that this new VM may intefere with the production VM network availability, so take the necessary precautions that this restore does not cause a VM network conflict.**

### Pool Restore from the config pool_db_backup=1
If config pool_db_backup=1 has been specified then a %BACKUP_DIR%/METADATA_host-name/pool_db_date-time.dump file will be created.

In the situation where the pool is corrupt and no hosts will start in the pool then it may be necessary to restore and rebuild the XenServer pool. **This decision should be carefully reviewed with advice from Citrix Support.** Consult the Citrix XenServer Administrator's Guide chapter 8 and review sections that discuss the `xe pool-restore-database` command.

