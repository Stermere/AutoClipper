# a class that takes edits clips in to videos it is assumed that the clips are already edited and ready to be slaped together
from moviepy.editor import *

from src.ClipGetter import ClipGetter
from src.Clip import Clip
from src.ClipCompiler import ClipCompiler
from src.TwitchAuthenticator import TwitchAuthenticator
from src.WhisperInterface import WhisperInterface
from src.OpenAIUtils import OpenAIUtils
from src.YoutubeUploader import YoutubeUploader
import datetime
import json

with open('config.json') as f:
    config = json.load(f)

TRANSITION_VOLUME = config['TRANSITION_VOLUME']
TRANSITION_SUBCLIP = tuple(config['TRANSITION_SUBCLIP'])
OUTPUT_RESOLUTION = tuple(config['OUTPUT_RESOLUTION'])
SORT_BY_TIME = config['SORT_BY_TIME']
DEFAULT_TRANSITION_DIR = config['DEFAULT_TRANSITION_DIR']
DEFAULT_OUTPUT_DIR = config['DEFAULT_OUTPUT_DIR']
DEFAULT_CLIP_DIR = config['DEFAULT_CLIP_DIR']
DEFAULT_CLIP_INFO_DIR = config['DEFAULT_CLIP_INFO_DIR']
DEFAULT_READY_CHANNEL_CSV = config['DEFAULT_READY_CHANNEL_CSV']
TARGET_VIDEO_LENGTH = config['TARGET_VIDEO_LENGTH']
LOOK_BACK_TIME = config['LOOK_BACK_TIME']
REQUIRED_CLIP_NUM = config['REQUIRED_CLIP_NUM']
TRANSITION_THRESHOLD = config['TRANSITION_THRESHOLD']
EDGE_TRIM_TIME = config['EDGE_TRIM_TIME']
VIDEOS_TO_FETCH = config['VIDEOS_TO_FETCH']

# these are likly not going to change so they are not in the config file
EDGE_TRIM_THRESHOLD = 5.0
MIDDLE_TRIM_THRESHOLD = 5.0
MIN_CLIP_LENGTH = 3.0
LENGTH_TO_TRIM = 10.0
TRANSCRIPTION_LENGTH = 600
TEMP_AUDIO_FILE = "temp/audio.wav"
NO_SPEECH_THRESHOLD = 0.25


