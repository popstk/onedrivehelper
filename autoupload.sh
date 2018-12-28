#!/bin/bash
if [ $2 -eq 0 ]; then 
    exit 0
fi

redis-cli -n 1 rpush upload "$3"
