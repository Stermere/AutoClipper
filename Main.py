# starts the program and have it either combine exiting clips, make new ones, or render a video

import sys
from src.VideoMaker import VideoMaker
from src.YoutubeUploader import YoutubeUploader
import asyncio
import json
import os
import time

with open('config.json') as f:
    config = json.load(f)

DEFAULT_CLIP_DIR = config['DEFAULT_CLIP_DIR']
HELP_MENU = 'Usage: python3 Main.py <task>\n\
                <task> can be one of the following:\n\
                -v render a video\n\
                -mv schedule multiple short videos\n\
                -r register with the youtube api\n\
                -clean delete all clips in the clip directory\n\
                --h: help menu (this menu)'

def main():
    # help menu
    if len(sys.argv) == 1:
        print(HELP_MENU)
        exit(0)

    # make a clip compilation
    if sys.argv[1] == '-v':
        # check for the second arg for the streamer name
        if len(sys.argv) < 3:
            print('Usage: python3 Main.py -v streamer_name <target_stream>')
            exit(0)
        # check for the third arg of the target stream
        vods_back = 0
        if len(sys.argv) >= 4:
            vods_back = int(sys.argv[3])  
        asyncio.run(VideoMaker.make_from_channel(sys.argv[2], vods_back=vods_back))

    # make many short videos and schedule them to be posted
    elif sys.argv[1] == '-mv':
        if len(sys.argv) < 5:
            print('Usage: python3 Main.py -mv num_videos days_back streamer_names')
            exit(0)

        num_videos = int(sys.argv[2])
        days_back = int(sys.argv[3])
        streamer_names = sys.argv[4:]

        asyncio.run(VideoMaker.make_from_top_clips(streamer_names, num_videos, days_back))
        
    # delete all clips in the clip directory
    elif sys.argv[1] == '-clean':
        clips = os.listdir(DEFAULT_CLIP_DIR)
        for clip in clips:
            os.remove(os.path.join(DEFAULT_CLIP_DIR, clip))

    # register with the youtube api
    elif sys.argv[1] == '-r':
        os.remove('credentials.json')
        sys.argv = sys.argv[:0]
        uploader = YoutubeUploader()

    else:
        print(HELP_MENU)


if __name__ == '__main__':
    main()