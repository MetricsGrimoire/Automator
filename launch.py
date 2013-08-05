#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2012 Bitergia
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
#       Alvaro del Castillo <acs@bitergia.com>
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


# conf variables from file(see read_main_conf)
options = {}

# global var for directories
project_dir = ''
msg_body = ''#project_dir + '/log/launch.log'
scm_dir = ''#os.getcwd() + '/../scm/'
conf_dir = ''#os.getcwd() + '/../conf/'
json_dir = ''
production_dir = ''

def get_options():     
    parser = OptionParser(usage='Usage: %prog [options]',
                          description='Update data, process it and obtain JSON files',
                          version='0.1')
    
    parser.add_option('-d','--dir', dest='project_dir',
                     help='Path with the configuration of the project', default=None)

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
    global conf_dir
    global json_dir
    global production_dir
    
    project_dir = pdir     
    msg_body = project_dir + '/log/launch.log'
    scm_dir = project_dir + '/scm/'
    conf_dir = project_dir + '/conf/'
    json_dir = project_dir + '/json/'
    production_dir = project_dir + '/production/'

def read_main_conf():

    from ConfigParser import SafeConfigParser
    import codecs
    
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

def update_scm():
    # basically git pull of the dirs inside scm dir
    compose_msg("SCM is being updated")
    repos = os.listdir(scm_dir)
    for r in repos:
        os.chdir(scm_dir + r)
        os.system("git pull >> %s 2>&1" %(msg_body))
        compose_msg(r + " pull ended")
    compose_msg("[OK] SCM updated")

def launch_cvsanaly():
    # using the conf executes cvsanaly for the repos inside scm dir
    if options.has_key('cvsanaly'):
        update_scm()
        compose_msg("cvsanaly is being executed")
        launched = False
        extensions = options['cvsanaly']['extensions']
        db_name = options['generic']['db_cvsanaly']
        db_user = options['generic']['db_user']

        # we launch cvsanaly against the repos
        repos = os.listdir(scm_dir)
        for r in repos:
            launched = True
            os.chdir(scm_dir + r)
            compose_msg("/usr/local/bin/cvsanaly2 -u %s -d %s --extensions=%s >> %s 2>&1" 
                        %(db_user, db_name, extensions, msg_body))
            os.system("/usr/local/bin/cvsanaly2 -u %s -d %s --extensions=%s >> %s 2>&1" 
                      %(db_user, db_name, extensions, msg_body))
        
        if launched:
            compose_msg("[OK] cvsanaly executed")
        else:
            compose_msg("[SKIPPED] cvsanaly was not executed")
    else:
        compose_msg("cvsanaly not executed, no conf available")

def launch_bicho():
    # reads a conf file with all of the information and launches bicho
    if options.has_key('bicho'):
        compose_msg("bicho is being executed")
        launched = False
        
        database = options['generic']['db_bicho']
        db_user = options['generic']['db_user']
        db_pass = options['generic']['db_password']
        delay = options['bicho']['delay']
        backend = options['bicho']['backend']
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

            compose_msg("/usr/local/bin/bicho --db-user-out=%s --db-password-out=%s --db-database-out=%s -d %s -b %s -u %s %s >> %s 2>&1" 
                        % (db_user, db_pass, database, str(delay), backend, t, flags, msg_body))
            os.system("/usr/local/bin/bicho --db-user-out=%s --db-password-out=%s --db-database-out=%s -d %s -b %s -u %s %s >> %s 2>&1" 
                      % (db_user, db_pass, database, str(delay), backend, t, flags, msg_body))
        if launched:
            compose_msg("[OK] bicho executed")
        else:
            compose_msg("[SKIPPED] bicho was not executed")
    else:
        compose_msg("bicho not executed, no conf available")

