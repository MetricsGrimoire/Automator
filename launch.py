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
    'r': '/usr/bin/R',
    'git': '/usr/bin/git',
    'svn': '/usr/bin/svn',
    'mysqldump': '/usr/bin/mysqldump',
    'compress': '/usr/bin/7zr',
    'rm': '/bin/rm',
    'rsync': '/usr/bin/rsync'
}

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

# git specific: search all repos in a directory recursively
def get_scm_repos(dir = scm_dir):
    all_repos = []

    if (dir == ''):  dir = scm_dir
    if not os.path.isdir(dir): return all_repos

    repos = os.listdir(dir)

    for r in repos:
        repo_dir_git = os.path.join(dir,r,".git")
        repo_dir_svn = os.path.join(dir,r,".svn")
        if not os.path.isdir(repo_dir_git) and not os.path.isdir(repo_dir_svn):
            sub_repos = get_scm_repos(os.path.join(dir,r))
            for sub_repo in sub_repos:
                all_repos.append(sub_repo)
        else:
            all_repos.append(os.path.join(dir,r))
    return all_repos

def update_scm(dir = scm_dir):
    compose_msg("SCM is being updated")
    repos = get_scm_repos()
    updated = False
    log_file = project_dir + '/log/launch_cvsanaly.log'

    for r in repos:
        os.chdir(r)
        if os.path.isdir(os.path.join(dir,r,".git")):
            os.system("git fetch origin >> %s 2>&1" %(log_file))
            os.system("git reset --hard origin/master >> %s 2>&1" %(log_file))
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

    if options['generic'].has_key('db_cvsanaly'):
        dbs.append(options['generic']['db_cvsanaly'])
    if options['generic'].has_key('db_bicho'):
        dbs.append(options['generic']['db_bicho'])
    # mlstats creates the db if options['generic'].has_key('db_mlstats'): 
    if options['generic'].has_key('db_gerrit'):
        dbs.append(options['generic']['db_gerrit'])
    if options['generic'].has_key('db_irc'):
        dbs.append(options['generic']['db_irc'])
    if options['generic'].has_key('db_mediawiki'):
        dbs.append(options['generic']['db_mediawiki'])
    if options['generic'].has_key('db_releases'):
        dbs.append(options['generic']['db_releases'])
    if options['generic'].has_key('db_qaforums'):
        dbs.append(options['generic']['db_qaforums'])
    if options['generic'].has_key('db_downloads'):
        dbs.append(options['generic']['db_downloads'])
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
    if options[tool].has_key('pre_scripts'):
        compose_msg("Running %s pre scripts" % tool)
        launch_scripts(options[tool]['pre_scripts'])
        compose_msg("%s pre scripts completed" % tool)
    else:
        compose_msg("No %s pre scripts configured" % tool)

def launch_post_tool_scripts(tool):
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

def launch_bicho():
    # reads a conf file with all of the information and launches bicho
    if options.has_key('bicho'):
        if not check_tool(tools['its']):
            return

        compose_msg("bicho is being executed")
        launched = False

        database = options['generic']['db_bicho']
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        delay = options['bicho']['delay']
        backend = options['bicho']['backend']
        backend_user = backend_password = None
        num_issues_query = None
        if options['bicho'].has_key('backend_user'):
            backend_user = options['bicho']['backend_user']
        if options['bicho'].has_key('backend_password'):
            backend_password = options['bicho']['backend_password']
        if options['bicho'].has_key('num-issues-query'):
            num_issues_query = options['bicho']['num-issues-query']
        trackers = options['bicho']['trackers']
        log_table = None
        debug = options['bicho']['debug']
        if options['bicho'].has_key('log_table'):
            log_table = options['bicho']['log_table']
        log_file = project_dir + '/log/launch_bicho.log'


        # we compose some flags
        flags = ""
        if debug:
            flags = flags + " -g"

        # we'll only create the log table in the last execution
        cont = 0
        last = len(trackers)

        # pre-scripts
        launch_pre_tool_scripts('bicho')

        for t in trackers:
            launched = True
            cont = cont + 1

            if cont == last and log_table:
                flags = flags + " -l"

            user_opt = ''
            if backend_user and backend_password:
                user_opt = '--backend-user=%s --backend-password=%s' % (backend_user, backend_password)
            if num_issues_query:
                user_opt = '--num-issues=%s' % (num_issues_query)
            cmd = tools['its'] + " --db-user-out=%s --db-password-out=%s --db-database-out=%s -d %s -b %s %s -u %s %s >> %s 2>&1" \
                        % (db_user, db_pass, database, str(delay), backend, user_opt, t, flags, log_file)
            compose_msg(cmd, log_file)
            os.system(cmd)
        if launched:
            compose_msg("[OK] bicho executed")

            # post-scripts
            launch_post_tool_scripts('bicho')
        else:
            compose_msg("[SKIPPED] bicho was not executed")
    else:
        compose_msg("[SKIPPED] bicho not executed, no conf available")

