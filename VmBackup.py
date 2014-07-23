#!/usr/bin/python

# Copyright (C) 2009-2014, Northern Arizona University (NAU)
# Information Technology Services, Academic Computing SCAN division.
# Use of this software is "as-is".  NAU takes no responsibility
# for the results of making use of this or related programs and any data
# directly or indirectly affected.

# Title: a XenServer simple vm backup script
# Package Contents: README, VmBackup.py (this file), example.cfg
# Version History
# - v2.0 2014/04/09 New VmBackup version (supersedes all previous NAUbackup versions)

# ** DO NOT RUN THIS SCRIPT UNLESS YOU ARE COMFORTABLE WITH THESE ACTIONS. **
# => To accomplish the vm backup this script uses the following xe commands:
#   (a) vm-snapshot, (b) template-param-set, (c) vm-export, (d) vm-uninstall,
#   where vm-uninstall is against the snapshot uuid.

# See README for usage and installation documentation.
# See example.cfg for config file example usage.

# Usage w/ vm name for single vm backup:
#    ./VmBackup.py <password> <vm-name>

# Usage w/ config file for multiple vm backups:
#    ./VmBackup.py <password> <config-file-path>

import sys, time, os, datetime, subprocess, re, shutil, XenAPI
from subprocess import PIPE
from subprocess import STDOUT
from os.path import join

#############################
# modify these hard coded default values, only used if not specified in config file
DEFAULT_POOL_DB_BACKUP = 0
DEFAULT_MAX_BACKUPS = 4
DEFAULT_BACKUP_DIR = '/snapshots/BACKUPS'
BACKUP_DIR_PATTERN = '%s/backup-%04d-%02d-%02d-(%02d:%02d:%02d)'

config = {}
expected_keys = ['pool_db_backup', 'max_backups', 'backup_dir', 'vm-export']
message = ''
xe_path = '/opt/xensource/bin' 
status_log = '/snapshots/NAUbackup/status.log'

