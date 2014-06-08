#!/usr/bin/env python

import os.path
import os
import re
import signal
from subprocess import Popen, PIPE
import logging
import locale

logger = logging.getLogger(__name__)

console_encoding = locale.getdefaultlocale()[1] or 'UTF-8'


class AvConvError(Exception):
    pass


class AvConvConvertError(Exception):
    def __init__(self, message, cmd, output, details=None, pid=0):
        """
        @param    message: Error message.
        @type     message: C{str}

        @param    cmd: Full command string used to spawn AvConv.
        @type     cmd: C{str}

        @param    output: Full stdout output from the AvConv command.
        @type     output: C{str}

        @param    details: Optional error details.
        @type     details: C{str}
        """
        super(AvConvConvertError, self).__init__(message)

        self.cmd = cmd
        self.output = output
        self.details = details
        self.pid = pid

    def __repr__(self):
        error = self.details if self.details else self.message
        return ('<AvConvConvertError error="%s", pid=%s, cmd="%s">' %
                (error, self.pid, self.cmd))

    def __str__(self):
        return self.__repr__()


class MediaFormatInfo(object):
    """
    Describes the media container format. The attributes are:
      * format - format (short) name (eg. "ogg")
      * fullname - format full (descriptive) name
      * bitrate - total bitrate (bps)
      * duration - media duration in seconds
      * filesize - file size
    """

    def __init__(self):
        self.format = None
        self.fullname = None
        self.bitrate = None
        self.duration = None
        self.filesize = None

    def parse_avprobe(self, key, val):
        """
        Parse raw avprobe output (key=value).
        """
        if key == 'format_name':
            self.format = val
        elif key == 'format_long_name':
            self.fullname = val
        elif key == 'bit_rate':
            self.bitrate = MediaStreamInfo.parse_float(val, None)
        elif key == 'duration':
            self.duration = MediaStreamInfo.parse_float(val, None)
        elif key == 'size':
            self.size = MediaStreamInfo.parse_float(val, None)

    def __repr__(self):
        if self.duration is None:
            return 'MediaFormatInfo(format=%s)' % self.format
        return 'MediaFormatInfo(format=%s, duration=%.2f)' % (self.format,
                                                              self.duration)


