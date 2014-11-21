#
#   Stress tests for XT based systems.
#
#   Could design the different tests as classes and begin to move away from current bvt design
#   *Stick with bvt design, name the function for what it does and create the test_cases dict
#   for now...man but XenRT class design is so much cleaner *** maybe I should implement this
#   as an alternate option...
#

def vmUpDown(host, iterations, vhd_path):
    """Back to back vm start and vm shutdown of 2 windows VMs"""
    #maybe consider downloading/checking to see if the vhd is already there?
    #Prep the system
    guest1 = install_guest(host, guest="winguest1",kind="vhd",vhd_url=vhd_path)
    guest2 = install_guest(host, guest="winguest2",kind="vhd",vhd_url=vhd_path)
    
    #Ensure they are shutdown first
    run(['xec-vm', '-n', guest1, 'shutdown'],host=host,timeout=60)
    

    #Run the test
    for i in range(0,iterations):
        run(['xec-vm','-n',guest1,
        



