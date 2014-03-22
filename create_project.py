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
from subprocess import call
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
    projects = {}
    parser = SafeConfigParser()
    fd = open(proj_file, 'r')
    parser.readfp(fd)
    fd.close()

    projects_list = parser.sections()
    for project in projects_list:
        projects[project] = {}
        opts = parser.options(project)
        for opt in opts:
            data_sources = parser.get(project,opt).split(',')
            projects[project][opt] = [ds.replace('\n', '') for ds in data_sources]
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

def safe_git_clone(git_repo, dir_repo = ""):
    """Clone a git_repo y dir_repo with error control"""

    # Remove delimiters. Added by call command later.
    git_repo = git_repo.replace("\"","").replace("'","")

    if (dir_repo != ""):
        cmd = ["git", "clone" , git_repo, dir_repo]
    else:
        cmd = ["git", "clone" , git_repo]
    logging.info(" ".join(cmd))
    return_code = call(cmd)
    if return_code == 1:
        logging.error("Error in " + " ".join(cmd))
        sys.exit()

def config_r(tools_dir):
    # Configure R environment
    cmd = ["R", "CMD", "INSTALL", "-l",
           os.path.join(tools_dir,"r-lib"),
           os.path.join(tools_dir,"GrimoireLib","vizgrimoire")]
    r_lib_dir = os.path.join(tools_dir, "r-lib")
    if not os.path.exists(r_lib_dir):
        os.makedirs(r_lib_dir)
    return_code = call(cmd)
    if return_code == 1:
        logging.error("Error in " + " ".join(cmd))
        sys.exit()
    # Legacy dir
    legacy_link = os.path.join(tools_dir,"VizGrimoireR")
    if not os.path.islink(legacy_link):
        os.symlink("GrimoireLib", legacy_link)

def config_viz(tools_dir):
    data_dir = os.path.join(tools_dir,"VizGrimoireJS",
                             "browser","data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    json_link = os.path.join(data_dir,"json")
    if not os.path.islink(json_link):
        os.symlink("../../../../json", json_link)
    db_dir = os.path.join(tools_dir,"../production/browser/data/db/")
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)


def download_tools (project_name, output_dir):
    """
        Download and configure tools needed to create the dashboard
        GrimoireLib, VizGrimoireUtils, VizGrimoireJS
    """

    gits = {
            "GrimoireLib":  "https://github.com/VizGrimoire/GrimoireLib.git",
            "VizGrimoireUtils" : "https://github.com/VizGrimoire/VizGrimoireUtils.git",
            "VizGrimoireJS" :  "https://github.com/VizGrimoire/VizGrimoireJS.git"
            }
    tools_dir = os.path.join(output_dir,project_name,"tools")
    logging.info("Downloading tools to: " + tools_dir)

    for git in gits:
        dir_repo = os.path.join(tools_dir, git)
        safe_git_clone(gits[git], dir_repo)

    config_r(tools_dir)
    config_viz(tools_dir)

def download_gits (git_repos, dir_project):
    """Download the gits for a project"""
    repos_dir = os.path.join(dir_project,"scm")
    path_orig = os.getcwd()
    os.chdir(repos_dir)
    for repo in git_repos:
        logging.info(repo)
        safe_git_clone(repo)
    os.chdir(path_orig)

def download_irc (archive_urls, dir_project):
    """Download IRC logs from URLs. One channel per URL in tgz format."""
    import tarfile
    irc_dir = os.path.join(dir_project,"irc")
    for url in archive_urls:
        # Remove delimiters.
        url = url.replace("\"","").replace("'","")

        i = url.rfind('/')
        file_name = url[i+1:]
        file_path = os.path.join(irc_dir,file_name)
        logging.info("Downloading IRC channel archive " + url)
        urllib.urlretrieve(url, file_path)
        # File supported "tar.gz"
        data_dir = file_name.replace(".tar.gz","")
        data_dir = os.path.join(irc_dir,data_dir)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        tfile = tarfile.open(file_path, 'r:gz')
        tfile.extractall(data_dir)
        tfile.close()

def get_config_generic(project_data):
    global project_name
    db_prefix = "cp"
    db_suffix = project_name
    # Keep the order using a list
    vars = [
            ["config_generator","create_project"],
            ["mail","YOUR EMAIL"],
            ["project",project_name],
            ["db_user","root"],
            ["db_password",""],
            ["db_identities",db_prefix+"_cvsanaly_"+db_suffix]
        ]
    if "source" in project_data:
        vars.append(["db_cvsanaly",db_prefix+"_cvsanaly_"+db_suffix])
    if "trackers" in project_data:
        vars.append(["db_bicho",db_prefix+"_bicho_"+db_suffix])
    if "gerrit_projects" in project_data:
        vars.append(["db_gerrit",db_prefix+"_gerrit_"+db_suffix])
    if "mailing_lists" in project_data:
        vars.append(["db_mlstats",db_prefix+"_mlstats_"+db_suffix])
    if "irc_channels" in project_data:
        vars.append(["db_irc",db_prefix+"_irc_"+db_suffix])
    if "mediawiki_sites" in project_data:
        vars.append(["db_mediawiki",db_prefix+"_mediawiki_"+db_suffix])

    return vars

