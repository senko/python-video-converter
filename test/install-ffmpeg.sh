#!/usr/bin/env bash
# Based on https://raw.github.com/christianselig/islandora_solution_pack_video/7.x/ffmpeg-install.sh

apt-get -y update
apt-get -y install yasm lame autoconf build-essential checkinstall libvpx-dev libmp3lame-dev \
	libtheora-dev libvorbis-dev libx264-dev

## Install ffmpeg from source
mkdir ~/ffmpeg-source
cd ~/ffmpeg-source
wget http://www.ffmpeg.org/releases/ffmpeg-1.1.1.tar.gz
tar xf ffmpeg-1.1.1.tar.gz && rm -rf ffmpeg-1.1.1.tar.gz
cd ffmpeg-1.1.1
# don't configure with --enable-nonfree to allow distributin pre-build binaries
./configure --enable-gpl --enable-libmp3lame --enable-libtheora --enable-libvorbis --enable-libvpx --enable-libx264
make
checkinstall --pkgname=ffmpeg --pkgversion="7:$(date +%Y%m%d%H%M)-git" --backup=no --deldoc=yes --fstrans=no --default
hash -r
cd ~
