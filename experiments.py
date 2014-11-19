#!/usr/bin/python
#
# Copyright (c) 2014 Citrix Systems, Inc.
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

from optparse import OptionParser
from bvtlib import test_names, test_cases, mongodb
from bvtlib.domains import find_domain, name_split, CannotFindDomain
from bvtlib.maybe import maybe
from bvtlib.validate_dut_name import validate_dut_name
from bvtlib.record_test import RecordTest
from bvtlib.settings import STATUS_REPORTS_ALWAYS, STATUS_REPORTS_NEVER
from bvtlib.run import run
from bvtlib.console_logging import ConsoleMonitor
from bvtlib.stdout_filter import StdoutFilter
from sys import exc_info
from random import choice
from pdb import post_mortem
from traceback import print_exc
from bvtlib.get_build import get_build
from bvtlib.mongodb import NoMongoHost

class NoValueForArgument(Exception):
    """We have no value for a test argument"""

class NoBuildFound(Exception):
    """Did not find suitable build in database"""

def set_experiment_install_flag(dut, value):
    """Set write flag for machine named dut"""
    try:
        mongodb.get_autotest().duts.update({'name':dut}, {'$set':{'write':value}})
    except NoMongoHost:
        print 'NOTE: no mongodb so not setting install flag'

def construct_arg_dict(options, guest, test_parameters, test_case, result_id, vhd_url, vhd_name):
    """Work out test arguments given options, guest and test parameters.
    Also returns an expanded test_paramters"""
    if guest is None: 
        os_name = 'dom0'
    else: 
        os_name, _ = name_split(guest)
        os_name = dict(test_names.ordering).get(os_name, os_name)

    specials = {
        '$(OS_NAME)' : os_name,
        '$(VHD_URL)': vhd_url,
        '$(PRESEVE_DATABASE)' : options.preserve_database,
        '$(RESULT_ID)' : result_id,
        '$(GUEST)' : guest,
        '$(VHD_NAME)': vhd_name}
    if options.machine:
        specials['$(DUT)'] = options.machine
    
    arg_dict = {}
    for name, value in test_case['arguments']:
        if type(value) == type('') and value.startswith('$('):
            if value == '$(BUILD)':
                if options.build or options.release:
                    ov = options.build
                else:
                    ov = get_build(options.machine)
            elif value == '$(RELEASE)':
                ov = options.release
            elif value == '$(MAC_ADDRESS)':
                ov = options.mac_address
            elif value in specials:
                ov = specials[value]
            elif value.startswith('$(') and value.endswith(')'):
                option_form = value[2:-1].lower()
                if hasattr(options, option_form):
                    ov = getattr(options, option_form)
                else:
                    raise NoValueForArgument(name, value)
        else:
            ov = value
        arg_dict[name] = ov

    des = test_case['description']
    for specialk, value in specials.items():
        if value is not None:
            des = des.replace(specialk, str(value))
    tpout = dict(test_parameters)
    tpout['description'] = des
    for k in test_case:
        tpout.setdefault(k, test_case[k])
    return arg_dict, tpout

def run_test(test_parameters, test_case, options, guest=None):
    """Invoke test_callback described by test_case if it can run in the 
    context of options for guest"""
    optlist = test_case.get('command_line_options', []) + test_case.get(
        'store_list', [])
    if optlist:
        assert optlist[-1].startswith('--')
        optname = optlist[-1][2:].replace('-', '_')
        if not getattr(options, optname): 
            return

    pred = test_case.get('options_predicate')
    if pred and not pred(options): 
        return

    try:
        with StdoutFilter(verbose=options.verbose) as logger:
            # XXX; we need to example arguments in test_case['description']
            # but do that in construct_arg_dict which requires result_id
            with RecordTest(record=options.record,
                            description=test_case['description'], 
                            build=options.build, 
                            dut=options.machine,
                            stdout_filter=logger) as recording:
                with ConsoleMonitor(options.machine, recording.result_id):
                    arg_dict, tps = construct_arg_dict(options, guest, 
                                                       test_parameters, 
                                                       test_case, 
                                                       recording.result_id,
                                                       options.vhd_url,
                                                       options.vhd_name)
                    recording.set_description(tps['description'])
                    return test_case['function'](**arg_dict)
    except Exception, exc:
        if options.debugger_on_failure:
            print_exc()
            post_mortem(exc_info()[2])
        else:
            raise

