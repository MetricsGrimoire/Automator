#!/bin/sh
# Basic init script without git publishing (production dir)

# Clone SCM repos
cd scm
git clone https://github.com/MetricsGrimoire/Bicho.git
git clone https://github.com/MetricsGrimoire/CVSAnalY.git
git clone https://github.com/MetricsGrimoire/Automator.git
git clone https://github.com/MetricsGrimoire/MailingListStats.git
git clone https://github.com/MetricsGrimoire/IRCAnalysis.git
git clone https://github.com/VizGrimoire/VizGrimoireJS-lib.git
git clone https://github.com/VizGrimoire/VizGrimoireR.git
git clone https://github.com/VizGrimoire/VizGrimoireJS.git
cd ..

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
# cp -a ../test VizGrimoireJS
# cp -a ../test/Makefile VizGrimoireJS/

cd ..

# DBs
mkdir -p production/browser/data/db/
cd ..

# Global dir with automator
cd ..
echo ./launch.py -d `pwd`/grimoire
