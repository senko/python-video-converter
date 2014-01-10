#!/usr/bin/env bash

## tests fails with jon-severinsson binaries (version 0.10.7)
# add-apt-repository -y ppa:jon-severinsson/ffmpeg
# apt-get -y -qq update
# apt-get -y -qq install ffmpeg

wget -P /tmp http://ffmpeg.gusari.org/static/64bit/ffmpeg.static.64bit.2014-01-10.tar.gz
tar -xvf /tmp/ffmpeg.static.64bit.2014-01-10.tar.gz -C /usr/local/bin