# starts the program and have it either combine exiting clips, make new ones, or render a video

import sys
from src.ChatClassifier import main as chat_classifier
from src.VideoMaker import VideoMaker
from src.ClipCompiler import ClipCompiler
import asyncio

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] == '-h' or sys.argv[1] == '--help':
        print('Usage: python3 Main.py <task>\n <task> can be one of the following:\n-l: lurk chat\n-v render a video\n-c combine clips\n--h: help menu (this menu)')
        exit(0)
    
    if sys.argv[1] == '-l':
        chat_classifier(sys.argv)
    elif sys.argv[1] == '-v':
        # check for the second arg of the directory of the clips
        if len(sys.argv) < 3:
            print('Usage: python3 Main.py -v channel_name')
            exit(0)
        asyncio.run(VideoMaker.make_from_channel(sys.argv[2]))
    elif sys.argv[1] == '-c':
        # check for the second arg of the csv file specifying the clips
        if len(sys.argv) < 3 and sys.argv[2].endswith('.csv'):
            print('Usage: python3 Main.py -c <csv_file_dir>')
            exit(0)
        ClipCompiler().merge_clips(sys.argv[2])
        
    else:
        print('how did you get here?')