def main(session): 

    success = True
    warning = False
    success_cnt = 0
    warning_cnt = 0
    error_cnt = 0 

    #setting autoflush on (aka unbuffered)
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
    
    #server_name = run_get_lastline('/bin/hostname -s')
    server_name = os.uname()[1].split('.')[0]
    log('VmBackup config loaded from: %s' % cfg_file)

    if config_specified:
        status_log_begin(server_name)

    log('===========================')
    log('VmBackup running on %s ...' % server_name)
    df_snapshots('Space before backups: df -Th %s' % config['backup_dir'])

    if int(config['pool_db_backup']):
        log('*** begin backup_pool_metadata ***')
        if not backup_pool_metadata(server_name):
            success = False
            error_cnt += 1 

    ######################################################################
    # Iterate through all vm-export= in cfg
    log('************ vm-export= ***************')
    for vm_parm in config['vm-export']:
        log('*** vm-export begin %s' % vm_parm)
        beginTime = datetime.datetime.now()
        this_success = True

        # check for optional vm=VM-NAME:MAX-BACKUP override
        if (vm_parm.find(':') == -1):
            vm_name = vm_parm
            vm_max_backups = int(config['max_backups'])
        else:
            (vm_name,tmp_max_backups) = vm_parm.split(':')
            vm_max_backups = int(tmp_max_backups)
            if (vm_max_backups < 1):
                vm_max_backups = int(config['max_backups'])

        # verify vm_name exists with only one instance for this name
        vm = session.xenapi.VM.get_by_name_label(vm_name)
        if (len(vm) > 1):
            log('ERROR more than one vm with the name %s' % vm_name)
            success = False
            error_cnt += 1 
            if config_specified:
                status_log_vm_export(server_name, 'DUP-NAME %s' % vm_name)
            # next vm
            continue
        elif (len(vm) == 0):
            log('WARNING no machines found with the name %s' % vm_name)
            warning = True
            warning_cnt += 1
            if config_specified:
                status_log_vm_export(server_name, 'NOT-FOUND %s' % vm_name)
            # next vm
            continue 

        vm_record = session.xenapi.VM.get_record(vm[0])

        vm_backup_dir = os.path.join(config['backup_dir'], vm_name) 
        if (not os.path.exists(vm_backup_dir)):
            # Create new dir
            try:
                os.mkdir(vm_backup_dir)
            except OSError, error:
                log('ERROR creating directory %s' % vm_backup_dir)
                success = False
                error_cnt += 1 
                # fatal, stop all vm backups
                break

        # if last backup was not successful, then delete it
        dir_not_success = get_last_backup_dir_that_failed(vm_backup_dir)
        if (dir_not_success):
            if (not os.path.exists(vm_backup_dir + '/' + dir_not_success + '/fail')):
                log ('Delete last **unsuccessful** backup %s/%s ' % (vm_backup_dir, dir_not_success))

                try:
                    shutil.rmtree(vm_backup_dir + '/' + dir_not_success)
                except OSError, error:
                    log ('ERROR deleting unsuccessful backup %s/%s ' % (vm_backup_dir, dir_not_success))
                    # for this error, keep working on vm backup
                    # note this is only case where this_success is false
                    this_success = False
                    success = False
                    error_cnt += 1 

        # create new backup dir
        backup_dir = get_backup_dir(vm_backup_dir)
        if not backup_dir:
            log ('ERROR no backup dir exists %s ' % vm_backup_dir)
            success = False
            error_cnt += 1 
            # next vm
            continue

        # Backup vm meta data
        log ('Writing vm config file.')
        vm_out = open ('%s/vm.cfg' % backup_dir, 'w')
        vm_out.write('name_label=%s\n' % vm_record['name_label'])
        vm_out.write('name_description=%s\n' % vm_record['name_description'])
        vm_out.write('memory_dynamic_max=%s\n' % vm_record['memory_dynamic_max'])
        vm_out.write('VCPUs_max=%s\n' % vm_record['VCPUs_max'])
        vm_out.write('VCPUs_at_startup=%s\n' % vm_record['VCPUs_at_startup'])
        vm_out.write('os_version=%s\n' % get_os_version(vm_record['uuid']))
        # get orig uuid for special metadata disaster recovery
        vm_out.write('orig_uuid=%s\n' % vm_record['uuid'])
        vm_uuid = vm_record['uuid']
        vm_out.close()
       
        # Write metadata files for vdis and vbds.  These end up inside of a DISK- directory.
        log ('Writing disk info')
        for vbd in vm_record['VBDs']:
            vbd_record = session.xenapi.VBD.get_record(vbd)  
            # For each vbd, find out if its a disk
            if vbd_record['type'].lower() != 'disk':
                continue
            vdi_record = session.xenapi.VDI.get_record(vbd_record['VDI'])

            log('Backing up disk: %s - begin' % vdi_record['name_label'])

            # now write out the vbd info.
            device_path = '%s/DISK-%s' % (backup_dir,  vbd_record['device'])
            os.mkdir(device_path)
            vbd_out = open('%s/vbd.cfg' % device_path, 'w')
            vbd_out.write('userdevice=%s\n' % vbd_record['userdevice'])
            vbd_out.write('bootable=%s\n' % vbd_record['bootable'])
            vbd_out.write('mode=%s\n' % vbd_record['mode'])
            vbd_out.write('type=%s\n' % vbd_record['type'])
            vbd_out.write('unpluggable=%s\n' % vbd_record['unpluggable'])
            vbd_out.write('empty=%s\n' % vbd_record['empty'])
            # get orig uuid for special metadata disaster recovery
            vbd_out.write('orig_uuid=%s\n' % vbd_record['uuid'])
            # other_config and qos stuff is not backed up
            vbd_out.close()

            # now write out the vdi info.
            vdi_out = open('%s/vdi.cfg' % device_path, 'w')
            vdi_out.write('name_label=%s\n' % vdi_record['name_label'])
            vdi_out.write('name_description=%s\n' % vdi_record['name_description'])
            vdi_out.write('virtual_size=%s\n' % vdi_record['virtual_size'])
            vdi_out.write('type=%s\n' % vdi_record['type'])
            vdi_out.write('sharable=%s\n' % vdi_record['sharable'])
            vdi_out.write('read_only=%s\n' % vdi_record['read_only'])
            # get orig uuid for special metadata disaster recovery
            vdi_out.write('orig_uuid=%s\n' % vdi_record['uuid'])
            sr_uuid = session.xenapi.SR.get_record(vdi_record['SR'])['uuid']
            vdi_out.write('orig_sr_uuid=%s\n' % sr_uuid)
            # other_config and qos stuff is not backed up
            vdi_out.close()

        # Write metadata files for vifs.  These are put in VIFs directory
        log ('Writing VIF info')
        for vif in vm_record['VIFs']:
            vif_record = session.xenapi.VIF.get_record(vif)
            log ('Writing VIF: %s' % vif_record['device'])
            device_path = '%s/VIFs' % backup_dir
            if (not os.path.exists(device_path)):
                os.mkdir(device_path)
            vif_out = open('%s/vif-%s.cfg' % (device_path, vif_record['device']), 'w') 
            vif_out.write('device=%s\n' % vif_record['device'])
            network_name = session.xenapi.network.get_record(vif_record['network'])['name_label']
            vif_out.write('network_name_label=%s\n' % network_name)
            vif_out.write('MTU=%s\n' % vif_record['MTU'])
            vif_out.write('MAC=%s\n' % vif_record['MAC'])
            vif_out.write('other_config=%s\n' % vif_record['other_config'])
            vif_out.write('orig_uuid=%s\n' % vif_record['uuid'])
            vif_out.close()

        # is vm currently running?
        cmd = '%s/xe vm-list name-label=%s params=power-state | grep running' % (xe_path, vm_name)
        if run_log_out_wait_rc(cmd) == 0:
            log ('vm is running')
        else:
            log ('vm is NOT running')

        # take a snapshot of this vm
        snap_name = 'RESTORE_%s' % vm_name
        log ('snap_name: %s  vm_uuid: %s' % (snap_name,vm_uuid))
        cmd = '%s/xe vm-snapshot vm=%s new-name-label=%s' % (xe_path, vm_uuid, snap_name)
        log('1.cmd: %s' % cmd)
        snap_uuid = run_get_lastline(cmd)
        log ('snap-uuid: %s' % snap_uuid)
        if snap_uuid == '':
            log('ERROR %s' % cmd)
            success = False
            error_cnt += 1 
            if config_specified:
                status_log_vm_export(server_name, 'SNAPSHOT-FAIL %s' % vm_name)
            # next vm
            continue

        # change snapshot so that it can be referenced by vm-export
        cmd = '%s/xe template-param-set is-a-template=false ha-always-run=false uuid=%s' % (xe_path, snap_uuid)
        log('2.cmd: %s' % cmd)
        if run_log_out_wait_rc(cmd) != 0:
            log('ERROR %s' % cmd)
            success = False
            error_cnt += 1 
            if config_specified:
                status_log_vm_export(server_name, 'PARAM-SET-FAIL %s' % vm_name)
            # next vm
            continue
    
        # vm-export snapshot
        cmd = '%s/xe vm-export uuid=%s' % (xe_path, snap_uuid)
        if compress:
            xva_file = os.path.join(backup_dir, vm_name + '.xva.gz')
            cmd = '%s filename="%s" compress=true' % (cmd, xva_file)
        else:
            xva_file = os.path.join(backup_dir, vm_name + '.xva')
            cmd = '%s filename="%s"' % (cmd, xva_file) 
        log('3.cmd: %s' % cmd)
        if run_log_out_wait_rc(cmd) == 0:
            log('vm-export success')
        else:
            log('ERROR %s' % cmd)
            success = False
            error_cnt += 1 
            if config_specified:
                status_log_vm_export(server_name, 'VM-EXPORT-FAIL %s' % vm_name)
            # next vm
            continue
    
        # vm-uninstall snapshot
        cmd = '%s/xe vm-uninstall uuid=%s force=true' % (xe_path, snap_uuid)
        log('4.cmd: %s' % cmd)
        if run_log_out_wait_rc(cmd) != 0:
            log('WARNING-ERROR %s' % cmd)
            warning = True
            warning_cnt += 1
            if config_specified:
                status_log_vm_export(server_name, 'VM-UNINSTALL-FAIL %s' % vm_name)

        log ('*** vm-export end')
        elapseTime = datetime.datetime.now() - beginTime
        xva_size = os.path.getsize(xva_file) / (1024 * 1024 * 1024)

        if (this_success):
            # mark this a successful backup, note: this will 'touch' a file named 'success'
            # if backup size is greater than 60G, then nfs server side compression occurs
            if xva_size > 60:
                log('*** LARGE FILE > 60G: %s : %sG' % (xva_file, xva_size))
                # forced compression via background gzip (requires nfs server side script)
                open('%s/success_compress' % backup_dir, 'w').close()
                log('*** success_compress: %s : %sG' % (xva_file, xva_size))
            else:
                open('%s/success' % backup_dir, 'w').close()
                log('*** success: %s : %sG' % (xva_file, xva_size))

            if (are_all_backups_successful(vm_backup_dir)):
                success_cnt += 1
            else:
                log('**WARNING** cleanup needed - not all backup history is successful')
                warning = True
                warning_cnt += 1
            
            # Remove oldest if more than vm_max_backups
            dir_to_remove = get_dir_to_remove(vm_backup_dir, vm_max_backups)
            while (dir_to_remove):
                log ('Deleting oldest backup %s/%s ' % (vm_backup_dir, dir_to_remove))
                try:
                    shutil.rmtree(vm_backup_dir + '/' + dir_to_remove)
                except OSError, error:
                    log ('ERROR deleting backup %s/%s ' % (vm_backup_dir, dir_to_remove))
                    success = False
                    break
                dir_to_remove = get_dir_to_remove(vm_backup_dir, vm_max_backups)

            log('VmBackup vm %s - ***Success*** t:%s' % (vm_name, str(elapseTime.seconds/60)))
            if config_specified:
                status_log_vm_export(server_name, 'SUCCESS %s,elapse:%s size:%sG' % (vm_name, str(elapseTime.seconds/60), xva_size))

        else:
            log('VmBackup vm %s - +++ERROR+++ t:%s' % (vm_name, str(elapseTime.seconds/60)))
            if config_specified:
                status_log_vm_export(server_name, 'ERROR %s,elapse:%s size:%sG' % (vm_name, str(elapseTime.seconds/60), xva_size))

    # end of for vm_parm in config['vm-export']:
    ######################################################################

    log('===========================')
    df_snapshots('Space status: df -Th %s' % config['backup_dir'])

    # gather a final VmBackup.py status
    summary = 'S:%s W:%s E:%s' % (success_cnt, warning_cnt, error_cnt)
    if (not success):
        if config_specified:
            status_log_end(server_name, 'ERROR,%s' % summary)
        log('VmBackup ended - **ERRORS DETECTED** - %s' % summary)
    elif (warning):
        if config_specified:
            status_log_end(server_name, 'WARNING,%s' % summary)
        log('VmBackup ended - **Warning(s)** - %s' % summary)
    else:
        if config_specified:
            status_log_end(server_name, 'SUCCESS,%s' % summary)
        log('VmBackup ended - Success - %s' % summary)

    # done with main()
    ######################################################################

