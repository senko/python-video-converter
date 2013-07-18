# Video Converter

[![Build Status](https://travis-ci.org/senko/python-video-converter.png?branch=master)](https://travis-ci.org/senko/python-video-converter)

Video Converter is a Python module for converting video files from one format
and codec to another.

It uses the [FFmpeg multimedia framework](http://ffmpeg.org/) for actual file
processing, and adds an easy-to-use API for probing and converting media files
on top of it.

## Quickstart

    from converter import Converter
    c = Converter()

    info = c.probe('test1.ogg')

    conv = c.convert('test1.ogg', '/tmp/output.mkv', {
        'format': 'mkv',
        'audio': {
            'codec': 'mp3',
            'samplerate': 11025,
            'channels': 2
        },
        'video': {
            'codec': 'h264',
            'width': 720,
            'height': 400,
            'fps': 15
        })

    for timecode in conv:
        print "Converting (%f) ...\r" % timecode


## Documentation and tests

There's a fair amount of documentation in `doc/` directory.
To generate it from Sphinx sources, use:

    python setup.py doc

and then visit `doc/_build/html/index.html`.

To run the automated tests:

    python setup.py test

The test suite assumes you already have the required `ffmpeg` and `ffprobe`
tools installed on your system.

## Installation and requirements

To install the package:

    python setup.py install

Note that this only installs the Python Video Converter library. The `ffmpeg`
and `ffprobe` tools should be installed on the system separately, with all the
codec and format support you require.

If you need to compile and install the tools manually, have a look at the
example script `test/install-ffmpeg.sh` (used for automated test suite). It may
or may not be useful for your requirements, so don't just blindly run it -
check that it does what you need first.

## Authors and Copyright

Copyright &copy; 2011-2013. Python Video Converter contributors. See the
[AUTHORS.txt](AUTHORS.txt) File.

## Licensing and Patents

Although FFmpeg is licensed under LGPL/GPL, Video Converter only invokes the
existing ffmpeg executables on the system (ie. doesn’t link to the ffmpeg
libraries), so it doesn’t need to be LGPL/GPL as well.

The same applies to patents. If you’re in a country which recognizes software
patents, it’s up to you to ensure you’re complying with the patent laws. Please
read the FFMpeg Legal FAQ for more information.
