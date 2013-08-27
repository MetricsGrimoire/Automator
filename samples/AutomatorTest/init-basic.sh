#!/bin/sh
# Basic init script without git publishing (production dir)

# Clone SCM repos
cd scm
git clone https://gerrit.wikimedia.org/r/p/mediawiki/extensions/OpenID
git clone https://gerrit.wikimedia.org/r/p/mediawiki/extensions/SolrStore
cd ..

# Download IRC logs
cd irc
wget http://bots.wmflabs.org/~wm-bot/logs/%23wikimedia-analytics/%23wikimedia-analytics.tar.gz
wget http://bots.wmflabs.org/~wm-bot/logs/%23wikimedia-fundraising/%23wikimedia-fundraising.tar.gz
mkdir wikimedia-analytics
mkdir wikimedia-fundraising
cd wikimedia-analytics/
tar xfz ../#wikimedia-analytics.tar.gz
cd ..
cd wikimedia-fundraising
tar xfz ../#wikimedia-fundraising.tar.gz
cd ../..

# Download tools
cd tools
# VizR
git clone https://github.com/VizGrimoire/VizGrimoireR.git
mkdir r-lib
cd VizGrimoireR
R CMD INSTALL -l ../r-lib vizgrimoire
cd ..
# VizJS
git clone https://github.com/VizGrimoire/VizGrimoireJS.git
cp VizGrimoireJS/data/* ../json/
mkdir VizGrimoireJS/browser/data/
ln -s ../../../../json VizGrimoireJS/browser/data/json
mkdir VizGrimoireJS/dashboard/data/
ln -s ../../../../json VizGrimoireJS/dashboard/data/json
# Copy test suite
cp -a ../test VizGrimoireJS
cp -a ../test/Makefile VizGrimoireJS/

cd ..

# DBs
mkdir -p production/browser/data/db/
cd ..

# Global dir with automator
cd ..
echo ./launch.py -d `pwd`/samples/AutomatorTest 