# Setup backup dir structure
def get_backup_dir(base_path):
    # Check that directory exists
    if not os.path.exists(base_path):
        # Create new dir
        try:
            os.mkdir(base_path)
        except OSError, error:
            log('ERROR creating directory %s : %s' % (base_path, error.as_string()))
            return False

    date = datetime.datetime.today()
    #backup_dir = '%s/backup-%04d-%02d-%02d-(%02d:%02d:%02d)' 
    backup_dir = BACKUP_DIR_PATTERN \
    % (base_path, date.year, date.month, date.day, date.hour, date.minute, date.second)
    print 'backup_dir: %s' % backup_dir

    if not os.path.exists(backup_dir):
        # Create new dir
        try:
            os.mkdir(backup_dir)
        except OSError, error:
            log('ERROR creating directory %s : %s' % (backup_dir, error.as_string()))
            return False

    return backup_dir

# Setup meta dir structure
def get_meta_path(base_path):
    # Check that directory exists
    if not os.path.exists(base_path):
        # Create new dir
        try:
            os.mkdir(base_path)
        except OSError, error:
            log('ERROR creating directory %s : %s' % (base_path, error.as_string()))
            return False

    date = datetime.datetime.today()
    backup_path = '%s/pool_db-%04d%02d%02d-%02d%02d%02d.dump' \
    % (base_path, date.year, date.month, date.day, date.hour, date.minute, date.second)

    return backup_path

