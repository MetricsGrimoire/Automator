#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2012-2013 Bitergia
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

import os
import subprocess
import sys
import time
import distutils.dir_util

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
    'r': '/usr/bin/R',
    'git': '/usr/bin/git',
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
    parser.add_option('-s','--section', dest='section',
                     help='Section to be executed', default=None)

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
    global json_dir
    global production_dir
    global identities_dir
    global r_dir
    
    project_dir = pdir
    msg_body = project_dir + '/log/launch.log'
    scm_dir = project_dir + '/scm/'
    irc_dir = project_dir + '/irc/'
    conf_dir = project_dir + '/conf/'
    json_dir = project_dir + '/json/'
    production_dir = project_dir + '/production/'
    identities_dir = project_dir + '/tools/VizGrimoireR/misc/'
    r_dir = project_dir + '/tools/VizGrimoireR/vizGrimoireJS/'

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
            elif o == 'trackers':
                options[s][o] = parser.get(s,o).split(',') 
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
        repo_dir = os.path.join(dir,r,".git")
        if not os.path.isdir(repo_dir):
            sub_repos = get_scm_repos(os.path.join(dir,r))
            for sub_repo in sub_repos:
                all_repos.append(sub_repo)
        else:
            all_repos.append(os.path.join(dir,r))
    return all_repos     

def update_scm():
    # basically git pull of the dirs inside scm dir
    compose_msg("SCM is being updated")
    repos = get_scm_repos()
    for r in repos:
        os.chdir(r)
        os.system("git pull >> %s 2>&1" %(msg_body))
        compose_msg(r + " pull ended")
    compose_msg("[OK] SCM updated")

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
    
    for dbname in dbs:
        try:
             db = MySQLdb.connect(user = db_user, passwd = db_password,  db = dbname)
             db.close()
        except:
            print ("Can't connect to " + dbname)
            db = MySQLdb.connect(user = db_user, passwd = db_password)
            cursor = db.cursor()
            query = "CREATE DATABASE " + dbname + " CHARACTER SET utf8 COLLATE utf8_unicode_ci"
            cursor.execute(query)
            db.close()
            print (dbname+" created")