def get_bicho_backend(repos):
    """Try to find the bicho backend"""
    backend = "bg"
    if repos[0].find("bugzilla") > -1:
        backend = "bg"
    elif repos[0].find("launchpad") > -1:
        backend = "launchpad"
    return backend

def get_config_bicho(project_data):
    backend = get_bicho_backend(project_data['trackers'])
    trackers = ",".join(project_data['trackers'])
    # avoid interpolation in ConfigParser
    trackers = trackers.replace("%","%%")
    vars = [
            ["backend",backend],
            ["debug","True"],
            ["delay","1"],
            ["log_table","False"],
            ["trackers",trackers]
        ]
    return vars

def get_config_gerrit(project_data):
    # projects = '"mediawiki/extensions/Cite","mediawiki/extensions/ArticleFeedback"'
    projects = ",".join(project_data['gerrit_projects'])
    vars = [
        ["backend","gerrit"],
        ["# user","gerrit user name account"],
        ["user","acs"],
        ["debug","True"],
        ["delay","1"],
        ["trackers","gerrit.wikimedia.org"],
        ["log_table","True"],
        ["projects",projects],
    ]
    return vars

def get_config_cvsanaly(project_data):
    # TODO: not used yet in Automator
    source  = ",".join(project_data['source'])
    vars = [
            ["extensions","CommitsLOC,FileTypes"]
            ]
    return vars

def get_config_mlstats(project_data):
    mailing_lists = ",".join(project_data['mailing_lists'])
    vars = [
            ["mailing_lists", mailing_lists]
            ]
    return vars

def get_config_irc(project_data):
    # TODO: not used yet in Automator
    irc_channels = ",".join(project_data['irc_channels'])
    # avoid interpolation in ConfigParser
    irc_channels = irc_channels.replace("%","%%")

    vars = [
            ["format","plain"]
            ]
    return vars

def get_config_mediawiki(project_data):
    # sites = "http://openstack.redhat.com"
    sites = ",".join(project_data['mediawiki_sites'])
    vars = [
            ["sites", sites]
    ]
    return vars

def get_config_r(project_data):
    vars = [
            ["rscript","run-analysis.py"],
            ["start_date","2010-01-01"],
            ["end_data","2014-03-20"],
            ["reports","repositories,companies,countries,people,domains"],
            ["period","months"]
    ]
    return vars

def get_config_identities(project_data):
    vars = [
            ["countries","debug"],
            ["companies","debug"],
    ]
    return vars

def get_config_git_production(project_data):
    vars = [
            ["destination_json","production/browser/data/json/"]
    ]
    return vars

def get_config_db_dump(project_data):
    vars = [
            ["destination_db_dump","production/browser/data/db/"]
    ]

    return vars

def get_config_rsync(project_data):
    vars = [
            ["destination","yourmaildomain@activity.AutomatorTest.org:/var/www/dash/"]
    ]
    return vars

def check_config_file(project_data):
    pass

def create_project_config(name, project_data, output_dir):
    """Create Automator project config file."""

    parser = SafeConfigParser()
    project_dir = os.path.join(output_dir,name)
    config_file = os.path.join(project_dir,"conf/main.conf")

    fd = open(config_file, 'w')

    sections = [
                ["generic",get_config_generic],
                ["bicho",get_config_bicho],
                ["gerrit",get_config_gerrit],
                ["cvsanaly",get_config_cvsanaly],
                ["mlstats",get_config_mlstats],
                ["irc",get_config_irc],
                ["mediawiki",get_config_mediawiki],
                ["r",get_config_r],
                ["identities",get_config_identities],
                ["git-production_OFF",get_config_git_production],
                ["db-dump",get_config_db_dump],
                ["rsync_OFF",get_config_rsync]
                ]

    for section in sections:
        if section[0] == "cvsanaly" and not "source" in project_data:
            continue
        elif section[0] == "bicho" and not "trackers" in project_data:
            continue
        elif section[0] == "gerrit" and not "gerrit_projects" in project_data:
            continue
        elif section[0] == "mlstats" and not "mailing_lists" in project_data:
            continue
        elif section[0] == "irc" and not "irc_channels" in project_data:
            continue
        elif section[0] == "mediawiki" and not "mediawiki_sites" in project_data:
            continue
        parser.add_section(section[0])
        config_vars = section[1](project_data)
        for var in config_vars:
            parser.set(section[0], var[0], var[1])

    parser.write(fd)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')

    opts = read_options()
    projects = get_project_repos(opts.project_file)
    for project in projects:
        project_name = project
        logging.info("Creating automator projects under: " + opts.output_dir)
        create_project_dirs(project_name, opts.output_dir)
        project_dir = os.path.join(opts.output_dir, project_name)
        download_gits(projects[project]['source'], project_dir)
        create_project_config(project_name, projects[project], opts.output_dir)
        download_tools(project_name, opts.output_dir)
        if 'irc_channels' in projects[project]:
            download_irc(projects[project]['irc_channels'], project_dir)
