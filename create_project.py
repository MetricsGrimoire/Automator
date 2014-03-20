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

project_name = None

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

def get_config_generic():
    global project_name
    # Keep the order using a list
    vars = [["config_generator","create_project"],
            ["mail","YOUR EMAIL"],
            ["project",project_name],
            ["db_user","root"],
            ["db_password",""],
            ["bicho_backend","bugzilla"],
            ["db_bicho","acs_bicho_automatortest_2388"],
            ["db_cvsanaly","acs_cvsanaly_automatortest_2388"],
            ["db_identities","acs_cvsanaly_automatortest_2388"],
            ["db_mlstats","acs_mlstats_automatortest_2388"],
            ["db_gerrit","acs_gerrit_automatortest_2388"],
            ["db_irc","acs_irc_automatortest_2388_2"],
            ["db_mediawiki","acs_mediawiki_rdo_2478"]
        ]
    return vars

def get_config_bicho():
    trackers  = 'https://bugzilla.wikimedia.org/buglist.cgi?product=Huggle,'
    trackers += 'https://bugzilla.wikimedia.org/buglist.cgi?product=Analytics,'
    trackers += '"https://bugzilla.wikimedia.org/buglist.cgi?product=analytics&component=kraken",'
    trackers += '"https://bugzilla.wikimedia.org/buglist.cgi?product=Parsoid",'
    trackers += '"https://bugzilla.wikimedia.org/buglist.cgi?product=VisualEditor"'
    vars = {
            "backend":"bg",
            "debug":"True",
            "delay":"1",
            "log_table":"False",
            "trackers":trackers
            }
    return vars

def get_config_gerrit():
    projects = '"mediawiki/extensions/Cite","mediawiki/extensions/ArticleFeedback"'
    vars = {
        "backend":"gerrit",
        "# user":"gerrit user name account",
        "user":"acs",
        "debug":"True",
        "delay":"1",
        "trackers":"gerrit.wikimedia.org",
        "log_table":"True",
        "projects":projects,
    }
    return vars

def get_config_cvsanaly():
    vars = {
            "extensions":"CommitsLOC,FileTypes"
            }
    return vars

def get_config_mlstats():
    mailing_lists = "http://lists.wikimedia.org/pipermail/mediawiki-announce,http://lists.wikimedia.org/pipermail/mediawiki-api-announce"
    vars = {
            "mailing_lists": mailing_lists
            }
    return vars

def get_config_irc():
    vars = {
            "format":"plain"
            }
    return vars

def get_config_mediawiki():
    sites = "http://openstack.redhat.com"
    vars = {
            "sites": sites
    }
    return vars

def get_config_r():
    vars = {
            "rscript":"run-analysis.py",
            "start_date":"2010-01-01",
            "end_data":"2014-03-20",
            "reports":"repositories,companies,countries,people,domains",
            "period":"months"
    }
    return vars

def get_config_identities():
    vars = {
            "countries":"debug",
            "companies":"debug",
    }
    return vars

def get_config_git_production():
    vars = {
            "destination_json":"production/browser/data/json/"
    }
    return vars

def get_config_db_dump():
    vars = {
            "destination_db_dump":"production/browser/data/db/"
    }

    return vars

def get_config_rsync():
    vars = {
            "destination":"yourmaildomain@activity.AutomatorTest.org:/var/www/dash/"
    }
    return vars

def check_config_file(config_file):
    pass

def create_project_config(name, output_dir):
    """Create Automator project config file."""

    parser = SafeConfigParser()
    project_dir = os.path.join(output_dir,name)
    config_file = os.path.join(project_dir,"conf/main.conf")

    fd = open(config_file, 'w')

    sections = ["generic","bicho","gerrit","cvsanaly","mlstats","irc","mediawiki","r",
                "identities","git-production","db-dump","rsync"]
    for section in sections:
        parser.add_section(section)

        fn_section_name = ("get_config_"+section).replace("-","_")
        fn_section = getattr(sys.modules[__name__], fn_section_name)
        config_vars = fn_section()
        if isinstance(config_vars, list):
            for var in config_vars:
                parser.set(section, var[0], var[1])
        else:
            for var in config_vars:
                parser.set(section, var, config_vars[var])

    parser.write(fd)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')

    opts = read_options()
    projects = get_project_repos(opts.project_file)
    project_name = "Test"
    logging.info("Creating automator projects under: " + opts.output_dir)
    create_project_dirs(project_name, opts.output_dir)
    create_project_config(project_name, opts.output_dir)