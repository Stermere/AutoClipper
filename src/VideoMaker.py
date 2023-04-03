# a class that takes edits clips in to videos it is assumed that the clips are already edited and ready to be slaped together
from moviepy.editor import *

from src.ClipGetter import ClipGetter
from src.Clip import Clip
from src.ClipCompiler import ClipCompiler
from src.TwitchAuthenticator import TwitchAuthenticator
import datetime

TRANSITION_VOLUME = 0.1
TRANSITION_SUBCLIP = (2, 2.5)
OUTPUT_RESOLUTION = (1920, 1080)
SORT_BY_TIME = True
DEFAULT_TRANSITION_DIR = 'video_assets/transition.mp4'
DEFAULT_OUTPUT_DIR = 'temp/output/'
DEFAULT_CLIP_DIR = 'temp/clips/'
DEFAULT_READY_CHANNEL_CSV = 'clip_info/saturated_channels.csv'

class VideoMaker:
    def __init__(self, clip_dirs, output_dir, intro_clip_dir=None, outro_clip_dir=None, transition_dir=None):
        self.intro_clip_dir = intro_clip_dir
        self.outro_clip_dir = outro_clip_dir
        self.clip_dirs = clip_dirs
        self.output_dir = output_dir
        self.transition_dir = transition_dir

    # makes a video from the clips Returns True if successful
    def make_video(self):
        # first thing lets combine all the clips in clip_dirs
        videos = []
        for i, clip_dir in enumerate(self.clip_dirs):
            videos.append(VideoFileClip(clip_dir))
            if (i == len(self.clip_dirs) - 1):
                continue
            videos.append(VideoFileClip(self.transition_dir).volumex(TRANSITION_VOLUME).subclip(TRANSITION_SUBCLIP[0], TRANSITION_SUBCLIP[1]))

        # now lets add the intro and outro clips
        if (self.intro_clip_dir != None):
            videos.insert(0, VideoFileClip(self.intro_clip_dir))

        if (self.outro_clip_dir != None):
            videos.append(VideoFileClip(self.outro_clip_dir))

        # resize all videos to 1080p
        for i in range(len(videos)):
            videos[i] = videos[i].resize(OUTPUT_RESOLUTION)

        # get the combined video
        final_clip = concatenate_videoclips(videos, method="compose")

        # now that we have all the clips lets add some visual effects
        # TODO 

        # get the streamer name from the first clip
        streamer_name = self.clip_dirs[0].split('/')[-1].split('_')[0]

        # render the video
        final_clip.write_videofile(self.output_dir + streamer_name + datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S") + '.mp4')

        return True
    
    # makes a video from a directory of clips and uses the default transition and content for the channel 
    # specified by channel_name
    @staticmethod
    async def make_from_channel(channel_name, clip_count=10, output_dir=DEFAULT_OUTPUT_DIR, transition_dir=DEFAULT_TRANSITION_DIR):
        # init the twitch authenticator
        authenticator = TwitchAuthenticator()

        # authenticate the bot
        await authenticator.authenticate()

        # get user ids
        users = authenticator.get_users_from_names([channel_name])

        clipGetter = ClipGetter()

        print("Getting clips for " + users[0].display_name)

        dirs = clipGetter.get_clips(users[0], authenticator.get_client(), clip_dir=DEFAULT_CLIP_DIR, clip_count=clip_count)

        print("Got clips... making video")

        # TODO cross reference the clipinfo files to see if there are any of our clips in the top num

        # make sure the output dir exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # now lets make the video
        video_maker = VideoMaker(dirs, output_dir, transition_dir=transition_dir)

        video_maker.make_video()

        # delete the clips
        for dir_ in dirs:
            try:
                os.remove(dir_)
            except OSError:
                # if one file is not deleted its not a big deal
                pass

    # makes a video from a csv file that specifies the clips to use csv_dir can be a csv file or a directory of csv files
    @staticmethod
    async def make_from_csv(csv_dir, output_dir=DEFAULT_OUTPUT_DIR , transition_dir=DEFAULT_TRANSITION_DIR):
        # load in the csv
        clips = []
        with open(csv_dir, 'r') as f:
            lines = f.readlines()
        for line in lines:
            clips.append(Clip.from_string(line))

        # sort the clips by time
        if (SORT_BY_TIME):
            clips.sort(key=lambda x: x.time)

        # get the clip dirs
        dirs = []
        for clip in clips:
            dirs.append(clip.clip_dir)

        # make sure the output dir exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # now lets make the video
        video_maker = VideoMaker(dirs, output_dir, transition_dir=transition_dir)

        video_maker.make_video()

        # delete the clips
        for dir_ in dirs:
            try:
                os.remove(dir_)
            except OSError:
                # if one file is not deleted its not a big deal
                pass

        # remove all the clips from the csv
        with open(csv_dir, 'w') as f:
            f.write('')

    # makes all a video from each csv specified in the csv provided
    @staticmethod
    async def make_from_csvs(csv_dir=DEFAULT_READY_CHANNEL_CSV):
        # load in the csv
        with open(csv_dir, 'r') as f:
            dirs = f.readlines()

        # combine any clips that overlap
        clip_compiler = ClipCompiler()
        for dir_ in dirs:
            clip_compiler.compile_clips(dir_)

        # make a video for each channel
        for dir_ in dirs:
            await VideoMaker.make_from_csv(dir_)





