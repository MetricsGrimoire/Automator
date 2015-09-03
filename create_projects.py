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
import MySQLdb
from optparse import OptionParser
import os.path
from subprocess import call
import sys
import urllib
from ConfigParser import SafeConfigParser

def read_options():
    """Read options from command line."""
    parser = OptionParser(usage="usage: %prog [options]",
                          version="%prog 0.1")
    parser.add_option("-p", "--projects",
                      action="store",
                      dest="project_file",
                      help="File with the projects repositories to be analyzed")
    parser.add_option("-d", "--dir",
                      action="store",
                      dest="output_dir",
                      default = "projects",
                      help="Directory in which to store the Automator projects or the web")
    parser.add_option("-w", "--web",
                      action="store_true",
                      dest="web",
                      help="Create a web portal for all projects")
    parser.add_option("-s", "--single",
                      action="store_true",
                      dest="single_dash",
                      help="Create a single dashboard with all projects.")
    parser.add_option("--projects-tables",
                      action="store_true",
                      dest="projects_tables",
                      help="Only create the projects SQL tables.")
    parser.add_option("--projects-json",
                      action="store_true",
                      dest="projects_json",
                      help="Create the projects_hierarchy.json file.")
    parser.add_option("-n", "--name",
                      action="store",
                      dest="name",
                      help="Name of the global project.")
    parser.add_option("--dbuser",
                      action="store",
                      dest="dbuser", default="root",
                      help="db user name.")
    parser.add_option("--dbpasswd",
                      action="store",
                      dest="dbpasswd", default="",
                      help="db user password")
    parser.add_option("--remove-filter-item",
                      action="store",
                      dest="remove_filter_item",
                      help="Remove a filter item (i.e. repository URL) from a data source.")
    parser.add_option("--list-filter-items",
                      action="store_true",
                      dest="list_filter_items",
                      help="List all items from a filter from a data source.")
    parser.add_option("--data-source",
                      action="store",
                      dest="data_source",
                      help="Data source from which to remove a filter item.")
    parser.add_option("--bicho-user",
                      action="store",
                      dest="bicho_user",
                      help="bicho user name for the backend.")
    parser.add_option("--bicho-password",
                      action="store",
                      dest="bicho_password",
                      help="bicho user password for the backend.")

    (opts, args) = parser.parse_args()

    if len(args) != 0:
        parser.error("Wrong number of arguments")

    if opts.web and not (opts.output_dir and opts.project_file):
        parser.error("--web needs also --dir")

    if opts.single_dash and not (opts.output_dir and opts.dbuser and opts.name and opts.project_file):
        parser.error("--single needs also --dir --dbuser --name --projects")

    if opts.projects_tables and not opts.single_dash:
        parser.error("--projects-tables needs also --single")

    if opts.projects_json and not (opts.output_dir and opts.name):
        parser.error("--projects-json needs also --dir --name")

    if opts.remove_filter_item and not (opts.data_source and opts.output_dir):
        parser.error("--remove-filter-url  needs also --data-source")

    if opts.list_filter_items and not (opts.data_source and opts.output_dir):
        parser.error("--list-filter-items  needs also --data-source and --dir")

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

    basic_dirs = ["conf","irc","json","log","production","scm","scripts","tools","backups"]

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

def get_db_prefix():
    return "cp"

def get_config_generic(project_name, project_data):
    db_prefix = get_db_prefix()
    db_suffix = project_name
    # Keep the order using a list
    vars = [
            ["config_generator","create_project"],
            ["mail","automator@bitergia.com"],
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
    if "sibyl_url" in project_data:
        vars.append(["db_sibyl",db_prefix+"_sibyl_"+db_suffix])

    return vars

def get_bicho_backend(repos):
    """Try to find the bicho backend"""
    backend = "bg"
    if repos[0].find("bugzilla") > -1:
        backend = "bg"
    elif repos[0].find("launchpad") > -1:
        backend = "launchpad"
    elif repos[0].find("jira") > -1:
        backend = "jira"
    elif repos[0].find("api.github.com") > -1:
        backend = "github"
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
            ["# num-issues-query","250"],
            ["# backend_user","miningbitergia"],
            ["# backend_password","passwd"],
            ["# num-issues-query","250"],
            ["trackers",trackers]
        ]

    if opts.bicho_user:
        vars.append(["backend_user", opts.bicho_user])
    if opts.bicho_password:
        vars.append(["backend_password", opts.bicho_password])

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
        ["trackers",project_data['gerrit_url'][0]],
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

def get_sibyl_backend(repos):
    """Try to find the sibyl backend"""
    backend = None
    discourse_url = repos[0]+"/categories.json"
    res = urllib.urlopen(discourse_url)
    if res.getcode() == 200:
        backend = "discourse"
    return backend