class MediaStreamInfo(object):
    """
    Describes one stream inside a media file. The general
    attributes are:
      * index - stream index inside the container (0-based)
      * type - stream type, either 'audio' or 'video'
      * codec - codec (short) name (e.g "vorbis", "theora")
      * codec_desc - codec full (descriptive) name
      * duration - stream duration in seconds
      * metadata - optional metadata associated with a video or audio stream
      * bitrate - stream bitrate in bytes/second
      * attached_pic - (0, 1 or None) is stream a poster image? (e.g. in mp3)
    Video-specific attributes are:
      * video_width - width of video in pixels
      * video_height - height of video in pixels
      * video_fps - average frames per second
    Audio-specific attributes are:
      * audio_channels - the number of channels in the stream
      * audio_samplerate - sample rate (Hz)
    """

    def __init__(self):
        self.index = None
        self.type = None
        self.codec = None
        self.codec_desc = None
        self.duration = None
        self.bitrate = None
        self.video_width = None
        self.video_height = None
        self.video_fps = None
        self.audio_channels = None
        self.audio_samplerate = None
        self.attached_pic = None
        self.sub_forced = None
        self.sub_default = None
        self.metadata = {}

    @staticmethod
    def parse_float(val, default=0.0):
        try:
            return float(val)
        except:
            return default

    @staticmethod
    def parse_int(val, default=0):
        try:
            return int(val)
        except (TypeError, ValueError):
            return default

    def parse_avprobe(self, key, val):
        """
        Parse raw avprobe output (key=value).
        """

        if key == 'index':
            self.index = self.parse_int(val)
        elif key == 'codec_type':
            self.type = val
        elif key == 'codec_name':
            self.codec = val
        elif key == 'codec_long_name':
            self.codec_desc = val
        elif key == 'duration':
            self.duration = self.parse_float(val)
        elif key == 'bit_rate':
            self.bitrate = self.parse_int(val, None)
        elif key == 'width':
            self.video_width = self.parse_int(val)
        elif key == 'height':
            self.video_height = self.parse_int(val)
        elif key == 'channels':
            self.audio_channels = self.parse_int(val)
        elif key == 'sample_rate':
            self.audio_samplerate = self.parse_float(val)
        elif key == 'DISPOSITION:attached_pic':
            self.attached_pic = self.parse_int(val)

        if key.startswith('TAG:'):
            key = key.split('TAG:')[1]
            value = val
            self.metadata[key] = value

        if self.type == 'audio':
            if key == 'avg_frame_rate':
                if '/' in val:
                    n, d = val.split('/')
                    n = self.parse_float(n)
                    d = self.parse_float(d)
                    if n > 0.0 and d > 0.0:
                        self.video_fps = float(n) / float(d)
                elif '.' in val:
                    self.video_fps = self.parse_float(val)

        if self.type == 'video':
            if key == 'avg_frame_rate':
                if '/' in val:
                    n, d = val.split('/')
                    n = self.parse_float(n)
                    d = self.parse_float(d)
                    if n > 0.0 and d > 0.0:
                        self.video_fps = float(n) / float(d)
                elif '.' in val:
                    self.video_fps = self.parse_float(val)

        if self.type == 'subtitle':
            if key == 'disposition:forced':
                self.sub_forced = self.parse_int(val)
            if key == 'disposition:default':
                self.sub_default = self.parse_int(val)


    def __repr__(self):
        d = ''
        metadata_str = ['%s=%s' % (key, value) for key, value
                        in self.metadata.items()]
        metadata_str = ', '.join(metadata_str)

        if self.type == 'audio':
            d = 'type=%s, codec=%s, channels=%d, rate=%.0f' % (self.type,
                self.codec, self.audio_channels, self.audio_samplerate)
        elif self.type == 'video':
            d = 'type=%s, codec=%s, width=%d, height=%d, fps=%.1f' % (
                self.type, self.codec, self.video_width, self.video_height,
                self.video_fps)
        elif self.type == 'subtitle':
            d = 'type=%s, codec=%s' % (self.type, self.codec)
        if self.bitrate is not None:
            d += ', bitrate=%d' % self.bitrate

        if self.metadata:
            value = 'MediaStreamInfo(%s, %s)' % (d, metadata_str)
        else:
            value = 'MediaStreamInfo(%s)' % d

        return value


class MediaInfo(object):
    """
    Information about media object, as parsed by ffprobe.
    The attributes are:
      * format - a MediaFormatInfo object
      * streams - a list of MediaStreamInfo objects
    """

    def __init__(self, posters_as_video=True):
        """
        :param posters_as_video: Take poster images (mainly for audio files) as
            A video stream, defaults to True
        """
        self.format = MediaFormatInfo()
        self.posters_as_video = posters_as_video
        self.streams = []

    def parse_avprobe(self, raw):
        """
        Parse raw avprobe output.
        """
        in_format = False
        current_stream = None

        for line in raw.split('\n'):
            line = line.strip()
            if line == '':
                if current_stream is None and not in_format:
                    continue
                elif current_stream is not None:
                    self.streams.append(current_stream)
                    current_stream = None
                elif in_format:
                    in_format = False
            elif line.startswith('[stream'):
                current_stream = MediaStreamInfo()
            elif line == '[format]':
                in_format = True
            elif '=' in line:
                k, v = line.split('=', 1)
                k = k.strip()
                v = v.strip()
                if current_stream:
                    current_stream.parse_avprobe(k, v)
                elif in_format:
                    self.format.parse_avprobe(k, v)

    def __repr__(self):
        return 'MediaInfo(format=%s, streams=%s)' % (repr(self.format),
                                                     repr(self.streams))

    @property
    def video(self):
        """
        First video stream, or None if there are no video streams.
        """
        for s in self.streams:
            if s.type == 'video' and (self.posters_as_video
                                      or not s.attached_pic):
                return s
        return None

    @property
    def posters(self):
        return [s for s in self.streams if s.attached_pic]

    @property
    def audio(self):
        """
        First audio stream, or None if there are no audio streams.
        """
        for s in self.streams:
            if s.type == 'audio':
                return s
        return None


