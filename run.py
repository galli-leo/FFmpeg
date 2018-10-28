import os
import sys
import requests
import logging
import subprocess
import json
import re

#################################
### CONFIG

LOG_LEVEL = logging.DEBUG
# Whether to automatically inject filter for hdr tonemapping. Note: This runs a small ffprobe beforehand, to know whether tonemapping is needed.
HDR_TONEMAPPING = True
# What codecs to actually run through ffmplex and patch the arguments. i.e. what codecs should be hardware decoded. NOTE: The codec needs to be selected here, for HDR tonemapping to work!
CODECS = ["hevc", "h264"]

### ADVANCED CONFIG

# Command used to probe for hdr.
FFPROBE_COMMAND = "-hide_banner -select_streams v:0 -show_entries \"stream=color_space,color_transfer,color_primaries,color_range,pix_fmt\" \"{0}\" -loglevel quiet -print_format json"

#################################

def plex_request(method, url):
    headers = {"X-Plex-Token" : os.environ["X_PLEX_TOKEN"]}
    return requests.request(method, url, headers=headers)

# Logging Setup

class PlexHandler(logging.Handler):
    def emit(self, record):
        level = record.levelno
        level = logging.ERROR if level > logging.ERROR else level
        level = (logging.ERROR - level) / 10
        plex_request("GET", "http://127.0.0.1:32400/log?level={0}&source=ffmplex&message={1}".format(level, record.message))

logFormatter = logging.Formatter("%(asctime)s |%(levelname)s| [%(filename)s:%(lineno)s - %(funcName)20s()] %(message)s")
logger = logging.getLogger("ffmplex")
logger.setLevel(LOG_LEVEL)

fileHandler = logging.FileHandler("ffmplex.log")
fileHandler.setFormatter(logFormatter)
logger.addHandler(fileHandler)

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)

plexHandler = PlexHandler()
plexHandler.setFormatter(logFormatter)
logger.addHandler(plexHandler)

class Filter(object):
    def __init__(self, filter, logger):
        super(Filter, self).__init__()
        self.filter = filter
        self.logger = logger
        self.parse()

    def parse(self):
        self.logger.debug("Parsing filter: %s", self.filter)
        split = self.filter.split("=")
        self.name = split[0]
        self.args = {}
        if len(split) > 1:
            args = "=".join(split[1:])
            arg_split = args.split(":")
            for arg in arg_split:
                split_again = arg.split("=")
                arg_name = split_again[0]
                arg_value = None
                if len(split_again) > 1:
                    arg_value = split_again[1]
                self.args[arg_name] = arg_value

    def __str__(self):
        s = "{0}(".format(self.name)
        s += ",".join(["{0}={1}".format(key, self.args[key]) for key in self.args])
        s += ")"
        return s


class ComplexFilter(object):
    INPUT_REGEX = r"(\[.*?\])(.*)"
    OUTPUT_REGEX = r"(.*)(\[.*?\])"

    def __init__(self, filter, logger):
        super(ComplexFilter, self).__init__()
        self.filter = filter
        self.logger = logger
        self.parse()

    def parse(self):
        self.logger.debug("Parsing complex filter: %s", self.filter)
        self.graph = []
        self.input = None
        self.output = None
        # first see if there are subfilters
        split = self.filter.split(";")
        if len(split) > 1:
            for subfilter in split:
                self.graph.append(ComplexFilter(subfilter, self.logger))
        else:
            # get inputs
            match = re.search(ComplexFilter.INPUT_REGEX, self.filter)
            self.input = match.group(1)
            self.filter = match.group(2)
            print(self.input, self.filter)
            match = re.search(ComplexFilter.OUTPUT_REGEX, self.filter)
            self.output = match.group(2)
            self.filter = match.group(1)

            filters = self.filter.split(",")
            for filter in filters:
                self.graph.append(Filter(filter, self.logger))


    def __str__(self):
        s = ""
        if self.input is not None:
            s += self.input + " -> "

        s += " -> ".join([x.__str__() for x in self.graph])

        if self.output is not None:
            s += " -> " + self.output

        return s


class StreamSpecifier(object):
    STREAM_TYPES = {
        "v" : "Video",
        "a" : "Audio",
        "s" : "Subtitle",
        "d" : "Data",
        "t" : "Attachements"
    }

    def __init__(self, stream, logger):
        super(StreamSpecifier, self).__init__()
        self.stream = stream
        self.logger = logger
        self.parse()

    def parse(self):
        self.logger.debug("Parsing stream specifier: %s", self.stream)
        self.stream_type = None
        self.stream_index = None
        first = self.stream[0]
        if first in StreamSpecifier.STREAM_TYPES:
            self.stream_type = first
            if len(self.stream) > 1:
                self.stream_index = self.stream[1]
        else:
            self.stream_index = first

    def __str__(self):
        str = ""
        if self.stream_type is not None:
            str += StreamSpecifier.STREAM_TYPES[self.stream_type]
        if self.stream_index is not None:
            str += "#{0}".format(self.stream_index)

        return str

    def __repr__(self):
        return self.__str__()

