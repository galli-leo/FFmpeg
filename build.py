import os
import requests
import subprocess

def download_file(url, local_filename):
    # NOTE the stream=True parameter
    r = requests.get(url, stream=True)
    with open(local_filename, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk: # filter out keep-alive new chunks
                f.write(chunk)
                #f.flush() commented by recommendation from J.F.Sebastian
    return local_filename

external_libs = [
    "h264_decoder", "aac_decoder", "ac3_decoder", "libx264_encoder",
    "mpeg2video_decoder", "hevc_decoder", "dca_decoder", "aac_encoder",
    "ac3_encoder", "mp3_decoder", "mpeg4_decoder", "msmpeg4v3_decoder",
    "vc1_decoder"
]

import platform
def get_os_values():
    os_name = platform.system()
    if os_name == "Darwin":
        return ("darwin-x86_64", "dylib")
    if os_name == "Linux":
        return ("linux-ubuntu-x86_64", "so")

codecs_version = "e944d3a-1309"
CODEC_URL = "https://downloads.plex.tv/codecs/"
CODEC_FOLDER = "plex_libs"

configure_flags = "--libdir='{0}' --prefix='{1}' --disable-bzlib --disable-ffplay --disable-ffprobe --disable-avdevice --disable-schannel --disable-linux-perf --disable-mediacodec --disable-debug --disable-doc --disable-shared --pkg-config-flags=--static --enable-muxers --enable-gpl --enable-version3 --enable-gnutls --enable-eae --disable-encoders --disable-decoders --disable-hwaccels --enable-libass --disable-devices --disable-lzma --disable-iconv --disable-protocol=concat --enable-libvorbis --enable-libopus --enable-libx264 --disable-bsfs --enable-bsf='aac_adtstoasc,extract_extradata,dca_core,h264_mp4toannexb,hevc_mp4toannexb,vp9_superframe,vp9_superframe_split,framedrop' --enable-decoder=png --enable-decoder=apng --enable-decoder=bmp --enable-decoder=mjpeg --enable-decoder=thp --enable-decoder=gif --enable-decoder=dirac --enable-decoder=ffv1 --enable-decoder=ffvhuff --enable-decoder=huffyuv --enable-decoder=rawvideo --enable-decoder=zero12v --enable-decoder=ayuv --enable-decoder=r210 --enable-decoder=v210 --enable-decoder=v210x --enable-decoder=v308 --enable-decoder=v408 --enable-decoder=v410 --enable-decoder=y41p --enable-decoder=yuv4 --enable-decoder=ansi --enable-decoder=alac --enable-decoder=flac --enable-decoder=vorbis --enable-decoder=opus --enable-decoder=pcm_f32be --enable-decoder=pcm_f32le --enable-decoder=pcm_f64be --enable-decoder=pcm_f64le --enable-decoder=pcm_lxf --enable-decoder=pcm_s16be --enable-decoder=pcm_s16be_planar --enable-decoder=pcm_s16le --enable-decoder=pcm_s16le_planar --enable-decoder=pcm_s24be --enable-decoder=pcm_s24le --enable-decoder=pcm_s24le_planar --enable-decoder=pcm_s32be --enable-decoder=pcm_s32le --enable-decoder=pcm_s32le_planar --enable-decoder=pcm_s8 --enable-decoder=pcm_s8_planar --enable-decoder=pcm_u16be --enable-decoder=pcm_u16le --enable-decoder=pcm_u24be--enable-decoder=pcm_u24le --enable-decoder=pcm_u32be --enable-decoder=pcm_u32le --enable-decoder=pcm_u8 --enable-decoder=pcm_alaw --enable-decoder=pcm_mulaw --enable-decoder=ass --enable-decoder=dvbsub --enable-decoder=dvdsub --enable-decoder=ccaption --enable-decoder=pgssub --enable-decoder=jacosub --enable-decoder=microdvd --enable-decoder=movtext --enable-decoder=mpl2 --enable-decoder=pjs --enable-decoder=realtext --enable-decoder=sami --enable-decoder=ssa --enable-decoder=stl --enable-decoder=subrip --enable-decoder=subviewer --enable-decoder=text --enable-decoder=vplayer --enable-decoder=webvtt --enable-decoder=xsub  --enable-decoder=eac3_at --enable-decoder=eac3_eae --enable-decoder=truehd_eae --enable-decoder=mlp_eae --enable-encoder=flac --enable-encoder=alac--enable-encoder=libvorbis --enable-encoder=libopus --enable-encoder=mjpeg --enable-encoder=wrapped_avframe --enable-encoder=ass --enable-encoder=dvbsub --enable-encoder=dvdsub --enable-encoder=movtext --enable-encoder=ssa --enable-encoder=subrip --enable-encoder=text --enable-encoder=webvtt --enable-encoder=xsub --enable-encoder=pcm_f32be --enable-encoder=pcm_f32le --enable-encoder=pcm_f64be --enable-encoder=pcm_f64le --enable-encoder=pcm_s8 --enable-encoder=pcm_s8_planar --enable-encoder=pcm_s16be --enable-encoder=pcm_s16be_planar --enable-encoder=pcm_s16le --enable-encoder=pcm_s16le_planar --enable-encoder=pcm_s24be --enable-encoder=pcm_s24le --enable-encoder=pcm_s24le_planar --enable-encoder=pcm_s32be --enable-encoder=pcm_s32le --enable-encoder=pcm_s32le_planar --enable-encoder=pcm_u8 --enable-encoder=pcm_u16be --enable-encoder=pcm_u16le --enable-encoder=pcm_u24be --enable-encoder=pcm_u24le --enable-encoder=pcm_u32be --enable-encoder=pcm_u32le --enable-encoder=aac_at --enable-encoder=h264_videotoolbox --enable-encoder=eac3_eae --arch=x86_64 --cc='ccache clang' --extra-ldflags='-L{0} -Wl,-framework -Wl,CoreFoundation' --extra-libs='-lgcrypt -lgpg-error'"

PREFIX = os.path.abspath("build")
LIB_DIR = os.path.abspath(CODEC_FOLDER)

def download_codec(codec, os_name, version, extension):
    global CODEC_URL, CODEC_FOLDER
    codec_file = "lib"+codec+"."+extension
    url = "{0}{1}/{2}/{3}".format(CODEC_URL, version, os_name, codec_file)
    codec_path = os.path.join(CODEC_FOLDER, codec_file)
    print("[*] Downloading codec {0}, from {1} to {2}".format(codec, url, codec_path))
    if os.path.exists(codec_path):
        print("[*] Already downloaded codec at: {0}".format(codec_path))
        return
    download_file(url, codec_path)

def download_codecs(codecs = []):
    global codecs_version
    codecs_os, extension = get_os_values()
    print("Downloading {0} codecs...".format(len(codecs)))
    for codec in codecs:
        download_codec(codec, codecs_os, codecs_version, extension)

def configure(codecs, flags):
    global PREFIX, LIB_DIR
    ext_libs = []
    for codec in codecs:
        name, type = codec.split("_")
        print("[*] Appending {0} as external {1} to configure args".format(name, type))
        ext_libs.append("--external-{0}={1}".format(type, name))
    configure_args = flags.format(LIB_DIR, PREFIX)
    configure_args += " " + " ".join(ext_libs)
    print("[*] Running configure with the following arguments: {0}".format(configure_args))
    subprocess.check_output("./configure "+configure_args, shell=True)

def make():
    print("[*] Running make")
    subprocess.check_output("make -j8", shell=True)
    print("[*] Running make install")
    subprocess.check_output("make install", shell=True)

def make_install(codecs = []):
    print("[*] Running make install for all codecs")
    for codec in codecs:
        subprocess.check_output("make install-{0}".format(codec), shell=True)


download_codecs(external_libs)
configure(external_libs, configure_flags)
make()
make_install(external_libs)

print("[!] Success! You should now have a new shiny ffmpeg binary at: {0}/bin/ffmpeg".format(PREFIX))

