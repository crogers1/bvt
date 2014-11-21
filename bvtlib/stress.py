#
#   Standalone stress tests for XT based systems.
#
#

import sets
from string import replace
from time import sleep
from bvtlib.run import run
from bvtlib.run import writefile, readfile
from bvtlib.wait_for_windows import wait_for_guest_to_go_down
from bvtlib.wait_to_come_up import check_up
from bvtlib.settings import VM_MEMORY_ASSUMED_OVERHEAD_MEGABYTES
from bvtlib.domains import list_vms

HIDDEN_GUEST_MEMORY = 256
FILE_PATH = "/storage/testing-template"
TEMPLATE_ITERATIONS = 200
PRIMARY_TEMPLATE_PATH = "/usr/share/xenmgr-1.0/templates/default/"

class UnableToEstablishMemoryFree(Exception):
    """Couldn't parse the free memory for a xenops phsyinfo"""

class MultiVMStartStopTestFailure(Exception):
    """Test failed, see stdout for failure reason"""

class TimeoutException(Exception):
    """We timed out in one of these tests"""

class MissingVHDError(Exception):
    """Named VHD is missing on host"""

class InsufficientMemoryOnHostException(Exception):
    """Host doesn't have enough free memory to run the test"""

class IncrementalTestException(Exception):
    """Test failed, see stdout for failure reason"""

class TemplateNotSupportedException(Exception):
    """Template type specified is not supported"""

#-----------------utility functions-------------------#

def customize_template(host, kind, mem="1024"):
    """Read in an existing template, make modifications and write back to
       host machine as a separate file."""

    disk_entry = """      "0": {
        "path": "\/storage\/disks\/",
        "type": "vhd",
        "mode": "w",
        "device": "hda",
        "devtype": "disk",
        "shared": "true"
      },"""

    hidden_entry = """  "hidden": "true",\n  "hidden-in-ui": "true",\n  "slot": "-1" """

    def req_hidden(lined_content):
        lined_content[-3] = lined_content[-3]+','
        lined_content.insert(len(lined_content)-2, hidden_entry)
        return lined_content
   
    def req_disk(lined_content):
        index = 0
        for index, line in enumerate(lined_content):
            if "disk" in line:
                lined_content[index+1] = lined_content[index+1].replace('0','1')
                lined_content.insert(index+1, disk_entry)
                break
        return lined_content

    def mem_change(lined_content, memory):
        index = 0
        for index, line in enumerate(lined_content):
            if "memory" in line:
                lined_content[index] = line.replace(line[line.find(':'):], ': "'+memory+'",')
                break
        return lined_content

    def empty():
        return "new-vm-empty"

    def linux():
        return "new-vm-linux"
        
    def bypass():
        return "new-vm-linux"   
 
    options = {"empty" : empty,
               "linux" : linux,
               "bypass" : bypass,
              }
   
    content = readfile(PRIMARY_TEMPLATE_PATH+options[kind](), host=host)
    lined_content = content.split('\n')

    if kind == "empty":     
        out = req_hidden(lined_content)
    elif kind == "linux":   
        out = req_disk(lined_content)
    elif kind == "bypass":
        lined_content = req_hidden(lined_content)
        lined_content = req_disk(lined_content)
        out = mem_change(lined_content, mem)
    else:
        print 'INFO: Template type not supported.'
        raise TemplateNotSupportedException()
     
    writefile(FILE_PATH, '\n'.join(out), host=host)


def parse_physinfo(physinfo):
    
    for line in physinfo:
        spl = line.split()
        if spl[:2] == ['nr_cpus', '=']:
            cores = int(spl[2][0:])     #Number of cores visible to dom0
        if spl[:2] == ['free_pages', '=']:
            free_mem = int(spl[3][1:])

    return cores, free_mem
        

#NOTE: An actual 8-core machine should able to handle more than a quad-core 
#      hyperthreaded machine, but for now let's set the upper limit to 16 vms.
#      Don't have access to anything with 8 physical cores.
def calculate_multitest_limits(host):
    """Estimate a reasonable value for max_vms and sleep_time based on system hardware."""

    max_vms = 1
    sleep_time = 10
    physinfo = run(['xenops', 'physinfo'], host=host, line_split=True)
    cores, free_mem = parse_physinfo(physinfo)
   
    if cores < 8:       #Gated by available cores.  Probably can't handle more than 8 vms
        max_vms = 8
        sleep_time = 60
    else:               #We have enough cores, now gated by free memory available.
        if free_mem < 3072:
            max_vms = 8
            sleep_time = 60
        elif free_mem < 4096:
            max_vms = 12
            sleep_time = 90
        else:
            max_vms = 16
            sleep_time = 120
    
    return max_vms, sleep_time
        

