#!/bin/sh
if [ -d "production/browser/data/db/" ]
then
    echo "Project already configured"
    cd ../..
    echo ./launch.py -d `pwd`/samples/VizJS-lib
    exit
fi

# Basic dirs
mkdir -p json log scm tools production

# SCM repos to analyze
cd scm
git clone https://github.com/VizGrimoire/VizGrimoireJS-lib.git
cd ..

# Tools to do the analysis
cd tools
git clone https://github.com/VizGrimoire/VizGrimoireR.git
mkdir r-lib
cd VizGrimoireR
R CMD INSTALL -l ../r-lib vizgrimoire
cd ..
git clone https://github.com/VizGrimoire/VizGrimoireJS.git
cp -a VizGrimoireJS/* ../production/
rm -rf ../production/browser/data/json/*
rm -rf ../production/browser/data/db
cp VizGrimoireJS/browser/data/json/viz_cfg.json ../production/browser/data/json/
cp VizGrimoireJS/browser/data/json/project-info.json ../production/browser/data/json/
mkdir -p ../production/browser/data/db/
cd ..

# Main directory
cd ../..
echo ./launch.py -d `pwd`/samples/VizJS-lib
