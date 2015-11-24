#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2012-2014 Bitergia
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# Authors :
#       Luis Cañas-Díaz <lcanas@bitergia.com>
#       Daniel Izquierdo Cortázar <dizquierdo@bitergia.com>
#       Alvaro del Castillo San Felix <acs@bitergia.com>
#
# launch.py
#
# This script automates the execution of some of the metrics grimoire
# tools (Bicho, MLStats, CVSAnaly). It uses configuration files to get
# the parameters. Finally it execute R scripts in order to generate the
# JSON files

import logging
import logging.handlers
import os
import subprocess
import sys
import time
import distutils.dir_util
import json
import datetime as dt
from optparse import OptionGroup, OptionParser
from tempfile import NamedTemporaryFile
from ConfigParser import SafeConfigParser

import MySQLdb

# conf variables from file(see read_main_conf)
options = {}

# global var for logs
main_log = None
MAX_LOG_BYTES = 10000000 #10MB
MAX_LOG_FILES = 5 #6 files (.log, .log.1, ... , .log.5)
log_files = None

# global var for directories
project_dir = ''
msg_body = ''#project_dir + '/log/launch.log'
scm_dir = ''#os.getcwd() + '/../scm/'
conf_dir = ''#os.getcwd() + '/../conf/'
json_dir = ''
production_dir = ''

tools = {
    'scm' :'/usr/local/bin/cvsanaly2',
    'its': '/usr/local/bin/bicho',
    'scr': '/usr/local/bin/bicho',
    'mls': '/usr/local/bin/mlstats',
    'irc': '/usr/local/bin/irc_analysis.py',
    'mediawiki': '/usr/local/bin/mediawiki_analysis.py',
    'confluence': '/usr/local/bin/confluence_analysis.py',
    'sibyl': '/usr/local/bin/sibyl.py',
    'octopus': '/usr/local/bin/octopus',
    'pullpo': '/usr/local/bin/pullpo',
    'eventizer': '/usr/local/bin/eventizer',
    'r': '/usr/bin/R',
    'rremoval': '/usr/local/bin/rremoval',
    'git': '/usr/bin/git',
    'svn': '/usr/bin/svn',
    'mysqldump': '/usr/bin/mysqldump',
    'compress': '/usr/bin/7zr',
    'rm': '/bin/rm',
    'rsync': '/usr/bin/rsync',
    'sortinghat': '/usr/local/bin/sortinghat',
    'mg2sh': '/usr/local/bin/mg2sh',
    'sh2mg': '/usr/local/bin/sh2mg',
}

# Config files where lists of repositories are found.
# It is expected to find a repository per line
BICHO_TRACKERS = "bicho_trackers.conf"
BICHO_TRACKERS_BLACKLIST = "bicho_trackers_blacklist.conf"
BICHO_1_TRACKERS = "bicho_1_trackers.conf"
BICHO_1_TRACKERS_BLACKLIST = "bicho_1_trackers_blacklist.conf"
CVSANALY_REPOSITORIES = "cvsanaly_repositories.conf"
CVSANALY_REPOSITORIES_BLACKLIST = "cvsanaly_repositories_blacklist.conf"
GERRIT_PROJECTS = "gerrit_trackers.conf"
GERRIT_PROJECTS_BLACKLIST = "gerrit_trackers_blacklist.conf"
MLSTATS_MAILING_LISTS = "mlstats_mailing_lists.conf"
MLSTATS_MAILING_LISTS_BLACKLIST = "mlstats_mailing_lists_blacklist.conf"
PUPPET_RELEASES = "puppet_releases.conf"
DOCKER_PACKAGES = "docker_packages.conf"


def get_options():
    parser = OptionParser(usage='Usage: %prog [options]',
                          description='Update data, process it and obtain JSON files',
                          version='0.1')
    parser.add_option('-d','--dir', dest='project_dir',
                     help='Path with the configuration of the project', default=None)
    parser.add_option('-q','--quiet', action='store_true', dest='quiet_mode',
                      help='Disable messages in standard output', default=False)
    parser.add_option('-s','--section', dest='section',
                     help='Section to be executed', default=None)
    parser.add_option('-t','--data-source', dest='subtask',
                     help='Sub section to be executed (only for r)', default=None)
    parser.add_option('--filter', dest='filter',
                     help='Filter to be used (repository, company, project, country ...)', default=None)
    parser.add_option('-g', '--debug', action='store_true', dest='debug',
                        help='Enable debug mode', default=False)
    parser.add_option('--python', dest='python', action="store_true",
                      help='Use python script for getting metrics. (obsolete)')

    (ops, args) = parser.parse_args()

    if ops.project_dir is None:
        parser.print_help()
        print("Project dir is required")
        sys.exit(1)
    return ops

def initialize_globals(pdir):
    global project_dir
    global msg_body
    global scm_dir
    global irc_dir
    global conf_dir
    global downs_dir
    global json_dir
    global repos_dir
    global scripts_dir
    global production_dir
    global identities_dir
    global downloads_dir
    global r_dir

    global log_files

    project_dir = pdir
    msg_body = project_dir + '/log/launch.log'
    scm_dir = project_dir + '/scm/'
    irc_dir = project_dir + '/irc/'
    conf_dir = project_dir + '/conf/'
    downs_dir = project_dir + '/downloads/'
    json_dir = project_dir + '/json/'
    repos_dir = conf_dir + "repositories/"
    scripts_dir = project_dir + '/scripts/'
    production_dir = project_dir + '/production/'
    identities_dir = project_dir + '/tools/VizGrimoireUtils/identities/'
    downloads_dir = project_dir + '/tools/VizGrimoireUtils/downloads/'
    r_dir = project_dir + '/tools/GrimoireLib/vizGrimoireJS/'

    # global var for logs
    log_files = {
        'cvsanaly' : project_dir + '/log/retrieval_cvsanaly.log',
        'bicho' : project_dir + '/log/retrieval_bicho.log',
        'gerrit' : project_dir + '/log/retrieval_gerrit.log',
        'mlstats' : project_dir + '/log/retrieval_mlstats.log',
        'irc' : project_dir + '/log/retrieval_irc.log',
        'mediawiki' : project_dir + '/log/retrieval_mediawiki.log',
        'confluence' : project_dir + '/log/retrieval_confluence.log',
        'sibyl' : project_dir + '/log/retrieval_sibyl.log',
        'octopus_puppet' : project_dir + '/log/retrieval_octopus_puppet.log',
        'octopus_docker' : project_dir + '/log/retrieval_octopus_docker.log',
        'octopus_github' : project_dir + '/log/retrieval_octopus_github.log',
        'sortinghat_affiliations' : project_dir + '/log/sortinghat_affiliations.log',
        'sortinghat' : project_dir + '/log/sortinghat.log',
        'pullpo' : project_dir + '/log/retrieval_pullpo.log',
        'eventizer' : project_dir + '/log/retrieval_eventizer.log',
        'identities' : project_dir + '/log/identities.log',
    }

def read_main_conf():
    parser = SafeConfigParser()
    conf_file = project_dir + '/conf/main.conf'
    fd = open(conf_file, 'r')
    parser.readfp(fd)
    fd.close()

    sec = parser.sections()
    for s in sec:
        options[s] = {}
        opti = parser.options(s)
        for o in opti:
            # first, some special cases
            if o == 'debug':
                options[s][o] = parser.getboolean(s,o)
            elif o in ('trackers', 'projects', 'pre_scripts', 'post_scripts'):
                data_sources = parser.get(s,o).split(',')
                options[s][o] = [ds.replace('\n', '') for ds in data_sources]
            else:
                options[s][o] = parser.get(s,o)

    return options

def repositories(file_path):
   """ Returns the list of repositories found in file_path

   :param file_patch: file where the repositories are found
   :returns: a list of repositories
   """

   global conf_dir

   file_path  = os.path.join(conf_dir, file_path)
   repositories = open(file_path).read().splitlines()

   return repositories

# git specific: search all repos in a directory recursively
def get_scm_repos(dir = scm_dir):
    all_repos = []

    if (dir == ''):  dir = scm_dir
    if not os.path.isdir(dir): return all_repos

    repos = os.listdir(dir)

    for r in repos:
        repo_dir_git = os.path.join(dir,r,".git")
        repo_dir_svn = os.path.join(dir,r,".svn")
        if os.path.isdir(repo_dir_git) or os.path.isdir(repo_dir_svn):
            all_repos.append(os.path.join(dir,r))
        sub_repos = get_scm_repos(os.path.join(dir,r))
        for sub_repo in sub_repos:
            all_repos.append(sub_repo)
    return all_repos

def update_scm(scm_log, dir = scm_dir):
    main_log.info("SCM is being updated")
    repos = get_scm_repos()
    updated = False
    log_file = log_files['cvsanaly']

    for r in repos:
        os.chdir(r)
        if os.path.isdir(os.path.join(dir,r,".git")):
            os.system("GIT_ASKPASS=echo git fetch origin >> %s 2>&1" %(log_file))
            errcode = os.system("GIT_ASKPASS=echo git reset --hard origin/master -- >> %s 2>&1" %(log_file))

            if errcode != 0:
                # Sometimes master branch does not exists and it's replaced by trunk
                os.system("GIT_ASKPASS=echo git reset --hard origin/trunk -- >> %s 2>&1" %(log_file))
        elif os.path.isdir(os.path.join(dir,r,".svn")):
            os.system("svn update >> %s 2>&1" %(log_file))
        else: scm_log.info(r + " not git nor svn.")
        scm_log.info(r + " update ended")

    if updated: main_log.info("[OK] SCM updated")

def check_tool(cmd):
    return os.path.isfile(cmd) and os.access(cmd, os.X_OK)
    return True