def get_config_sibyl(project_data):
    vars = [
        ["url", ",".join(project_data['sibyl_url'])],
        ["backend",  get_sibyl_backend(project_data['sibyl_url'])],
        ["# stackoverflow sibyl_api_key",  ""],
        ["# stackoverflow sibyl_tags",  ""]
    ]
    return vars

def get_config_grimoirelib(project_data):
    vars = [
            ["start_date","2010-01-01"],
            ["# end_date","2014-03-20"],
            ["# reports","repositories,companies,countries,people,domains,projects"],
            ["reports","repositories,people,domains,projects"],
            ["# people_out", "bot1, bot2"],
            ["# companies_out", "company1, company2"],
            ["# domains_out", "domain1, domain2"],
            ["period","months"],
            ["studies","onion,ages"]
    ]
    return vars

def get_config_identities(project_data):
    vars = [
            ["#countries","debug"],
            ["#companies","debug"],
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

def get_data_sources():
    """Each data source will contains repository in a comma separated list"""
    return ["source","trackers","gerrit_projects",
            "mailing_lists","irc_channels","mediawiki_sites","sibyl_url"]

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
                ["sibyl",get_config_sibyl],
                ["r",get_config_grimoirelib],
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
        elif section[0] == "gerrit" and \
            (not "gerrit_projects" in project_data or not "gerrit_url" in project_data):
            continue
        elif section[0] == "mlstats" and not "mailing_lists" in project_data:
            continue
        elif section[0] == "irc" and not "irc_channels" in project_data:
            continue
        elif section[0] == "mediawiki" and not "mediawiki_sites" in project_data:
            continue
        elif section[0] == "sibyl" and not "sibyl_url" in project_data:
            continue
        parser.add_section(section[0])
        if section[0] == "generic":
            config_vars = section[1](name, project_data)
        else:
            config_vars = section[1](project_data)
        for var in config_vars:
            parser.set(section[0], var[0], var[1])

    parser.write(fd)

def create_project(name, data, destdir):
    logging.info("Creating automator project %s under %s " % (name, destdir))
    create_project_dirs(name, destdir)
    project_dir = os.path.join(destdir, name)
    if 'source' in data:
        download_gits(data['source'], project_dir)
    create_project_config(name, data, destdir)
    download_tools(name, destdir)
    if 'irc_channels' in data:
        download_irc(data['irc_channels'], project_dir)

def create_projects(projects, destdir):
    """Create projects dashboards"""
    for project in projects:
        create_project (project, projects[project], destdir)

def create_projects_schema(db_name):
    opts = read_options()
    db_user = opts.dbuser
    db_password = opts.dbpasswd

    db = MySQLdb.connect(user = db_user, passwd = db_password,  db = db_name)
    cursor = db.cursor()

    project_table = """
        CREATE TABLE projects (
            project_id int(11) NOT NULL AUTO_INCREMENT,
            id varchar(255) NOT NULL,
            title varchar(255) NOT NULL,
            PRIMARY KEY (project_id)
        ) ENGINE=MyISAM DEFAULT CHARSET=utf8
    """
    project_repositories_table = """
        CREATE TABLE project_repositories (
            project_id int(11) NOT NULL,
            data_source varchar(32) NOT NULL,
            repository_name varchar(255) NOT NULL,
            UNIQUE (project_id, data_source, repository_name)
        ) ENGINE=MyISAM DEFAULT CHARSET=utf8
    """
    project_children_table = """
        CREATE TABLE project_children (
            project_id int(11) NOT NULL,
            subproject_id int(11) NOT NULL,
            UNIQUE (project_id, subproject_id)
        ) ENGINE=MyISAM DEFAULT CHARSET=utf8
    """

    # The data in tables is created automatically.
    # No worries about dropping tables.
    cursor.execute("DROP TABLE IF EXISTS projects")
    cursor.execute("DROP TABLE IF EXISTS project_repositories")
    cursor.execute("DROP TABLE IF EXISTS project_children")

    cursor.execute(project_table)
    cursor.execute(project_repositories_table)
    cursor.execute(project_children_table)

    db.close()

def get_project_children(project_key, projects):
    """returns and array with the project names of its children"""
    children = []
    for project in projects:
        data = projects[project]
        if not 'parent_project' in data: return children
        if (len(data['parent_project']) == 0):
            continue
        else:
            parent = data['parent_project'][0]['id']
            if parent == project_key:
                children.append(project)
                children += get_project_children(project, projects)
    return children

def fill_projects(db_name, projects):
    opts = read_options()
    db_user = opts.dbuser
    db_password = opts.dbpasswd
    db = MySQLdb.connect(user = db_user, passwd = db_password,  db = db_name)
    cursor = db.cursor()

    projects_db = {}
    for key in projects:
        q = "INSERT INTO projects (title, id) values (%s, %s)"
        cursor.execute(q, (key, key))
        projects_db[key] = db.insert_id()
    logging.info("Projects added to " + db_name)

    # Insert children for all projects
    for project in projects_db:
        children = get_project_children(project, projects)
        for child in children:
            q = "INSERT INTO project_children (project_id, subproject_id) values (%s, %s)"
            project_id = projects_db[project]
            subproject_id = projects_db[child]
            cursor.execute(q, (project_id, subproject_id))
    logging.info("Projects children added")

    def insert_repos(project_id, repos, data_source, base_url = None):
        for repo in repos:
            repo = repo.replace('"','')
            if base_url:
                base_url = base_url.replace('"','')
                repo = base_url + "_" + repo
            q = "INSERT INTO project_repositories VALUES (%s, %s, %s)"
            cursor.execute(q, (project_id, data_source, repo))

    # Maps tool data sources to Grimoire Platform ds names
    ds_to_ds = {
        "source":"scm",
        "trackers":"its",
        "gerrit_projects":"scr",
        "mailing_lists":"mls",
        "irc_channels":"irc",
        "mediawiki_sites":"mediawiki",
        "sibyl_url":"sibyl"
    }

    for project in projects_db:
        for ds in get_data_sources():
            if ds in projects[project]:
                repos = projects[project][ds]
                if ds in ds_to_ds.keys():
                    base_url = None
                    if ds == "gerrit_projects":
                        base_url = projects[project]['gerrit_url'][0]
                    insert_repos(projects_db[project], repos, ds_to_ds[ds], base_url)
    db.close()


def create_db(db_name):
    opts = read_options()
    db_user = opts.dbuser
    db_password = opts.dbpasswd

    try:
         db = MySQLdb.connect(user = db_user, passwd = db_password,  db = db_name)
         db.close()
         logging.info (db_name+" already exists")
    except:
        db = MySQLdb.connect(user = db_user, passwd = db_password)
        cursor = db.cursor()
        query = "CREATE DATABASE " + db_name + " CHARACTER SET utf8 COLLATE utf8_unicode_ci"
        cursor.execute(query)
        db.close()
        logging.info (db_name+" created")

def create_single_dash(projects, destdir, name):
    """Create a single dashboard with all projects"""
    opts = read_options()
    logging.info("Creating a single dashboard with all projects")
    # Create project env
    logging.info("Joining all repositories for different projects")
    single_project_name = name
    single_project_data = {}

    for project in projects:
        for ds in get_data_sources():
            if ds in projects[project]:
                if ds not in single_project_data:
                    single_project_data[ds] = []
                single_project_data[ds] += projects[project][ds]
        # TODO: right now the same gerrit_url for all projects
        if 'gerrit_url' in projects[project]:
            single_project_data['gerrit_url'] = projects[project]['gerrit_url']

    # Create db for identities
    db_identities = get_db_prefix()+"_cvsanaly_"+single_project_name
    create_db(db_identities)
    # Create projects tables
    create_projects_schema(db_identities)
    # Fill projects tables
    fill_projects(db_identities, projects)
    # Just create the project tables
    if (opts.projects_tables): return
    # Create automator config
    create_project(single_project_name, single_project_data, destdir)

def read_main_conf(config_file):
    options = {}
    parser = SafeConfigParser()
    fd = open(config_file, 'r')
    parser.readfp(fd)
    fd.close()

    sec = parser.sections()
    # we'll read "generic" for db information and "r" for start_date and "bicho" for backend
    for s in sec:
        if not((s == "generic") or (s == "r") or (s == "bicho")):
            continue
        options[s] = {}
        opti = parser.options(s)
        for o in opti:
            options[s][o] = parser.get(s, o)
    return options

def import_grimoirelib(destdir):
    grimoirelib = os.path.join(destdir, "tools", "GrimoireLib","vizgrimoire")
    sys.path.append(grimoirelib)
    metricslib = os.path.join(destdir, "tools", "GrimoireLib","vizgrimoire","metrics")
    sys.path.append(metricslib)
    studieslib = os.path.join(destdir, "tools", "GrimoireLib","vizgrimoire","analysis")
    sys.path.append(studieslib)
    import report, GrimoireSQL
    automator_file = os.path.join(destdir,"conf/main.conf")
    report.Report.init(automator_file)


def get_filter_items(data_source, destdir):
    import_grimoirelib(destdir)
    import report, GrimoireSQL

    automator_file = os.path.join(destdir,"conf/main.conf")
    automator = read_main_conf(automator_file)
    db_user = automator['generic']['db_user']
    db_password = automator['generic']['db_password']
    db_name_automator = None

    for ds in report.Report.get_data_sources():
        if (ds.get_name() == data_source):
            db_name_automator = ds.get_db_name()
            break
    if db_name_automator is None:
        logging.error("Can't find the db_name in %s for the data source %s" % (automator_file, data_source))
        sys.exit()
    db_name = automator['generic'][db_name_automator]

    GrimoireSQL.SetDBChannel (database=db_name, user=db_user, password=db_password)
    if (data_source == "scm"):
        q = "SELECT * from repositories"
        field = "uri"
    elif (data_source == "its" or data_source == "scr"):
        q = "SELECT * from trackers"
        field = "url"
    elif (data_source == "mls"):
        q = "SELECT * from mailing_lists"
        field = "mailing_list_url"
    else:
        logging.info("%s data source filter items lists not supported" % data_source)
        return

    res = GrimoireSQL.ExecuteQuery(q)[field]
    return res

def remove_filter_item(item_uri, data_source, destdir):
    import_grimoirelib(destdir)
    import report, GrimoireSQL, filter

    if item_uri not in get_filter_items(data_source, destdir):
        logging.info('%s not found' % (item_uri))
        return

    automator_file = os.path.join(destdir,"conf/main.conf")
    automator = read_main_conf(automator_file)
    db_user = automator['generic']['db_user']
    db_password = automator['generic']['db_password']
    db_name_automator = None
    ds = None

    for dsaux in report.Report.get_data_sources():
        if (dsaux.get_name() == data_source):
            db_name_automator = dsaux.get_db_name()
            ds = dsaux
            break
    if db_name_automator is None:
        logging.error("Can't find the db_name in %s for the data source %s" % (automator_file, data_source))
        sys.exit()
    db_name = automator['generic'][db_name_automator]

    GrimoireSQL.SetDBChannel (database=db_name, user=db_user, password=db_password)
    logging.info('Removing %s from %s' % (item_uri, data_source))
    ds.remove_filter_data(filter.Filter("repository", item_uri))

def create_web(projects, destdir):
    """Create a web portal to access the projects dashboards"""
    browser_url = "tools/VizGrimoireJS/browser/"
    html_file = open(os.path.join(destdir,"projects.html"), 'w')
    html = "<html><head><title></title></head><body>"
    html += "<ul>"
    for project in projects:
        html += "<li><a href='%s/%s'>%s</a></li>" % (project,browser_url,project)
    html += "</ul>"
    html += "</body></html>"
    html_file.write(html)
    html_file.close()
    logging.info("Created html file " + os.path.join(destdir,"projects.html"))

def create_projects_json(destdir, name):
    """Create the projects_hierarchy.json to be used in the dash"""
    import_grimoirelib(destdir)
    import report, GrimoireSQL
    from GrimoireUtils import createJSON


    logging.info("Creating projects_hierarchy.json file ")

    automator_file = os.path.join(destdir,"conf/main.conf")
    automator = read_main_conf(automator_file)
    db_user = automator['generic']['db_user']
    db_password = automator['generic']['db_password']
    db_name = automator['generic']['db_identities']

    GrimoireSQL.SetDBChannel (database=db_name, user=db_user, password=db_password)
    # JSON entry
    #"mylyn.tasks": {
    #    "parent_project": "mylyn",
    #    "title": "Mylyn Tasks"
    # }
    # In the current implementation just one leve, all "parent_project":"root"
    q = "SELECT id, title from projects"
    res = GrimoireSQL.ExecuteQuery(q)

    projects = {}
    for i in range(0,len(res['id'])):
        projects[res['id'][i]] = {"parent_project":"root","title":res['title'][i]}
    projects["root"] = {"title": name}

    createJSON(projects, "projects_hierarchy.json")
    logging.info("projects_hierarchy.json created.")

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')

    opts = read_options()

    if opts.web:
        projects = get_project_repos(opts.project_file)
        create_web(projects, opts.output_dir)
    elif opts.single_dash:
        projects = get_project_repos(opts.project_file)
        create_single_dash(projects, opts.output_dir, opts.name)
    elif opts.list_filter_items:
        items = get_filter_items(opts.data_source, opts.output_dir)
        for item in items: print(item)
    elif opts.remove_filter_item:
        remove_filter_item(opts.remove_filter_item, opts.data_source, opts.output_dir)
    elif opts.projects_json:
        create_projects_json(opts.output_dir, opts.name)
    else:
        projects = get_project_repos(opts.project_file)
        create_projects(projects, opts.output_dir)
