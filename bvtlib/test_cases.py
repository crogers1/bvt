#
# Copyright (c) 2013 Citrix Systems, Inc.
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

"""The master list of bvtlib test cases"""

from bvtlib import pxe_install_xc, network_test, install_python, boot_time
from bvtlib import install_guest, install_tools, accelerate_graphics
from bvtlib import vhdcompact_reboot, dbus_logger, installer_test
from bvtlib import store_status_report, soak, reboot_test
from bvtlib import partition_table_test, license_check
from bvtlib import switch_vm_loop, archive_vhd, ensure
from bvtlib import advertised_wireless, check_mac_addresses
from bvtlib import wireless_download, upgrade_latest_release
from bvtlib import admin_ui_check, authentication_test
from bvtlib import winsat, stubdom_boot, check_mounts
from bvtlib import testModules, XCXT, syncxt_test
from bvtlib import build_network_test_vm, vm_reboot
from bvtlib import install_network_test_vm
from bvtlib import vm_resource_leakage
from bvtlib import enforce_encrypted_disks
from bvtlib import stress

TEST_CASES = (pxe_install_xc.TEST_CASES + network_test.TEST_CASES +
              install_python.TEST_CASES + boot_time.TEST_CASES + 
              check_mac_addresses.TEST_CASES +
              advertised_wireless.TEST_CASES + wireless_download.TEST_CASES +
              soak.TEST_CASES + accelerate_graphics.TEST_CASES +
              install_guest.TEST_CASES + install_tools.TEST_CASES +
              list(vhdcompact_reboot.make_test_cases()) +
              archive_vhd.TEST_CASES + 
              dbus_logger.TEST_CASES + installer_test.TEST_CASES +
              partition_table_test.TEST_CASES + license_check.TEST_CASES +
              store_status_report.TEST_CASES + reboot_test.TEST_CASES +
              switch_vm_loop.TEST_CASES + ensure.TEST_CASES +
              admin_ui_check.TEST_CASES + authentication_test.TEST_CASES +
              winsat.TEST_CASES + stubdom_boot.TEST_CASES +
              check_mounts.TEST_CASES + syncxt_test.TEST_CASES + 
              testModules.TEST_CASES + XCXT.TEST_CASES +
              upgrade_latest_release.TEST_CASES +
              build_network_test_vm.TEST_CASES +
              install_network_test_vm.TEST_CASES +
              vm_resource_leakage.TEST_CASES + vm_reboot.TEST_CASES +
              enforce_encrypted_disks.TEST_CASES + stress.TEST_CASES)
