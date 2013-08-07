#!/bin/sh

if [ $# -ne 1 ]
    then
    	echo "new_project.sh <project_dir>"
    	exit
fi

# Create directories
mkdir -p $1/conf
mkdir -p $1/irc
mkdir -p $1/json
mkdir -p $1/log
mkdir -p $1/production
mkdir -p $1/scm
mkdir -p $1/tools

# Copy config template
cp main.conf $1/conf

# Instructions with next steps
echo "Run project with: ./launch.py -d " `pwd`/$1 