def launch_gerrit():
    # reads a conf file with all of the information and launches bicho
    if options.has_key('gerrit'):
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

        #Given that gerrit backend for Bicho is not still incremental, database will be truncated
        compose_msg("/usr/bin/mysqladmin -u %s drop %s -f " 
                    % (db_user, database))
        os.system("/usr/bin/mysqladmin -u %s drop %s -f "
                    % (db_user, database))
        compose_msg("/usr/bin/mysqladmin -u %s create %s "
                    % (db_user, database))
        os.system("/usr/bin/mysqladmin -u %s create %s "
                    % (db_user, database))

        #some flags
        flags = ""
        if debug:
            flags = flags + " -g"
    
        cont = 0
        last = len(projects)

        for project in projects.split(","):
            launched = True
            cont = cont + 1

            compose_msg("/usr/local/bin/bicho --db-user-out=%s --db-password-out=%s --db-database-out=%s -d %s -b %s -u %s --gerrit-project=%s %s >> %s 2>&1"
                            % (db_user, db_pass, database, str(delay), backend, trackers[0], project, flags, msg_body))
            os.system("/usr/local/bin/bicho --db-user-out=%s --db-password-out=%s --db-database-out=%s -d %s -b %s -u %s --gerrit-project=%s %s >> %s 2>&1"
                            % (db_user, db_pass, database, str(delay), backend, trackers[0], project, flags, msg_body))

        if launched:
            compose_msg("[OK] bicho (gerrit) executed")
        else:
            compose_msg("[SKIPPED] bicho (gerrit) not executed")
    else:
        compose_msg("bicho (gerrit) not executed, no conf available")



def launch_mlstats():
    # reads a conf file with all of the information and launches bicho
    if options.has_key('mlstats'):
        compose_msg("mlstats is being executed")
        launched = False
        files = os.listdir(conf_dir)
        db_admin_user = options['generic']['db_user']        
        db_user = db_admin_user
        db_pass = options['generic']['db_password']
        db_name = options['generic']['db_mlstats']
        mlists = options['mlstats']['mailing_lists']
        for m in mlists.split(","):
            compose_msg("/usr/local/bin/mlstats --no-report --db-user=\"%s\" --db-password=\"%s\" --db-name=\"%s\" --db-admin-user=\"%s\" --db-admin-password=\"\" \"%s\" >> %s 2>&1" 
                        %(db_user, db_pass, db_name, db_admin_user, m, msg_body))
            os.system("/usr/local/bin/mlstats --no-report --db-user=\"%s\" --db-password=\"%s\" --db-name=\"%s\" --db-admin-user=\"%s\" --db-admin-password=\"\" \"%s\" >> %s 2>&1" 
                      %(db_user, db_pass, db_name, db_admin_user, m, msg_body))            
        compose_msg("[OK] mlstats executed")
        print "executed"
    else:
        compose_msg("[SKIPPED] mlstats was not executed")
        print "not executed"

def launch_rscripts():
    # reads data about r scripts for a conf file and execute it
    if options.has_key('r'):
        compose_msg("R scripts being launched")
 
        script = options['r']['rscript']
        path = options['r']['rscripts_path']
        r_libs = options['r']['r_libs']
        db_cvsanaly = options['generic']['db_cvsanaly']
        db_mlstats = options['generic']['db_mlstats']
        db_bicho = options['generic']['db_bicho']
        db_gerrit = options['generic']['db_gerrit']
        today = time.strftime('%Y-%m-%d')
        ddir = json_dir
        compose_msg("R_LIBS=%s ./%s %s %s %s %s %s %s %s >> %s 2>&1" %
                    (r_libs, script, db_cvsanaly, db_mlstats, db_bicho, 
                     today, ddir, db_gerrit, msg_body, msg_body))
        os.chdir(path)
        os.system("R_LIBS=%s ./%s %s %s %s %s %s %s %s >> %s 2>&1" %
                  (r_libs, script, db_cvsanaly, db_mlstats, db_bicho, 
                   today, ddir, db_gerrit, msg_body, msg_body))

        compose_msg("[OK] R scripts executed")
    else:
        compose_msg("[SKIPPED] R scripts were not executed")