class AvConv(object):
    """
    AvConv wrapper object, takes care of calling the AvConv binaries,
    passing options and parsing the output.

    >>> f = AvConv()
    """
    DEFAULT_JPEG_QUALITY = 4

    def __init__(self, conv_path=None, probe_path=None):
        """
        Initialize a new AvConv wrapper object. Optional parameters specify
        the paths to AvConv and avprobe utilities.
        """

        def which(name):
            path = os.environ.get('PATH', os.defpath)
            for d in path.split(':'):
                fpath = os.path.join(d, name)
                if os.path.exists(fpath) and os.access(fpath, os.X_OK):
                    return fpath
            return None

        if conv_path is None:
            conv_path = 'avconv'

        if probe_path is None:
            probe_path = 'avprobe'

        if '/' not in conv_path:
            conv_path = which(conv_path) or conv_path
        if '/' not in probe_path:
            probe_path = which(probe_path) or probe_path

        self.avconv_path = conv_path
        self.avprobe_path = probe_path

        if not os.path.exists(self.avconv_path):
            raise AvConvError("avconv binary not found: " + self.avconv_path)

        if not os.path.exists(self.avprobe_path):
            raise AvConvError("avprobe binary not found: " + self.avprobe_path)

    @staticmethod
    def _spawn(cmds):
        logger.debug('Spawning AvConv with command: ' + ' '.join(cmds))
        return Popen(cmds, shell=False, stdin=PIPE, stdout=PIPE, stderr=PIPE,
                     close_fds=True)

    def probe(self, fname, posters_as_video=True):
        """
        Examine the media file and determine its format and media streams.
        Returns the MediaInfo object, or None if the specified file is
        not a valid media file.

        >>> info = AvConv().probe('test1.ogg')
        >>> info.format
        'ogg'
        >>> info.duration
        33.00
        >>> info.video.codec
        'theora'
        >>> info.video.width
        720
        >>> info.video.height
        400
        >>> info.audio.codec
        'vorbis'
        >>> info.audio.channels
        2
        :param posters_as_video: Take poster images (mainly for audio files) as
            A video stream, defaults to True
        """

        if not os.path.exists(fname):
            return None

        info = MediaInfo(posters_as_video)

        p = self._spawn([self.avprobe_path,
                         '-show_format', '-show_streams', fname])
        stdout_data, _ = p.communicate()
        stdout_data = stdout_data.decode(console_encoding)
        info.parse_avprobe(stdout_data)

        if not info.format.format and len(info.streams) == 0:
            return None

        return info

    def convert(self, infile, outfile, opts, timeout=10):
        """
        Convert the source media (infile) according to specified options
        (a list of AvConv switches as strings) and save it to outfile.

        Convert returns a generator that needs to be iterated to drive the
        conversion process. The generator will periodically yield timecode
        of currently processed part of the file (ie. at which second in the
        content is the conversion process currently).

        The optional timeout argument specifies how long should the operation
        be blocked in case AvConv gets stuck and doesn't report back. See
        the documentation in Converter.convert() for more details about this
        option.

        >>> conv = AvConv().convert('test.ogg', '/tmp/output.mp3',
        ...    ['-acodec libmp3lame', '-vn'])
        >>> for timecode in conv:
        ...    pass # can be used to inform the user about conversion progress

        """
        if not os.path.exists(infile):
            raise AvConvError("Input file doesn't exist: " + infile)

        cmds = [self.avconv_path, '-i', infile]
        cmds.extend(opts)
        cmds.extend(['-y', outfile])

        if timeout:
            def on_sigalrm(*_):
                signal.signal(signal.SIGALRM, signal.SIG_DFL)
                raise Exception('timed out while waiting for AvConv')

            signal.signal(signal.SIGALRM, on_sigalrm)

        try:
            p = self._spawn(cmds)
        except OSError:
            raise AvConvError('Error while calling AvConv binary')

        yielded = False
        buf = ''
        total_output = ''
        pat = re.compile(r'time=([0-9.:]+) ')
        while True:
            if timeout:
                signal.alarm(timeout)

            ret = p.stderr.read(10)

            if timeout:
                signal.alarm(0)

            if not ret:
                break

            ret = ret.decode(console_encoding)
            total_output += ret
            buf += ret
            if '\r' in buf:
                line, buf = buf.split('\r', 1)

                tmp = pat.findall(line)
                if len(tmp) == 1:
                    timespec = tmp[0]
                    if ':' in timespec:
                        timecode = 0
                        for part in timespec.split(':'):
                            timecode = 60 * timecode + float(part)
                    else:
                        timecode = float(tmp[0])
                    yielded = True
                    yield timecode

        if timeout:
            signal.signal(signal.SIGALRM, signal.SIG_DFL)

        p.communicate()  # wait for process to exit

        if total_output == '':
            raise AvConvError('Error while calling AvConv binary')

        cmd = ' '.join(cmds)
        if '\n' in total_output:
            line = total_output.split('\n')[-2]

            if line.startswith('Received signal'):
                # Received signal 15: terminating.
                raise AvConvConvertError(line.split(':')[0], cmd, total_output, pid=p.pid)
            if line.startswith(infile + ': '):
                err = line[len(infile) + 2:]
                raise AvConvConvertError('Encoding error', cmd, total_output,
                                         err, pid=p.pid)
            if line.startswith('Error while '):
                raise AvConvConvertError('Encoding error', cmd, total_output,
                                         line, pid=p.pid)
            if not yielded:
                raise AvConvConvertError('Unknown AvConv error', cmd,
                                         total_output, line, pid=p.pid)
        if p.returncode != 0:
            raise AvConvConvertError('Exited with code %d' % p.returncode, cmd,
                                     total_output, pid=p.pid)

    def thumbnail(self, fname, time, outfile, size=None, quality=DEFAULT_JPEG_QUALITY):
        """
        Create a thumbnal of media file, and store it to outfile
        @param time: time point (in seconds) (float or int)
        @param size: Size, if specified, is WxH of the desired thumbnail.
            If not specified, the video resolution is used.
        @param quality: quality of jpeg file in range 2(best)-31(worst)
            recommended range: 2-6

        >>> AvConv().thumbnail('test1.ogg', 5, '/tmp/shot.png', '320x240')
        """
        return self.thumbnails(fname, [(time, outfile, size, quality)])

    def thumbnails(self, fname, option_list):
        """
        Create one or more thumbnails of video.
        @param option_list: a list of tuples like:
            (time, outfile, size=None, quality=DEFAULT_JPEG_QUALITY)
            see documentation of `converter.AvConv.thumbnail()` for details.

        >>> AvConv().thumbnails('test1.ogg', [(5, '/tmp/shot.png', '320x240'),
        >>>                                   (10, '/tmp/shot2.png', None, 5)])
        """
        if not os.path.exists(fname):
            raise IOError('No such file: ' + fname)

        cmds = [self.avconv_path, '-i', fname, '-y', '-an']
        for thumb in option_list:
            if len(thumb) > 2 and thumb[2]:
                cmds.extend(['-s', str(thumb[2])])

            cmds.extend([
                '-f', 'image2', '-vframes', '1',
                '-ss', str(thumb[0]), thumb[1],
                '-q:v', str(AvConv.DEFAULT_JPEG_QUALITY if len(thumb) < 4 else str(thumb[3])),
            ])

        p = self._spawn(cmds)
        _, stderr_data = p.communicate()
        if stderr_data == '':
            raise AvConvError('Error while calling AvConv binary')
        stderr_data.decode(console_encoding)
        if any(not os.path.exists(option[1]) for option in option_list):
            raise AvConvError('Error creating thumbnail: %s' % stderr_data)
