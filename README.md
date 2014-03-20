Automator
=========

Automator is a Python script which executes the Metrics Grimoire tools and the VizGrimoireR scripts. It is a work in progress.


    python launch.py --dir [ path to the directory where the main.conf file is ]


Configuration file
------------------

Automator was designed to run the Metrics Grimoire + VizGrimoireR tools automatically. The configuration file is very simple, 
if section exists it executes the tool, if not it doesn't.

    luis@tahine:~/repos/automator$ cat main.conf
    [generic]
    ## generic configuration here
  
    # where to send notifications
    mail = personone@yourmaildomain.com,persontwo@yourmaildomain.com
    project = DevStack
  
    # data about the databases
    db_user = root
    db_password = rootpassword
    db_bicho = bicho_db
    db_cvsanaly = cvsanaly_db
    db_mlstats = mlstats_db
    db_gerrit = gerrit_db
    db_irc = gerrit_irc
    db_downloads = downloads_db
    
    [bicho]
    # This file contains the information needed to execute Bicho
    backend = lp
    debug = True
    delay = 1
    log_table = True
    trackers = https://bugs.launchpad.net/devstack
    
    [gerrit]
    # This file contains the information needed to execute Bicho for gerrit
    backend = gerrit
    debug = True
    delay = 1
    trackers = review.openstack.org 
    projects = openstack-dev/devstack
    
    [cvsanaly]
    # This file contains the information needed to execute cvsanaly
    extensions = CommitsLOC,FileTypes
    
    [mlstats]
    # This file contains the information needed to execute mlstats
    mailing_lists = http://lists.openstack.org/pipermail/community/
   
    [downloads]
    # This section contains information about a downloads web directory
    url_user = user
    url_password = pass
    url = http://testing.url/logs/
 
    [irc]
    
    [r]
    # This file contains information about the R script. The launcher
    # basically chdir into the dir and execute the rscript with the
    # parameters

    rscript = run_scripts-devstack.sh
    r_libs = ../r-lib:$R_LIBS
    
    [identities]
    # Data about the scripts executed to get unified identities
    iscripts_path = /home/owl/automator/automatic_retrieval/devstack/tools/VizGrimoireR/misc/
    
    [git-production]
    # Details about the git destination of the JSON
    destination_json = /home/owl/automator/automatic_retrieval/devstack/production/browser/data/json/
   
    [json-dump]
    # This option will compress all of the json files into one file
    origin_json_dump = production/browser/data/json/
    destination_json_dump = production/browser/data/db/
 
    [db-dump]
    #Data about final dir to dump databases
    destination_db_dump = /home/owl/automator/automatic_retrieval/devstack/production/browser/data/db/
    
    [rsync]
    # Destination where the production dir will be sync
    destination = yourmaildomain@activity.devstack.org:/var/www/dash/
  
Dependencies
------------
  
Have a look to the header of the Python file to know what Python libraries it uses.

It is capable of executing the following tools (remember they are optional):
+ CVSAnaly
+ Bicho
+ MLStats
+ IRC Analysis
+ VizGrimoireR scripts
