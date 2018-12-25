#!/bin/bash
if [ $2 -eq 0 ]; then 
    exit 0
fi

# http://stackoverflow.com/questions/4774054/reliable-way-for-a-bash-script-to-get-the-full-path-to-itself
SelfDir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo $SelfDir
cd $SelfDir

/usr/bin/python3 filter.py $3