def do_iteration(i, options):
    """Do one iteration of the test loop"""
    set_experiment_install_flag(options.machine, 
                                (options.install_first or not 
                                 options.soak_power_level) and (i == 1))

    try:
        mdb = mongodb.get_autotest()
        dutdoc = mdb.duts.find_one({'name':options.machine}) 
    except NoMongoHost:
        dutdoc = {'write':True}
    write = (dutdoc if dutdoc else {}).get('write')
    test_parameters = {
        'dut':options.machine, 'record': options.record,
        'status_report_mode': STATUS_REPORTS_ALWAYS if 
         options.diagnostic_status_report else STATUS_REPORTS_NEVER,
        'stash_guests' : options.guest, 'verbose' : options.verbose,
        'stash_on_failure'  : options.stash_on_failure,
        'reinstall_on_failure' : options.reinstall_on_failure}
    def trigger_tests(condition, guest=None):
        """Trigger test cases matching condition for guest"""
        for test_case in test_cases.TEST_CASES:
            if test_case.get('trigger') == condition:
                run_test(test_parameters, test_case, options, guest)
    trigger_tests('first')        
    if write:
        trigger_tests('platform install')

    trigger_tests('build ready')
    trigger_tests('soakup')
    trigger_tests('platform ready')
    trigger_tests('stress')

    for guest in options.guest if options.guest else []:
        try:
            find_domain(options.machine, guest)
            have_domain = True
        except CannotFindDomain:
            have_domain = False
        print 'check for domain', guest, 'returned', have_domain
        write_guest = options.rebuild_vms or write or not have_domain 
        if write_guest:
            trigger_tests('VM install', guest)
        domain = find_domain(options.machine, guest)
        if domain['status'] == 'stopped':
            run(['xec-vm', '-n', domain['name'], 'start'], 
                host=options.machine, timeout=600)
        if write_guest:
            trigger_tests('VM configure', guest)
            trigger_tests('VM accelerate', guest)
        trigger_tests('VM ready', guest)
    trigger_tests('soakdown')

def top_loop(options):
    """Run tests repeatedly"""
    set_experiment_install_flag(options.machine, 1)
    i = 0
    while True:
        i += 1
        do_iteration(i, options)

        set_experiment_install_flag(
            options.machine, 0 if options.soak_power_level else 1)
        if options.loop_iterations is not None:
            if options.loop_iterations > i:
                break
        elif not options.loop:
            break
        print 'EXPERIMENTS: loop', i, options.loop_iterations, options.loop

