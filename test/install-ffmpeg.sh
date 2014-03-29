#!/usr/bin/env bash

## tests fails with jon-severinsson binaries (version 0.10.7)
# add-apt-repository -y ppa:jon-severinsson/ffmpeg
# apt-get -y -qq update
# apt-get -y -qq install ffmpeg
# list directory of ffmpeg binary file there is in http://ffmpeg.gusari.org/static/64bit/
wget -P /tmp http://ffmpeg.gusari.org/static/64bit/ffmpeg.static.64bit.latest.tar.gz
tar -xvf /tmp/ffmpeg.static.64bit.latest.tar.gz -C /usr/local/bin