def get_dir_to_remove(path, numbackups):
    # Find oldest backup and select for deletion
    dirs = os.listdir(path)
    dirs.sort()
    if (len(dirs) > numbackups and len(dirs) > 1):
        return dirs[0]
    else:
        return False

def get_last_backup_dir_that_failed(path):
    # if the last backup dir was not success, then return that backup dir
    dirs = os.listdir(path)
    if (len(dirs) <= 1):
        return False
    dirs.sort()
    # note: dirs[-1] is the last entry
    if (not os.path.exists(path + '/' + dirs[-1] + '/success')) and (not os.path.exists(path + '/' + dirs[-1] + '/success_restore')) and (not os.path.exists(path + '/' + dirs[-1] + '/success_compress' )) and (not os.path.exists(path + '/' + dirs[-1] + '/success_compressing' )):
        return dirs[-1]
    else:
        return False

def are_all_backups_successful(path):
    # expect at least one backup dir, and all should be successful
    dirs = os.listdir(path)
    if (len(dirs) == 0):
        return False
    for dir in dirs:
        if (not os.path.exists(path + '/' + dir + '/success' )) and (not os.path.exists(path + '/' + dir + '/success_restore' )) and (not os.path.exists(path + '/' + dir + '/success_compress' )) and (not os.path.exists(path + '/' + dirs[-1] + '/success_compressing' )):
            return False
    return True