def experiments():
    """Run test cases"""
    parser = OptionParser()
    parser.add_option(
        '-v', '--verbose', action='store_true',
        help='Show all logging on stdout')
    parser.add_option(
        '-m', '--machine',  metavar='MACHINE',
        help='Do test on MACHINE (e.g. kermit)')
    parser.add_option(
        '-g', '--guest', metavar='GUEST',action='append',
        help='Test vm GUEST (e.g. win7 or vista or xp). '
        'Optionally you may specify '
        'a name for the VM like this win7:fish xp:soup.')
    for test_case in test_cases.TEST_CASES:
        optlist = test_case.get('command_line_options')
        if optlist:
            parser.add_option(*optlist, **{'action' : 'store_true',
                                           'help':test_case['description']})
        store_list = test_case.get('store_list')
        if store_list:
            parser.add_option(*store_list, **{'action' : 'store',
                                           'help':test_case['description']})
    parser.add_option(
        '-b', '--build', action='store', 
        help='Have --xen-client install BUILD', metavar='BUILD')
    parser.add_option('--mac-address', metavar='MACADDRESS', 
                      help='Target machine has MACADDRESS (for PXE installs')
    parser.add_option(
        '--release', action='store', 
        help='Have --xen-client install RELEASE', metavar='RELEASE')
    parser.add_option(
        '-B', '--branch', action='store', 
        help='Have --xen-client install BRANCH. Ignored if '
        'build specified with --build', 
        metavar='BRANCH')
    parser.add_option(
        '-n', '--network-test', action='store_true', 
        help='Do some quick network traffic tests')
    parser.add_option(
        '-l', '--loop', action='store_true', help='Repeat until failure')
    parser.add_option(
        '-z', '--rebuild-vms', action='store_true',
        help='Rebuild VMs on each loop iteration')
    parser.add_option(
        '-c','--loop-iterations', metavar='NUMBER',
        help='Stop test loop after NUMBER iterations')
    parser.add_option(
        '--reboot', action='store', help='Enable reboot loop for N hours',
        metavar='N')
    parser.add_option(
        '--soak-power-level', action='append', metavar='LEVEL',
        help='Do soak test involving transition to LEVEL (e.g. s3)')
    parser.add_option(
        '--read-test', action='store_true',
        help='Do a read test when installing VHDs')
    parser.add_option(
        '-r', '--record', action='store_true', help='Store records in database')
    parser.add_option(
        '--synchronizer-name', action='store',
        help='Name of Synchronizer host to run tests against')
    parser.add_option( # XXX old remove me
        '--xcbe-version', action='store',
        help='X-XCBE-version header to send to Synchronizer')
    parser.add_option('-S', '--stash-on-failure', action='store_true',
                      help='Stash away VHDs on failure')
    parser.add_option('-R', '--reinstall-on-failure', action='store_true',
                      help='Reinstall after stress test failures')
    parser.add_option('-F', '--install-first', action='store_true',
                      help='Install at start, even for stress tests. '
                      'For non-stress tests (i.e. -s not specified) this is '
                      'standard behaviour so this option has no effect.')
    parser.add_option('--do-not-detect-build', action='store_true',
                      help='Do not detect the build')
    parser.add_option('--xen-server', action='store', metavar='SERVER',
                      help='Activate xen server')
    parser.add_option('-s', '--source-directory', action='store', 
                      metavar='DIRECTORY',
                      help='Assume extra source code for testing is '
                      'in DIRECTORY')
    parser.add_option('-D', '--debugger-on-failure', action='store_true',
                      help="Start PDB if a test failure occurs")
    parser.add_option('-E', '--encrypt-vhd', action='store_true',
                      help='Create encrypted VHD files during OS '
                      'install from ISO')
    parser.add_option('-P', '--preserve-database', action='store_true',
                      help='Preserve synchronizer database between runs')
    parser.add_option('--update-branch', action='store',
                      help='When upgrading deploy BRANCH', metavar='BRANCH')
    parser.add_option('--update-build', action='store',
                      help='When upgrading deploy BUILD', metavar='BUILD')
    parser.add_option('--build-type', action='store', default='oeprod',
                      metavar='KEYWORD', help='Use builds with type KEYWORD e.g. oeprod')
    parser.add_option('--vhd-url', action='store', metavar='URL',
                      help='Use VHD from URL')
    parser.add_option('--vm-reboot-toolstack', action='store_true',
                      help='Reboot the Windows VM using toolstack')
    parser.add_option('--vm-reboot-guest', action='store_true',
                      help='Reboot the Windows VM using a guest initiated shutdown')
    parser.add_option('--vhd-name', action='store', metavar='VHDNAME',
                       help='Use this name for the VHD at the destination')
    options, args = parser.parse_args()
    if args and options.machine is None:
        options.machine = args[0]
        args = args[1:]
    if options.build is None and options.release is None:
        branch = options.branch or 'master'
        query = {'branch':branch, 'build_type':options.build_type, 'suppress' : {'$exists':0}}
        if options.upgrade_xt or options.install_xt:
            build_doc = mongodb.get_autotest().builds.find_one(
                query,
                sort=[('tag_time', mongodb.DESCENDING)])
            if build_doc is None:
                raise NoBuildFound(query)
            print 'HEADLINE: chose %(_id)s on %(branch)s' % build_doc
            options.build = str(build_doc['_id'])
            assert branch == build_doc['branch']
    
    if options.machine:
        try:
            validate_dut_name(options.machine)
        except NoMongoHost:
            print 'NOTE: no mongodb so disabling DUT name validation'
    top_loop(options)

if __name__ == '__main__': 
    experiments()