def report_failures(states, guest_uuids, target_state):
    """Print uuids of guests that failed to reach a target state."""

    for i in range(0, len(states)):
        if states[i] != target_state:
            print 'INFO: Guest %s failed to achieve the target state %s' % \
                (guest_uuids[i].split('-')[0], target_state)


def verify_states_running(states):
    """Verify that all guest states have the value of 'running'."""
    
    if len(sets.Set(states)) == 1: #1 set means all entries are the same
        if states[0] == 'running':  #if the first entry is 'running' they all are 
            return True
    return False

    
def verify_states_stopped(states):
    """Verify that all guest states have the value of 'stopped'."""

    if len(sets.Set(states)) == 1:
        if states[0] == 'stopped': 
            return True
    return False


def have_free_mem(host):
    """Implements the memory check portion of check_free"""

    out = run(['xenops', 'physinfo'], host=host, line_split=True)
    freemem = None
    for line in out:
        spl = line.split()
        if len(spl) == 5 and spl[:2] == ['free_pages', '=']:
            freemem = int(spl[3][1:])
    if freemem is None:
        raise UnableToEstablishMemoryFree(out)

    vm_off_mem = 0
    for vm in list_vms(host):
        if vm['status'] != 'running':
            vm_mem = run(['xec-vm', '-u', vm['uuid'], 'get', 'memory'], host=host)
            try:
                vm_off_mem += (int(vm_mem.split()[0])+
                                VM_MEMORY_ASSUMED_OVERHEAD_MEGABYTES)
            except ValueError:
                print 'Error'
    if freemem < HIDDEN_GUEST_MEMORY + vm_off_mem:
        return False
    return True

def multi_vm_test_clean(max_vms, guest_uuids, disks, host):
    """Clean up the environment that we created for the multi_vm test."""

    for i in range(0, max_vms):
        run(['xec-vm', '-u', guest_uuids[i], 'destroy'], host=host)
        run(['xec-vm', '-u', guest_uuids[i], 'delete'], host=host)
        run(['rm', disks[i]], host=host)
    run(['rm', FILE_PATH], host=host)


def create_and_install_guests(host, vhd_path, num_vms, kind, mem=1024):
    """Uses templates and a local VHD to quickly create a new guest for stress testing."""

    guest_uuids = []
    disks = []
    #send the template to the host
    customize_template(host, kind, mem)
    for i in range(0, num_vms):
        uuid = run(['xec', 'create-vm-with-template', FILE_PATH], host=host, line_split=True)
        guest_uuids.append(replace(uuid[0].strip('/vm/'), '_', '-'))
        print 'INFO: guest_uuid:', guest_uuids[i]
        #Name the disk after the first oct of the uuid
        disks.append('/storage/disks/' + guest_uuids[i].split('-')[0] + '.vhd')
        run(['vhd-util', 'snapshot', '-n', disks[i], '-p', vhd_path], host=host)
        run(['xec-vm', '-u', guest_uuids[i], '-k', '0', 'set', 'phys-path', disks[i]], host=host)
        run(['xec-vm', '-u', guest_uuids[i], 'set', 'name', guest_uuids[i].split('-')[0]], host=host)

    return guest_uuids, disks 


def verify_guest_state(host, guest_uuid):
    """Verifies the state of a single guest is stopped"""

    sleep(5)
    state = run(['xec-vm', '-u', guest_uuid[0], 'get', 'state'], host=host, line_split=True)
    if state[0] != 'stopped':
        print 'INFO: Guest failed to stop, exiting'
        raise IncrementalTestException()

def get_names(host, guest_uuids):
    """For each guest, return it's name in a list."""

    names = []
    for i in range(0, len(guest_uuids)):
        names.append(run(['xec-vm', '-u', guest_uuids[i], 'get', 'name'], host=host, \
                line_split=True)[0])
    return names
        

#--------------------Tests---------------------------#

