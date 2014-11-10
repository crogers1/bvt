#
#   Standalone stress tests for XT based systems.
#
#

import sets
from string import replace
from time import sleep
from bvtlib.run import run
from bvtlib.run import writefile
from bvtlib.wait_for_windows import wait_for_guest_to_go_down
from bvtlib.wait_to_come_up import check_up
from bvtlib.settings import VM_MEMORY_ASSUMED_OVERHEAD_MEGABYTES
from bvtlib.domains import list_vms
from bvtlib.templates import EMPTY_TEMPLATE, MAX_BYPASS_TEMPLATE, LINUX_TEMPLATE

#Matches memory value in the Bypass Template. 
HIDDEN_GUEST_MEMORY=256

FILE_PATH="/storage/testing-template"

class UnableToEstablishMemoryFree(Exception):
    """Couldn't parse the free memory for a xenops phsyinfo"""

class multiVMStartStopTestFailure(Exception):
    """Test failed, see stdout for failure reason"""

class TimeoutException(Exception):
    """We timed out in one of these tests"""

class MissingVHDError(Exception):
    """Named VHD is missing on host"""

class InsufficientMemoryOnHostException(Exception):
    """Host doesn't have enough free memory to run the test"""

class IncrementalTestException(Exception):
    """Test failed, see stdout for failure reason"""

#-----------------utility functions-------------------#

def report_failures(states, guest_uuids, target_state):
    for i in range(0, len(states)):
        if(states[i] != target_state):
            print 'INFO: Guest %s failed to achieve the target state %s' % \
                (guest_uuids[i].split('-')[0], target_state)

def verify_states_running(states):
    
    if(len(sets.Set(states)) == 1): #1 set means all entries are the same
        if states[0] == 'running':  #if the first entry is 'running' they all are 
            return True
    return False
    
def verify_states_stopped(states):
    
    if(len(sets.Set(states)) == 1): #1 set means all entries are the same
        if states[0] == 'stopped':  #if the first entry is 'running' they all are 
            return True
    return False

#Duplicates part of check_free, maybe try and just use check_free?
def have_free_mem(host, max_vms):
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
    if freemem < 256 + vm_off_mem:
        return False
    return True

def multiVMTestClean(max_vms, guest_uuids, disks, host):
    for i in range(0, max_vms):
        run(['xec-vm', '-u', guest_uuids[i], 'destroy'], host=host)
        run(['xec-vm', '-u', guest_uuids[i], 'delete'], host=host)
        run(['rm', disks[i]], host=host)
    run(['rm', FILE_PATH], host=host)

# Uses templates and a local VHD to quickly create a new guest for stress testing.
def createAndInstallGuests(host, vhd_path, num_vms, template):
    guest_uuids = []
    disks = []
    #send the template to the host
    writefile(FILE_PATH, template, host=host)
    for i in range(0, num_vms):
        uuid = run(['xec', 'create-vm-with-template', FILE_PATH], host=host, line_split=True)
        guest_uuids.append(replace(uuid[0].strip('/vm/'),'_', '-'))
        print 'INFO dbg guest_uuid:',guest_uuids[i]
        #Name the disk after the first oct of the uuid
        disks.append('/storage/disks/' + guest_uuids[i].split('-')[0] + '.vhd')
        run(['vhd-util', 'snapshot', '-n', disks[i], '-p', vhd_path], host=host)
        run(['xec-vm', '-u', guest_uuids[i], '-k', '0', 'set', 'phys-path', disks[i]], host=host)
        run(['xec-vm', '-u', guest_uuids[i], 'set', 'name', guest_uuids[i].split('-')[0]],host=host)

    return guest_uuids, disks 

#Verifies the state of a single guest is stopped
def verifyGuestState(host, guest_uuid):
    sleep(5)
    state = run(['xec-vm', '-u', guest_uuid[0], 'get', 'state'], host=host, line_split=True)
    if(state[0] != 'stopped'):
        print 'INFO: Guest failed to stop, exiting'
        #probably need to clean the VM but what to do if destroy doesn't stop it?
        raise IncrementalTestException()

def getNames(host, guest_uuids):
    names = []
    for i in range(0, len(guest_uuids)):
        names.append(run(['xec-vm', '-u', guest_uuids[i], 'get', 'name'], host=host, \
                line_split=True)[0])
    return names
        

#--------------------Tests---------------------------#