def backup_pool_metadata(svr_name):

    # xe-backup-metadata can only run on master
    if not is_xe_master():
        log('** ignore: NOT master')
        return True

    metadata_base = os.path.join(config['backup_dir'], 'METADATA_' + svr_name)
    metadata_file = get_meta_path(metadata_base)

    cmd = "%s/xe pool-dump-database file-name='%s'" % (xe_path, metadata_file)
    log(cmd)
    if run_log_out_wait_rc(cmd) != 0:
        log('ERROR failed to backup pool metadata')
        return False

    return True

# some run notes with xe return code and output examples
#  xe vm-lisX -> error .returncode=1 w/ error msg
#  xe vm-list name-label=BAD-vm-name -> success .returncode=0 with no output
#  xe pool-dump-database file-name=<dup-file-already-exists> 
#     -> error .returncode=1 w/ error msg
def run_log_out_wait_rc(cmd, log_w_timestamp=True):
    #child = subprocess.Popen(cmd.split(' '), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    child = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
    line = child.stdout.readline()
    while line:
        log(line.rstrip("\n"), log_w_timestamp)
        line = child.stdout.readline()
    return child.wait()

def run_get_lastline(cmd):
    # exec cmd - expect 1 line output from cmd
    # return last line
    f = os.popen(cmd)
    resp = ''
    for line in f.readlines():
        resp = line.rstrip("\n")
    return resp

def get_os_version(uuid):
    f = os.popen('%s/xe vm-list params=os-version uuid=%s' % (xe_path, uuid))
    for line in f.readlines():
        if re.search('([Mm]icrosoft|[Ww]indows)',line):
            return 'windows'
        elif re.search('[Ll]inux',line):
            return 'linux'
    return 'unknown'

def df_snapshots(log_msg):
    log(log_msg)
    f = os.popen('df -Th %s' % config['backup_dir'])
    for line in f.readlines():
        line = line.rstrip("\n")
        log(line)

def is_xe_master():
    # test to see if we are running on xe master

    cmd = '%s/xe pool-list params=master --minimal' % xe_path
    master_uuid = run_get_lastline(cmd)

    hostname = os.uname()[1]
    cmd = '%s/xe host-list name-label=%s --minimal' % (xe_path, hostname)
    host_uuid = run_get_lastline(cmd)

    if host_uuid == master_uuid:
        return True

    return False

def config_verify():

    if not (int(config['pool_db_backup']) >= 0 and int(config['pool_db_backup']) <= 1):
        print 'ERROR: config pool_db_backup -> %s' % config['pool_db_backup']
        return False
 
    if not (int(config['max_backups']) > 0):
        print 'ERROR: config max_backups -> %s' % config['max_backups']
        return False

    if not os.path.exists(config['backup_dir']):
        print 'ERROR: config backup_dir does not exist -> %s' % config['backup_dir']
        return False

    return True

def config_load(path):
    return_value = True
    config_file = open(path, 'r')
    for line in config_file:
        if (not line.startswith('#') and len(line.strip()) > 0):
            (key,value) = line.strip().split('=')
            key = key.strip()
            value = value.strip()
            if not key in expected_keys:
                if allow_extra_keys:
                    log('ignoring config key: %s' % key)
                else:
                    print '***unexpected config key: %s' % key
                    return_value = False
            if key in config.keys():
                if type(config[key]) is list:
                    config[key].append(value)
                else:
                    config[key] = [config[key], value]
            else:
                config[key] = value

    return return_value

def config_defaults():
    # init config with default values
    if not 'pool_db_backup' in config.keys():
        config['pool_db_backup'] = str(DEFAULT_POOL_DB_BACKUP)
    if not 'max_backups' in config.keys():
        config['max_backups'] = str(DEFAULT_MAX_BACKUPS)
    if not 'backup_dir' in config.keys():
        config['backup_dir'] = str(DEFAULT_BACKUP_DIR)

