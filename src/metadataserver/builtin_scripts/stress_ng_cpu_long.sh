#!/bin/sh -e

sudo apt-get install -q -y stress-ng

sudo stress-ng \
    --aggressive -a 0 --class cpu,cpu-cache --ignite-cpu --log-brief \
    --metrics --times --tz --verify --timeout 12h