def check_tools():
    tools_ok = True
    for tool in tools:
        if not check_tool(tools[tool]):
            main_log.info(tools[tool]+" not found or not executable.")
            tools_ok = False
    if not tools_ok:
        main_log.info("Missing tools. Some reports could not be created.")

def launch_checkdbs():
    dbs = []
    db_user = options['generic']['db_user']
    db_password = options['generic']['db_password']

    if options['generic'].has_key('db_identities'):
        dbs.append(options['generic']['db_identities'])
    if options['generic'].has_key('db_cvsanaly'):
        dbs.append(options['generic']['db_cvsanaly'])
    if options['generic'].has_key('db_bicho'):
        dbs.append(options['generic']['db_bicho'])
    if options['generic'].has_key('db_bicho_1'):
        dbs.append(options['generic']['db_bicho_1'])
    # mlstats creates the db if options['generic'].has_key('db_mlstats'):
    if options['generic'].has_key('db_gerrit'):
        dbs.append(options['generic']['db_gerrit'])
    if options['generic'].has_key('db_irc'):
        dbs.append(options['generic']['db_irc'])
    if options['generic'].has_key('db_mediawiki'):
        dbs.append(options['generic']['db_mediawiki'])
    if options['generic'].has_key('db_releases'):
        dbs.append(options['generic']['db_releases'])
    # LEGACY qaforums. Use sibyl in new deployments.
    if options['generic'].has_key('db_qaforums'):
        dbs.append(options['generic']['db_qaforums'])
    if options['generic'].has_key('db_sibyl'):
        dbs.append(options['generic']['db_sibyl'])
    if options['generic'].has_key('db_downloads'):
        dbs.append(options['generic']['db_downloads'])
    if options['generic'].has_key('db_pullpo'):
        dbs.append(options['generic']['db_pullpo'])
    if options['generic'].has_key('db_eventizer'):
        dbs.append(options['generic']['db_eventizer'])
    # sortinghat creates the db itself if options['generic'].has_key('db_sortinghat'):
    if options['generic'].has_key('db_projects'):
        dbs.append(options['generic']['db_projects'])
    # Octopus db
    if options['generic'].has_key('db_octopus'):
        dbs.append(options['generic']['db_octopus'])
    for dbname in dbs:
        try:
             db = MySQLdb.connect(user = db_user, passwd = db_password,  db = dbname)
             db.close()
        except:
            main_log.error("Can't connect to " + dbname)
            print("ERROR: Can't connect to " + dbname)
            db = MySQLdb.connect(user = db_user, passwd = db_password)
            cursor = db.cursor()
            query = "CREATE DATABASE " + dbname + " CHARACTER SET utf8"
            cursor.execute(query)
            db.close()
            main_log.info(dbname+" created")

def launch_scripts(scripts):
    # Run a list of scripts
    for script in scripts:
        cmd = os.path.join(scripts_dir, script) + " >> %s 2>&1" % msg_body

        main_log.info("Running %s" % cmd)
        os.system(cmd)
        main_log.info("%s script completed" % script)

def launch_pre_tool_scripts(tool):
    if tool not in options:
        return

    if options[tool].has_key('pre_scripts'):
        main_log.info("Running %s pre scripts" % tool)
        launch_scripts(options[tool]['pre_scripts'])
        main_log.info("%s pre scripts completed" % tool)
    else:
        main_log.info("No %s pre scripts configured" % tool)

def launch_post_tool_scripts(tool):
    if tool not in options:
        return

    if options[tool].has_key('post_scripts'):
        main_log.info("Running %s post scripts" % tool)
        launch_scripts(options[tool]['post_scripts'])
        main_log.info("%s post scripts completed" % tool)
    else:
        main_log.info("No %s post scripts configured" % tool)

def launch_cvsanaly():

    log_file = log_files['cvsanaly']
    cvsanaly_log = logs(log_file, MAX_LOG_BYTES, MAX_LOG_FILES)

    # using the conf executes cvsanaly for the repos inside scm dir
    if options.has_key('cvsanaly'):
        if not check_tool(tools['scm']):
            return
        update_scm(cvsanaly_log)
        main_log.info("cvsanaly is being executed")
        launched = False
        db_name = options['generic']['db_cvsanaly']
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        if (db_pass == ""): db_pass = "''"


        # we launch cvsanaly against the repos
        repos = get_scm_repos()

        # pre-scripts
        launch_pre_tool_scripts('cvsanaly')

        for r in repos:
            launched = True
            os.chdir(r)
            if options['cvsanaly'].has_key('extensions'):
                cmd = tools['scm'] + " -u %s -p %s -d %s --extensions=%s >> %s 2>&1" \
                        %(db_user, db_pass, db_name, options['cvsanaly']['extensions'], log_file)
            else:
                cmd = tools['scm'] + " -u %s -p %s -d %s >> %s 2>&1" \
                        %(db_user, db_pass, db_name, log_file)

            cvsanaly_log.info(cmd)
            os.system(cmd)

        if launched:
            main_log.info("[OK] cvsanaly executed")

            # post-scripts
            launch_post_tool_scripts('cvsanaly')
        else:
            main_log.info("[skipped] cvsanaly was not executed")
    else:
        main_log.info("[skipped] cvsanaly not executed, no conf available")

def launch_bicho(section = None):
    do_bicho('bicho')
    # find additional configs
    do_bicho('bicho_1')

def do_bicho(section = None):
    # reads a conf file with all of the information and launches bicho
    if section is None: section = 'bicho'
    if not section.startswith("bicho"):
        main_log.error("Wrong bicho section name " + section)
    if options.has_key(section):
        if not check_tool(tools['its']):
            return

        main_log.info("bicho is being executed")
        launched = False

        database = options['generic']['db_' + section]
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        delay = options[section]['delay']
        backend = options[section]['backend']
        backend_user = backend_password = None
        backend_token = None
        num_issues_query = None
        if options[section].has_key('backend_user'):
            backend_user = options[section]['backend_user']
        if options[section].has_key('backend_password'):
            backend_password = options[section]['backend_password']
        if options[section].has_key('backend_token'):
            backend_token = options[section]['backend_token']
        if options[section].has_key('num-issues-query'):
            num_issues_query = options[section]['num-issues-query']
        # Retrieving trackers from config file or from an external config file
        if options[section].has_key('trackers'):
            trackers = options[section]['trackers']
        else:
            trackers = repositories(BICHO_TRACKERS)
        if section == "bicho_1" and not options[section].has_key('trackers'):
            trackers = repositories(BICHO_1_TRACKERS)
        log_table = None
        debug = options[section]['debug']
        if options[section].has_key('log_table'):
            log_table = options[section]['log_table']
        log_file = log_files['bicho']
        bicho_log = logs(log_file, MAX_LOG_BYTES, MAX_LOG_FILES)


        # we compose some flags
        flags = ""
        if debug:
            flags = flags + " -g"

        # we'll only create the log table in the last execution
        cont = 0
        last = len(trackers)

        # pre-scripts
        launch_pre_tool_scripts(section)

        for t in trackers:
            launched = True
            cont = cont + 1

            if cont == last and log_table:
                flags = flags + " -l"

            user_opt = ''

            # Authentication parameters
            if backend_token:
                user_opt = '--backend-token=%s' % (backend_token)
            elif backend_user and backend_password:
                user_opt = '--backend-user=%s --backend-password=%s' % (backend_user, backend_password)

            if num_issues_query:
                user_opt = user_opt + ' --num-issues=%s' % (num_issues_query)

            cmd = tools['its'] + " --db-user-out=%s --db-password-out=%s --db-database-out=%s -d %s -b %s %s -u %s %s >> %s 2>&1" \
                        % (db_user, db_pass, database, str(delay), backend, user_opt, t, flags, log_file)
            bicho_log.info(cmd)
            os.system(cmd)
        if launched:
            main_log.info("[OK] bicho executed")

            # post-scripts
            launch_post_tool_scripts(section)
        else:
            main_log.info("[skipped] bicho was not executed")
    else:
        main_log.info("[skipped] bicho not executed, no conf available for " + section)

def launch_gather():
    """ This tasks will execute in parallel all data gathering tasks """
    main_log.info("Executing all data gathering tasks in parallel")

    from multiprocessing import Process, active_children

    gather_tasks_order = ['cvsanaly','bicho','gerrit','mlstats',
                          'irc','mediawiki', 'downloads', 'sibyl',
                          'octopus','pullpo','eventizer']
    for section in gather_tasks_order:
        p = Process(target=tasks_section_gather[section])
        p.start()

    # Wait until all processes finish
    while True:
        active = active_children()
        if len(active) == 0:
            break
        else:
            time.sleep(0.5)