def vmUpDown(host, vhd_path, iterations=1):
    """Back to back vm start and forced vm shutdown of 2 VMs, boots will be incomplete
        Styled after XenRT testcase"""
    #Verify vhd exists
    out = run(['ls', vhd_path],host=host)
    if out.split('\n')[0] != vhd_path:
        raise MissingVHDError()

    #Prep the system
    guest_uuids, disks = createAndInstallGuests(host, vhd_path, 2, LINUX_TEMPLATE)
    names = getNames(host, guest_uuids) 
    print 'INFO dbg: Names:', names

    #Ensure they are shutdown first
    run(['xec-vm', '-u', guest_uuids[0], 'shutdown'],host=host,timeout=60)
    wait_for_guest_to_go_down(host, names[0])
    
    run(['xec-vm', '-u', guest_uuids[1], 'shutdown'],host=host,timeout=60)
    wait_for_guest_to_go_down(host, names[1])

    print 'INFO: Sleeping for 5 seconds prior to test'
    sleep(5)
    #Run the test
    print 'INFO: Beginning test execution for a duration of %s iterations' %iterations
    for i in range(0,iterations):
        run(['xec-vm', '-n', names[0], 'start'], host=host)
        run(['xec-vm', '-n', names[1], 'start'], host=host)
        sleep(5)
        run(['xec-vm', '-n', names[0], 'destroy'], host=host)
        run(['xec-vm', '-n', names[1], 'destroy'], host=host)
        sleep(5)
    
    check_up(host)
    print 'INFO PASS: Test complete for %s iterations, host is stable' %iterations
    print 'INFO: Cleaning up'
    
    #Clean up after ourselves.
    run(['xec-vm', '-n', names[0], 'delete'], host=host)
    run(['xec-vm', '-n', names[1], 'delete'], host=host)


#
# Start and stop a 'large' number of guests simultaneously and verify
# the host is still healthy.
# Tests should on failure, cleanup whatever got allocated.
#
def multiVMStartStop(host, vhd_path, iterations=1):
   
    max_vms = 15        #15 guests simultaneously might be the limit on this test machine
    sleep_val = 60      #This value should increase as the number of guests increases.
    guest_uuids = []
    disks = []
    state = [0] *max_vms
    #Verify we have enough memory to run the test
    if not have_free_mem(host, max_vms):
        raise InsufficientMemoryOnHostException()

    #Verify that the base VHD exists
    print 'INFO dbg path is type:', len(vhd_path)
    out = run(['ls', vhd_path],host=host)
    print 'INFO dbg out is type:', out.split('\n')[0] #strip the newline at the end of out
    if out.split('\n')[0] != vhd_path:
        raise MissingVHDError()
    
    guest_uuids, disks = createAndInstallGuests(host, vhd_path, max_vms, MAX_BYPASS_TEMPLATE)

    print 'INFO: Beginning test'

    for i in range(0, max_vms):
        run(['xec-vm', '-u', guest_uuids[i], 'start'], host=host, wait=False)

    print 'INFO: Sleeping while guests start'
    sleep(sleep_val)   #Give em some time to start

    for i in range(0, max_vms):
        state[i] = (run(['xec-vm', '-u', guest_uuids[i], 'get', 'state'], host=host, \
                line_split=True))[0]
    all_running = verify_states_running(state)

    if not all_running:
        #last chance
        #issue the command again
        for i in range(0, max_vms):
            run(['xec-vm', '-u', guest_uuids[i], 'start'], host=host, wait=False)
        print 'INFO: Sleeping again while guests attempt to start'
        sleep(sleep_val)
        for i in range(0, max_vms):
            state[i] = (run(['xec-vm', '-u', guest_uuids[i], 'get', 'state'], host=host, \
                    line_split=True))[0]
        all_running = verify_states_running(state)
        if not all_running:
            report_failures(state, guest_uuids, 'running')
            multiVMTestClean(max_vms, guest_uuids, disks, host)
            raise multiVMStartStopTestFailure(Exception)

    check_up(host)  #Verify host is still reachable, if we got here it probably is.

    #Shutdown the guests
    for i in range(0, max_vms):
        run(['xec-vm', '-u', guest_uuids[i], 'shutdown'], host=host, wait=False)
        
    print 'INFO: Sleeping while guests stop'
    sleep(sleep_val)   #Give em some time to stop, might need more than 30 seconds

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
            multiVMTestClean(max_vms, guest_uuids, disks, host)
            raise multiVMStartStopTestFailure(Exception)

    check_up(host)  #Verify host is still reachable, if we got here it probably is.
    
    multiVMTestClean(max_vms, guest_uuids, disks, host)
    
    print 'INFO PASS: Multiple parallel VM start and stop test completed successfully.'

        