def vm_up_down(host, vhd_path, iterations=1):
    """Back to back vm start and forced vm shutdown of 2 VMs, boots will be incomplete
        Styled after XenRT testcase"""

    print 'INFO: Preparing system for test...'

    #Verify vhd exists
    out = run(['ls', vhd_path], host=host)
    if out.split('\n')[0] != vhd_path:
        raise MissingVHDError()

    guest_uuids, disks = create_and_install_guests(host, vhd_path, 2, "linux")
    names = get_names(host, guest_uuids) 
    print 'INFO: Guest names:', names

    #Ensure they are shutdown first
    run(['xec-vm', '-u', guest_uuids[0], 'shutdown'], host=host, timeout=60)
    wait_for_guest_to_go_down(host, names[0])
    
    run(['xec-vm', '-u', guest_uuids[1], 'shutdown'], host=host, timeout=60)
    wait_for_guest_to_go_down(host, names[1])

    print 'INFO: Sleeping for 5 seconds prior to test'
    sleep(5)
    
    print 'INFO: Beginning test execution for a duration of %s iterations' % iterations
    for i in range(0, iterations):
        run(['xec-vm', '-n', names[0], 'start'], host=host)
        run(['xec-vm', '-n', names[1], 'start'], host=host)
        sleep(5)
        run(['xec-vm', '-n', names[0], 'destroy'], host=host)
        run(['xec-vm', '-n', names[1], 'destroy'], host=host)
        sleep(5)
    
    check_up(host)
    print 'INFO: PASS... Test complete for %s iterations, host is stable' % iterations
    print 'INFO: Cleaning up'
    
    run(['xec-vm', '-n', names[0], 'delete'], host=host)
    run(['xec-vm', '-n', names[1], 'delete'], host=host)
    run(['rm', disks[0]], host=host)
    run(['rm', disks[1]], host=host)
    run(['rm', FILE_PATH], host=host)

def multi_vm_start_stop(host, vhd_path, iterations=1):
    """Start/stop a large number of guests simultaneously and verify the host is
    still healthy."""
   
    max_vms, sleep_val = calculate_multitest_limits(host)
    guest_uuids = []
    disks = []
    state = [0] *max_vms

    print 'INFO: Preparing system for test...'

    #Verify we have enough memory to run the test
    if not have_free_mem(host):
        raise InsufficientMemoryOnHostException()

    #Verify that the base VHD exists
    out = run(['ls', vhd_path], host=host)
    if out.split('\n')[0] != vhd_path:
        raise MissingVHDError()
    
    guest_uuids, disks = create_and_install_guests(host, vhd_path, max_vms, "bypass", "256")

    print 'INFO: Beginning test'

    for i in range(0, max_vms):
        run(['xec-vm', '-u', guest_uuids[i], 'start'], host=host, wait=False)

    print 'INFO: Sleeping while guests start'
    sleep(sleep_val)   #Give em some time to start

    for i in range(max_vms):
        state[i] = (run(['xec-vm', '-u', guest_uuids[i], 'get', 'state'], host=host, \
                line_split=True))[0]
    all_running = verify_states_running(state)

    if not all_running:
        #last chance
        print 'INFO: Sleeping again while guests attempt to start'
        sleep(sleep_val)
        for i in range(0, max_vms):
            state[i] = (run(['xec-vm', '-u', guest_uuids[i], 'get', 'state'], host=host, \
                    line_split=True))[0]
        all_running = verify_states_running(state)
        if not all_running:
            report_failures(state, guest_uuids, 'running')
            multi_vm_test_clean(max_vms, guest_uuids, disks, host)
            raise MultiVMStartStopTestFailure(Exception)

    check_up(host)  #Verify host is still reachable, if we got here it probably is.

    for i in range(0, max_vms):
        run(['xec-vm', '-u', guest_uuids[i], 'shutdown'], host=host, wait=False)
        
    print 'INFO: Sleeping while guests stop'
    sleep(sleep_val)   #Give em some time to stop

    for i in range(0, max_vms):
        state[i] = (run(['xec-vm', '-u', guest_uuids[i], 'get', 'state'], host=host, \
                    line_split=True))[0]
    all_stopped = verify_states_stopped(state)
        
    if not all_stopped:
        #last chance
        #issue the command again
        for i in range(0, max_vms):
            run(['xec-vm', '-u', guest_uuids[i], 'shutdown'], host=host, wait=False)
        print 'INFO: Sleeping again while guests attempt to stop'
        sleep(sleep_val)

        for i in range(0, max_vms):
            state[i] = (run(['xec-vm', '-u', guest_uuids[i], 'get', 'state'], host=host, \
                    line_split=True))[0]
        all_stopped = verify_states_stopped(state)
        if not all_stopped:
            report_failures(state, guest_uuids, 'stopped')
            multi_vm_test_clean(max_vms, guest_uuids, disks, host)
            raise MultiVMStartStopTestFailure(Exception)

    check_up(host)  #Verify host is still reachable.
    
    multi_vm_test_clean(max_vms, guest_uuids, disks, host)
    
    print 'INFO: PASS... Multiple parallel VM start and stop test completed successfully.'

        
