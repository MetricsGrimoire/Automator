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
    global scripts_dir
    global production_dir
    global identities_dir
    global downloads_dir
    global r_dir

    project_dir = pdir
    msg_body = project_dir + '/log/launch.log'
    scm_dir = project_dir + '/scm/'
    irc_dir = project_dir + '/irc/'
    conf_dir = project_dir + '/conf/'
    downs_dir = project_dir + '/downloads/'
    json_dir = project_dir + '/json/'
    scripts_dir = project_dir + '/scripts/'
    production_dir = project_dir + '/production/'
    identities_dir = project_dir + '/tools/VizGrimoireUtils/identities/'
    downloads_dir = project_dir + '/tools/VizGrimoireUtils/downloads/'
    r_dir = project_dir + '/tools/GrimoireLib/vizGrimoireJS/'

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
   print file_path
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

def update_scm(dir = scm_dir):
    compose_msg("SCM is being updated")
    repos = get_scm_repos()
    updated = False
    log_file = project_dir + '/log/launch_cvsanaly.log'

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
        else: compose_msg(r + " not git nor svn.", log_file)
        compose_msg(r + " update ended", log_file)

    if updated: compose_msg("[OK] SCM updated")

def check_tool(cmd):
    return os.path.isfile(cmd) and os.access(cmd, os.X_OK)
    return True

def check_tools():
    tools_ok = True
    for tool in tools:
        if not check_tool(tools[tool]):
            compose_msg(tools[tool]+" not found or not executable.")
            print (tools[tool]+" not found or not executable.")
            tools_ok = False
    if not tools_ok: print ("Missing tools. Some reports could not be created.")

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
            print ("Can't connect to " + dbname)
            db = MySQLdb.connect(user = db_user, passwd = db_password)
            cursor = db.cursor()
            query = "CREATE DATABASE " + dbname + " CHARACTER SET utf8"
            cursor.execute(query)
            db.close()
            print (dbname+" created")

def launch_scripts(scripts):
    # Run a list of scripts
    for script in scripts:
        cmd = os.path.join(scripts_dir, script) + " >> %s 2>&1" % msg_body

        compose_msg("Running %s" % cmd)
        os.system(cmd)
        compose_msg("%s script completed" % script)

def launch_pre_tool_scripts(tool):
    if tool not in options:
        return

    if options[tool].has_key('pre_scripts'):
        compose_msg("Running %s pre scripts" % tool)
        launch_scripts(options[tool]['pre_scripts'])
        compose_msg("%s pre scripts completed" % tool)
    else:
        compose_msg("No %s pre scripts configured" % tool)

def launch_post_tool_scripts(tool):
    if tool not in options:
        return

    if options[tool].has_key('post_scripts'):
        compose_msg("Running %s post scripts" % tool)
        launch_scripts(options[tool]['post_scripts'])
        compose_msg("%s post scripts completed" % tool)
    else:
        compose_msg("No %s post scripts configured" % tool)

def launch_cvsanaly():
    # using the conf executes cvsanaly for the repos inside scm dir
    if options.has_key('cvsanaly'):
        if not check_tool(tools['scm']):
            return
        update_scm()
        compose_msg("cvsanaly is being executed")
        launched = False
        db_name = options['generic']['db_cvsanaly']
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        if (db_pass == ""): db_pass = "''"
        log_file = project_dir + '/log/launch_cvsanaly.log'


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

            compose_msg(cmd, log_file)
            os.system(cmd)

        if launched:
            compose_msg("[OK] cvsanaly executed")

            # post-scripts
            launch_post_tool_scripts('cvsanaly')
        else:
            compose_msg("[SKIPPED] cvsanaly was not executed")
    else:
        compose_msg("[SKIPPED] cvsanaly not executed, no conf available")

def launch_bicho(section = None):
    do_bicho('bicho')
    # find additional configs
    do_bicho('bicho_1')

def do_bicho(section = None):
    # reads a conf file with all of the information and launches bicho
    if section is None: section = 'bicho'
    if not section.startswith("bicho"):
        logging.error("Wrong bicho section name " + section)
    if options.has_key(section):
        if not check_tool(tools['its']):
            return

        compose_msg("bicho is being executed")
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
        log_file = project_dir + '/log/launch_bicho.log'


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
            compose_msg(cmd, log_file)
            os.system(cmd)
        if launched:
            compose_msg("[OK] bicho executed")

            # post-scripts
            launch_post_tool_scripts(section)
        else:
            compose_msg("[SKIPPED] bicho was not executed")
    else:
        compose_msg("[SKIPPED] bicho not executed, no conf available for " + section)

