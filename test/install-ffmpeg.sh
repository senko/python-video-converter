#!/usr/bin/env bash

## tests fails with jon-severinsson binaries (version 0.10.7)
# add-apt-repository -y ppa:jon-severinsson/ffmpeg
# apt-get -y -qq update
# apt-get -y -qq install ffmpeg
# list directory of ffmpeg binary file there is in http://johnvansickle.com/ffmpeg/
wget -O /tmp/ffmpeg-static $1
mkdir /tmp/ffmpeg-bin/
tar -xvf /tmp/ffmpeg-static -C /tmp/ffmpeg-bin/
cp `find /tmp/ffmpeg-bin/ -name 'ff*' -executable -type f` /usr/local/bin