def launch_cvsanaly():
    # using the conf executes cvsanaly for the repos inside scm dir
    if options.has_key('cvsanaly'):
        if not check_tool(tools['scm']):
            return
        update_scm()
        compose_msg("cvsanaly is being executed")
        launched = False
        extensions = options['cvsanaly']['extensions']
        db_name = options['generic']['db_cvsanaly']
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        if (db_pass == ""): db_pass = "''"

        # we launch cvsanaly against the repos
        repos = get_scm_repos()
        for r in repos:
            launched = True
            os.chdir(r)
            compose_msg(tools['scm'] + " -u %s -p %s -d %s --extensions=%s >> %s 2>&1"
                        %(db_user, db_pass, db_name, extensions, msg_body))
            os.system(tools['scm'] + " -u %s -p %s -d %s --extensions=%s >> %s 2>&1"
                      %(db_user, db_pass, db_name, extensions, msg_body))
        
        if launched:
            compose_msg("[OK] cvsanaly executed")
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
        if options['bicho'].has_key('backend_user'):
            backend_user = options['bicho']['backend_user']
        if options['bicho'].has_key('backend_password'):
            backend_password = options['bicho']['backend_password']
        trackers = options['bicho']['trackers']
        debug = options['bicho']['debug']
        log_table = options['bicho']['log_table']
        
        # we compose some flags
        flags = ""
        if debug:
            flags = flags + " -g"

        # we'll only create the log table in the last execution
        cont = 0
        last = len(trackers)

        for t in trackers:
            launched = True
            cont = cont + 1

            if cont == last and log_table:
                flags = flags + " -l"

            if backend_user and backend_password:
                compose_msg(tools['its'] + " --db-user-out=%s --db-password-out=%s --backend-user=%s --backend-password=%s --db-database-out=%s -d %s -b %s -u %s %s >> %s 2>&1"
                            % (db_user, db_pass, backend_user, backend_password, database, str(delay), backend, t, flags, msg_body))
                os.system(tools['its'] + " --db-user-out=%s --db-password-out=%s --backend-user=%s --backend-password=%s --db-database-out=%s -d %s -b %s -u %s %s >> %s 2>&1"
                            % (db_user, db_pass, backend_user, backend_password, database, str(delay), backend, t, flags, msg_body))
            else:
                compose_msg(tools['its'] + " --db-user-out=%s --db-password-out=%s --db-database-out=%s -d %s -b %s -u %s %s >> %s 2>&1"
                            % (db_user, db_pass, database, str(delay), backend, t, flags, msg_body))
                os.system(tools['its'] + " --db-user-out=%s --db-password-out=%s --db-database-out=%s -d %s -b %s -u %s %s >> %s 2>&1"
                          % (db_user, db_pass, database, str(delay), backend, t, flags, msg_body))
        if launched:
            compose_msg("[OK] bicho executed")
        else:
            compose_msg("[SKIPPED] bicho was not executed")
    else:
        compose_msg("[SKIPPED] bicho not executed, no conf available")

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
        #log_table = options['bicho']['log_table']

        # acs - gerrit is incremental
        #Given that gerrit backend for Bicho is not still incremental, database will be truncated
        # compose_msg("/usr/bin/mysqladmin -u %s drop %s -f " 
        #             % (db_user, database))
        # os.system("/usr/bin/mysqladmin -u %s drop %s -f "
        #             % (db_user, database))
        # compose_msg("/usr/bin/mysqladmin -u %s create %s "
        #             % (db_user, database))
        # os.system("/usr/bin/mysqladmin -u %s create %s "
        #             % (db_user, database))

        #some flags
        flags = ""
        if debug:
            flags = flags + " -g"
    
        cont = 0
        last = len(projects)

        for project in projects.split(","):
            launched = True
            cont = cont + 1

            if options['gerrit'].has_key('user'):
                user = options['gerrit']['user']
                compose_msg(tools['scr'] + " --db-user-out=%s --db-password-out=%s --db-database-out=%s -d %s -b %s --backend-user %s -u %s --gerrit-project=%s %s >> %s 2>&1"
                            % (db_user, db_pass, database, str(delay), backend, user, trackers[0], project, flags, msg_body))
                os.system(tools['scr'] + " --db-user-out=%s --db-password-out=%s --db-database-out=%s -d %s -b %s --backend-user %s -u %s --gerrit-project=%s %s >> %s 2>&1"
                            % (db_user, db_pass, database, str(delay), backend, user, trackers[0], project, flags, msg_body))
            else:
                compose_msg(tools['scr'] + " --db-user-out=%s --db-password-out=%s --db-database-out=%s -d %s -b %s -u %s --gerrit-project=%s %s >> %s 2>&1"
                            % (db_user, db_pass, database, str(delay), backend, trackers[0], project, flags, msg_body))
                os.system(tools['scr'] + " --db-user-out=%s --db-password-out=%s --db-database-out=%s -d %s -b %s -u %s --gerrit-project=%s %s >> %s 2>&1"
                            % (db_user, db_pass, database, str(delay), backend, trackers[0], project, flags, msg_body))

        if launched:
            compose_msg("[OK] bicho (gerrit) executed")
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
        for m in mlists.split(","):
            launched = True
            compose_msg(tools['mls'] + " --no-report --db-user=\"%s\" --db-password=\"%s\" --db-name=\"%s\" --db-admin-user=\"%s\" --db-admin-password=\"%s\" \"%s\" >> %s 2>&1"
                        %(db_user, db_pass, db_name, db_admin_user, db_pass, m, msg_body))
            os.system(tools['mls'] + " --no-report --db-user=\"%s\" --db-password=\"%s\" --db-name=\"%s\" --db-admin-user=\"%s\" --db-admin-password=\"%s\" \"%s\" >> %s 2>&1"
                      %(db_user, db_pass, db_name, db_admin_user, db_pass, m, msg_body))
        if launched:
            compose_msg("[OK] mlstats executed")
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
        channels = os.listdir(irc_dir)
        os.chdir(irc_dir)
        for channel in channels:
            if not os.path.isdir(os.path.join(irc_dir,channel)): continue
            launched = True
            compose_msg(tools['irc'] + " --db-user=\"%s\" --db-password=\"%s\" --database=\"%s\" --dir=\"%s\" --channel=\"%s\">> %s 2>&1"
                        % (db_user, db_pass, db_name, channel, channel, msg_body))
            os.system(tools['irc'] + " --db-user=\"%s\" --db-password=\"%s\" --database=\"%s\" --dir=\"%s\" --channel=\"%s\">> %s 2>&1"
                        %(db_user, db_pass, db_name, channel, channel, msg_body))
        if launched:
            compose_msg("[OK] irc_analysis executed")
        else:
            compose_msg("[SKIPPED] irc_analysis not executed")
    else:
        compose_msg("[SKIPPED] irc_analysis was not executed, no conf available")


def launch_rscripts():
    # reads data about r scripts for a conf file and execute it
    if options.has_key('r'):
        if not check_tool(tools['r']):
            return

        compose_msg("R scripts being launched")

        conf_file = project_dir + '/conf/main.conf'

        # script = options['r']['rscript']
        script = "run-analysis.py"
        # path = options['r']['rscripts_path']
        path = r_dir
        
        os.chdir(path)
        compose_msg("./%s script -f %s >> %s 2>&1" % (script, conf_file, msg_body))
        os.system("./%s script -f %s >> %s 2>&1" % (script, conf_file, msg_body)) 

        compose_msg("[OK] R scripts executed")
    else:
        compose_msg("[SKIPPED] R scripts were not executed, no conf available")