def launch_identity_scripts():
    # using the conf executes cvsanaly for the repos inside scm dir
    if options.has_key('identities'):
        compose_msg("Unify identity scripts are being executed")
        idir = options['identities']['iscripts_path']
        db_scm = options['generic']['db_cvsanaly']
        db_its = options['generic']['db_bicho']
        db_mls = options['generic']['db_mlstats']
        db_user = options['generic']['db_user']

        # we launch cvsanaly against the repos

        compose_msg("%s/unifypeople.py -u %s -d %s >> %s 2>&1" % (idir, db_user, db_scm, msg_body))
        os.system("%s/unifypeople.py -u %s -d %s >> %s 2>&1" % (idir, db_user, db_scm, msg_body))
        
        compose_msg("%s/its2identities.py -u %s --db-database-its=%s --db-database-ids=%s >> %s 2>&1" % (idir, db_user, db_its, db_scm, msg_body))
        os.system("%s/its2identities.py -u %s --db-database-its=%s --db-database-ids=%s >> %s 2>&1" % (idir, db_user, db_its, db_scm, msg_body))

        compose_msg("%s/mls2identities.py -u %s --db-database-mls=%s --db-database-ids=%s >> %s 2>&1" % (idir, db_user, db_mls, db_scm, msg_body))
        os.system("%s/mls2identities.py -u %s --db-database-mls=%s --db-database-ids=%s >> %s 2>&1" % (idir, db_user, db_mls, db_scm, msg_body))
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

def commit_jsones():
    # copy JSON files and commit + push them
    if options.has_key('git-production'):
        destination = options['git-production']['destination_json']
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

def database_dump():
    # copy and compression of database to be rsync with customers
    if options.has_key('db-dump'):

        # databases
        # this may fail if any of the four is not found
        db_user = options['generic']['db_user']
        db_bicho = options['generic']['db_bicho']
        db_cvsanaly = options['generic']['db_cvsanaly']
        db_mlstats = options['generic']['db_mlstats']
        db_gerrit = options['generic']['db_gerrit']
        dbs = [(db_bicho, 'tickets'),
               (db_cvsanaly, 'source_code'),
               (db_mlstats, 'mailing_lists'),
               (db_gerrit, 'reviews')]

        fd = open(msg_body, 'a')
        destination = options['db-dump']['destination_db_dump']


        # it's supposed to have db_user as root user
        for db in dbs:
            dest_mysql_file = destination + db[1] + '.mysql'
            dest_7z_file = dest_mysql_file + '.7z'

            fd_dump = open(dest_mysql_file, 'w')
            # Creation of dump file
            pr = subprocess.Popen(['/usr/bin/mysqldump', '-u', db_user, db[0]],
                     stdout = fd_dump,
                     stderr = fd,
                     shell = False)
            (out, error) = pr.communicate()
            fd_dump.close()

            # Creation of compressed dump file
            pr = subprocess.Popen(['/usr/bin/7zr', 'a', dest_7z_file, dest_mysql_file],
                     stdout = fd,
                     stderr = fd,
                     shell = False)
            (out, error) = pr.communicate()

            # Remove not compressed file
            pr = subprocess.Popen(['/bin/rm', dest_mysql_file],
                     stdout = fd,
                     stderr = fd,
                     shell = False)
            (out, error) = pr.communicate()

        fd.close()



def launch_rsync():
    # copy JSON files and commit + push them
    if options.has_key('rsync'):

        fd = open(msg_body, 'a')

        destination = options['rsync']['destination']
        pr = subprocess.Popen(['/usr/bin/rsync','--rsh', 'ssh', '-zva', '--stats', '--progress', '--update' ,'--delete', production_dir, destination],
                              stdout=fd, 
                              stderr=fd, 
                              shell=False)
        (out, error) = pr.communicate()

        fd.close()


if __name__ == '__main__':
    opt = get_options()   
    initialize_globals(opt.project_dir)

    reset_log()
    compose_msg("Starting ..") 
    
    read_main_conf()
    
    launch_cvsanaly()
    launch_bicho()
    launch_gerrit()
    launch_mlstats()
    launch_identity_scripts()
    launch_rscripts()

    commit_jsones()
    database_dump()
    launch_rsync()

    # done, we sent the result
    project = options['generic']['project']
    mail = options['generic']['mail']
    os.system("mail -s \"[%s] data updated\" %s < %s" % (project, mail, msg_body))