def create_from_template(host):
    """Create a single vm from template and then delete it a large number of times. """
   
    customize_template(host, "bypass") 

    for i in range(0, TEMPLATE_ITERATIONS):
        print 'INFO: Iteration %d' % i
        uuid = run(['xec', 'create-vm-with-template', FILE_PATH], host=host, line_split=True)
        uuid = (replace(uuid[0].strip('/vm/'), '_', '-'))
        run(['xec-vm', '-u', uuid, 'delete'], host=host)
    run(['rm', FILE_PATH], host=host)


def incremental_guest_reboot(host, vhd_path):
    """Test for stability after starting and destroying a guest, increase incrementally."""

    print 'INFO: Installing guest VM for test.'
    guest_uuid, disk = create_and_install_guests(host, vhd_path, 1, "linux")

    def hard_reboot_op():
        run(['xec-vm', '-u', guest_uuid[0], 'start'], host=host)
        run(['xec-vm', '-u', guest_uuid[0], 'destroy'], host=host)
 
    print 'INFO: Beginning incremental reboot test. Starting 50 iterations'
    for i in range(0, 50):
        hard_reboot_op()

    verify_guest_state(host, guest_uuid)

    print 'INFO: Starting 100 iterations'
    for i in range(0, 100):
        hard_reboot_op()
   
    verify_guest_state(host, guest_uuid)

    print 'INFO: Starting 200 iterations' 
    for i in range(0, 200):
        hard_reboot_op()
        
    verify_guest_state(host, guest_uuid)

    print 'INFO: Starting 500 iterations' 
    for i in range(0, 500):
        hard_reboot_op()
    
    verify_guest_state(host, guest_uuid)

    check_up(host)
    
    print 'INFO: PASS... Passed incremental reboot test.'
    
    run(['xec-vm', '-u', guest_uuid[0], 'destroy'], host=host)
    run(['xec-vm', '-u', guest_uuid[0], 'delete'], host=host)
    run(['rm', disk[0]], host=host)
    run(['rm', FILE_PATH], host=host)

def get_vhd(host, vhd_url, base_name="base.vhd"):
   
    DESTPATH = "/storage/disks/"
    run(['wget', '-q', '-O', DESTPATH+base_name, vhd_url], host=host, timeout=7200)

    

TEST_CASES = [
    {'description':'Back to back start and shutdown of two guests',
     'function':vm_up_down, 'trigger':'stress',
     'bvt':True, 'command_line_options': ['--upDownStress'],
     'arguments': [('host', '$(DUT)'),
                   ('vhd_path', '$(VHD_NAME)')]},

    {'description':'Start and stop large number of guests simultaneously',
     'function':multi_vm_start_stop, 'trigger':'stress',
     'bvt':True, 'command_line_options': ['--multiStress'],
     'arguments': [('host', '$(DUT)'),
                   ('vhd_path', '$(VHD_NAME)')]},

    {'description':'Create a vm from template and delete it a large number of times',
     'function':create_from_template, 'trigger':'stress',
     'bvt':True, 'command_line_options': ['--templateStress'],
     'arguments': [('host', '$(DUT)')]},

    {'description':'Start and --force stop a guest an incrementally increasing number of times',
     'function':incremental_guest_reboot, 'trigger':'stress',
     'bvt':True, 'command_line_options': ['--incrementalReboot'],
     'arguments': [('host', '$(DUT)'),('vhd_path', '$(VHD_NAME)')]},

    {'description':'Utility function to download a vhd',
     'function':get_vhd, 'trigger':'stress',
     'bvt':True, 'command_line_options': ['--getVHD'],
     'arguments': [('host', '$(DUT)'),('vhd_url', '$(VHD_URL)'),('base_name', '$(VHD_NAME)')]}
]
    