def launch_gather():
    """ This tasks will execute in parallel all data gathering tasks """
    logging.info("Executing all data gathering tasks in parallel")

    from multiprocessing import Process, active_children

    gather_tasks_order = ['cvsanaly','bicho','gerrit','mlstats',
                          'irc','mediawiki', 'downloads', 'sibyl',
                          'octopus','pullpo','eventizer']
    for section in gather_tasks_order:
        logging.info("Executing %s ...." % (section))
        p = Process(target=tasks_section_gather[section])
        p.start()

    # Wait until all processes finish
    while True:
        active = active_children()
        if len(active) == 0:
            break
        else:
            time.sleep(0.5)

def launch_gerrit():
    # reads a conf file with all of the information and launches bicho
    if options.has_key('gerrit'):

        if not check_tool(tools['scr']):
            return

        compose_msg("bicho (gerrit) is being executed")
        launched = False

        database = options['generic']['db_gerrit']
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        delay = options['gerrit']['delay']
        backend = options['gerrit']['backend']
        trackers = options['gerrit']['trackers']

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
            all_projects = repositories(GERRIT_PROJECTS)
            # Open repositories to be analyzed
            projects_blacklist = repositories(GERRIT_PROJECTS_BLACKLIST)
            projects = [project for project in all_projects if project not in projects_blacklist ]
            # Using format from Bicho database to manage Gerrit URLs
            projects = [str(trackers[0]) + "_" + project for project in projects]
            projects_blacklist = [str(trackers[0]) + "_" + project for project in projects_blacklist]

            # Removing blacklist projects if they are found in the database
            projects_blacklist = [project for project in projects_blacklist if project in db_projects]
            compose_msg("Removing the following projects found in the blacklist and in the database")
            for project in projects_blacklist:
                compose_msg("Removing from blacklist %s " % (project))
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

        # Removing those projects that are found in the database, but not in
        # the list of projects.
        to_remove_projects = [project for project in db_projects if project not in projects]
        compose_msg("Removing the following deprecated projects from the database")
        for project in to_remove_projects:
            compose_msg("Removing %s" % (project))
            # Remove not found projects.
            # WARNING: if a repository name is different from the one in the database
            # list of repositories, this piece of code may remove all
            # of the repositories in the database.
            # An example would be how Gerrit returns the name of the projects, while
            # Bicho stores such information in URL format.
            proc = subprocess.Popen([tools['rremoval'], "-u", db_user, "-p", db_pass,
                                     "-d", database, "-b", "bicho", "-r", project],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        debug = options['gerrit']['debug']
        log_table = None
        if options['gerrit'].has_key('log_table'):
            log_table = options['gerrit']['log_table']
        log_file = project_dir + '/log/launch_gerrit.log'


        flags = ""
        if debug:
            flags = flags + " -g"

        # pre-scripts
        launch_pre_tool_scripts('gerrit')

        # we'll only create the log table in the last execution
        cont = 0
        last = len(projects)

        # Re-formating the projects name
        projects = [project.replace(str(trackers[0]) + "_", "") for project in projects]
        for project in projects:
            launched = True
            cont = cont + 1

            if cont == last and log_table:
                flags = flags + " -l"

            g_user = ''
            if options['gerrit'].has_key('user'):
                g_user = '--backend-user ' + options['gerrit']['user']
            cmd = tools['scr'] + " --db-user-out=%s --db-password-out=%s --db-database-out=%s -d %s -b %s %s -u %s --gerrit-project=%s %s >> %s 2>&1" \
                            % (db_user, db_pass, database, str(delay), backend, g_user, trackers[0], project, flags, log_file)
            compose_msg(cmd, log_file)
            os.system(cmd)


        if launched:
            compose_msg("[OK] bicho (gerrit) executed")

            # post-scripts
            launch_post_tool_scripts('gerrit')
        else:
            compose_msg("[SKIPPED] bicho (gerrit) not executed")
    else:
        compose_msg("[SKIPPED] bicho (gerrit) not executed, no conf available")



def launch_mlstats():
    if options.has_key('mlstats'):
        if not check_tool(tools['mls']):
            return

        compose_msg("mlstats is being executed")
        launched = False
        db_admin_user = options['generic']['db_user']
        db_user = db_admin_user
        db_pass = options['generic']['db_password']
        db_name = options['generic']['db_mlstats']
        # Retrieving mailing lists
        if options['mlstats'].has_key('mailing_lists'):
            mlists = options['mlstats']['mailing_lists'].split(",")
        else:
            mlists = repositories(MLSTATS_MAILING_LISTS)

        force = ''
        if options['mlstats'].has_key('force'):
            if options['mlstats']['force'] is True:
                force = '--force'
        log_file = project_dir + '/log/launch_mlstats.log'


        # pre-scripts
        launch_pre_tool_scripts('mlstats')

        for m in mlists:
            launched = True
            cmd = tools['mls'] + " %s --no-report --db-user=\"%s\" --db-password=\"%s\" --db-name=\"%s\" --db-admin-user=\"%s\" --db-admin-password=\"%s\" \"%s\" >> %s 2>&1" \
                        %(force, db_user, db_pass, db_name, db_admin_user, db_pass, m, log_file)
            compose_msg(cmd, log_file)
            os.system(cmd)
        if launched:
            compose_msg("[OK] mlstats executed")

            # post-scripts
            launch_post_tool_scripts('mlstats')
        else:
            compose_msg("[SKIPPED] mlstats not executed")
    else:
        compose_msg("[SKIPPED] mlstats was not executed, no conf available")

def launch_irc():
    if options.has_key('irc'):
        if not check_tool(tools['irc']):
            return

        compose_msg("irc_analysis is being executed")
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
        log_file = project_dir + '/log/launch_irc.log'


        # pre-scripts
        launch_pre_tool_scripts('irc')

        if format == 'slack':
            if options['irc'].has_key('token'):
                token = options['irc']['token']
                launched = True
                cmd = tools['irc'] + " --db-user=\"%s\" --db-password=\"%s\" --database=\"%s\" --token %s --format %s>> %s 2>&1" \
                            % (db_user, db_pass, db_name, token, format, log_file)
                compose_msg(cmd, log_file)
                os.system(cmd)
            else:
                logging.error("Slack IRC supports need token option.")
        else:
            for channel in channels:
                if not os.path.isdir(os.path.join(irc_dir,channel)): continue
                launched = True
                cmd = tools['irc'] + " --db-user=\"%s\" --db-password=\"%s\" --database=\"%s\" --dir=\"%s\" --channel=\"%s\" --format %s>> %s 2>&1" \
                            % (db_user, db_pass, db_name, channel, channel, format, log_file)
                compose_msg(cmd, log_file)
                os.system(cmd)
        if launched:
            compose_msg("[OK] irc_analysis executed")

            # post-scripts
            launch_post_tool_scripts('irc')
        else:
            compose_msg("[SKIPPED] irc_analysis not executed")
    else:
        compose_msg("[SKIPPED] irc_analysis was not executed, no conf available")

def launch_mediawiki():
    if options.has_key('mediawiki'):
        if not check_tool(tools['mediawiki']):
            return

        compose_msg("mediawiki_analysis is being executed")
        launched = False
        db_admin_user = options['generic']['db_user']
        db_user = db_admin_user
        db_pass = options['generic']['db_password']
        db_name = options['generic']['db_mediawiki']
        sites = options['mediawiki']['sites']
        log_file = project_dir + '/log/launch_mediawiki.log'


        # pre-scripts
        launch_pre_tool_scripts('mediawiki')

        for site in sites.split(","):
            launched = True
            # ./mediawiki_analysis.py --database acs_mediawiki_rdo_2478 --db-user root --url http://openstack.redhat.com
            cmd = tools['mediawiki'] + " --db-user=\"%s\" --db-password=\"%s\" --database=\"%s\" --url=\"%s\" >> %s 2>&1" \
                      %(db_user, db_pass, db_name,  sites, log_file)
            compose_msg(cmd, log_file)
            os.system(cmd)
        if launched:
            compose_msg("[OK] mediawiki_analysis executed")

            # post-scripts
            launch_post_tool_scripts('mediawiki')
        else:
            compose_msg("[SKIPPED] mediawiki_analysis not executed")
    else:
        compose_msg("[SKIPPED] mediawiki_analysis was not executed, no conf available")

def launch_downloads():
    # check if downloads option exists. If it does, downloads are executed
    if options.has_key('downloads'):
        compose_msg("downloads does not execute any tool. Only pre and post scripts")

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

        compose_msg("sibyl is being executed")
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
        log_file = project_dir + '/log/launch_sibyl.log'

        # pre-scripts
        launch_pre_tool_scripts('sibyl')

        cmd = tools['sibyl'] + " --db-user=\"%s\" --db-password=\"%s\" --database=\"%s\" --url=\"%s\" --type=\"%s\" %s %s >> %s 2>&1" \
                      %(db_user, db_pass, db_name,  url, backend, api_key, tags, log_file)
        compose_msg(cmd, log_file)
        os.system(cmd)
        # TODO: it's needed to check if the process correctly finished
        launched = True

        if launched:
            compose_msg("[OK] sibyl executed")
        else:
            compose_msg("[SKIPPED] sibyl not executed")
    else:
        compose_msg("[SKIPPED] sibyl was not executed, no conf available")


def launch_octopus():
    launch_octopus_puppet()
    launch_octopus_docker()
    launch_octopus_github()
    launch_octopus_gerrit()


def launch_octopus_export(cmd, backend):
    """ Exports the list of repositories to the specific config file"""

    # Adding the '--export' option, this disable the rest of the Octopus options
    cmd = cmd + ' --export '

    if backend == 'puppet':
        output = PUPPET_RELEASES
    elif backend == 'docker':
        output = DOCKER_PACKAGES
    elif backend == 'github':
        output = CVSANALY_REPOSITORIES
    elif backend == 'gerrit':
        output = GERRIT_PROJECTS

    os.system(cmd + " > " + conf_dir + output)

def launch_octopus_puppet():
    # check if octopus_puppet option exists
    if options.has_key('octopus_puppet'):
        if not check_tool(tools['octopus']):
            return

        compose_msg("octopus for puppet is being executed")
        launched = False
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        db_name = options['generic']['db_releases']
        url = options['octopus_puppet']['url']
        log_file = project_dir + '/log/launch_octopus_puppet.log'

        # pre-scripts
        launch_pre_tool_scripts('octopus_puppet')

        cmd = tools['octopus'] + " -u \"%s\" -p \"%s\" -d \"%s\" puppet \"%s\">> %s 2>&1" \
                      %(db_user, db_pass, db_name, url, log_file)
        export_cmd = tools['octopus'] + " -u \"%s\" -p \"%s\" -d \"%s\" puppet \"%s\" "\
                      %(db_user, db_pass, db_name, url, log_file)

        compose_msg(cmd, log_file)
        os.system(cmd)
        # TODO: it's needed to check if the process correctly finished
        launched = True

        # Export data if required
        if options['octopus_puppet'].has_key('export'):
            launch_octopus_export(export_cmd, 'puppet')

        if launched:
            compose_msg("[OK] octopus for puppet executed")

            launch_post_tool_scripts('octopus_puppet')
        else:
            compose_msg("[SKIPPED] octopus for puppet not executed")
    else:
        compose_msg("[SKIPPED] octopus for puppet was not executed, no conf available")


def launch_octopus_docker():
    # check if octopus_docker option exists
    if options.has_key('octopus_docker'):
        if not check_tool(tools['octopus']):
            return

        compose_msg("octopus for docker is being executed")
        launched = False
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        db_name = options['generic']['db_releases']
        url = options['octopus_docker']['url']
        log_file = project_dir + '/log/launch_octopus_docker.log'

        owner = options['octopus_docker']['owner']
        owners = owner.split(",")

        # pre-scripts
        launch_pre_tool_scripts('octopus_docker')

        octopus_cmd = tools['octopus'] + " -u \"%s\" -p \"%s\" -d \"%s\" docker \"%s\" " \
            % (db_user, db_pass, db_name, url)
        export_cmd = octopus_cmd

        for owner in owners:
            owner = owner.strip()

            repositories = None

            if options['octopus_docker'].has_key('repositories') and len(owners) == 1:
                repositories = options['octopus_docker']['repositories'].split(",")
            elif options['octopus_docker'].has_key('repositories'):
                logging.error("Wrong main.conf. Several octopus docker owners and general repositories config.")
                raise

            if len(owners) > 1:
                if options['octopus_docker'].has_key('repositories_' + owner.lower()):
                    repositories = options['octopus_docker']['repositories_' + owner.lower()].split(",")

            if repositories:
                # Launch octopus for each docker repository configured
                for repo in repositories:
                    repo = repo.strip()
                    cmd = octopus_cmd +  "\"%s\"  \"%s\">> %s 2>&1" % (owner, repo, log_file)
                    compose_msg(cmd, log_file)
                    os.system(cmd)
            else:
                logging.error("No repositories configured for %s docker owner. Skipped" % owner)

        # Export data if required
        if options['octopus_docker'].has_key('export'):
            launch_octopus_export(export_cmd, 'docker')

        launched = True

        if launched:
            compose_msg("[OK] octopus for docker executed")

            launch_post_tool_scripts('octopus_docker')
        else:
            compose_msg("[SKIPPED] octopus for docker not executed")
    else:
        compose_msg("[SKIPPED] octopus for docker was not executed, no conf available")


def launch_octopus_github():
    # check if octopus_github option exists
    if options.has_key('octopus_github'):
        if not check_tool(tools['octopus']):
            return

        compose_msg("octopus for github is being executed")
        launched = False
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        db_name = options['generic']['db_releases']
        log_file = project_dir + '/log/launch_octopus_github.log'

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
                logging.error("Wrong main.conf. Several octopus github owners and general repositories config.")
                raise

            if len(owners) > 1:
                if options['octopus_github'].has_key('repositories_' + owner.lower()):
                    repositories = options['octopus_github']['repositories_' + owner.lower()].split(",")

            if repositories:
                # Launch octopus for each docker repository configured
                for repo in repositories:
                    repo = repo.strip()
                    cmd = octopus_cmd +  "\"%s\"  \"%s\">> %s 2>&1" % (owner, repo, log_file)
                    compose_msg(cmd, log_file)
                    os.system(cmd)
            else:
                # Launch octopus for all the repositories
                cmd = octopus_cmd + "\"%s\"  >> %s 2>&1" % (owner, log_file)
                compose_msg(cmd, log_file)
                os.system(cmd)

        # Export data if required
        if options['octopus_github'].has_key('export'):
            launch_octopus_export(export_cmd, 'github')

        launched = True

        if launched:
            compose_msg("[OK] octopus for github executed")

            launch_post_tool_scripts('octopus_github')
        else:
            compose_msg("[SKIPPED] octopus for github not executed")
    else:
        compose_msg("[SKIPPED] octopus for github was not executed, no conf available")


def launch_octopus_gerrit():
    """ Octopus Gerrit backend """

    launched = False
    if options.has_key('octopus_gerrit'):
        if not check_tool(tools['octopus']):
            return

        compose_msg("octopus for gerrit is being executed")
        # Common options
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        db_name = options['generic']['db_octopus']
        log_file = project_dir + '/log/launch_octopus_gerrit.log'

        # Gerrit specific options
        gerrit_user = options['octopus_gerrit']['gerrit_user']
        gerrit_url = options['octopus_gerrit']['gerrit_url']

        octopus_cmd = tools['octopus'] + " -u \"%s\" -p \"%s\" -d \"%s\" gerrit --gerrit-user \"%s\" --gerrit-url \"%s\" " \
                      % (db_user, db_pass, db_name, gerrit_user, gerrit_url)
        export_cmd = octopus_cmd

        # pre-scripts
        launch_pre_tool_scripts('octopus_gerrit')

        # Execute Octopus Gerrit backend
        compose_msg(octopus_cmd, log_file)
        os.system(octopus_cmd)

        launched = True
        compose_msg("[OK] octopus for gerrit executed")
        # post-scripts
        launch_post_tool_scripts('octopus_gerrit')

        # Export data if required
        if options['octopus_gerrit'].has_key('export'):
            launch_octopus_export(export_cmd, 'gerrit')

    if not launched:
        compose_msg("[SKIPPED] octopus for gerrit not executed")


def check_sortinghat_db(db_user, db_pass, db_name):
    """ Check that the db exists and if not, create it """
    log_file = project_dir + '/log/launch_sortinghat_affiliations.log'
    try:
         db = MySQLdb.connect(user = db_user, passwd = db_pass,  db = db_name)
         db.close()
         print ("Sortinghat " + db_name + " already exists")
    except:
        print ("Can't connect to " + db_name)
        print ("Creating sortinghat database ...")
        cmd = tools['sortinghat'] + " -u \"%s\" -p \"%s\" init \"%s\">> %s 2>&1" \
                      %(db_user, db_pass, db_name, log_file)
        compose_msg(cmd, log_file)
        os.system(cmd)

def launch_sortinghat():
    logging.info("Sortinghat working ...")
    if not check_tool(tools['sortinghat']):
        logging.info("Sortinghat tool not available,")
        return
    if 'db_sortinghat' not in options['generic']:
        logging.info("No database for Sortinghat configured.")
        return
    project_name = options['generic']['project']
    db_user = options['generic']['db_user']
    db_pass = options['generic']['db_password']
    db_name = options['generic']['db_sortinghat']
    log_file = project_dir + '/log/launch_sortinghat.log'

    check_sortinghat_db(db_user, db_pass, db_name)

    # pre-scripts
    launch_pre_tool_scripts('sortinghat')

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
            logging.error(ds.get_db_name() + " not in automator main.conf")
            continue
        # Export identities from ds
        cmd = tools['mg2sh'] + " -u \"%s\" -p \"%s\" -d \"%s\" --source \"%s:%s\" -o %s >> %s 2>&1" \
                      %(db_user, db_pass, db_ds, project_name.lower(), ds.get_name(), io_file_name, log_file)
        compose_msg(cmd, log_file)
        os.system(cmd)
        # Load identities in sortinghat in incremental mode
        cmd = tools['sortinghat'] + " -u \"%s\" -p \"%s\" -d \"%s\" load --matching email-name -n %s >> %s 2>&1" \
                      %(db_user, db_pass, db_name, io_file_name, log_file)
        compose_msg(cmd, log_file)
        os.system(cmd)
        os.remove(io_file_name)

    # Complete main identifier
    db_pass_id = db_pass
    if db_pass_id == '': db_pass_id = "''"
    identifier2sh = identities_dir + '/identifier2sh.py'
    cmd = identifier2sh + " -u %s -p %s -d \"%s\" " % (db_user, db_pass_id, db_name)
    compose_msg(cmd, log_file)
    os.system(cmd)

    # Do affiliations
    cmd = tools['sortinghat'] + " -u \"%s\" -p \"%s\" -d \"%s\" affiliate  >> %s 2>&1" \
              %(db_user, db_pass, db_name, log_file)
    compose_msg(cmd, log_file)
    os.system(cmd)

    # Export data from Sorting Hat
    for ds in dss:
        if ds.get_name() in dss_not_supported: continue
        if ds.get_db_name() in options['generic']:
            db_ds = options['generic'][ds.get_db_name()]
        else:
            logging.error(ds.get_db_name() + " not in automator main.conf")
            continue
        # Export identities from sh to file
        cmd = tools['sortinghat'] + " -u \"%s\" -p \"%s\" -d \"%s\" export --source \"%s:%s\" --identities %s >> %s 2>&1" \
                      %(db_user, db_pass, db_name, project_name.lower(), ds.get_name(), io_file_name, log_file)
        compose_msg(cmd, log_file)
        os.system(cmd)
        # Load identities in mg from file
        cmd = tools['sh2mg'] + " -u \"%s\" -p \"%s\" -d \"%s\" --source \"%s:%s\" %s >> %s 2>&1" \
                      %(db_user, db_pass, db_ds, project_name.lower(), ds.get_name(), io_file_name, log_file)
        compose_msg(cmd, log_file)
        os.system(cmd)
        os.remove(io_file_name)

    # Create domains tables
    if db_pass == '': db_pass = "''"
    db_sortinghat = options['generic']['db_sortinghat']
    cmd = "%s/domains_analysis.py -u %s -p %s -d %s --sortinghat>> %s 2>&1" \
        % (identities_dir, db_user, db_pass, db_name, log_file)
    compose_msg(cmd, log_file)
    os.system(cmd)

    # post-scripts
    launch_post_tool_scripts('sortinghat')

    logging.info("Sortinghat done")

def launch_pullpo():
    # check if octopusl option exists
    if options.has_key('pullpo'):
        if not check_tool(tools['pullpo']):
            return

        compose_msg("pullpo is being executed")
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
        log_file = project_dir + '/log/launch_pullpo.log'

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
                logging.error("Wrong main.conf. Several pullpo owners and general projects config.")
                raise
            if len(owners) > 1:
                if options['pullpo'].has_key('projects_' + owner.lower()):
                    projects = options['pullpo']['projects_' + owner.lower()].split(",")
            if projects:
                # Launch pullpo for each project configured
                for project in projects:
                    cmd = pullpo_cmd +  "\"%s\"  \"%s\">> %s 2>&1" % (owner, project, log_file)
                    compose_msg(cmd, log_file)
                    os.system(cmd)
            else:
                # Launch pullpo for all the repositories
                cmd = pullpo_cmd + "\"%s\"  >> %s 2>&1" % (owner, log_file)
                compose_msg(cmd, log_file)
                os.system(cmd)
        launched = True

        if launched:
            compose_msg("[OK] pullpo executed")
        else:
            compose_msg("[SKIPPED] pullpo not executed")
    else:
        compose_msg("[SKIPPED] pullpo was not executed, no conf available")

def launch_eventizer():
    # check if eventizer option exists
    if options.has_key('eventizer'):
        if not check_tool(tools['eventizer']):
            return

        compose_msg("eventizer is being executed")
        launched = False
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        db_name = options['generic']['db_eventizer']

        if 'key' not in options['eventizer']:
            msg = "Metup API key not provided. Use 'key' parameter to set one."
            logging.error('[eventizer] ' + msg)
            compose_msg("[SKIPPED] eventizer not executed. %s" % msg)
            return

        if 'groups' not in options['eventizer']:
            msg = "Groups list not provided. Use 'groups' parameter to set one."
            logging.error('[eventizer] ' + msg)
            compose_msg("[SKIPPED] eventizer not executed. %s" % msg)
            return

        eventizer_key = options['eventizer']['key']

        groups = options['eventizer']['groups']
        groups = groups.split(",")

        log_file = project_dir + '/log/launch_eventizer.log'

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
            compose_msg(cmd, log_file)
            os.system(cmd)
            launched = True

        if launched:
            compose_msg("[OK] eventizer executed")

            # post-scripts
            launch_post_tool_scripts('eventizer')
        else:
            compose_msg("[SKIPPED] eventizer not executed")
    else:
        compose_msg("[SKIPPED] eventizer was not executed, no conf available")

# http://code.activestate.com/recipes/577376-simple-way-to-execute-multiple-process-in-parallel/
def exec_commands(cmds):
    ''' Exec commands in parallel in multiple process '''

    if not cmds: return # empty list

    def done(p):
        return p.poll() is not None
    def success(p):
        return p.returncode == 0
    def fail():
        logging.error("Problems in report_tool.py execution. See logs.")
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
        sys.path.append(dir)
    import report
    report.Report.init(os.path.join(conf_dir,"main.conf"))
    return report.Report

def launch_events_scripts():
    # Execute metrics tool using the automator config
    # Start one report_tool per data source active
    if options.has_key('metrics') or options.has_key('r'):

        compose_msg("events being generated")

        json_dir = '../../../json'
        conf_file = project_dir + '/conf/main.conf'
        log_file = project_dir + '/log/launch-'

        metrics_tool = "report_tool.py"
        path = r_dir

        params = get_options()

        commands = [] # One report_tool per data source
        report = get_report_module()
        dss = report.get_data_sources()

        if params.subtask:
            ds = report.get_data_source(params.subtask)
            if ds is None:
                logging.error("Data source " + params.subtask + " not found")
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

        compose_msg("[OK] events generated")

    else:
        compose_msg("[SKIPPED] Events not generated, no conf available")


def launch_metrics_scripts():
    # Execute metrics tool using the automator config
    # Start one report_tool per data source active

    if options.has_key('metrics') or options.has_key('r'):
        if not check_tool(tools['r']):
            return

        compose_msg("metrics tool being launched")

        r_libs = '../../r-lib'
        python_libs = '../grimoirelib_alch:../vizgrimoire:../vizgrimoire/analysis:../vizgrimoire/metrics:./'
        json_dir = '../../../json'
        metrics_dir = '../vizgrimoire/metrics'
        conf_file = project_dir + '/conf/main.conf'
        log_file = project_dir + '/log/launch-'


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
                logging.error("Data source " + params.subtask + " not found")
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

        compose_msg("[OK] metrics tool executed")

        launch_post_tool_scripts('r')
    else:
        compose_msg("[SKIPPED] Metrics tool was not executed, no conf available")

def get_ds_identities_cmd(db, type):
    idir = identities_dir
    db_user = options['generic']['db_user']
    db_pass = options['generic']['db_password']
    if (db_pass == ""): db_pass="''"
    db_ids = options['generic']['db_identities']
    log_file = project_dir + '/log/identities.log'

    cmd = "%s/datasource2identities.py -u %s -p %s --db-name-ds=%s --db-name-ids=%s --data-source=%s>> %s 2>&1" \
            % (idir, db_user, db_pass, db, db_ids, type, log_file)

    return cmd

def launch_identity_scripts():
    # using the conf executes cvsanaly for the repos inside scm dir
    if options.has_key('identities'):
        logging.info("Unique identities scripts are being executed")
        # idir = options['identities']['iscripts_path']
        idir = identities_dir
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        if (db_pass == ""): db_pass="''"
        log_file = project_dir + '/log/identities.log'

        if options['generic'].has_key('db_identities') and \
            options['generic'].has_key('db_sortinghat'):
            if options['generic']['db_identities'] == options['generic']['db_sortinghat']:
                compose_msg("Sortinghat configuration. Not executing identities.")
                return

        if options['generic'].has_key('db_identities'):
            db_identities = options['generic']['db_identities']
            cmd = "%s/unifypeople.py -u %s -p %s -d %s >> %s 2>&1" % (idir, db_user, db_pass, db_identities, log_file)
            compose_msg(cmd, log_file)
            os.system(cmd)
            cmd = "%s/domains_analysis.py -u %s -p %s -d %s >> %s 2>&1" % (idir, db_user, db_pass, db_identities, log_file)
            compose_msg(cmd, log_file)
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
                logging.error(ds.get_db_name() + " not in automator main.conf")
                continue
            cmd = get_ds_identities_cmd(db_ds, ds.get_name())
            compose_msg(cmd, log_file)
            os.system(cmd)

        if options['identities'].has_key('countries'):
            cmd = "%s/load_ids_mapping.py -m countries -t true -u %s -p %s --database %s >> %s 2>&1" \
                        % (idir, db_user, db_pass, db_identities, log_file)
            compose_msg(cmd, log_file)
            os.system(cmd)

        if options['identities'].has_key('companies'):
            cmd = "%s/load_ids_mapping.py -m companies -t true -u %s -p %s --database %s >> %s 2>&1" \
                        % (idir, db_user, db_pass, db_identities, log_file)
            compose_msg(cmd, log_file)
            os.system(cmd)

        logging.info("[OK] Identity scripts executed")
    else:
        logging.info("[SKIPPED] Unify identity scripts not executed, no conf available")

def compose_msg(text, log_file = None):
    # append text to log file
    if log_file is None:
        fd = open(msg_body, 'a')
    else:
        fd = open(log_file, 'a')
    time_tag = '[' + time.strftime('%H:%M:%S') + ']'
    fd.write(time_tag + ' ' + text)
    fd.write('\n')
    fd.close()

def reset_log():
    # remove log file
    try:
        os.remove(msg_body)
    except OSError:
        fd = open(msg_body, 'w')
        fd.write('')
        fd.close()

def launch_copy_json():
    # copy JSON files to other directories
    # This option helps when having more than one automator, but all of the
    # json files should be moved to a centralized directory
    if options.has_key('copy-json'):
        compose_msg("Copying JSON files to another directory")
        destination = os.path.join(project_dir,options['copy-json']['destination_json'])
        distutils.dir_util.copy_tree(json_dir, destination)

def launch_commit_jsones():
    # copy JSON files and commit + push them
    if options.has_key('git-production'):

        if not check_tool(tools['git']):
            return

        compose_msg("Commiting new JSON files with git")

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

        compose_msg("Dumping databases")

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

        compose_msg("rsync to production server")

        fd = open(msg_body, 'a')

        destination = options['rsync']['destination']
        pr = subprocess.Popen([tools['rsync'],'--rsh', 'ssh', '-zva', '--stats', '--progress', '--update' ,'--delete', '--exclude', '.git', production_dir, destination],
                              stdout=fd,
                              stderr=fd,
                              shell=False)
        (out, error) = pr.communicate()

        fd.close()
    else:
        compose_msg("[SKIPPED] rsync scripts not executed, no conf available")

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
    compose_msg("Writing metrics definition in: " + filename)
    report = get_report_module()
    automator_file = project_dir + '/conf/main.conf'
    metrics_dir = os.path.join(project_dir, "tools", "GrimoireLib","vizgrimoire","metrics")
    report.init(automator_file, metrics_dir)
    dss_active = report.get_data_sources()
    all_metricsdef = {}
    for ds in dss_active:
        compose_msg("Metrics def for " + ds.get_name())
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

    compose_msg("Writing config file for VizGrimoireJS: " + production_dir + "config.json")

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
        mediawiki_url = options['mediawiki']['sites']
        project_info['mediawiki_url'] = mediawiki_url

    return project_info

def print_std(string, new_line=True):
    # Send string to standard input if quiet mode is disabled
    if not opt.quiet_mode:
        if new_line:
            print(string)
        else:
            print(string),

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
                      'sibyl','octopus','pullpo','eventizer','sortinghat','events','metrics','copy-json',
                      'git-production','db-dump','json-dump','rsync']

