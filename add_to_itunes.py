#!/usr/bin/env python
import os, re, subprocess, sys
from xml.etree import ElementTree

HANDBRAKE_PRESET = 'AppleTV 2'

def extract_metadata(source_filepath):
    extensionless = '.'.join(source.split('.')[:-1])
    nfo = extensionless + ".nfo"

    # the show name comes from the folder name
    srcdir = os.path.dirname(source_filepath)
    show = os.path.basename(srcdir)

    season = episode = title = plot = None
    if os.path.exists(nfo):
        epi = ElementTree.parse(open(nfo))
        if 'xbmcmultiepisode' in epi.getroot().tag:
            epi = epi.find("episodedetails")
        season = epi.findtext("season")
        episode = epi.findtext("episode")
        title = epi.findtext("title")
        plot = epi.findtext("plot")
        if season is None or episode is None or title is None or plot is None:
            print >> sys.stderr, ".nfo Missing item: %s %s %s" % (season, episode, title)
    else:
        print >> sys.stderr, "No .nfo, trying to extract from title"
        m = re.match(".* - (\d+)x(\d+) - (.*)\.[\w\d]{3}", source_filepath)
        if m:
            season, episode, title = m.groups()
        else:
            print >> sys.stderr, "Couldn't match", source_filepath

    return show, season, episode, title, plot

def set_metadata(filepath, show, season, episode, title, plot):
    command = ["AtomicParsley",  filepath, "--stik", 'TV Show', "--TVShowName", show]
    for flag, value in [("--TVSeasonNum", season), ("--TVEpisodeNum", episode), ("--TVEpisode", title),
                        ("--title", title), ("--description", plot)]:
        if value is not None:
            command.append(flag)
            command.append(value)

    print >> sys.stderr, command
    subprocess.check_call(command)

    # get rid of the temp file left behind by AtomicParsley
    srcdir = os.path.dirname(filepath)
    tmp = [i for i in os.listdir(srcdir) if "-temp" in i]
    assert len(tmp) == 1
    os.rename(srcdir + "/" + tmp[0], filepath)

def add_to_itunes(source_filepath):
    add_failed = os.system("""osascript << EOF
    tell application "iTunes"
        launch
        with timeout of 30000 seconds
            set new_track to add ("%s" as POSIX file)
            log new_track   # raises error if the add() failed
        end timeout
    end tell
    EOF """ % (source_filepath,))

    if add_failed: raise Exception("Unable to add to iTunes: %s" % (source_filepath,))

def encode_video(source_filepath, is_retag=False, handbrake_preset=HANDBRAKE_PRESET):
    extensionless = '.'.join(source.split('.')[:-1])
    destination_filepath = extensionless + '.m4v'

    if not os.path.exists(destination_filepath):
        command = ["HandBrakeCLI", "-i", source, "-o", destination_filepath, "--preset", HANDBRAKE_PRESET]
        print >> sys.stderr, command
        subprocess.check_call(command)
        return destination_filepath

    elif not is_retag:
        print "Output already exists at", destination_filepath
        sys.exit(0)
    else:
        print >> sys.stderr, "Retagging", destination_filepath
        return source_filepath


if __name__ == '__main__':
    retag = sys.argv[1] == "retag"
    if retag:
        del sys.argv[1]
    source = os.path.abspath(sys.argv[1])

    # extract metadata for this file
    metadata = extract_metadata(source)

    try:
        # attempt to set the metadata and add the file to iTunes; it might succeed and then we don't need to go any further
        set_metadata(source, *metadata)
        add_to_itunes(source)

    except Exception as e:
        print >> sys.stderr, "Could not add file automatically, must convert with HandBrake first..."
        print >> sys.stderr, e

        # encode the file in our desired format, and then try to add the file again
        source = encode_video(source)
        set_metadata(source, *metadata)
        add_to_itunes(source)
