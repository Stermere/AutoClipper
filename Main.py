# starts the program and have it either combine exiting clips, make new ones, or render a video

import sys
from src.ChatClassifier import main as chat_classifier
from src.VideoMaker import VideoMaker
from src.ClipCompiler import ClipCompiler
import asyncio
import json
import os
import time

# TODO add a mode to run on start up and continuously make videos scheduling them to be posted once every 8 hours
# TODO remove the old cliping and chat logging code
# TODO test the clip compiler on synthetic data and real data

with open('config.json') as f:
    config = json.load(f)

DEFAULT_CLIP_DIR = config['DEFAULT_CLIP_DIR']
DEFAULT_CLIP_INFO_DIR = config['DEFAULT_CLIP_INFO_DIR']

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] == '-h' or sys.argv[1] == '--help':
        print('Usage: python3 Main.py <task>\n <task> can be one of the following:\n-l: lurk chat\n-v render a video\n-c combine clips\n--h: help menu (this menu)')
        exit(0)
    
    if sys.argv[1] == '-l':
        chat_classifier(sys.argv)

    elif sys.argv[1] == '-v':
        # check for the second arg of the directory of the clips
        if len(sys.argv) < 3:
            print('Usage: python3 Main.py -v clip_info_dir')
            exit(0)
        if sys.argv[2].endswith('.csv'):
            asyncio.run(VideoMaker.make_from_csv(sys.argv[2]))
        else:
            # check for the third arg of the time
            if len(sys.argv) < 4:
                print('Usage: python3 Main.py -v channel_name streams to include')
                exit(0)
            if len(sys.argv) < 5:
                vods_back = 0
            else:
                vods_back = int(sys.argv[4])
            
            asyncio.run(VideoMaker.make_from_channel(sys.argv[2], rest_time=int(sys.argv[3]), vods_back=vods_back))

    elif sys.argv[1] == '-c':
        # check for the second arg of the csv file specifying the clips
        if len(sys.argv) < 3 or  not sys.argv[2].endswith('.csv'):
            print('Usage: python3 Main.py -c <csv_file_dir>')
            exit(0)
        ClipCompiler().merge_clips(sys.argv[2])


    elif sys.argv[1] == '-clean':
        for i in range(5, 0, -1):
            print('Cleaning up in {} seconds'.format(i))
            time.sleep(1)
        clips = os.listdir(DEFAULT_CLIP_DIR)

        for clip in clips:
            os.remove(os.path.join(DEFAULT_CLIP_DIR, clip))
        
        clip_infos = os.listdir(DEFAULT_CLIP_INFO_DIR)
        
        for clip_info in clip_infos:
            os.remove(os.path.join(DEFAULT_CLIP_INFO_DIR, clip_info))

    elif sys.argv[1] == '-auto':
        # run the clip compiler and then the video maker on every csv 
        # file in the directory if there is a clip older than 8 hours
        # and the total length of the clips is greater than 5 minutes 
        asyncio.run(VideoMaker.make_from_csvs())
        
    else:
        print('Usage: python3 Main.py <task>\n <task> can be one of the following:\n-l: lurk chat\n-v render a video\n-c combine clips\n--h: help menu (this menu)')
        
    quit(1)