class VideoMaker:
    def __init__(self, clips, output_dir, intro_clip_dir=None, outro_clip_dir=None, transition_dir=None):
        self.intro_clip_dir = intro_clip_dir
        self.outro_clip_dir = outro_clip_dir
        self.clips = clips
        self.output_dir = output_dir
        self.transition_dir = transition_dir

        # used to get time stamps of words in the audio
        self.audio_to_text = WhisperInterface()

        # used to get the title, description, and tags using a LLM and a more advanced transcription
        self.ml_models = OpenAIUtils()

    # makes a video from the clips Returns True if successful
    def make_video(self):
        # second thing lets combine all the clips in clip_dirs
        videos = []
        added_transition = False
        transcription = ""

        # loop through all the clips and filter them as well as add transitions
        for i, clip in enumerate(self.clips):
            # check if the clip exists
            if not os.path.exists(clip.clip_dir):
                print("Clip " + clip.clip_dir + " does not exist")
                added_transition = False
                continue

            # get the text and time stamps
            text_data, no_speech_probability = self.audio_to_text.transcribe_from_video(clip.clip_dir) 

            # run the video through the filter to get the subclip we want
            filter_result = self.filter_clips(clip.clip_dir, text_data, no_speech_probability)

            # if None the clip was completely rejected
            if filter_result == None:
                added_transition = False
                continue

            # add the text to the transcriptions
            for text in text_data:
                transcription += text["text"] + " "
            transcription += "\n"

            # add the clip to the list of clips
            videos.append(filter_result)

            # find the time between this clip and the next clip
            time_between_clips = datetime.timedelta(seconds=TRANSITION_THRESHOLD)
            if (i != len(self.clips) - 1):
                time_between_clips = self.clips[i + 1].time - self.clips[i].time

            # do not add transitions in these cases
            if (time_between_clips < datetime.timedelta(seconds=TRANSITION_THRESHOLD)):
                added_transition = False
                continue

            added_transition = True
            videos.append(VideoFileClip(self.transition_dir).volumex(TRANSITION_VOLUME).subclip(TRANSITION_SUBCLIP[0], TRANSITION_SUBCLIP[1]))

        # if we added a transition at the end remove it
        if added_transition:
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

        # get the save name
        streamer_name = self.clips[0].clip_dir.split('/')[-1].split('_')[0]
        save_name = self.output_dir + streamer_name + datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S") + '.mp4'

        print(f"\nTranscription: {transcription}\n")

        # render the video
        final_clip.write_videofile(save_name, threads=4)

        # query the language model for the title, description, and tags
        title, description, tags = self.ml_models.get_video_info(streamer_name, transcription)

        print(f"Title: {title}\nDescription: {description}\nTags: {tags}\n")

        # upload the video to youtube
        youtube = YoutubeUploader()
        youtube.upload(title, description, tags, "private", save_name, None)

        return True
    
    def check_time(self, clip, target_time):
        if (clip.duration < target_time):
            return False
        return True
    
    # filter the clips to not include time periods where the streamer is not talking
    def filter_clips(self, clip_dir, text_data, no_speech_probability):
        # load the clip 
        clip_video = VideoFileClip(clip_dir)

        print("Clip length before trim: " + str(clip_video.duration))

        # if the no speech probability is too high then reject the clip
        if (no_speech_probability > NO_SPEECH_THRESHOLD):
            print("No speech probability too high rejecting clip...")
            return None

        if (clip_video.duration < LENGTH_TO_TRIM):
            print("Clip started short skipping filter...")
            return clip_video

        # trim the clip to remove silence at the beginning and end
        clip_video = self.trim_clip(clip_video, text_data)

        # if the clip was rejected then return None
        if clip_video == None:
            print("Clip to short after trimming rejecting...")
            return None
        print("Clip length after trim: " + str(clip_video.duration))

        # remove extra silence in the middle of the clip
        clip_video = self.trim_silence(clip_video, text_data)

        # if the clip was rejected then return None
        if clip_video == None:
            print("Clip to short after trimming rejecting...")
            return None
        print("Clip length after middle trim: " + str(clip_video.duration))

        return clip_video
    
    # trims the clip to remove silence at the end and beginning
    def trim_clip(self, clip, text_times):
        if clip == None:
            return None

        # the variable to store the desired start and end times
        start_time = 0
        end_time = 0
        
        # filter out the begining and end silence
        for i in range(len(text_times)):
            # if a word took unusally long to say we know to filter that section out
            if (text_times[i]["end"] - text_times[i]["start"] < EDGE_TRIM_THRESHOLD):
                start_time = text_times[i]["start"] - EDGE_TRIM_TIME
                break
        
        for i in range(len(text_times) - 1, 0, -1):
            # if a word took unusally long to say we know to filter that section out
            if (text_times[i]["end"] - text_times[i]["start"] < EDGE_TRIM_THRESHOLD):
                end_time = text_times[i]["end"] + EDGE_TRIM_TIME
                break

        # if the start and end times are to close then we reject the clip
        clip = clip.subclip(self.clamp(start_time, 0, clip.duration), self.clamp(end_time, 0, clip.duration))
        if (clip.duration < MIN_CLIP_LENGTH):
            return None
        
        return clip

    # trims the clip to remove silence in the middle
    def trim_silence(self, clip, text_times):
        if clip == None:
            return None
        
        # loop over the text and cut the words that take longer than the threshold
        clips = []
        last_end_time = 0
        for i in range(len(text_times)):
            # if a word took unusally long to say we know to filter that section out
            if (text_times[i]["end"] - text_times[i]["start"] > MIDDLE_TRIM_THRESHOLD):
                clips.append(clip.subclip(self.clamp(last_end_time, 0, clip.duration), self.clamp(text_times[i]["start"] + 0.1, 0, clip.duration)))
                last_end_time = self.clamp(text_times[i]["end"] - 0.1, 0, clip.duration)

        # append the last clip
        if (clip.duration - last_end_time > MIDDLE_TRIM_THRESHOLD):
            clips.append(clip.subclip(last_end_time, clip.duration))

        # if there are no clips return None
        if (len(clips) == 0):
            return None
        
        # now we need to combine the clips
        final_clip = concatenate_videoclips(clips, method="chain")

        # if the start and end times are to close then we reject the clip
        if (final_clip.duration < MIN_CLIP_LENGTH):
            return None

        return final_clip
    
    def clamp(self, n, minn, maxn):
        return max(min(maxn, n), minn)
                
    # makes a video from a directory of clips and uses the default transition and content for the channel 
    # specified by channel_name
    @staticmethod
    async def make_from_channel(channel_name, clip_count=VIDEOS_TO_FETCH, output_dir=DEFAULT_OUTPUT_DIR, transition_dir=DEFAULT_TRANSITION_DIR, time=LOOK_BACK_TIME, sort_by_time=SORT_BY_TIME):
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

        clips = clipGetter.get_clips(users[0], authenticator.get_client(), time=time, clip_dir=DEFAULT_CLIP_DIR, clip_count=clip_count, sort_by_time=sort_by_time)

        if len(clips) == 0:
            print("No clips found")
            return False

        print("\nGot clips... making video")

        # sort all the clips
        if (sort_by_time):
            clips.sort(key=lambda x: x.time, reverse=False)

        dirs = [clip.clip_dir for clip in clips]

        # make sure the output dir exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # now lets make the video
        video_maker = VideoMaker(clips, output_dir, transition_dir=transition_dir)

        status = video_maker.make_video()

        if not status:
            return False

        # delete the clips
        for dir_ in dirs:
            try:
                if os.path.exists(dir_):
                    os.remove(dir_)
            except OSError:
                print("Error while deleting file " + dir_)

        return True

    # makes a video from a csv file that specifies the clips to use csv_dir can be a csv file or a directory of csv files
    @staticmethod
    async def make_from_csv(csv_dir, output_dir=DEFAULT_OUTPUT_DIR , transition_dir=DEFAULT_TRANSITION_DIR):
        # combine any overlaping clips
        clip_compiler = ClipCompiler()
        clip_compiler.merge_clips(csv_dir)
        
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
        dirs = [clip.clip_dir for clip in clips]

        # make sure the output dir exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # now lets make the video
        video_maker = VideoMaker(clips, output_dir, transition_dir=transition_dir)

        status = video_maker.make_video()

        if not status:
            return False

        # delete the clips
        for dir_ in dirs:
            try:
                if os.path.exists(dir_):
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

        # make a video for each channel
        for dir_ in dirs:
            await VideoMaker.make_from_csv(clip_info + '/' + dir_)

        # remove all the clips from the csv
        for dir_ in dirs:
            with open(dir_, 'w') as f:
                f.write('')