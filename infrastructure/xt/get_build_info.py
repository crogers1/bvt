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

"""Work out information about a build, using a config file or using the old
convention if that config file is not present"""

from os.path import isfile

BUILD_PATH = 'setme/%s/%s' # add path to build directory here

class NoVanillaBuild(Exception):
    """Build has no vanilla (non-XT) variant."""

def get_build_info(branch, build, xt=True, build_dir=None):
    if build_dir is None:
        build_dir = BUILD_PATH % (branch, build)
    try:
        info = {}
        info_file = build_dir +'/info'
        with open(info_file, 'r') as f:
            if not xt:
                raise NoVanillaBuild(branch, build)
            for line in f.read().splitlines():
                try:
                    key, value = line.split(': ', 1)
                except ValueError:
                    pass
                else:
                    info[key] = value
        return info
    except IOError:
        # Build is from old branch which doesn't have info file.
        suffix = '-kent' if xt else ''
        info = {'installer': 'iso/installer' + suffix + '.iso',
                'installer-trial': 'iso/installer-trial.iso',
                'netboot': 'netboot' + suffix,
                'sources': 'iso/source-1-of-2.iso iso/source-2-of-2.iso',
                'ota-update': 'update/update' + suffix + '.tar'}

        if isfile(build_dir+'/netboot-trial/pxelinux.cfg'):                                                                                                              
            info['netboot-trial'] = 'netboot-trial'
        return info
