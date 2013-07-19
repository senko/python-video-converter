#!/usr/bin/env bash

add-apt-repository -y ppa:jon-severinsson/ffmpeg
apt-get -y -qq update
apt-get -y -qq install ffmpeg
