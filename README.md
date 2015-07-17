# Automator

Automator is a Python script which executes the Metrics Grimoire tools and the GrimoireLib report_tool.py tool. It is a work in progress.

<pre>
python launch.py --dir [ path to the directory where the main.conf file is ]
</pre>

## Dependencies

Have a look to the header of the Python file to know what Python libraries it uses.

It is capable of executing the following tools (remember they are optional):

For database population:
* CVSAnaly >= 2.1.0 or latest
* Bicho >= 0.9.1 or latest
* MLStats = 0.4.2 (newer versions are not supported)
* IRC Analysis >= 0.1 or latest
* sortinghat >= latest
* Sibyl >= v0.4 or latest
* Octopus >= latest
* pullpo >= latest
* MediaWikiAnalysis >= 0.3 or latest
* Eventizer >= latest

For database analysis and data visualization:
* GrimoireLib >= 15.04 or latest
* VizGrimoireUtils >= latest
* VizGrimoireJS >= 2.2.2 or latest

# How-to create a Dashboard using Grimoire Tools

There are 5 mains steps:

1. [Create the environment - configure the backends](#environment)
2. [Collect the data using MetricsGrimoire tools](#retrieval)
3. [Generate database/s with all the identities](#gen_db)
4. [Generate metrics using VizGrimoire](#gen_metrics)
5. [Configure the dashboard](#dashboard_conf)

## <a name="environment"/> 1. Create the environment - configure the backends

All the information regarding a project/dashboard should be placed inside a directory. 

Inside that directory, we have the following structure:

<pre>
|-- conf
|-- downloads (optional)
|-- irc (optional)
|-- json
|-- log
|-- production
|-- scm
|-- scripts
`-- tools
    |-- GrimoireLib
    |-- VizGrimoireJS
    `-- VizGrimoireUtils
</pre>

* conf: is where the `main.conf` is located. This file is one of the most important, will be described in brief later.
* downloads: if the backend is activated and configured, is where the logs are retrieved
* irc: if the backend is activated, where the IRC logs are placed
* json: folder where the jsons generated with the VizGrimoire utils are located
* log: folder where the logs are. There are 2 types of logs:
    * `launch_*.log`: logs of the data retrieval. This logs are the ones regarding the backends of data retrieval
    * `launch-*.log`: logs of the metrics generation. Displays the metrics generation logs
* production: folder containing VizGrimoireJS for visualization
* scm: where the repositories from SCM are downloaded (CVSAnaly)
* scripts: folder where some scripts are used (when needed)
* tools: folder where the VizGrimoire tools are located (GrimoireLib, vizGrimoireJS and VizGrimoireUtils)

Let's now describe the file `main.conf`. Every information regarding data retrieval will be here (all but CVSAnalY, which will be described later).
We will need one database for each tool. Let's go section by section:

NOTE: this sections should be added in the main.conf file as needed.

### **generic**
```
[generic]
# where to send notifications
mail = <email>
project = <project_name>
# data about the databases
db_user = <db_user>
db_password = <db_password>
db_sortinghat = <sortinghat_db>
db_identities = <sortinghat_db>
db_<tool> = <tool_db>			 // One for each tool. 
								 // Tools available: 'cvsanaly', 'bicho', 'gerrit', 'mlstats', 'irc', 'mediawiki', 'sibyl', 'pullpo', 'octopus'
bicho_backend = <bicho_backend>	 // Options available: 'bugzilla', 'lp'(launchpad), 'jira', 'github', 'redmine', 'storyboard'
people_number = 100				 // Number of people to display 
db_projects = <projects_db>		 // When needed
```

### **Bicho backends**

Bicho is a command line based tool used to parse bug/issue tracking systems. It has several configurations depending the backend we are about to use. The list of available backends is:
* [bugzilla](#bugzilla) 
* [lp](#launchpad)
* [jira](#jira)
* [github](#github)
* [redmine](#redmine)
* [storyboard](#storyboard)

So for each one, the section to add in the config file is different:

<a name="bugzilla"/> **Bugzilla**
```
# This file contains the information needed to execute Bicho
backend = bg
debug = True
delay = 1
log_table = True
trackers = <add_here_your_trackers>
# Supported tracker formats. We support products and components or subsections. The format is:
# For products:     "https://<your_bugzilla_host>/buglist.cgi?product=<your_product_name>" 
# For components:   "https://<your_bugzilla_host>/buglist.cgi?product=<your_product_name>&component=<your_component_name>"
# NOTE: if the tracker has any whitespace in the product_name/component_name, add it like it and not in the url format or %20
# Example: 
# trackers = 'https://bugzilla.samba.org/buglist.cgi?product=Samba 2.2'
# NOTE 2: with this backend, don't forget to activate 'tickets_states' study at [r] section!
```

<a name="launchpad"/> **Launchpad**
```
# This file contains the information needed to execute Bicho
backend = lp
debug = True
delay = 1
log_table = True
trackers = <add_here_your_trackers>
# NOTE: with this backend, don't forget to activate 'tickets_states' study at [r] section!
```

<a name="jira"/> **Jira**
```
[bicho]
# This file contains the information needed to execute Bicho
backend = jira
backend_user = <if_needed>
backend_password = <if_needed>
debug = True
delay = 1
log_table = True
trackers = <add_here_your_trackers>
# NOTE: with this backend, don't forget to activate 'tickets_states' study at [r] section!
```

<a name="github"/> **Github**
```
[bicho]
# This file contains the information needed to execute Bicho (user and password NEEDED to authenticate against the API)
backend = github
debug = True
delay = 1
log_table = False
backend_user = <user>
backend_password = <password>
trackers = <add_here_your_trackers>
```

<a name="redmine"/> **Redmine**
```
[bicho]
# This file contains the information needed to execute Bicho 
backend = redmine
debug = True
delay = 1
log_table = False
backend_user = <if_needed>
backend_password = <if_needed>
trackers = <add_here_your_trackers>
# NOTE: with this backend, don't forget to activate 'tickets_states' study at [r] section!
```

<a name="storyboard"/> **Storyboard**
```
[bicho]
backend = storyboard
debug = True
delay = 1
log_table = False
trackers = <add_here_your_trackers>
```

### **Gerrit**

Extracts information from a Gerrit code review source. It usually needs previous configuration. You will have to register there and, once registered, add the ssh public key in your profile to be able to retrieve data. Then, there are couple ways to retrieve a projects list from that tracker:

1. By ssh (user need to be registered)

```
ssh -p 29418 <username>@<gerrit_server> gerrit ls-projects
```

2. Using the rest API. For example, using Ovirt gerrit:

```
curl -s -X GET https://gerrit.ovirt.org/projects/?d -q | grep "\"id\"" | awk -F': "' '{print $2}' | sed -e 's/",//g'
```

So once we have the list, the configuration to add in the config file is:

```
[gerrit]
# Information about gerrit
backend = gerrit
user = <username>
debug = True
delay = 1
log_table = False
trackers = <add_here_your_tracker>
projects = <project1,project2,project3>
```

### **Mlstats**

MLStats is a tool to parse and analyze mail boxes into a database.

```
[mlstats]
# Add there the complete URL(s) and/or path of your mailing lists ARCHIVE (divided by commas and no whitespaces)
mailing_lists = <include_here_your_mailing_lists>
```
IMPORTANT: Not the URL(s) of your mailing lists, the URL(s) of your mailing lists ARCHIVES.
WRONG-URL: https://lists.libresoft.es/listinfo/metrics-grimoire
CORRECT-URL: https://lists.libresoft.es/pipermail/metrics-grimoire/

### **IRC**

Tool to analyze IRC channels and parse logs

We are now supporting 2 backends:
* IRC plain logs
* slack

IRC plain logs can be retrieved in different ways; but for the analysis they must be placed in the irc folder. If we want to analyze different channels, we can divide the channels inside folders like `<#channel_name>`.

```
[irc]
format = <format>        // (2 options: 'plain' or 'slack')
token = <token>			 // slack token, just needed for slack backend. Otherwise remove it
```

### **Mediawiki**

MediaWiki Analysis Tool to gather information about pages, changes and people in MediaWiki based websites

```
[mediawiki]
sites = <add_your_mediawiki_url_here>     // Add here the URL from your mediawiki site
```

### **Sibyl**

Sibyl aims at extracting information from question and answer sites and storing it into a database
There are 3 different backends supported: 
* discourse
* 'ab'(askbot)
* stackoverflow

```
[sibyl]
url = https://api.stackexchange.com
backend = <backend>					// 'discourse','ab','stackoverflow'
# api_key = <your_api_key>			// Needed for stackoverflow
# tags = <tags_to_analyze>			// Needed for stackoverflow
```

### **Pullpo**

Pull requests / reviews analyzer from Github

```
[pullpo]
user = <github_user>
password = <github_password>
debug = True
owner = <owner> 					// Add here the organization to analyze
projects = <list_of_projects>		// Repos name(just repo's name, divided by commas and no whitespaces)
```

In case we would like to analyze more than one organizations, the section can be added like:

```
[pullpo]
user = <github_user>
password = <github_password>
debug = True
owner = <org_1>,<org_2> 					
projects_<org_1> = <list_of_projects>
projects_<org_2> = <list_of_projects>
```

### **Octopus**

Octopus is a tool to retrieve information, which is publicly available on the Internet, about free software projects.

```
[octopus_<backend>]                  // Available backends: ('github','docker','puppet')   
url = <add_here_the_URL>             // Add here the complete URL of your backend
```

### **Eventizer**

Eventizer is a python tool created by Bitergia to retrieve information from Meetup groups. It store the data in a MySQL database.

```
[eventizer]
key = <api-key>                      // Add here your meetup API key
groups = <list-of-groups>            // Add here the list of groups you would like to analyze
```

### CVSAnalY 

The CVSAnalY tool extracts information out of source code repository logs and stores it into a database

```
[cvsanaly]
# This file contains the information needed to execute CVSAnalY (extensions)
extensions = CommitsLOC,FileTypes
```

For CVSAnalY, we need to retrieve the repositories manually. This means, CVSAnalY will analyze every repository placed under the 'scm' folder, so you need to download every repository to analyze there.

### **r**

In this section we can configure the metrics to generate. 

* Reports available: 
    * `repositories`
    * `organizations`
    * `people`
    * `countries`
    * `domains`
* Studies available: 
    * `ages`
    * `onion`
    * `timezone`
    * `tickets_states`

NOTE: for the `organizations` analysis (report), we should load the organizations wanted in the identities database first. (see sortinghat)

NOTE 2: `tickets_states` study is just available in the backends listed below

```
[r]
start_date = 2002-01-01							// This date should match the first date of each source
# end_date = 2015-01-01
reports = <report1, report2>
studies = <study1, study2>
# period = <month,weeks>
# people_out = <bot1, bot2>
# companies_out = <company1, company2>
# domains_out = <domain1, domain2>
```

## <a name="retrieval"/> 2. Collect the data using MetricsGrimoire tools

For each data source, you'll need to have the tool installed in your system. After that, you can start retrieving data easily using Automator. Once the `main.conf` is properly configured, you can launch every tool just by doing:

```
python launch.py --dir <PATH_TO_PROJECT_DIR> -s <tool>
```

So let's say we already have installed the tools and configured the main.conf to analyze JIRA (bicho). So to retrieve all, we just need to generate the databases listed in the `generic` section (just once).

NOTE: for sortinghat, before launching `check-dbs` option, we should initialize a database doing:

```
sortinghat init <db_name>
```

Then create the rest of them:

```
python launch.py -d /test/project-jira/ -s check-dbs
```
and then launch:

```
python launch.py -d /test/project-jira/ -s bicho
```
NOTE: for sortinghat, before launching `check-dbs` option, we should initialize a database doing:

```
sortinghat init <db_name>
```
Where `db_name` should match the one added in the `generic` section.

## <a name="gen_db"/> 3. Generate a database with all the identities

Once we've already retrieved all the data, we can start populating the identities database using sortinghat. Sortinghat basically retrieves all the identities information from each data source in the main.conf and load it in a sortinghat format database. This is as easy as:

```
python launch.py -d <PATH_TO_PROJECT_DIR> -s sortinghat
```

## <a name="gen_metrics"/> 4. Generate metrics using VizGrimoire

At this point, with the databases populated, we can generate the JSONs with all the data to be displayed. For this, we will use GrimoireLib (required). With the tool installed, we can:

```
python launch.py -d <PATH_TO_PROJECT_DIR> -s metrics
```

This will generate all the jsons regarding all the information provided in the `main.conf`. Also, we can generate the metrics of one tool by doing, for example:

```
python launch.py -d <PATH_TO_PROJECT_DIR> -s metrics -t scm
```

Supported metrics: 

| Metric | Retrieved with |
|--------| ---------------|
| `scm` | CVSAnalY |
| `its` | Bicho |
| `irc` | IRCAnalysis |
| `mls` | MailingListStats |
| `scr` | Bicho (gerrit) |
| `pullpo` | pullpo |
| `mediawiki` | MediaWikiAnalysis |
| `qaforums` | Sibyl |
| `releases` | Octopus |
| `eventizer` | Eventizer |

## <a name="dashboard_conf"/> 5. Configure the dashboard

The dashboard (VizGrimoireJS) is configured already to display every information generated. To adjust a bit more the info to display, we can tweak our dashboard by doing the following:

* Configure the `project_info.json` (dashboard information)
* Configure `menu_elements.conf` (Navigation bar)
