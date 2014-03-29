#!/usr/bin/env python

# modify the path so that parent directory is in it
import sys

sys.path.append('../')

import random
import string
import shutil
import unittest
import os
from os.path import join as pjoin

from converter import ffmpeg, formats, avcodecs, Converter, ConverterError


def verify_progress(p):
    if not p:
        return False

    li = list(p)
    if len(li) < 1:
        return False

    prev = 0
    for i in li:
        if type(i) != int or i < 0 or i > 100:
            return False
        if i < prev:
            return False
        prev = i
    return True


class TestFFMpeg(unittest.TestCase):
    def setUp(self):
        current_dir = os.path.abspath(os.path.dirname(__file__))
        temp_name = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(20))

        self.temp_dir = pjoin(current_dir, temp_name)

        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

        self.video_file_path = pjoin(self.temp_dir, 'output.ogg')
        self.audio_file_path = pjoin(self.temp_dir, 'output.mp3')
        self.shot_file_path = pjoin(self.temp_dir, 'shot.png')
        self.shot2_file_path = pjoin(self.temp_dir, 'shot2.png')
        self.shot3_file_path = pjoin(self.temp_dir, 'shot3.png')

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def assertRaisesSpecific(self, exception, fn, *args, **kwargs):
        try:
            fn(*args, **kwargs)
            raise Exception('Expected exception %s not raised' % repr(exception))
        except exception:
            ex = sys.exc_info()[1]
            return ex

    @staticmethod
    def ensure_notexist(f):
        if os.path.exists(f):
            os.unlink(f)

    def test_ffmpeg_probe(self):
        self.assertRaisesSpecific(ffmpeg.FFMpegError, ffmpeg.FFMpeg,
                                  ffmpeg_path='/foo', ffprobe_path='/bar')

        f = ffmpeg.FFMpeg()

        self.assertEqual(None, f.probe('nonexistent'))
        self.assertEqual(None, f.probe('/dev/null'))

        info = f.probe('test1.ogg')
        self.assertEqual('ogg', info.format.format)
        self.assertAlmostEqual(33.00, info.format.duration, places=2)
        self.assertEqual(2, len(info.streams))

        v = info.streams[0]
        self.assertEqual(v, info.video)
        self.assertEqual('video', v.type)
        self.assertEqual('theora', v.codec)
        self.assertEqual(720, v.video_width)
        self.assertEqual(400, v.video_height)
        self.assertEqual(None, v.bitrate)
        self.assertAlmostEqual(25.00, v.video_fps, places=2)
        self.assertEqual(v.metadata['ENCODER'], 'ffmpeg2theora 0.19')

        a = info.streams[1]
        self.assertEqual(a, info.audio)
        self.assertEqual('audio', a.type)
        self.assertEqual('vorbis', a.codec)
        self.assertEqual(2, a.audio_channels)
        self.assertEqual(80000, a.bitrate)
        self.assertEqual(48000, a.audio_samplerate)
        self.assertEqual(a.metadata['ENCODER'], 'ffmpeg2theora 0.19')

        self.assertEqual(repr(info), 'MediaInfo(format='
                                     'MediaFormatInfo(format=ogg, duration=33.00), streams=['
                                     'MediaStreamInfo(type=video, codec=theora, width=720, '
                                     'height=400, fps=25.0, ENCODER=ffmpeg2theora 0.19), '
                                     'MediaStreamInfo(type=audio, codec=vorbis, channels=2, rate=48000, '
                                     'bitrate=80000, ENCODER=ffmpeg2theora 0.19)])')

    def test_ffmpeg_convert(self):
        f = ffmpeg.FFMpeg()

        def consume(fn, *args, **kwargs):
            return list(fn(*args, **kwargs))

        self.assertRaisesSpecific(ffmpeg.FFMpegError, consume,
                                  f.convert, 'nonexistent', self.video_file_path, [])

        self.assertRaisesSpecific(ffmpeg.FFMpegConvertError, consume,
                                  f.convert, '/etc/passwd', self.video_file_path, [])

        info = f.probe('test1.ogg')

        convert_options = [
            '-acodec', 'libvorbis', '-ab', '16k', '-ac', '1', '-ar', '11025',
            '-vcodec', 'libtheora', '-r', '15', '-s', '360x200', '-b', '128k']
        conv = f.convert('test1.ogg', self.video_file_path, convert_options)

        last_tc = 0.0
        for tc in conv:
            assert (last_tc < tc <= info.format.duration + 0.1), (last_tc, tc, info.format.duration)

        self._assert_converted_video_file()

    def _assert_converted_video_file(self):
        """
            Asserts converted test1.ogg (in path self.video_file_path) is converted correctly
        """
        f = ffmpeg.FFMpeg()
        info = f.probe(self.video_file_path)
        self.assertEqual('ogg', info.format.format)
        self.assertAlmostEqual(33.00, info.format.duration, places=0)
        self.assertEqual(2, len(info.streams))

        self.assertEqual('video', info.video.type)
        self.assertEqual('theora', info.video.codec)
        self.assertEqual(360, info.video.video_width)
        self.assertEqual(200, info.video.video_height)
        self.assertAlmostEqual(15.00, info.video.video_fps, places=2)

        self.assertEqual('audio', info.audio.type)
        self.assertEqual('vorbis', info.audio.codec)
        self.assertEqual(1, info.audio.audio_channels)
        self.assertEqual(11025, info.audio.audio_samplerate)

    def test_ffmpeg_termination(self):
        # test when ffmpeg is killed
        f = ffmpeg.FFMpeg()
        convert_options = [
            '-acodec', 'libvorbis', '-ab', '16k', '-ac', '1', '-ar', '11025',
            '-vcodec', 'libtheora', '-r', '15', '-s', '360x200', '-b', '128k']
        p_list = {}  # modifiable object in closure
        f._spawn = lambda *args: p_list.setdefault('', ffmpeg.FFMpeg._spawn(*args))
        conv = f.convert('test1.ogg', self.video_file_path, convert_options)
        next(conv)  # let ffmpeg to start
        p = p_list['']
        p.terminate()
        self.assertRaisesSpecific(ffmpeg.FFMpegConvertError, list, conv)

    def test_ffmpeg_thumbnail(self):
        f = ffmpeg.FFMpeg()
        thumb = self.shot_file_path
        thumb2 = self.shot2_file_path

        self.assertRaisesSpecific(IOError, f.thumbnail, 'nonexistent', 10, thumb)

        self.ensure_notexist(thumb)
        f.thumbnail('test1.ogg', 10, thumb)
        self.assertTrue(os.path.exists(thumb))

        self.ensure_notexist(thumb)
        self.assertRaisesSpecific(ffmpeg.FFMpegError, f.thumbnail, 'test1.ogg', 34, thumb)
        self.assertFalse(os.path.exists(thumb))

        # test multiple thumbnail
        self.ensure_notexist(thumb)
        self.ensure_notexist(thumb2)
        f.thumbnails('test1.ogg', [
            (5, thumb),
            (10, thumb2, None, 5),  # set quality
            (5, self.shot3_file_path, '320x240'),  # set size
        ])
        self.assertTrue(os.path.exists(thumb))
        self.assertTrue(os.path.exists(thumb2))
        self.assertTrue(os.path.exists(self.shot3_file_path))

    def test_formats(self):
        c = formats.BaseFormat()
        self.assertRaisesSpecific(ValueError, c.parse_options, {})
        self.assertEqual(['-f', 'ogg'], formats.OggFormat().parse_options({'format': 'ogg'}))

    def test_avcodecs(self):
        c = avcodecs.BaseCodec()
        self.assertRaisesSpecific(ValueError, c.parse_options, {})

        c.encoder_options = {'foo': int, 'bar': bool}
        self.assertEqual({}, c.safe_options({'baz': 1, 'quux': 1, 'foo': 'w00t'}))
        self.assertEqual({'foo': 42, 'bar': False}, c.safe_options({'foo': '42', 'bar': 0}))

        c = avcodecs.AudioCodec()
        c.codec_name = 'doctest'
        c.ffmpeg_codec_name = 'doctest'

        self.assertEqual(['-acodec', 'doctest'],
                         c.parse_options({'codec': 'doctest', 'channels': 0, 'bitrate': 0, 'samplerate': 0}))

        self.assertEqual(['-acodec', 'doctest', '-ac', '1', '-ab', '64k', '-ar', '44100'],
                         c.parse_options({'codec': 'doctest', 'channels': '1', 'bitrate': '64', 'samplerate': '44100'}))

        c = avcodecs.VideoCodec()
        c.codec_name = 'doctest'
        c.ffmpeg_codec_name = 'doctest'

        self.assertEqual(['-vcodec', 'doctest'],
                         c.parse_options({'codec': 'doctest', 'fps': 0, 'bitrate': 0, 'width': 0, 'height': '480'}))

        self.assertEqual(['-vcodec', 'doctest', '-r', '25', '-vb', '300k', '-s', '320x240', '-aspect', '320:240'],
                         c.parse_options(
                             {'codec': 'doctest', 'fps': '25', 'bitrate': '300', 'width': 320, 'height': 240}))

        self.assertEqual(['-vcodec', 'doctest', '-s', '384x240', '-aspect', '320:240', '-vf', 'crop=320:240:32:0'],
                         c.parse_options({'codec': 'doctest', 'src_width': 640, 'src_height': 400, 'mode': 'crop',
                                          'width': 320, 'height': 240}))

        self.assertEqual(['-vcodec', 'doctest', '-s', '320x240', '-aspect', '320:200', '-vf', 'crop=320:200:0:20'],
                         c.parse_options({'codec': 'doctest', 'src_width': 640, 'src_height': 480, 'mode': 'crop',
                                          'width': 320, 'height': 200}))

        self.assertEqual(['-vcodec', 'doctest', '-s', '320x200', '-aspect', '320:240', '-vf', 'pad=320:240:0:20'],
                         c.parse_options({'codec': 'doctest', 'src_width': 640, 'src_height': 400, 'mode': 'pad',
                                          'width': 320, 'height': 240}))

        self.assertEqual(['-vcodec', 'doctest', '-s', '266x200', '-aspect', '320:200', '-vf', 'pad=320:200:27:0'],
                         c.parse_options({'codec': 'doctest', 'src_width': 640, 'src_height': 480, 'mode': 'pad',
                                          'width': 320, 'height': 200}))

        self.assertEqual(['-vcodec', 'doctest', '-s', '320x240'],
                         c.parse_options({'codec': 'doctest', 'src_width': 640, 'src_height': 480, 'width': 320}))

        self.assertEqual(['-vcodec', 'doctest', '-s', '320x240'],
                         c.parse_options({'codec': 'doctest', 'src_width': 640, 'src_height': 480, 'height': 240}))

    def test_converter(self):
        c = Converter()

        self.assertRaisesSpecific(ConverterError, c.parse_options, None)
        self.assertRaisesSpecific(ConverterError, c.parse_options, {})
        self.assertRaisesSpecific(ConverterError, c.parse_options, {'format': 'foo'})

        self.assertRaisesSpecific(ConverterError, c.parse_options, {'format': 'ogg'})
        self.assertRaisesSpecific(ConverterError, c.parse_options, {'format': 'ogg', 'video': 'whatever'})
        self.assertRaisesSpecific(ConverterError, c.parse_options, {'format': 'ogg', 'audio': {}})
        self.assertRaisesSpecific(ConverterError, c.parse_options,
                                  {'format': 'ogg', 'audio': {'codec': 'bogus'}})

        self.assertEqual(['-an', '-vcodec', 'libtheora', '-r', '25', '-sn', '-f', 'ogg'],
                         c.parse_options({'format': 'ogg', 'video': {'codec': 'theora', 'fps': 25}}))
        self.assertEqual(['-acodec', 'copy', '-vcodec', 'copy', '-sn', '-f', 'ogg'],
                         c.parse_options({'format': 'ogg', 'audio': {'codec': 'copy'}, 'video': {'codec': 'copy'}, 'subtitle': {'codec': None}}))

        info = c.probe('test1.ogg')
        self.assertEqual('theora', info.video.codec)
        self.assertEqual(720, info.video.video_width)
        self.assertEqual(400, info.video.video_height)

        f = self.shot_file_path

        self.ensure_notexist(f)
        c.thumbnail('test1.ogg', 10, f)
        self.assertTrue(os.path.exists(f))
        os.unlink(f)

        conv = c.convert('test1.ogg', self.video_file_path, {
            'format': 'ogg',
            'video': {
                'codec': 'theora', 'width': 160, 'height': 120, 'fps': 15, 'bitrate': 300},
            'audio': {
                'codec': 'vorbis', 'channels': 1, 'bitrate': 32}
        })

        self.assertTrue(verify_progress(conv))

        conv = c.convert('test.aac', self.audio_file_path, {
            'format': 'mp3',
            'audio': {
                'codec': 'mp3', 'channels': 1, 'bitrate': 32}
        })

        self.assertTrue(verify_progress(conv))

    def test_converter_2pass(self):
        c = Converter()
        self.video_file_path = 'xx.ogg'
        options = {
            'format': 'ogg',
            'audio': {'codec': 'vorbis', 'samplerate': 11025, 'channels': 1, 'bitrate': 16},
            'video': {'codec': 'theora', 'bitrate': 128, 'width': 360, 'height': 200, 'fps': 15}
        }
        options_repr = repr(options)
        conv = c.convert('test1.ogg', self.video_file_path, options, twopass=True)

        verify_progress(conv)

        # Convert should not change options dict
        self.assertEqual(options_repr, repr(options))

        self._assert_converted_video_file()

    def test_converter_vp8_codec(self):
        c = Converter()
        conv = c.convert('test1.ogg', self.video_file_path, {
            'format': 'webm',
            'video': {
                'codec': 'vp8', 'width': 160, 'height': 120, 'fps': 15, 'bitrate': 300},
            'audio': {
                'codec': 'vorbis', 'channels': 1, 'bitrate': 32}
        })

        self.assertTrue(verify_progress(conv))

    def test_probe_audio_poster(self):
        c = Converter()

        info = c.probe('test.mp3', posters_as_video=True)
        self.assertNotEqual(None, info.video)
        self.assertEqual(info.video.attached_pic, 1)

        info = c.probe('test.mp3', posters_as_video=False)
        self.assertEqual(None, info.video)
        self.assertEqual(len(info.posters), 1)
        poster = info.posters[0]
        self.assertEqual(poster.type, 'video')
        self.assertEqual(poster.codec, 'png')
        self.assertEqual(poster.video_width, 32)
        self.assertEqual(poster.video_height, 32)
        self.assertEqual(poster.attached_pic, 1)


if __name__ == '__main__':
    unittest.main()