def launch_gather():
    """ This tasks will execute in parallel all data gathering tasks """
    logging.info("Executing all data gathering tasks in parallel")

    from multiprocessing import Process, active_children

    gather_tasks_order = ['cvsanaly','bicho','gerrit','mlstats',
                          'irc','mediawiki', 'downloads', 'sibyl','octopus','pullpo']
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
        projects = options['gerrit']['projects']
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
        mlists = options['mlstats']['mailing_lists']

        force = ''
        if options['mlstats'].has_key('force'):
            if options['mlstats']['force'] is True:
                force = '--force'
        log_file = project_dir + '/log/launch_mlstats.log'


        # pre-scripts
        launch_pre_tool_scripts('mlstats')

        for m in mlists.split(","):
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
        db_name = options['generic']['db_qaforums']
        url = options['sibyl']['url']
        backend = options['sibyl']['backend']
        log_file = project_dir + '/log/launch_sibyl.log'

        # pre-scripts
        launch_pre_tool_scripts('sibyl')

        cmd = tools['sibyl'] + " --db-user=\"%s\" --db-password=\"%s\" --database=\"%s\" --url=\"%s\" --type=\"%s\" >> %s 2>&1" \
                      %(db_user, db_pass, db_name,  url, backend, log_file)
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
    # check if octopusl option exists
    if options.has_key('octopus'):
        if not check_tool(tools['octopus']):
            return

        compose_msg("octopus is being executed")
        launched = False
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        db_name = options['generic']['db_releases']
        url = options['octopus']['url']
        backend = options['octopus']['backend']
        log_file = project_dir + '/log/launch_octopus.log'

        # pre-scripts
        launch_pre_tool_scripts('octopus')

        cmd = tools['octopus'] + " -u \"%s\" -p \"%s\" -d \"%s\" --backend=\"%s\" \"%s\">> %s 2>&1" \
                      %(db_user, db_pass, db_name,  backend, url, log_file)
        compose_msg(cmd, log_file)
        os.system(cmd)
        # TODO: it's needed to check if the process correctly finished
        launched = True

        if launched:
            compose_msg("[OK] octopus executed")
        else:
            compose_msg("[SKIPPED] octopus not executed")
    else:
        compose_msg("[SKIPPED] octopus was not executed, no conf available")

def launch_pullpo():
    # check if octopusl option exists
    if options.has_key('pullpo'):
        if not check_tool(tools['pullpo']):
            return

        compose_msg("pullpo is being executed")
        launched = False
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        db_name = options['generic']['db_releases']
        owner = options['pullpo']['owner']
        project = options['pullpo']['project']
        user = options['pullpo']['user']
        password = options['pullpo']['password']
        log_file = project_dir + '/log/launch_pullpo.log'

        # pre-scripts
        launch_pre_tool_scripts('pullpo')

        cmd = tools['pullpo'] + " -u \"%s\" -p \"%s\" -d \"%s\" --gh-user=\"%s\" --gh-password=\"%s\" \"%s\" \"%s\">> %s 2>&1" \
                      %(db_user, db_pass, db_name,  user, password, owner, project, log_file)
        compose_msg(cmd, log_file)
        os.system(cmd)
        # TODO: it's needed to check if the process correctly finished
        launched = True

        if launched:
            compose_msg("[OK] pullpo executed")
        else:
            compose_msg("[SKIPPED] pullpo not executed")
    else:
        compose_msg("[SKIPPED] pullpo was not executed, no conf available")

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
    else:
        compose_msg("[SKIPPED] Metrics tool was not executed, no conf available")

def get_ds_identities_cmd(db, type):
    idir = identities_dir
    db_user = options['generic']['db_user']
    db_pass = options['generic']['db_password']
    if (db_pass == ""): db_pass="''"
    db_scm = options['generic']['db_cvsanaly']
    db_ids = db_scm
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

        # SCM is specific in generating identities. It includes identities tables.
        if options['generic'].has_key('db_cvsanaly'):
            # TODO: -i no is needed in first execution
            db_scm = options['generic']['db_cvsanaly']
            cmd = "%s/unifypeople.py -u %s -p %s -d %s >> %s 2>&1" % (idir, db_user, db_pass, db_scm, log_file)
            compose_msg(cmd, log_file)
            os.system(cmd)
            # Companies are needed in Top because bots are included in a company
            cmd = "%s/domains_analysis.py -u %s -p %s -d %s >> %s 2>&1" % (idir, db_user, db_pass, db_scm, log_file)
            compose_msg(cmd, log_file)
            os.system(cmd)

        # Generate unique identities for all data sources active
        report = get_report_module()
        dss = report.get_data_sources()
        for ds in dss:
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
                        % (idir, db_user, db_pass, db_scm, log_file)
            compose_msg(cmd, log_file)
            os.system(cmd)

        if options['identities'].has_key('companies'):
            cmd = "%s/load_ids_mapping.py -m companies -t true -u %s -p %s --database %s >> %s 2>&1" \
                        % (idir, db_user, db_pass, db_scm, log_file)
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
            dbs.append([options['generic']['db_irc'],'irc']);
        if options['generic'].has_key('db_mediawiki'):
            dbs.append([options['generic']['db_mediawiki'],'mediawiki']);

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

        origin = options['json-dump']['origin_json_dump']
        origin = origin + '*json'
        dest = options['json-dump']['destination_json_dump']

        fd = open(msg_body, 'a')

        pr = subprocess.Popen([tools['compress'], 'a', dest, origin],
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
        pr = subprocess.Popen([tools['rsync'],'--rsh', 'ssh', '-zva', '--stats', '--progress', '--update' ,'--delete', production_dir, destination],
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
    'pullpo': launch_pullpo
}

tasks_section = dict({
    'check-dbs':launch_checkdbs,
    'copy-json': launch_copy_json,
    'db-dump':launch_database_dump,
    'gather':launch_gather,
    'git-production':launch_commit_jsones,
    'identities': launch_identity_scripts,
    'json-dump':launch_json_dump,
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
                      'sibyl','octopus','pullpo','identities','metrics','copy-json',
                      'git-production','db-dump','json-dump','rsync']

# Use this for parallel execution of data gathering
tasks_order_parallel = ['check-dbs','gather','identities','metrics','copy-json',
                        'git-production','db-dump','json-dump','rsync']

tasks_order = tasks_order_parallel


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
    opt = get_options()
    initialize_globals(opt.project_dir)

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
