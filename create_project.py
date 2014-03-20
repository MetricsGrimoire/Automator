#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# This script parses IRC logs and stores the extracted data in
# a database
# 
# Copyright (C) 2014 Bitergia
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# Authors:
#   Alvaro del Castillo San Felix <acs@bitergia.com>
#

""" Tool for creating an Automator project from a basic config file """

import json
import logging
from optparse import OptionParser
import os.path
import sys
import urllib2, urllib
from ConfigParser import SafeConfigParser

def read_options():
    """Read options from command line."""
    parser = OptionParser(usage="usage: %prog [options]",
                          version="%prog 0.1")
    parser.add_option("-p", "--project",
                      action="store",
                      dest="project_file",
                      help="File with the project repositories to be analyzed")
    parser.add_option("-d", "--dir",
                      action="store",
                      dest="output_dir",
                      default = "projects",
                      help="Directory in which to store the Automator projects")

    (opts, args) = parser.parse_args()
    if len(args) != 0:
        parser.error("Wrong number of arguments")

    if not(opts.project_file):
        parser.error("--project is needed")

    return opts

def get_project_repos(proj_file):
    """Read projects information from a file and return it parsed."""
    parser = SafeConfigParser()
    fd = open(proj_file, 'r')
    parser.readfp(fd)
    fd.close()

    projects = parser.sections()
    return projects

def create_project_dirs(name, output_dir):
    """Create Automator project directories."""

    logging.info("Creating project: " + name)
    if not os.path.exists(output_dir): 
        os.makedirs(output_dir)
    project_dir = os.path.join(output_dir,name)
    if not os.path.exists(project_dir): 
        os.makedirs(project_dir)

    basic_dirs = ["conf","irc","json","log","production","scm","tools"]

    for dir in basic_dirs:
        new_dir = os.path.join(project_dir,dir)
        if not os.path.exists(new_dir): 
            os.makedirs(new_dir)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')

    opts = read_options()
    projects = get_project_repos(opts.project_file)
    name = "Test"
    logging.info("Creating automator projects under: " + opts.output_dir)
    create_project_dirs(name, opts.output_dir)