class MetadataSpecifier(object):
    def __init__(self, specifier, logger):
        super(MetadataSpecifier, self).__init__()
        self.specifier = specifier
        self.logger = logger
        self.parse()

    def parse(self):
        self.logger.debug("Parsing metadata specifier: %s", self.specifier)
        first = self.specifier[0]
        if first == "s":
            self.stream_specifier = StreamSpecifier(self.specifier[1:], self.logger)

    def __str__(self):
        return "s:{0}".format(self.stream_specifier)

    def __repr__(self):
        return self.__str__()

class KeywordArgument(object):
    def __init__(self, keyword, arg, logger):
        super(KeywordArgument, self).__init__()
        self.keyword = keyword
        self.arg = arg
        self.logger = logger
        self.parse()

    def parse(self):
        self.logger.debug("Parsing additional info for keyword: %s:%s", self.keyword, self.arg)
        key = self.keyword[1:]
        split = key.split(':')
        if len(split) > 1:
            self.key = split[0]
            self.specifier = self.parse_specifier(split[1:])
        else:
            self.key, self.specifier = split[0], None

        if self.key == "filter_complex":
            self.arg = ComplexFilter(self.arg, self.logger)

    def parse_specifier(self, stream):
        if self.key == "metadata":
            return MetadataSpecifier(stream, self.logger)
        return StreamSpecifier(stream, self.logger)

    def __str__(self):
        if self.specifier:
            return "{0}[{2}]:{1}".format(self.key, self.arg, self.specifier)
        return "{0}:{1}".format(self.key, self.arg)

    def __repr__(self):
        return self.__str__()


class TranscoderArgumentParser(object):
    """docstring for TranscoderArgumentParser."""
    def __init__(self, args, logger):
        super(TranscoderArgumentParser, self).__init__()
        self.args = args
        self.logger = logger
        self.parse()

    def parse(self):
        self.logger.debug("Parsing arguments for transcoder: %s", self.args)
        # first we clean up the args
        cleaned_args = []
        for arg in self.args:
            if arg[0:1] == "'":
                cleaned_args.append(arg[1:len(arg)-1])
            elif arg != "\\":
                cleaned_args.append(arg)
        self.parsed_args = []
        position = 0
        while position < len(cleaned_args):
            arg = cleaned_args[position]
            self.logger.debug("Current arg %s", arg)
            next_arg = None
            if position < len(cleaned_args)-1:
                next_arg = cleaned_args[position+1]
                self.logger.debug("Next arg %s", next_arg)
            # keyword argument
            if arg[0:1] == "-":
                # next arg is param for keyword
                if next_arg is not None and next_arg[0:1] != "-":
                    position += 1
                    self.parsed_args.append(KeywordArgument(arg, next_arg, self.logger))
                else:
                    self.parsed_args.append(KeywordArgument(arg, None, self.logger))
            else:
                self.logger.warning("Unrecognized argument: %s", arg)
            position += 1

        self.logger.info("Parsed arguments for transcoder: %s", self.parsed_args)

    def get_input(self):
        ret = []
        for arg in self.parsed_args:
            if arg.key == "i":
                ret.append(arg.arg)
        return ret

    def get_input_codecs(self):
        ret = []
        for arg in self.parsed_args:
            if arg.key == "codec":
                ret.append(arg)
            # Came across input file, codecs are going to be for output afterwards
            if arg.key == "i":
                return ret

    def get_output_codecs(self):
        ret = []
        i_came = False
        for arg in self.parsed_args:
            if i_came and arg.key == "codec":
                ret.append(arg)
            # Came across input file, codecs are going to be for output afterwards
            if arg.key == "i":
                i_came = True
        return ret

def color_info(file):
    global FFPROBE_COMMAND, logger
    logger.info("Running ffprobe on %s", file)
    output = subprocess.check_output("ffprobe " + FFPROBE_COMMAND.format(file), shell=True)
    info = json.loads(output)
    logger.info("ffprobe returned %s", info)
    return info["streams"][0]

def add_hdr_tonemapping(parser):
    global logger
    logger.info("Adding HDR tonemapping filter")
    input_file = parser.get_input()[0]
    colors = color_info(input_file)
    color_space = colors["color_space"]
    if color_space != "bt2020":
        logger.info("File is not actually HDR, not adding tonemapping filter")
        return parser
    return parser

args = sys.argv[1:]
env = os.environ.copy()

parser = TranscoderArgumentParser(args, logger)
input_codecs = parser.get_input_codecs()
output_codecs = parser.get_output_codecs()
print(input_codecs, output_codecs)

if HDR_TONEMAPPING:
    parser = add_hdr_tonemapping(parser)