# Create a single vm from template and then delete it 
# a large number of times. Looking to max out on Dbus match rules here
def createFromTemplate(host):
    writefile(FILE_PATH, EMPTY_TEMPLATE, host=host)

    for i in range(0,200):
        print 'INFO dbg: Iteration %d' %i
        uuid = run(['xec', 'create-vm-with-template', FILE_PATH], host=host, line_split=True)
        uuid = (replace(uuid[0].strip('/vm/'),'_', '-'))
        run(['xec-vm', '-u', uuid, 'delete'], host=host)
    run(['rm', FILE_PATH], host=host)


#Test for stability after starting and destroying a guest
#Increase the iterations incrementally.  If we pass 500, dat stuff is stable.
def incrementalGuestReboot(host, vhd_path):
    
    #Prep
    print 'INFO: Installing guest VM for test.'
    guest_uuid, disk = createAndInstallGuests(host, vhd_path, 1, LINUX_TEMPLATE)
    
    #run
    print 'INFO: Beginning incremental reboot test. Starting 50 iterations'
    for i in range(0, 50):
        run(['xec-vm', '-u', guest_uuid[0], 'start'], host=host)
        run(['xec-vm', '-u', guest_uuid[0], 'destroy'], host=host)

    verifyGuestState(host, guest_uuid)

    print 'INFO: Starting 100 iterations'
    for i in range(0, 100):
        run(['xec-vm', '-u', guest_uuid[0], 'start'], host=host)
        run(['xec-vm', '-u', guest_uuid[0], 'destroy'], host=host)
   
    verifyGuestState(host, guest_uuid)

    print 'INFO: Starting 200 iterations' 
    for i in range(0, 200):
        run(['xec-vm', '-u', guest_uuid[0], 'start'], host=host)
        run(['xec-vm', '-u', guest_uuid[0], 'destroy'], host=host)
        
    verifyGuestState(host, guest_uuid)

    print 'INFO: Starting 500 iterations' 
    for i in range(0, 500):
        run(['xec-vm', '-u', guest_uuid[0], 'start'], host=host)
        run(['xec-vm', '-u', guest_uuid[0], 'destroy'], host=host)
    
    verifyGuestState(host, guest_uuid)

    #is host still reachable?
    check_up(host)
    
    print 'INFO PASS: Passed incremental reboot test.'
    
    #cleanup
    run(['xec-vm', '-u', guest_uuid[0], 'destroy'], host=host)
    run(['xec-vm', '-u', guest_uuid[0], 'delete'], host=host)

def getVHD(host, vhd_url):
   
    #modify the DESTFILE to specify the target for your vhd download. 
    DESTFILE="/storage/disks/<vhd name here.vhd>"
    run(['wget', '-q', '-O', DESTFILE, vhd_url], host=host, timeout=7200)

    

TEST_CASES = [
    {'description':'Back to back start and shutdown of two guests',
     'function':vmUpDown, 'trigger':'stress',
     'bvt':True, 'command_line_options': ['--upDownStress'],
     'arguments': [('host', '$(DUT)'),
                   ('vhd_path', '$(VHD_URL)')]},

    {'description':'Start and stop large number of guests simultaneously',
     'function':multiVMStartStop, 'trigger':'stress',
     'bvt':True, 'command_line_options': ['--multiStress'],
     'arguments': [('host', '$(DUT)'),
                   ('vhd_path', '$(VHD_URL)')]},

    {'description':'Create a vm from template and delete it a large number of times',
     'function':createFromTemplate, 'trigger':'stress',
     'bvt':True, 'command_line_options': ['--templateStress'],
     'arguments': [('host', '$(DUT)')]},

    {'description':'Start and --force stop a guest an incrementally increasing number of times',
     'function':incrementalGuestReboot, 'trigger':'stress',
     'bvt':True, 'command_line_options': ['--incrementalReboot'],
     'arguments': [('host', '$(DUT)'),('vhd_path', '$(VHD_URL)')]},

    {'description':'Utility function to download a vhd',
     'function':getVHD, 'trigger':'stress',
     'bvt':True, 'command_line_options': ['--getVHD'],
     'arguments': [('host', '$(DUT)'),('vhd_url', '$(VHD_URL)')]}
]
    