def launch_identity_scripts():
    # using the conf executes cvsanaly for the repos inside scm dir
    if options.has_key('identities'):
        compose_msg("Unify identity scripts are being executed")
        # idir = options['identities']['iscripts_path']
        idir = identities_dir
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        if (db_pass == ""): db_pass="''"

        if options['generic'].has_key('db_cvsanaly'):
            # TODO: -i no is needed in first execution
            db_scm = options['generic']['db_cvsanaly']
            compose_msg("%s/unifypeople.py -u %s -p %s -d %s >> %s 2>&1" % (idir, db_user, db_pass, db_scm, msg_body))
            os.system("%s/unifypeople.py -u %s -p %s -d %s >> %s 2>&1" % (idir, db_user, db_pass, db_scm, msg_body))
            # Companies are needed in Top because bots are included in a company
            compose_msg("%s/domains_analysis.py -u %s -p %s -d %s >> %s 2>&1" % (idir, db_user, db_pass, db_scm, msg_body))
            os.system("%s/domains_analysis.py -u %s -p %s -d %s >> %s 2>&1" % (idir, db_user, db_pass, db_scm, msg_body))

        if options['generic'].has_key('db_bicho'):
            db_its = options['generic']['db_bicho']
            compose_msg("%s/its2identities.py -u %s -p %s --db-database-its=%s --db-database-ids=%s >> %s 2>&1"
                        % (idir, db_user, db_pass, db_its, db_scm, msg_body))
            os.system("%s/its2identities.py -u %s -p %s --db-database-its=%s --db-database-ids=%s >> %s 2>&1"
                      % (idir, db_user, db_pass, db_its, db_scm, msg_body))
        
        # Gerrit use the same schema than its: both use bicho tool              
        if options['generic'].has_key('db_gerrit'):
            db_its = options['generic']['db_gerrit']
            compose_msg("%s/its2identities.py -u %s -p %s --db-database-its=%s --db-database-ids=%s >> %s 2>&1"
                        % (idir, db_user, db_pass, db_its, db_scm, msg_body))
            os.system("%s/its2identities.py -u %s -p %s --db-database-its=%s --db-database-ids=%s >> %s 2>&1"
                      % (idir, db_user, db_pass, db_its, db_scm, msg_body))

        if options['generic'].has_key('db_mlstats'):
            db_mls = options['generic']['db_mlstats']
            compose_msg("%s/mls2identities.py -u %s -p %s --db-database-mls=%s --db-database-ids=%s >> %s 2>&1"
                        % (idir, db_user, db_pass, db_mls, db_scm, msg_body))
            os.system("%s/mls2identities.py -u %s -p %s --db-database-mls=%s --db-database-ids=%s >> %s 2>&1"
                      % (idir, db_user, db_pass, db_mls, db_scm, msg_body))

        if options['generic'].has_key('db_irc'):
            db_irc = options['generic']['db_irc']
            compose_msg("%s/irc2identities.py -u %s -p %s --db-database-irc=%s --db-database-ids=%s >> %s 2>&1"
                        % (idir, db_user, db_pass, db_irc, db_scm, msg_body))
            os.system("%s/irc2identities.py -u %s -p %s --db-database-irc=%s --db-database-ids=%s >> %s 2>&1"
                      % (idir, db_user, db_pass, db_irc, db_scm, msg_body))

        if options['identities'].has_key('countries'):
            compose_msg("%s/load_ids_mapping.py -m countries -t true -u %s -p %s --database %s >> %s 2>&1"
                        % (idir, db_user, db_pass, db_scm, msg_body))
            os.system("%s/load_ids_mapping.py -m countries -t true -u %s -p %s --database %s >> %s 2>&1"
                        % (idir, db_user, db_pass, db_scm, msg_body))

        compose_msg("[OK] Identity scripts executed")
    else:
        compose_msg("[SKIPPED] Unify identity scripts not executed, no conf available")

def compose_msg(text):
    # append text to log file
    fd = open(msg_body, 'a')
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

        fd = open(msg_body, 'a')
        destination = os.path.join(project_dir,options['db-dump']['destination_db_dump'])


        # it's supposed to have db_user as root user
        for db in dbs:
            dest_mysql_file = destination + db[1] + '.mysql'
            dest_7z_file = dest_mysql_file + '.7z'

            fd_dump = open(dest_mysql_file, 'w')
            # Creation of dump file
            pr = subprocess.Popen([tools['mysqldump'], '-u', db_user, db[0]],
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


tasks_section = {
    'check-dbs':launch_checkdbs,
    'cvsanaly':launch_cvsanaly,
    'bicho':launch_bicho,
    'gerrit':launch_gerrit,
    'mlstats':launch_mlstats,
    'irc': launch_irc,
    'identities': launch_identity_scripts,
    'r':launch_rscripts,
    'git-production':launch_commit_jsones,
    'db-dump':launch_database_dump,
    'json-dump':launch_json_dump,
    'rsync':launch_rsync
}
tasks_order = ['check-dbs','cvsanaly','bicho','gerrit','mlstats','irc',
               'identities','r','git-production','db-dump','json-dump','rsync']

if __name__ == '__main__':
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
            tasks_section[section]()
    
    compose_msg("Process finished correctly ...")

    # done, we sent the result
    project = options['generic']['project']
    mail = options['generic']['mail']
    os.system("mail -s \"[%s] data updated\" %s < %s" % (project, mail, msg_body))