# Use this for parallel execution of data gathering
tasks_order_parallel = ['check-dbs','gather','sortinghat','events','metrics','copy-json',
                        'git-production','db-dump','json-dump','rsync']

tasks_order = tasks_order_parallel


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
    opt = get_options()
    initialize_globals(opt.project_dir)

    pid = str(os.getpid())
    pidfile = os.path.join(opt.project_dir, "launch.pid")

    if os.path.isfile(pidfile):
        print_std("%s already exists, launch process seems to be running. Exiting .." % pidfile)
        sys.exit()
    else:
        file(pidfile, 'w').write(pid)

    reset_log()
    compose_msg("Starting ..")

    read_main_conf()

    check_tools()

    if opt.section is not None:
        tasks_section[opt.section]()
    else:
        for section in tasks_order:
            t0 = dt.datetime.now()
            print_std("Executing %s ...." % (section), new_line=False)
            sys.stdout.flush()
            tasks_section[section]()
            t1 = dt.datetime.now()
            print_std(" %s minutes" % ((t1-t0).seconds/60))
    print_std("Finished.")

    compose_msg("Process finished correctly ...")

    # done, we sent the result
    project = options['generic']['project']
    mail = options['generic']['mail']
    os.system("mail -s \"[%s] data updated\" %s < %s" % (project, mail, msg_body))

    os.unlink(pidfile)