def remove_gerrit_repositories(repositories, db_user, db_pass, database):
    for project in repositories:
        main_log.info("Removing %s " % (project))
        # Remove not found projects.
        # WARNING: if a repository name is different from the one in the database
        # list of repositories, this piece of code may remove all
        # of the repositories in the database.
        # An example would be how Gerrit returns the name of the projects, while
        # Bicho stores such information in URL format.
        proc = subprocess.Popen([tools['rremoval'], "-u", db_user, "-p", db_pass,
                                "-d", database, "-b", "bicho", "-r", project],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process_output = proc.communicate()

def update_gerrit_repositories(db_user, db_pass, database, trackers):
        # Retrieving projects from database
        proc = subprocess.Popen([tools['rremoval'], "-u", db_user, "-p", db_pass,
                                 "-d", database, "-b", "bicho", "-l"],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process_output = proc.communicate()
        db_projects = eval(process_output[0])

        # Retrieving projects
        if options['gerrit'].has_key('projects'):
            projects = options['gerrit']['projects']
            projects = [str(trackers[0]) + "_" + project.replace('"', '') for project in projects]
        else:
            all_projects = repositories(repos_dir + GERRIT_PROJECTS)
            # Open repositories to be analyzed
            projects_blacklist = repositories(repos_dir + GERRIT_PROJECTS_BLACKLIST)
            projects = [project for project in all_projects if project not in projects_blacklist ]
            # Using format from Bicho database to manage Gerrit URLs
            projects = [str(trackers[0]) + "_" + project for project in projects]
            projects_blacklist = [str(trackers[0]) + "_" + project for project in projects_blacklist]

            # Removing blacklist projects if they are found in the database
            projects_blacklist = [project for project in projects_blacklist if project in db_projects]
            main_log.info("Removing the following projects found in the blacklist and in the database")
            # Checking if more than a 5% of the total list is going to be removed.
            # If so, a warning message is raised and no project is removed.
            if len(projects) == 0 or float(len(projects_blacklist))/float(len(projects)) > 0.05:
                main_log.info("WARNING: More than a 5% of the total number of projects is required to be removed. No action.")
            else:
                remove_gerrit_repositories(projects_blacklist, db_user, db_pass, database)

        # Removing those projects that are found in the database, but not in
        # the list of projects.
        to_remove_projects = [project for project in db_projects if project not in projects]
        main_log.info("Removing the following deprecated projects from the database")
        if len(projects) == 0 or float(len(to_remove_projects)) / float(len(projects)) >= 0.05:
            main_log.info("WARNING: More than a 5% of the total number of projects is required to be removed. No action.")
        else:
            remove_gerrit_repositories(to_remove_projects, db_user, db_pass, database)        # Retrieving projects
        if options['gerrit'].has_key('projects'):
            projects = options['gerrit']['projects']
            projects = [str(trackers[0]) + "_" + project.replace('"', '') for project in projects]
        else:
            all_projects = repositories(repos_dir + GERRIT_PROJECTS)
            # Open repositories to be analyzed
            projects_blacklist = repositories(repos_dir + GERRIT_PROJECTS_BLACKLIST)
            projects = [project for project in all_projects if project not in projects_blacklist ]
            # Using format from Bicho database to manage Gerrit URLs
            projects = [str(trackers[0]) + "_" + project for project in projects]
            projects_blacklist = [str(trackers[0]) + "_" + project for project in projects_blacklist]

            # Removing blacklist projects if they are found in the database
            projects_blacklist = [project for project in projects_blacklist if project in db_projects]
            main_log.info("Removing the following projects found in the blacklist and in the database")
            # Checking if more than a 5% of the total list is going to be removed.
            # If so, a warning message is raised and no project is removed.
            if len(projects) == 0 or float(len(projects_blacklist))/float(len(projects)) > 0.05:
                main_log.info("WARNING: More than a 5% of the total number of projects is required to be removed. No action.")
            else:
                remove_gerrit_repositories(projects_blacklist, db_user, db_pass, database)

        # Removing those projects that are found in the database, but not in
        # the list of projects.
        to_remove_projects = [project for project in db_projects if project not in projects]
        main_log.info("Removing the following deprecated projects from the database")
        if len(projects) == 0 or float(len(to_remove_projects)) / float(len(projects)) >= 0.05:
            main_log.info("WARNING: More than a 5% of the total number of projects is required to be removed. No action.")
        else:
            remove_gerrit_repositories(to_remove_projects, db_user, db_pass, database)

        return projects

def launch_gerrit():
    # reads a conf file with all of the information and launches bicho
    if options.has_key('gerrit'):
        backend  = options['gerrit']['backend']

        if not check_tool(tools['scr']):
            return

        main_log.info("bicho (gerrit) is being executed")
        launched = False

        database = options['generic']['db_gerrit']
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        delay = options['gerrit']['delay']
        backend = options['gerrit']['backend']
        trackers = options['gerrit']['trackers']

        debug = options['gerrit']['debug']
        log_table = None
        if options['gerrit'].has_key('log_table'):
            log_table = options['gerrit']['log_table']
        log_file = log_files['gerrit']
        gerrit_log = logs(log_file, MAX_LOG_BYTES, MAX_LOG_FILES)

        flags = ""
        if debug:
            flags = flags + " -g"

        if backend == 'gerrit':
            projects = update_gerrit_repositories(db_user, db_pass, database, trackers)
            projects = [project.replace(str(trackers[0]) + "_", "") for project in projects]
        elif backend == 'reviewboard':
            projects = options['gerrit']['projects']
            projects = [str(trackers[0]) + "/groups/" + project.replace('"', '') for project in projects]
        else:
            main_log.info("[skipped] bicho (gerrit) not executed. Backend %s not found." % backend)
            return

        # pre-scripts
        launch_pre_tool_scripts('gerrit')

        # we'll only create the log table in the last execution
        cont = 0
        last = len(projects)

        # Re-formating the projects name
        for project in projects:
            launched = True
            cont = cont + 1

            if cont == last and log_table:
                flags = flags + " -l"

            g_user = ''
            if options['gerrit'].has_key('user'):
                g_user = '--backend-user ' + options['gerrit']['user']
            if backend == 'gerrit':
                cmd = tools['scr'] + " --db-user-out=%s --db-password-out=%s --db-database-out=%s -d %s -b %s %s -u %s --gerrit-project=%s %s >> %s 2>&1" \
                            % (db_user, db_pass, database, str(delay), backend, g_user, trackers[0], project, flags, log_file)
            elif backend == 'reviewboard':
                cmd = tools['scr'] + " --db-user-out=%s --db-password-out=%s --db-database-out=%s -d %s -b %s -u %s %s >> %s 2>&1" \
                            % (db_user, db_pass, database, str(delay), backend, project, flags, log_file)
            else:
                main_log.info("[skipped] bicho (gerrit) not executed. Backend %s not found." % backend)
                return

            gerrit_log.info(cmd)
            os.system(cmd)

        if launched:
            main_log.info("[OK] bicho (gerrit) executed")

            # post-scripts
            launch_post_tool_scripts('gerrit')
        else:
            main_log.info("[skipped] bicho (gerrit) not executed")
    else:
        main_log.info("[skipped] bicho (gerrit) not executed, no conf available")

def launch_mlstats():
    if options.has_key('mlstats'):
        if not check_tool(tools['mls']):
            return

        main_log.info("mlstats is being executed")
        launched = False
        db_admin_user = options['generic']['db_user']
        db_user = db_admin_user
        db_pass = options['generic']['db_password']
        db_name = options['generic']['db_mlstats']
        # Retrieving mailing lists
        if options['mlstats'].has_key('mailing_lists'):
            mlists = options['mlstats']['mailing_lists'].split(",")
            mlists = [m[m.find('"')+1:m.rfind('"')] for m in mlists]
        else:
            mlists = repositories(MLSTATS_MAILING_LISTS)

        force = ''
        if options['mlstats'].has_key('force'):
            if options['mlstats']['force'] is True:
                force = '--force'
        log_file = log_files['mlstats']
        mlstats_log = logs(log_file, MAX_LOG_BYTES, MAX_LOG_FILES)


        # pre-scripts
        launch_pre_tool_scripts('mlstats')

        for m in mlists:
            launched = True
            cmd = tools['mls'] + " %s --no-report --db-user=\"%s\" --db-password=\"%s\" --db-name=\"%s\" --db-admin-user=\"%s\" --db-admin-password=\"%s\" \"%s\" >> %s 2>&1" \
                        %(force, db_user, db_pass, db_name, db_admin_user, db_pass, m, log_file)
            mlstats_log.info(cmd)
            os.system(cmd)
        if launched:
            main_log.info("[OK] mlstats executed")

            # post-scripts
            launch_post_tool_scripts('mlstats')
        else:
            main_log.info("[skipped] mlstats not executed")
    else:
        main_log.info("[skipped] mlstats was not executed, no conf available")

def launch_irc():
    if options.has_key('irc'):
        if not check_tool(tools['irc']):
            return

        main_log.info("irc_analysis is being executed")
        launched = False
        db_admin_user = options['generic']['db_user']
        db_user = db_admin_user
        db_pass = options['generic']['db_password']
        db_name = options['generic']['db_irc']
        format = 'plain'
        if options['irc'].has_key('format'):
            format = options['irc']['format']
        channels = os.listdir(irc_dir)
        os.chdir(irc_dir)
        log_file = log_files['irc']
        irc_log = logs(log_file, MAX_LOG_BYTES, MAX_LOG_FILES)


        # pre-scripts
        launch_pre_tool_scripts('irc')

        if format == 'slack':
            if options['irc'].has_key('token'):
                token = options['irc']['token']
                launched = True
                cmd = tools['irc'] + " --db-user=\"%s\" --db-password=\"%s\" --database=\"%s\" --token %s --format %s>> %s 2>&1" \
                            % (db_user, db_pass, db_name, token, format, log_file)
                irc_log.info(cmd)
                os.system(cmd)
            else:
                main_log.error("Slack IRC supports need token option.")
        else:
            for channel in channels:
                if not os.path.isdir(os.path.join(irc_dir,channel)): continue
                launched = True
                cmd = tools['irc'] + " --db-user=\"%s\" --db-password=\"%s\" --database=\"%s\" --dir=\"%s\" --channel=\"%s\" --format %s>> %s 2>&1" \
                            % (db_user, db_pass, db_name, channel, channel, format, log_file)
                irc_log.info(cmd)
                os.system(cmd)
        if launched:
            main_log.info("[OK] irc_analysis executed")

            # post-scripts
            launch_post_tool_scripts('irc')
        else:
            main_log.info("[skipped] irc_analysis not executed")
    else:
        main_log.info("[skipped] irc_analysis was not executed, no conf available")


def launch_mediawiki():
    if options.has_key('mediawiki'):
        backend  = options['mediawiki']['backend']

        if backend == 'mediawiki':
            launch_mediawiki_analysis()
        elif backend == 'confluence':
            launch_confluence_analysis()
        else:
            main_log.info("[skipped] mediawiki %s backend not available" % backend)
    else:
        main_log.info("[skipped] mediawiki was not executed, no conf available")


def launch_mediawiki_analysis():
    if options.has_key('mediawiki'):
        if not check_tool(tools['mediawiki']):
            return

        main_log.info("mediawiki_analysis is being executed")
        launched = False
        db_admin_user = options['generic']['db_user']
        db_user = db_admin_user
        db_pass = options['generic']['db_password']
        db_name = options['generic']['db_mediawiki']
        sites = options['mediawiki']['sites']
        log_file = log_files['mediawiki']
        mediawiki_log = logs(log_file, MAX_LOG_BYTES, MAX_LOG_FILES)


        # pre-scripts
        launch_pre_tool_scripts('mediawiki')

        for site in sites.split(","):
            launched = True
            # ./mediawiki_analysis.py --database acs_mediawiki_rdo_2478 --db-user root --url http://openstack.redhat.com
            cmd = tools['mediawiki'] + " --db-user=\"%s\" --db-password=\"%s\" --database=\"%s\" --url=\"%s\" >> %s 2>&1" \
                      %(db_user, db_pass, db_name,  sites, log_file)
            mediawiki_log.info(cmd)
            os.system(cmd)
        if launched:
            main_log.info("[OK] mediawiki_analysis executed")

            # post-scripts
            launch_post_tool_scripts('mediawiki')
        else:
            main_log.info("[skipped] mediawiki_analysis not executed")
    else:
        main_log.info("[skipped] mediawiki_analysis was not executed, no conf available")


def launch_confluence_analysis():
    if options.has_key('mediawiki'):
        if not check_tool(tools['confluence']):
            return

        main_log.info("confluence_analysis is being executed")
        launched = False
        db_admin_user = options['generic']['db_user']
        db_user = db_admin_user
        db_pass = options['generic']['db_password']
        db_name = options['generic']['db_mediawiki']
        url = options['mediawiki']['url']
        spaces = options['mediawiki']['spaces']
        log_file = log_files['confluence']
        confluence_log = logs(log_file, MAX_LOG_BYTES, MAX_LOG_FILES)

        # pre-scripts
        launch_pre_tool_scripts('mediawiki')

        for space in spaces.split(","):
            launched = True
            # ./confluence_analysis.py -d acs_confluence_geode -u root -p root https://cwiki.apache.org/confluence/
            cmd = tools['confluence'] + " -u \"%s\" -p \"%s\" -d \"%s\" \"%s\" \"%s\" >> %s 2>&1" \
                      % (db_user, db_pass, db_name, url, space, log_file)
            confluence_log.info(cmd)
            os.system(cmd)

        if launched:
            main_log.info("[OK] confluence_analysis executed")

            # post-scripts
            launch_post_tool_scripts('mediawiki')
        else:
            main_log.info("[skipped] confluence_analysis not executed")
    else:
        main_log.info("[skipped] confluence_analysis was not executed, no conf available")


def launch_downloads():
    # check if downloads option exists. If it does, downloads are executed
    if options.has_key('downloads'):
        main_log.info("downloads does not execute any tool. Only pre and post scripts")

        # pre-scripts
        launch_pre_tool_scripts('downloads')
        # post-scripts
        launch_post_tool_scripts('downloads')

def launch_sibyl():
    # check if sibyl option exists
    if options.has_key('sibyl'):
        if not check_tool(tools['sibyl']):
            return
        if not options['sibyl'].has_key('url'):
            return

        main_log.info("sibyl is being executed")
        launched = False
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        # db_name = options['generic']['db_qaforums']
        db_name = options['generic']['db_sibyl']
        url = options['sibyl']['url']
        backend = options['sibyl']['backend']
        api_key = tags = ""
        if 'api_key' in options['sibyl']:
            api_key = " -k \"" +  options['sibyl']['api_key'] + "\""
        if 'tags' in options['sibyl']:
            tags = " --tags \"" + options['sibyl']['tags'] + "\""
        log_file = log_files['sibyl']
        sibyl_log = logs(log_file, MAX_LOG_BYTES, MAX_LOG_FILES)

        # pre-scripts
        launch_pre_tool_scripts('sibyl')

        cmd = tools['sibyl'] + " --db-user=\"%s\" --db-password=\"%s\" --database=\"%s\" --url=\"%s\" --type=\"%s\" %s %s >> %s 2>&1" \
                      %(db_user, db_pass, db_name,  url, backend, api_key, tags, log_file)
        sibyl_log.info(cmd)
        os.system(cmd)
        # TODO: it's needed to check if the process correctly finished
        launched = True

        if launched:
            main_log.info("[OK] sibyl executed")
        else:
            main_log.info("[skipped] sibyl not executed")
    else:
        main_log.info("[skipped] sibyl was not executed, no conf available")

def pull_directory(path):

    pr = subprocess.Popen(['/usr/bin/git', 'fetch', 'origin'],
                          cwd=os.path.dirname(path),
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          shell=False)
    (out, error) = pr.communicate()


    pr = subprocess.Popen(['/usr/bin/git', 'reset', '--hard', 'origin/master', '--'],
                          cwd=os.path.dirname(path),
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          shell=False)
    (out, error) = pr.communicate()

def push_directory(path):

    pr = subprocess.Popen(['/usr/bin/git', 'add', './*'],
                          cwd=os.path.dirname(path),
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          shell=False)
    (out, error) = pr.communicate()

    pr = subprocess.Popen(['/usr/bin/git', 'commit', '-m', 'Updated by the Owl Bot'],
                          cwd=os.path.dirname(path),
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          shell=False)
    (out, error) = pr.communicate()

    pr = subprocess.Popen(['/usr/bin/git', 'push', 'origin', 'master'],
                          cwd=os.path.dirname(path),
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          shell=False)
    (out, error) = pr.communicate()


def launch_octopus():

    launch_octopus_puppet()
    launch_octopus_docker()
    launch_octopus_github()
    launch_octopus_gerrit()


def launch_octopus_export(cmd, backend):
    """ Exports the list of repositories to the specific config file"""

    # Adding the '--export' option, this disables the rest of the Octopus options
    cmd = cmd + ' --export '

    if backend == 'puppet':
        output = PUPPET_RELEASES
    elif backend == 'docker':
        output = DOCKER_PACKAGES
    elif backend == 'github':
        output = CVSANALY_REPOSITORIES
    elif backend == 'gerrit':
        output = GERRIT_PROJECTS

    if not os.path.isdir(repos_dir):
        main_log.info("WARNING: '" + repos_dir + "' does not exist")

    if os.path.isdir(repos_dir):
        # This tries to fetch and push new data when exporting octopus info
        pull_directory(repos_dir)
    os.system(cmd + " > " + repos_dir + output)

    if os.path.isdir(repos_dir):
        # This tries to push new changes in the file
        push_directory(repos_dir)

def launch_octopus_puppet():
    # check if octopus_puppet option exists
    if options.has_key('octopus_puppet'):
        if not check_tool(tools['octopus']):
            return

        main_log.info("octopus for puppet is being executed")
        launched = False
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        db_name = options['generic']['db_releases']
        url = options['octopus_puppet']['url']
        log_file = log_files['octopus_puppet']
        octopus_puppet_log = logs(log_file, MAX_LOG_BYTES, MAX_LOG_FILES)

        # pre-scripts
        launch_pre_tool_scripts('octopus_puppet')

        cmd = tools['octopus'] + " -u \"%s\" -p \"%s\" -d \"%s\" puppet \"%s\">> %s 2>&1" \
                      %(db_user, db_pass, db_name, url, log_file)
        export_cmd = tools['octopus'] + " -u \"%s\" -p \"%s\" -d \"%s\" puppet \"%s\" "\
                      %(db_user, db_pass, db_name, url, log_file)

        octopus_puppet_log.info(cmd)
        os.system(cmd)
        # TODO: it's needed to check if the process correctly finished
        launched = True

        # Export data if required
        if options['octopus_puppet'].has_key('export'):
            launch_octopus_export(export_cmd, 'puppet')

        if launched:
            main_log.info("[OK] octopus for puppet executed")

            launch_post_tool_scripts('octopus_puppet')
        else:
            main_log.info("[skipped] octopus for puppet not executed")
    else:
        main_log.info("[skipped] octopus for puppet was not executed, no conf available")


def launch_octopus_docker():
    # check if octopus_docker option exists
    if options.has_key('octopus_docker'):
        if not check_tool(tools['octopus']):
            return

        main_log.info("octopus for docker is being executed")
        launched = False
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        db_name = options['generic']['db_releases']
        url = options['octopus_docker']['url']
        log_file = log_files['octopus_docker']
        octopus_docker_log = logs(log_file, MAX_LOG_BYTES, MAX_LOG_FILES)

        owner = options['octopus_docker']['owner']
        owners = owner.split(",")

        # pre-scripts
        launch_pre_tool_scripts('octopus_docker')

        octopus_cmd = tools['octopus'] + " -u \"%s\" -p \"%s\" -d \"%s\" docker \"%s\" " \
            % (db_user, db_pass, db_name, url)
        export_cmd = octopus_cmd

        for owner in owners:
            owner = owner.strip()
            cmd = octopus_cmd +  "\"%s\" >> %s 2>&1" % (owner, log_file)
            octopus_docker_log.info(cmd)
            os.system(cmd)

        # Export data if required
        if options['octopus_docker'].has_key('export'):
            launch_octopus_export(export_cmd, 'docker')

        launched = True

        if launched:
            main_log.info("[OK] octopus for docker executed")

            launch_post_tool_scripts('octopus_docker')
        else:
            main_log.info("[skipped] octopus for docker not executed")
    else:
        main_log.info("[skipped] octopus for docker was not executed, no conf available")


def launch_octopus_github():
    # check if octopus_github option exists
    if options.has_key('octopus_github'):
        if not check_tool(tools['octopus']):
            return

        main_log.info("octopus for github is being executed")
        launched = False
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        db_name = options['generic']['db_releases']
        log_file = log_files['octopus_github']
        octopus_github_log = logs(log_file, MAX_LOG_BYTES, MAX_LOG_FILES)

        owner = options['octopus_github']['owner']
        owners = owner.split(",")

        if options['octopus_github'].has_key('oauth_key'):
            oauth_key = options['octopus_github']['oauth_key']
        else:
            user = options['octopus_github']['user']
            password = options['octopus_github']['password']

        url = ""
        if options['octopus_github'].has_key('url'):
            url = "--gh-url " + options['octopus']['url']

        # Common octopus command for all options
        if options['octopus_github'].has_key('oauth_key'):
            auth_params = "--gh-token " + oauth_key
        else:
            auth_params = "--gh-user=\""+user+"\" --gh-password=\""+password+"\""

        octopus_cmd = tools['octopus'] + " -u \"%s\" -p \"%s\" -d \"%s\" github %s %s " \
            %(db_user, db_pass, db_name, auth_params , url)
        export_cmd = octopus_cmd

        # pre-scripts
        launch_pre_tool_scripts('octopus_github')

        for owner in owners:
            owner = owner.strip()

            repositories = None

            if options['octopus_github'].has_key('repositories') and len(owners) == 1:
                repositories = options['octopus_github']['repositories'].split(",")
            elif options['octopus_github'].has_key('repositories'):
                main_log.error("Wrong main.conf. Several octopus github owners and general repositories config.")
                raise

            if len(owners) > 1:
                if options['octopus_github'].has_key('repositories_' + owner.lower()):
                    repositories = options['octopus_github']['repositories_' + owner.lower()].split(",")

            if repositories:
                # Launch octopus for each docker repository configured
                for repo in repositories:
                    repo = repo.strip()
                    cmd = octopus_cmd +  "\"%s\"  \"%s\">> %s 2>&1" % (owner, repo, log_file)
                    octopus_github_log.info(cmd)
                    os.system(cmd)
            else:
                # Launch octopus for all the repositories
                cmd = octopus_cmd + "\"%s\"  >> %s 2>&1" % (owner, log_file)
                octopus_github_log.info(cmd)
                os.system(cmd)

        # Export data if required
        if options['octopus_github'].has_key('export'):
            launch_octopus_export(export_cmd, 'github')

        launched = True

        if launched:
            main_log.info("[OK] octopus for github executed")

            launch_post_tool_scripts('octopus_github')
        else:
            main_log.info("[skipped] octopus for github not executed")
    else:
        main_log.info("[skipped] octopus for github was not executed, no conf available")


def launch_octopus_gerrit():
    """ Octopus Gerrit backend """

    launched = False
    if options.has_key('octopus_gerrit'):
        if not check_tool(tools['octopus']):
            return

        main_log.info("octopus for gerrit is being executed")
        # Common options
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        db_name = options['generic']['db_octopus']
        log_file = log_files['octopus_gerrit']
        octopus_gerrit_log = logs(log_file, MAX_LOG_BYTES, MAX_LOG_FILES)

        # Gerrit specific options
        gerrit_user = options['octopus_gerrit']['gerrit_user']
        gerrit_url = options['octopus_gerrit']['gerrit_url']

        octopus_cmd = tools['octopus'] + " -u \"%s\" -p \"%s\" -d \"%s\" gerrit --gerrit-user \"%s\" --gerrit-url \"%s\" " \
                      % (db_user, db_pass, db_name, gerrit_user, gerrit_url)
        export_cmd = octopus_cmd

        # pre-scripts
        launch_pre_tool_scripts('octopus_gerrit')

        # Execute Octopus Gerrit backend
        octopus_gerrit_log.info(octopus_cmd)
        os.system(octopus_cmd)

        launched = True
        main_log.info("[OK] octopus for gerrit executed")
        # post-scripts
        launch_post_tool_scripts('octopus_gerrit')

        # Export data if required
        if options['octopus_gerrit'].has_key('export'):
            launch_octopus_export(export_cmd, 'gerrit')

    if not launched:
        main_log.info("[skipped] octopus for gerrit not executed")


def check_sortinghat_db(db_user, db_pass, db_name):
    """ Check that the db exists and if not, create it """
    log_file = log_files['sortinghat_affiliations']
    sortinghat_affiliations_log = logs(log_file, MAX_LOG_BYTES, MAX_LOG_FILES)
    try:
         db = MySQLdb.connect(user = db_user, passwd = db_pass,  db = db_name)
         db.close()
         main_log.info("Sortinghat " + db_name + " already exists")
    except:
        main_log.error("Can't connect to " + db_name)
        main_log.info("Creating sortinghat database ...")
        cmd = tools['sortinghat'] + " -u \"%s\" -p \"%s\" init \"%s\">> %s 2>&1" \
                      %(db_user, db_pass, db_name, log_file)
        sortinghat_affiliations_log.info(cmd)
        os.system(cmd)

def launch_sortinghat():
    main_log.info("Sortinghat working ...")
    if not check_tool(tools['sortinghat']):
        main_log.error("Sortinghat tool not available,")
        return
    if 'db_sortinghat' not in options['generic']:
        main_log.error("No database for Sortinghat configured.")
        return
    project_name = options['generic']['project']
    db_user = options['generic']['db_user']
    db_pass = options['generic']['db_password']
    db_name = options['generic']['db_sortinghat']
    log_file = log_files['sortinghat']
    sortinghat_log = logs(log_file, MAX_LOG_BYTES, MAX_LOG_FILES)

    check_sortinghat_db(db_user, db_pass, db_name)

    # pre-scripts
    launch_pre_tool_scripts('sortinghat')

    # Import data from a master repo, if it's set
    success = False

    if 'master' in options['sortinghat']:
        success = restore_sortinghat_master(sortinghat_log)

    # For each data source export identities and load them in sortinghat
    report = get_report_module()
    dss = report.get_data_sources()
    dss_not_supported = ['downloads']

    # Temporal file to export and import identities from/in SH
    io_file = NamedTemporaryFile()
    io_file_name = io_file.name
    io_file.close()

    # Import data in Sorting Hat
    for ds in dss:
        if ds.get_name() in dss_not_supported: continue
        if ds.get_db_name() in options['generic']:
            db_ds = options['generic'][ds.get_db_name()]
        else:
            main_log.error(ds.get_db_name() + " not in automator main.conf")
            continue
        # Export identities from ds
        cmd = tools['mg2sh'] + " -u \"%s\" -p \"%s\" -d \"%s\" --source \"%s:%s\" -o %s >> %s 2>&1" \
                      %(db_user, db_pass, db_ds, project_name.lower(), ds.get_name(), io_file_name, log_file)
        sortinghat_log.info(cmd)
        os.system(cmd)
        # Load identities in sortinghat in incremental mode
        cmd = tools['sortinghat'] + " -u \"%s\" -p \"%s\" -d \"%s\" load --matching email-name -n %s >> %s 2>&1" \
                      %(db_user, db_pass, db_name, io_file_name, log_file)
        sortinghat_log.info(cmd)
        os.system(cmd)
        os.remove(io_file_name)

    # Complete main identifier
    db_pass_id = db_pass
    if db_pass_id == '': db_pass_id = "''"
    identifier2sh = identities_dir + '/identifier2sh.py'
    cmd = identifier2sh + " -u %s -p %s -d \"%s\" " % (db_user, db_pass_id, db_name)
    sortinghat_log.info(cmd)
    os.system(cmd)

    # Do affiliations
    cmd = tools['sortinghat'] + " -u \"%s\" -p \"%s\" -d \"%s\" affiliate  >> %s 2>&1" \
              %(db_user, db_pass, db_name, log_file)
    sortinghat_log.info(cmd)
    os.system(cmd)

    # Export data from Sorting Hat
    for ds in dss:
        if ds.get_name() in dss_not_supported: continue
        if ds.get_db_name() in options['generic']:
            db_ds = options['generic'][ds.get_db_name()]
        else:
            main_log.error(ds.get_db_name() + " not in automator main.conf")
            continue
        # Export identities from sh to file
        cmd = tools['sortinghat'] + " -u \"%s\" -p \"%s\" -d \"%s\" export --source \"%s:%s\" --identities %s >> %s 2>&1" \
                      %(db_user, db_pass, db_name, project_name.lower(), ds.get_name(), io_file_name, log_file)
        sortinghat_log.info(cmd)
        os.system(cmd)
        # Load identities in mg from file
        cmd = tools['sh2mg'] + " -u \"%s\" -p \"%s\" -d \"%s\" --source \"%s:%s\" %s >> %s 2>&1" \
                      %(db_user, db_pass, db_ds, project_name.lower(), ds.get_name(), io_file_name, log_file)
        sortinghat_log.info(cmd)
        os.system(cmd)
        os.remove(io_file_name)

    # Create domains tables
    if db_pass == '': db_pass = "''"
    db_sortinghat = options['generic']['db_sortinghat']
    cmd = "%s/domains_analysis.py -u %s -p %s -d %s --sortinghat>> %s 2>&1" \
        % (identities_dir, db_user, db_pass, db_name, log_file)
    sortinghat_log.info(cmd)
    os.system(cmd)

    if 'master' in options['sortinghat'] and success:
        upload_sortinghat_master(sortinghat_log)

    # post-scripts
    launch_post_tool_scripts('sortinghat')

    main_log.info("Sortinghat done")


def restore_sortinghat_master(restore_sortinghat_log):
    db_user = options['generic']['db_user']
    db_pass = options['generic']['db_password']
    db_name = options['generic']['db_sortinghat']
    log_file = log_files['sortinghat']

    master_dir = project_dir + '/sortinghat/'
    sh_master =  master_dir + options['sortinghat']['master']

    # Update master repository
    pull_directory(master_dir)

    # Export sh information to a file
    ts = dt.datetime.now()
    ts = str(ts.date())
    backup_file = project_dir + '/backups/sh_' + ts + '.json'

    code = export_sortinghat(restore_sortinghat_log, db_user, db_pass, db_name, backup_file, log_file)

    if code != 0:
        main_log.info("Error making a Sorting Hat backup.")
        return False
    else:
        main_log.info("Sorting Hat backup dumped to %s" % (backup_file))

    # Drop database
    db = MySQLdb.connect(user=db_user, passwd=db_pass)
    cursor = db.cursor()
    query = "DROP DATABASE " + db_name
    cursor.execute(query)
    db.close()

    # Create the new database
    check_sortinghat_db(db_user, db_pass, db_name)

    # Import data from master file
    code = import_sortinghat(restore_sortinghat_log, db_user, db_pass, db_name, sh_master, log_file)

    if code != 0:
        main_log.info("Error importing Sorting Hat data from master file %s." % sh_master)
        main_log.info("Restoring old data")

        code = import_sortinghat(restore_sortinghat_log, db_user, db_pass, db_name, backup_file, log_file)

        if code != 0:
            msg = "Fatal error restoring Sorting Hat backup"
            main_log.info(msg)
            raise Exception(msg)
        else:
            main_log.info("Backup restored.")
            main_log.info("New Sorting Hat info will not updated on master file.")
            return False
    else:
        main_log.info("Data from master file imported into Sorting Hat")

    return True


def upload_sortinghat_master(upload_sortinghat_log):
    db_user = options['generic']['db_user']
    db_pass = options['generic']['db_password']
    db_name = options['generic']['db_sortinghat']
    log_file = log_files['sortinghat']

    master_dir = project_dir + '/sortinghat/'
    sh_master =  master_dir + options['sortinghat']['master']

    export_sortinghat(upload_sortinghat_log, db_user, db_pass, db_name, sh_master, log_file)

    code = push_directory(master_dir)


def import_sortinghat(import_sortinghat_log, db_user, db_pass, db_name, io_file_name, log_file):
    cmd = tools['sortinghat'] + " -u \"%s\" -p \"%s\" -d \"%s\" load %s >> %s 2>&1" \
            % (db_user, db_pass, db_name, io_file_name, log_file)
    import_sortinghat_log.info(cmd)

    retcode = os.system(cmd)

    return retcode


def export_sortinghat(export_sortinghat_log, db_user, db_pass, db_name, io_file_name, log_file):
    cmd = tools['sortinghat'] + " -u \"%s\" -p \"%s\" -d \"%s\" export --identities %s >> %s 2>&1" \
            % (db_user, db_pass, db_name, io_file_name, log_file)
    export_sortinghat_log.info(cmd)

    retcode = os.system(cmd)

    return retcode


def launch_pullpo():
    # check if octopusl option exists
    if options.has_key('pullpo'):
        if not check_tool(tools['pullpo']):
            return

        main_log.info("pullpo is being executed")
        launched = False
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        db_name = options['generic']['db_pullpo']
        owner = options['pullpo']['owner']
        owners = owner.split(",")
        if options['pullpo'].has_key('oauth_key'):
            oauth_key = options['pullpo']['oauth_key']
        else:
            user = options['pullpo']['user']
            password = options['pullpo']['password']
        url = ""
        if options['pullpo'].has_key('url'):
            url = "--gh-url " + options['pullpo']['url']
        log_file = log_files['pullpo']
        pullpo_log = logs(log_file, MAX_LOG_BYTES, MAX_LOG_FILES)

        # pre-scripts
        launch_pre_tool_scripts('pullpo')

        # Common pullpo command for all options
        if options['pullpo'].has_key('oauth_key'):
            auth_params = "--gh-token " + oauth_key
        else:
            auth_params = "--gh-user=\""+user+"\" --gh-password=\""+password+"\""

        pullpo_cmd = tools['pullpo'] + " -u \"%s\" -p \"%s\" -d \"%s\" %s %s " \
                          %(db_user, db_pass, db_name, auth_params , url)

        for owner in owners:
            projects = None
            if options['pullpo'].has_key('projects') and len(owners) == 1:
                projects = options['pullpo']['projects']
            elif options['pullpo'].has_key('projects'):
                main_log.error("Wrong main.conf. Several pullpo owners and general projects config.")
                raise
            if len(owners) > 1:
                if options['pullpo'].has_key('projects_' + owner.lower()):
                    projects = options['pullpo']['projects_' + owner.lower()].split(",")
            if projects:
                # Launch pullpo for each project configured
                for project in projects:
                    cmd = pullpo_cmd +  "\"%s\"  \"%s\">> %s 2>&1" % (owner, project, log_file)
                    pullpo_log.info(cmd)
                    os.system(cmd)
            else:
                # Launch pullpo for all the repositories
                cmd = pullpo_cmd + "\"%s\"  >> %s 2>&1" % (owner, log_file)
                pullpo_log.info(cmd)
                os.system(cmd)
        launched = True

        if launched:
            main_log.info("[OK] pullpo executed")
        else:
            main_log.info("[skipped] pullpo not executed")
    else:
        main_log.info("[skipped] pullpo was not executed, no conf available")

def launch_eventizer():
    # check if eventizer option exists
    if options.has_key('eventizer'):
        if not check_tool(tools['eventizer']):
            return

        main_log.info("eventizer is being executed")
        launched = False
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        db_name = options['generic']['db_eventizer']

        if 'key' not in options['eventizer']:
            msg = "Metup API key not provided. Use 'key' parameter to set one."
            main_log.error('[eventizer] ' + msg)
            main_log.info("[skipped] eventizer not executed. %s" % msg)
            return

        if 'groups' not in options['eventizer']:
            msg = "Groups list not provided. Use 'groups' parameter to set one."
            main_log.error('[eventizer] ' + msg)
            main_log.info("[skipped] eventizer not executed. %s" % msg)
            return

        eventizer_key = options['eventizer']['key']

        groups = options['eventizer']['groups']
        groups = groups.split(",")

        log_file = log_files['eventizer']
        eventizer_log = logs(log_file, MAX_LOG_BYTES, MAX_LOG_FILES)

        # pre-scripts
        launch_pre_tool_scripts('eventizer')

        # Common pullpo command for all options
        auth_params = "--key " + eventizer_key

        eventizer_cmd = tools['eventizer'] + " -u \"%s\" -p \"%s\" -d \"%s\" %s " \
                             %(db_user, db_pass, db_name, auth_params)

        for group in groups:
            # Launch eventizer for each group
            group_name = group.strip()

            cmd = eventizer_cmd +  "\"%s\" >> %s 2>&1" % (group_name, log_file)
            eventizer_log.info(cmd)
            os.system(cmd)
            launched = True

        if launched:
            main_log.info("[OK] eventizer executed")

            # post-scripts
            launch_post_tool_scripts('eventizer')
        else:
            main_log.info("[skipped] eventizer not executed")
    else:
        main_log.info("[skipped] eventizer was not executed, no conf available")

# http://code.activestate.com/recipes/577376-simple-way-to-execute-multiple-process-in-parallel/
def exec_commands(cmds):
    ''' Exec commands in parallel in multiple process '''

    if not cmds: return # empty list

    def done(p):
        return p.poll() is not None
    def success(p):
        return p.returncode == 0
    def fail():
        main_log.error("Problems in report_tool.py execution. See logs.")
        sys.exit(1)

    # max_task = cpu_count()
    max_tasks = 2
    processes = []
    while True:
        while cmds and len(processes) < max_tasks:
            task = cmds.pop()
            # print subprocess.list2cmdline(task)
            processes.append(subprocess.Popen(task, shell = True))

        for p in processes:
            if done(p):
                if success(p):
                    processes.remove(p)
                else:
                    fail()

        if not processes and not cmds:
            break
        else:
            time.sleep(0.5)

def get_report_module():
    grimoirelib = os.path.join(project_dir, "tools", "GrimoireLib","vizgrimoire")
    metricslib = os.path.join(project_dir, "tools", "GrimoireLib","vizgrimoire","metrics")
    studieslib = os.path.join(project_dir, "tools", "GrimoireLib","vizgrimoire","analysis")
    alchemy = os.path.join(project_dir, "tools", "GrimoireLib")
    for dir in [grimoirelib,metricslib,studieslib,alchemy]:
        sys.path.insert(0,dir)
    import report
    report.Report.init(os.path.join(conf_dir,"main.conf"))
    return report.Report

def launch_events_scripts():
    # Execute metrics tool using the automator config
    # Start one report_tool per data source active
    if options.has_key('metrics') or options.has_key('r'):

        main_log.info("events being generated")

        json_dir = '../../../json'
        conf_file = project_dir + '/conf/main.conf'
        log_file = project_dir + '/log/analysis_'

        metrics_tool = "report_tool.py"
        path = r_dir

        params = get_options()

        commands = [] # One report_tool per data source
        report = get_report_module()
        dss = report.get_data_sources()

        if params.subtask:
            ds = report.get_data_source(params.subtask)
            if ds is None:
                main_log.error("Data source " + params.subtask + " not found")
                return
            dss = [ds]

        ds_events_supported = ['scm']
        for ds in dss:
            if ds.get_name() not in ds_events_supported: continue
            log_file_ds = log_file + ds.get_name()+"-events.log"
            os.chdir(path)
            cmd = "./%s -c %s -o %s --data-source %s --events  >> %s 2>&1" \
                % (metrics_tool, conf_file, json_dir, ds.get_name(), log_file_ds)
            commands.append([cmd])

        exec_commands (commands)

        main_log.info("[OK] events generated")

    else:
        main_log.info("[skipped] Events not generated, no conf available")


def launch_metrics_scripts():
    # Execute metrics tool using the automator config
    # Start one report_tool per data source active

    if options.has_key('metrics') or options.has_key('r'):
        if not check_tool(tools['r']):
            return

        main_log.info("metrics tool being launched")

        r_libs = '../../r-lib'
        python_libs = '../grimoirelib_alch:../vizgrimoire:../vizgrimoire/analysis:../vizgrimoire/metrics:./'
        json_dir = '../../../json'
        metrics_dir = '../vizgrimoire/metrics'
        conf_file = project_dir + '/conf/main.conf'
        log_file = project_dir + '/log/analysis_'


        metrics_tool = "report_tool.py"
        path = r_dir

        launch_pre_tool_scripts('r')

        params = get_options()

        metrics_section = ''
        if params.filter:
            metrics_section = "--filter " + params.filter

        commands = [] # One report_tool per data source
        report = get_report_module()
        dss = report.get_data_sources()

        if params.subtask:
            report = get_report_module()
            ds = report.get_data_source(params.subtask)
            if ds is None:
                main_log.error("Data source " + params.subtask + " not found")
                return
            dss = [ds]

        for ds in dss:
            # if ds.get_name() not in ['scm','its']: continue
            log_file_ds = log_file + ds.get_name()+".log"
            os.chdir(path)
            cmd = "LANG= R_LIBS=%s PYTHONPATH=%s ./%s -c %s -m %s -o %s --data-source %s %s >> %s 2>&1" \
                % (r_libs, python_libs, metrics_tool, conf_file, metrics_dir, json_dir, ds.get_name(), metrics_section, log_file_ds)
            commands.append([cmd])

        exec_commands (commands)

        main_log.info("[OK] metrics tool executed")

        launch_post_tool_scripts('r')
    else:
        main_log.info("[skipped] Metrics tool was not executed, no conf available")

def get_ds_identities_cmd(db, type):
    idir = identities_dir
    db_user = options['generic']['db_user']
    db_pass = options['generic']['db_password']
    if (db_pass == ""): db_pass="''"
    db_ids = options['generic']['db_identities']
    log_file = log_files['identities']

    cmd = "%s/datasource2identities.py -u %s -p %s --db-name-ds=%s --db-name-ids=%s --data-source=%s>> %s 2>&1" \
            % (idir, db_user, db_pass, db, db_ids, type, log_file)

    return cmd

def launch_identity_scripts():
    # using the conf executes cvsanaly for the repos inside scm dir
    if options.has_key('identities'):
        main_log.info("Unique identities scripts are being executed")
        # idir = options['identities']['iscripts_path']
        idir = identities_dir
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        if (db_pass == ""): db_pass="''"
        log_file = log_files['identities']
        identities_log = logs(log_file, MAX_LOG_BYTES, MAX_LOG_FILES)

        if options['generic'].has_key('db_identities') and \
            options['generic'].has_key('db_sortinghat'):
            if options['generic']['db_identities'] == options['generic']['db_sortinghat']:
                compose_msg("Sortinghat configuration. Not executing identities.")
                return

        if options['generic'].has_key('db_identities'):
            db_identities = options['generic']['db_identities']
            cmd = "%s/unifypeople.py -u %s -p %s -d %s >> %s 2>&1" % (idir, db_user, db_pass, db_identities, log_file)
            identities_log.info(cmd)
            os.system(cmd)
            cmd = "%s/domains_analysis.py -u %s -p %s -d %s >> %s 2>&1" % (idir, db_user, db_pass, db_identities, log_file)
            identities_log.info(cmd)
            os.system(cmd)

        # Generate unique identities for all data sources active
        report = get_report_module()
        dss = report.get_data_sources()
        for ds in dss:
            if ds.get_db_name() == "db_cvsanaly":
                continue # db_cvsanaly and db_identities are the same db
            if ds.get_db_name() in options['generic']:
                db_ds = options['generic'][ds.get_db_name()]
            else:
                main_log.error(ds.get_db_name() + " not in automator main.conf")
                continue
            cmd = get_ds_identities_cmd(db_ds, ds.get_name())
            identities_log.info(cmd)
            os.system(cmd)

        if options['identities'].has_key('countries'):
            cmd = "%s/load_ids_mapping.py -m countries -t true -u %s -p %s --database %s >> %s 2>&1" \
                        % (idir, db_user, db_pass, db_identities, log_file)
            identities_log.info(cmd)
            os.system(cmd)

        if options['identities'].has_key('companies'):
            cmd = "%s/load_ids_mapping.py -m companies -t true -u %s -p %s --database %s >> %s 2>&1" \
                        % (idir, db_user, db_pass, db_identities, log_file)
            identities_log.info(cmd)
            os.system(cmd)

        main_log.info("[OK] Identity scripts executed")
    else:
        main_log.info("[skipped] Unify identity scripts not executed, no conf available")

def logs(name, size, filesNumber):

    # log
    launch_log = logging.getLogger(name)
    launch_log.setLevel(logging.DEBUG)

    # rotating handler
    rotate_log = logging.handlers.RotatingFileHandler(name, backupCount=filesNumber)
    rotate_log.doRollover()

    # formatter
    formatter = logging.Formatter("[%(asctime)s] %(message)s", datefmt='%d/%b/%Y:%H:%M:%S')
    rotate_log.setFormatter(formatter)

    launch_log.addHandler(rotate_log)

    return launch_log

def launch_copy_json():
    # copy JSON files to other directories
    # This option helps when having more than one automator, but all of the
    # json files should be moved to a centralized directory
    if options.has_key('copy-json'):
        main_log.info("Copying JSON files to another directory")
        destination = os.path.join(project_dir,options['copy-json']['destination_json'])
        distutils.dir_util.copy_tree(json_dir, destination)

def launch_commit_jsones():
    # copy JSON files and commit + push them
    if options.has_key('git-production'):

        if not check_tool(tools['git']):
            return

        main_log.info("Commiting new JSON files with git")

        destination = os.path.join(project_dir,options['git-production']['destination_json'])
        distutils.dir_util.copy_tree(json_dir, destination)

        fd = open(msg_body, 'a')

        pr = subprocess.Popen(['/usr/bin/git', 'pull'],
                              cwd=os.path.dirname(destination),
                              stdout=fd,
                              stderr=fd,
                              shell=False)
        (out, error) = pr.communicate()

        pr = subprocess.Popen(['/usr/bin/git', 'add', './*'],
                              cwd=os.path.dirname(destination),
                              stdout=fd,
                              stderr=fd,
                              shell=False)
        (out, error) = pr.communicate()

        pr = subprocess.Popen(['/usr/bin/git', 'commit', '-m', 'JSON updated by the Owl Bot'],
                              cwd=os.path.dirname(destination),
                              stdout=fd,
                              stderr=fd,
                              shell=False)
        (out, error) = pr.communicate()

        pr = subprocess.Popen(['/usr/bin/git', 'push', 'origin', 'master'],
                              cwd=os.path.dirname(destination),
                              stdout=fd,
                              stderr=fd,
                              shell=False)
        (out, error) = pr.communicate()

        fd.close()

def launch_database_dump():
    # copy and compression of database to be rsync with customers
    if options.has_key('db-dump'):

        if not check_tool(tools['mysqldump']) or not check_tool(tools['compress']) or not check_tool(tools['rm']):
            return

        main_log.info("Dumping databases")

        dbs = []

        # databases
        # this may fail if any of the four is not found
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']

        if options['generic'].has_key('db_bicho'):
            dbs.append([options['generic']['db_bicho'], 'tickets']);
        if options['generic'].has_key('db_cvsanaly'):
            dbs.append([options['generic']['db_cvsanaly'],'source_code']);
        if options['generic'].has_key('db_mlstats'):
            dbs.append([options['generic']['db_mlstats'],'mailing_lists']);
        if options['generic'].has_key('db_gerrit'):
            dbs.append([options['generic']['db_gerrit'],'reviews']);
        if options['generic'].has_key('db_irc'):
            if options['irc'].has_key('format'):
                if options['irc']['format'] != 'slack':
                    dbs.append([options['generic']['db_irc'],'irc']);
            else:
                dbs.append([options['generic']['db_irc'],'irc']);
        if options['generic'].has_key('db_mediawiki'):
            dbs.append([options['generic']['db_mediawiki'],'mediawiki']);
        if options['generic'].has_key('db_releases'):
            dbs.append([options['generic']['db_releases'],'releases'])
        if options['generic'].has_key('db_qaforums'):
            dbs.append([options['generic']['db_qaforums'],'qaforums'])
        if options['generic'].has_key('db_sibyl'):
            dbs.append([options['generic']['db_sibyl'],'qaforums'])
        if options['generic'].has_key('db_downloads'):
            dbs.append([options['generic']['db_downloads'],'downloads'])
        if options['generic'].has_key('db_pullpo'):
            dbs.append([options['generic']['db_pullpo'],'pullpo'])
        if options['generic'].has_key('db_eventizer'):
            dbs.append([options['generic']['db_eventizer'],'eventizer'])
        if options['generic'].has_key('db_projects'):
            dbs.append([options['generic']['db_projects'],'projects'])

        fd = open(msg_body, 'a')
        destination = os.path.join(project_dir,options['db-dump']['destination_db_dump'])


        # it's supposed to have db_user as root user
        for db in dbs:
            dest_mysql_file = destination + db[1] + '.mysql'
            dest_7z_file = dest_mysql_file + '.7z'

            fd_dump = open(dest_mysql_file, 'w')
            # Creation of dump file
            pr = subprocess.Popen([tools['mysqldump'], '-u', db_user, '--password='+ db_pass, db[0]],
                     stdout = fd_dump,
                     stderr = fd,
                     shell = False)
            (out, error) = pr.communicate()
            fd_dump.close()

            # Creation of compressed dump file
            pr = subprocess.Popen([tools['compress'], 'a', dest_7z_file, dest_mysql_file],
                     stdout = fd,
                     stderr = fd,
                     shell = False)
            (out, error) = pr.communicate()

            # Remove not compressed file
            pr = subprocess.Popen([tools['rm'], dest_mysql_file],
                     stdout = fd,
                     stderr = fd,
                     shell = False)
            (out, error) = pr.communicate()

        fd.close()

def launch_json_dump():
    # copy and compression of json files to be rsync with customers
    if options.has_key('json-dump'):

        origin = os.path.join(project_dir,options['json-dump']['origin_json_dump'])
        origin = origin + "*.json"
        destination = os.path.join(project_dir, options['json-dump']['destination_json_dump'])

        fd = open(msg_body, 'a')

        pr = subprocess.Popen([tools['compress'], 'a', destination, origin],
                 stdout = fd,
                 stderr = fd,
                 shell = False)
        (out, error) = pr.communicate()

def launch_rsync():
    # copy JSON files and commit + push them
    if options.has_key('rsync'):

        if not check_tool(tools['rsync']):
            return

        main_log.info("rsync to production server")

        fd = open(msg_body, 'a')

        destination = options['rsync']['destination']
        pr = subprocess.Popen([tools['rsync'],'--rsh', 'ssh', '-zva', '--stats', '--progress', '--update' ,'--delete', '--exclude', '.git', production_dir, destination],
                              stdout=fd,
                              stderr=fd,
                              shell=False)
        (out, error) = pr.communicate()

        fd.close()
    else:
        main_log.info("[skipped] rsync scripts not executed, no conf available")

def write_json_config(data, filename):
    # The file should be created in project_dir
    # TODO: if file exists create a backup
    jsonfile = open(os.path.join(production_dir, filename), 'w')
    # jsonfile.write(json.dumps(data, indent=4, separators=(',', ': ')))
    jsonfile.write(json.dumps(data, indent=4, sort_keys=True))
    jsonfile.close()

def launch_metricsdef_config():
    filedir = os.path.join(production_dir, "data")
    if not os.path.isdir(filedir):
        os.makedirs(filedir)
    filename = os.path.join(filedir, "metrics.json")
    main_log.info("Writing metrics definition in: " + filename)
    report = get_report_module()
    automator_file = project_dir + '/conf/main.conf'
    metrics_dir = os.path.join(project_dir, "tools", "GrimoireLib","vizgrimoire","metrics")
    report.init(automator_file, metrics_dir)
    dss_active = report.get_data_sources()
    all_metricsdef = {}
    for ds in dss_active:
        main_log.info("Metrics def for " + ds.get_name())
        metricsdef = ds.get_metrics_definition(ds)
        if metricsdef is not None:
            all_metricsdef[ds.get_name()] = metricsdef

    from GrimoireUtils import createJSON
    createJSON(all_metricsdef, filename)

def launch_vizjs_config():
    report = get_report_module()
    config = {}
    active_ds = []

    dss = report.get_data_sources()
    for ds in dss:
        active_ds.append(ds.get_name())

    if options['generic'].has_key('markers'):
        config['markers'] = options['generic']['markers'];

    if not ('end_date' in options['r']):
        options['r']['end_date'] = time.strftime('%Y-%m-%d')

    config['data-sources'] = active_ds
    config['reports'] = options['r']['reports'].split(",")
    config['period'] = options['r']['period']
    config['start_date'] = options['r']['start_date']
    config['end_date'] = options['r']['end_date']
    config['project_info'] = get_project_info()

    main_log.info("Writing config file for VizGrimoireJS: " + production_dir + "config.json")

    write_json_config(config, 'config.json')

# create the project-info.json file
def get_project_info():
    project_info = {
        "date":"",
        "project_name" : options['generic']['project'],
        "project_url" :"",
        "scm_url":"",
        "scm_name":"",
        "scm_type":"git",
        "its_url":"",
        "its_name":"Tickets",
        "its_type":"",
        "mls_url":"",
        "mls_name":"",
        "mls_type":"",
        "scr_url":"",
        "scr_name":"",
        "scr_type":"",
        "irc_url":"",
        "irc_name":"",
        "irc_type":"",
        "mediawiki_url":"",
        "mediawiki_name":"",
        "mediawiki_type":"",
        "sibyl_url":"",
        "sibyl_name":"",
        "sibyl_type":"",
        "producer":"Automator",
        "blog_url":""
    }
    # ITS URL
    if options.has_key('bicho'):
        its_url = options['bicho']['trackers'][0]
        aux = its_url.split("//",1)
        its_url = aux[0]+"//"+aux[1].split("/")[0]
        project_info['its_url'] = its_url
    # SCM URL: not possible until automator download gits
    scm_url = ""
    # MLS URL
    if options.has_key('mlstats'):
        aux = options['mlstats']['mailing_lists']
        mls_url = aux.split(",")[0]
        aux = mls_url.split("//",1)
        if (len(aux) > 1):
            mls_url = aux[0]+"//"+aux[1].split("/")[0]
        project_info['mls_url'] = mls_url
        project_info['mls_name'] = "Mailing lists"
    # SCR URL
    if options.has_key('gerrit'):
        scr_url = "http://"+options['gerrit']['trackers'][0]
        project_info['scr_url'] = scr_url
    # Mediawiki URL
    if options.has_key('mediawiki'):
        if options['mediawiki']['backend'] == 'mediawiki':
            mediawiki_url = options['mediawiki']['sites']
            project_info['mediawiki_url'] = mediawiki_url
        elif ['mediawiki']['backend'] == 'confluence':
            confluence_url = options['mediawiki']['url']
            project_info['mediawiki_url'] = concluence_url

    return project_info

# All tasks related to data gathering
tasks_section_gather = {
    'cvsanaly':launch_cvsanaly,
    'bicho':launch_bicho,
    'downloads': launch_downloads,
    'gerrit':launch_gerrit,
    'irc': launch_irc,
    'mediawiki': launch_mediawiki,
    'mlstats':launch_mlstats,
    'sibyl': launch_sibyl,
    'octopus': launch_octopus,
    'pullpo': launch_pullpo,
    'eventizer': launch_eventizer
}

tasks_section = dict({
    'check-dbs':launch_checkdbs,
    'copy-json': launch_copy_json,
    'db-dump':launch_database_dump,
    'gather':launch_gather,
    'git-production':launch_commit_jsones,
    'identities': launch_identity_scripts,
    'sortinghat': launch_sortinghat,
    'json-dump':launch_json_dump,
    'events':launch_events_scripts,
    'metrics':launch_metrics_scripts,
    'metricsdef':launch_metricsdef_config,
    'r':launch_metrics_scripts, # compatibility support
    'rsync':launch_rsync,
    'vizjs':launch_vizjs_config
    }.items() + tasks_section_gather.items())


# vizjs: config.json deactivate until more testing in VizJS-lib
# metricsdef: metrics.json deactivated until more testing in VizJS-lib

# Use this for serial execution of data gathering
tasks_order_serial = ['check-dbs','cvsanaly','bicho','gerrit','mlstats','irc','mediawiki', 'downloads',
                      'sibyl','octopus','pullpo','eventizer', 'sortinghat','events','metrics','copy-json',
                      'git-production','db-dump','json-dump','rsync']

# Use this for parallel execution of data gathering
tasks_order_parallel = ['check-dbs','gather','sortinghat','events','metrics','copy-json',
                        'git-production','db-dump','json-dump','rsync']

tasks_order = tasks_order_parallel


if __name__ == '__main__':
    try:
        opt = get_options()
        initialize_globals(opt.project_dir)

        pid = str(os.getpid())
        pidfile = os.path.join(opt.project_dir, "launch.pid")

        if os.path.isfile(pidfile):
            # pid file could be wrong
            fd = open(pidfile, "r")
            written_pid = fd.read()
            fd.close()
            try:
                os.kill(int(written_pid), 0)
                print("%s already running pid %s\nExiting .."
                    % (pidfile, str(written_pid)))
                sys.exit(1)
            except OSError:
                # it is not running, we overwrite the pid
                file(pidfile, 'w').write(pid)
        else:
            # no pid file, let's create it
            file(pidfile, 'w').write(pid)

        main_log = logs(msg_body, MAX_LOG_BYTES, MAX_LOG_FILES)
        main_log.info("Starting ..")
        read_main_conf()
        check_tools()

        if opt.section is not None:
            tasks_section[opt.section]()
        else:
            for section in tasks_order:
                tasks_section[section]()

        main_log.info("Process finished correctly ...")

        # done, we sent the result
        project = options['generic']['project']
        mail = options['generic']['mail']
        os.system("mail -s \"[%s] data updated\" %s < %s" % (project, mail, msg_body))

        os.unlink(pidfile)
    except SystemExit as e:
        if e[0]==1:
            print("Finished OK")
        else:
            print(e)
            if os.path.isfile(project_dir+"/launch.pid"):
                os.remove(project_dir+"/launch.pid")
    except:
        print(sys.exc_info())
        if os.path.isfile(project_dir+"/launch.pid"):
            os.remove(project_dir+"/launch.pid")
