# a class that takes edits clips in to videos it is assumed that the clips are already edited and ready to be slaped together
from moviepy.editor import *

class VideoMaker:
    def __init__(self, intro_clip_dir, outro_clip_dir, clip_dirs, output_dir):
        self.intro_clip_dir = intro_clip_dir
        self.outro_clip_dir = outro_clip_dir
        self.clip_dirs = clip_dirs
        self.output_dir = output_dir

    # makes a video from the clips
    def make_video(self):
        pass