def config_print():
    log('VmBackup.py running with these settings:')
    log('  backup_dir     = %s' % config['backup_dir'])
    log('  compress       = %s' % compress)
    log('  max_backups    = %s' % config['max_backups'])
    log('  pool_db_backup = %s' % config['pool_db_backup'])
    log('  vm-export (cnt)= %s' % len(config['vm-export']))
    str = ''
    for vm_parm in config['vm-export']:
        str += '%s, ' % vm_parm
    if len(str) > 1:
        str = str[:-2]
    log('    %s' % str)

def status_log_begin(server):
    rec_begin = '%s,vmbackup.py,%s,begin\n' % (fmtDateTime(), server)
    open(status_log,'a',0).write(rec_begin)

def status_log_end(server, status):
    rec_end = '%s,vmbackup.py,%s,end,%s\n' % (fmtDateTime(), server, status)
    open(status_log,'a',0).write(rec_end)

def status_log_vm_export(server, status):
    rec_end = '%s,vm-export,%s,end,%s\n' % (fmtDateTime(), server, status)
    open(status_log,'a',0).write(rec_end)

def fmtDateTime():
    date = datetime.datetime.today()
    str = '%02d/%02d/%02d %02d:%02d:%02d' \
        % (date.year, date.month, date.day, date.hour, date.minute, date.second)
    return str

def log(mes, log_w_timestamp=True):
    # note - send_email uses message
    global message

    date = datetime.datetime.today()
    if log_w_timestamp:
        str = '%02d-%02d-%02d-(%02d:%02d:%02d) - %s\n' \
            % (date.year, date.month, date.day, date.hour, date.minute, date.second, mes)
    else:
        str = '%s\n' % mes
    message += str

    #if verbose: (old option, now always verbose)
    str = str.rstrip("\n")
    print str
    sys.stdout.flush()
    sys.stderr.flush()

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print 'Usage:'
        print sys.argv[0], ' <password> <config-file|vm-name> [compress=True|False] [allow_extra_keys=True|False'
        print sys.argv[0], ' == default ==>  compress=False  allow_extra_keys=False'
        sys.exit(1)
    password = sys.argv[1]
    cfg_file = sys.argv[2]

    # loop through remaining optional args
    arg_range = range(3,len(sys.argv))

    compress = False                # default
    allow_extra_keys = False # default
    for arg_ix in arg_range:
        if sys.argv[arg_ix].lower() == 'compress=true':
            compress = True
        if sys.argv[arg_ix].lower() == 'compress=false':
            compress = False
        if sys.argv[arg_ix].lower() == 'allow_extra_keys=true':
            allow_extra_keys = True
        if sys.argv[arg_ix].lower() == 'allow_extra_keys=false':
            allow_extra_keys = False

    # init vm-export list
    if not 'vm-export' in config:
        config['vm-export'] = []
    # process config file
    if (os.path.exists(cfg_file)):
        config_specified = 1
        if not config_load(cfg_file):
            print 'ERROR in config_load, consider allow_extra_keys=true'
            sys.exit(1)
        # set defaults if not loaded from config_load()
        config_defaults()
    else:
        config_specified = 0
        config['vm-export'].append(cfg_file)
        config_defaults()

    config_print()
    
    if not config_verify():
        print 'ERROR in configuration settings...'
        sys.exit(1)

    # acquire a xapi session by logging in
    try:
        username = 'root'
        session = XenAPI.Session('https://localhost/')
        session.xenapi.login_with_password(username, password)
        hosts = session.xenapi.host.get_all()
    except XenAPI.Failure, e:
        print e
        if e.details[0] == 'HOST_IS_SLAVE':
            session = XenAPI.Session('https://' + e.details[1])
            session.xenapi.login_with_password(username, password)
            hosts = session.xenapi.host.get_all()
        else:
            print 'ERROR - XenAPI authentication error'
            sys.exit(1)

    if not config_specified:
        # verify vm exists
        vm = session.xenapi.VM.get_by_name_label(cfg_file)
        if (len(vm) == 0):
            print 'ERROR - vm does not exist: %s' % cfg_file
            sys.exit(1)

    try:
        main(session)

    except Exception, e:
        print e
        log('***ERROR EXCEPTION - %s' % sys.exc_info()[0])
        log('***ERROR NOTE: see VmBackup output for details')
        raise
