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

from re import compile

TAG_REGEXP = compile(r'cam-oe(prod|test)-[0-9]{6}-.*')

class BadTag(Exception):
    """Tag does not match expected pattern"""

def is_tag(tag):
    """Return truish if tag is in an expected format"""
    return TAG_REGEXP.match(tag)

def check_tag(tag):
    """Raise BadTag if tag does not match standard XT tag format"""
    if not is_tag(tag):
        raise BadTag(tag)

def extract_build_number(tag):
    """Return build number in tag as in integer, or raise BadTag"""
    check_tag(tag)
    return int(tag.split('-')[2])

def extract_branch(tag):
    """Extract branch name from tag, or raise BadTag"""
    check_tag(tag)
    return tag.split('-', 3)[-1]

def extract_kind(tag):
    """Extract kind, e.g. cam-oeprod from tag, or raise BadTag"""
    check_tag(tag)
    spl = tag.split('-')
    return spl[0]+'-'+spl[1]
