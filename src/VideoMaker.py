# a class that takes edits clips in to videos it is assumed that the clips are already edited and ready to be slaped together
from moviepy.editor import *

from src.ClipGetter import ClipGetter
from src.Clip import Clip
from src.ClipCompiler import ClipCompiler
from src.TwitchAuthenticator import TwitchAuthenticator
from src.AudioToText import AudioToText
import datetime
import json

TRANSITION_VOLUME = 0.1
TRANSITION_SUBCLIP = (2, 2.5)
OUTPUT_RESOLUTION = (1920, 1080)
SORT_BY_TIME = True
DEFAULT_TRANSITION_DIR = 'video_assets/transition.mp4'
DEFAULT_OUTPUT_DIR = 'temp/output/'
DEFAULT_CLIP_DIR = 'temp/clips/'
DEFAULT_CLIP_INFO_DIR = 'clip_info/'
DEFAULT_READY_CHANNEL_CSV = 'clip_info/saturated_channels.csv'
TARGET_VIDEO_LENGTH = 1 * 60 # 1 minutes
LOOK_BACK_TIME = 24 * 7 # 1 week
REQUIRED_CLIP_NUM = 10

# these do not need to be changed
SPOKEN_WORD_TRIM = 3.0
MIN_CLIP_LENGTH = 5.0


class VideoMaker:
    def __init__(self, clip_dirs, output_dir, intro_clip_dir=None, outro_clip_dir=None, transition_dir=None):
        self.intro_clip_dir = intro_clip_dir
        self.outro_clip_dir = outro_clip_dir
        self.clip_dirs = clip_dirs
        self.output_dir = output_dir
        self.transition_dir = transition_dir

        self.audio_to_text = AudioToText()

    # makes a video from the clips Returns True if successful
    def make_video(self):
        # first thing lets combine all the clips in clip_dirs
        videos = []
        for i, clip_dir in enumerate(self.clip_dirs):
            if not os.path.exists(clip_dir):
                print("Clip " + clip_dir + " does not exist")
                continue

            # run the video through the filter to get the subclip we want
            filter_result = self.filter_clips(clip_dir)

            # if None the clip was completely rejected
            if filter_result == None:
                continue
            
            # add the clip to the list of clips
            videos.append(filter_result)

            videos.append(VideoFileClip(self.transition_dir).volumex(TRANSITION_VOLUME).subclip(TRANSITION_SUBCLIP[0], TRANSITION_SUBCLIP[1]))

        # if this is the last clip then we don't the transition
        if (len(videos) > 0):
            videos.pop()    

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
    
        # check the length of the video
        if not self.check_time(final_clip, TARGET_VIDEO_LENGTH):
            print("The video is only " + str(final_clip.duration) + " seconds long aborting...")
            return False

        # now that we have all the clips lets add some visual effects
        # TODO

        # get the streamer name from the first clip
        streamer_name = self.clip_dirs[0].split('/')[-1].split('_')[0]

        # render the video
        final_clip.write_videofile(self.output_dir + streamer_name + datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S") + '.mp4')

        return True
    
    def check_time(self, clip, target_time):
        if (clip.duration < target_time):
            return False
        return True
    
    # filter the clips to not include time periods where the streamer is not talking
    def filter_clips(self, clip_dir):
        text_data = self.audio_to_text.convert_video_to_text(clip_dir)
        # convert the json to a dict
        text_data = json.loads(text_data)


        text_times = text_data["result"]
        text = text_data["text"]

        # load the clip 
        clip_video = VideoFileClip(clip_dir)

        print("Clip length before trim: " + str(clip_video.duration))

        clip_video = self.trim_clip(clip_video, text_times)

        # if the clip was rejected then return None
        if clip_video == None:
            print("Clip to short after trimming rejecting...")
            return None
        
        print("Clip length after trim: " + str(clip_video.duration))

        return clip_video
    
    # trims the clip to remove silence at the end and beginning
    def trim_clip(self, clip, text_times):
        # the variable to store the desired start and end times
        start_time = 0
        end_time = 0
        
        # filter out the begining and end silence
        for i in range(len(text_times)):
            # if a word took unusally long to say we know to filter that section out
            if (text_times[i]["end"] - text_times[i]["start"] < SPOKEN_WORD_TRIM):
                start_time = text_times[i]["start"]
                break
        
        for i in range(len(text_times) - 1, 0, -1):
            # if a word took unusally long to say we know to filter that section out
            if (text_times[i]["end"] - text_times[i]["start"] < SPOKEN_WORD_TRIM):
                end_time = text_times[i]["end"]
                break

        # if the start and end times are to close then we reject the clip
        if (end_time - start_time < MIN_CLIP_LENGTH):
            return None
        
        
        return clip.subclip(start_time, end_time)


    # makes a video from a directory of clips and uses the default transition and content for the channel 
    # specified by channel_name
    @staticmethod
    async def make_from_channel(channel_name, clip_count=15, output_dir=DEFAULT_OUTPUT_DIR, transition_dir=DEFAULT_TRANSITION_DIR):
        # init the twitch authenticator
        authenticator = TwitchAuthenticator()

        # authenticate the bot
        await authenticator.authenticate()

        # get user ids
        users = authenticator.get_users_from_names([channel_name])

        if not users:
            print("Could not find user " + channel_name)
            return False

        clipGetter = ClipGetter()

        print("Getting clips for " + users[0].display_name)

        clips = clipGetter.get_clips(users[0], authenticator.get_client(), time=LOOK_BACK_TIME, clip_dir=DEFAULT_CLIP_DIR, clip_count=clip_count, sort_by_time=SORT_BY_TIME)
        dirs = [clip.clip_dir for clip in clips]

        print("Got clips... making video")

        # TODO cross reference the clipinfo files to see if there are any of our clips in the top num 

        # make sure the output dir exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # now lets make the video
        video_maker = VideoMaker(dirs, output_dir, transition_dir=transition_dir)

        status = video_maker.make_video()

        if not status:
            return False

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

        # only proceed if there are at least REQUIRED_CLIPS clips
        if len(clips) < REQUIRED_CLIP_NUM:
            print("Not enough clips to make a video")
            return False

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

        status = video_maker.make_video()

        if not status:
            return False

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
    async def make_from_csvs(clip_info=DEFAULT_CLIP_INFO_DIR):
        # get a count of the videos per channel by reading the csv's in the clip info dir
        dirs = os.listdir(clip_info)
        
        for dir_ in dirs:
            print(dir_)

        return

        # combine any clips that overlap
        clip_compiler = ClipCompiler()
        for dir_ in dirs:
            clip_compiler.merge_clips(dir_)

        # make a video for each channel
        for dir_ in dirs:
            await VideoMaker.make_from_csv(dir_)

        # remove all the clips from the csv
        with open(csv_dir, 'w') as f:
            f.write('')





