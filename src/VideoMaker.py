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
from copy import deepcopy

with open('config.json') as f:
    config = json.load(f)

TRANSITION_VOLUME = config['TRANSITION_VOLUME'] # volume of the transition clip
TRANSITION_SUBCLIP = tuple(config['TRANSITION_SUBCLIP']) # the subclip of the transition clip to use
OUTPUT_RESOLUTION = tuple(config['OUTPUT_RESOLUTION']) # the resolution of the output video
SORT_BY_TIME = config['SORT_BY_TIME'] # if true the clips will be sorted by time if false they will be sorted by popularity
DEFAULT_TRANSITION_DIR = config['DEFAULT_TRANSITION_DIR'] # the directory of the transition clip
DEFAULT_OUTPUT_DIR = config['DEFAULT_OUTPUT_DIR'] # the directory to save the output video
DEFAULT_CLIP_DIR = config['DEFAULT_CLIP_DIR'] # the directory to save the clips
DEFAULT_CLIP_INFO_DIR = config['DEFAULT_CLIP_INFO_DIR'] # the directory to save the clip info
DEFAULT_READY_CHANNEL_CSV = config['DEFAULT_READY_CHANNEL_CSV'] # the directory of the csv file with the channels that are ready to be compiled
REQUIRED_VIDEO_LENGTH = config['REQUIRED_VIDEO_LENGTH'] # the required length of the video
MAX_VIDEO_LENGTH = config['MAX_VIDEO_LENGTH'] # the maximum length of the video
CLIP_CLUSTER_TIME = config['CLIP_CLUSTER_TIME'] # clips that are within this time of each other will be clustered together before being sorted by views
LOOK_BACK_TIME = config['LOOK_BACK_TIME'] # the default time to fetch clips from
REQUIRED_CLIP_NUM = config['REQUIRED_CLIP_NUM'] # the number of clips that are required to make a video
TRANSITION_THRESHOLD = config['TRANSITION_THRESHOLD'] # the threshold time for when to add a transition
EDGE_TRIM_TIME = config['EDGE_TRIM_TIME'] # the time to add to the start and end udderance of a clip
VIDEOS_TO_FETCH = config['VIDEOS_TO_FETCH'] # the number of videos to fetch from the api
FADE_TIME = config['FADE_TIME'] # the time a fade in and out will take
SHORT_CLIP_IN_FRONT = config['SHORT_CLIP_IN_FRONT'] # the number of the short clips to add to the front of the video

# these are likly not going to change so they are not in the config file
MIN_CLIP_LENGTH = 3.0
LENGTH_TO_TRIM = 10.0
TEMP_AUDIO_FILE = "temp/audio.wav"
TALKING_THRESHOLD = 0.2 # the percentage of the clip that needs to be talking to be considered a talking clip
TRANSCRIPTS_IN_PROMPT = 3 # the number of transcripts to add to the prompt


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

        streamer_name = self.clips[0].clip_dir.split('/')[-1].split('_')[0]

        # loop through all the clips and filter them as well as add transitions
        for i, clip in enumerate(self.clips):
            # check if the clip exists
            if not os.path.exists(clip.clip_dir):
                print("Clip " + clip.clip_dir + " does not exist")
                continue

            # get the text and time stamps
            text_data = self.audio_to_text.transcribe_from_video(clip.clip_dir) 

            # run the video through the filter to get the subclip we want
            filter_result = self.filter_clips(clip.clip_dir, text_data)

            # if None the clip was completely rejected
            if filter_result == None:
                continue

            # add the text to the transcriptions
            clip_text = f"Transcription: '"
            for text in text_data:
                clip_text += text["text"] + " "
            clip_text += "'\n"
            if (i < TRANSCRIPTS_IN_PROMPT):
                transcription += clip_text

            print(clip_text)

            # add the clip to the list of clips
            videos.append(filter_result)

            added_transition = False

            # if the resulting video is longer than the max length then stop
            if (sum([video.duration for video in videos]) > MAX_VIDEO_LENGTH):
                break

            added_transition = True
            videos.append(VideoFileClip(self.transition_dir).volumex(TRANSITION_VOLUME).subclip(TRANSITION_SUBCLIP[0], TRANSITION_SUBCLIP[1]))

        # if we added a transition at the end remove it
        if added_transition:
            videos.remove(videos[-1])

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
        if not self.check_time(final_clip, REQUIRED_VIDEO_LENGTH):
            print("The video is only " + str(final_clip.duration) + " seconds long aborting...")
            return False
        
        # add a fade in and out to the video
        final_clip = final_clip.fx(vfx.fadein, FADE_TIME).fx(vfx.fadeout, FADE_TIME)

        # make the audio also fade in and out
        final_clip.audio_fadein(FADE_TIME)
        final_clip.audio_fadeout(FADE_TIME)

        # get the save name
        save_name = self.output_dir + streamer_name + datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S") + '.mp4'

        # render the video
        final_clip.write_videofile(save_name, threads=4)

        # query the language model for the title, description, and tags (loop until we get a good result)
        while True:
            title, description, tags = self.ml_models.get_video_info(streamer_name, transcription, clip_titles=[clip.title for clip in self.clips])
            print(f"Title: {title}\nDescription: {description}\nTags: {tags}\n")

            ans = input("Is this good? (y/n): ")
            if ans.lower() == "y":
                break

        # TODO save info to a file so we can use it later if we want to
        # ie if we want to make a video with the same title just increment the number at the end
        # or if we want to make sure we don't make a video to soon after another one

        # upload the video to youtube
        youtube = YoutubeUploader()
        youtube.upload(title, description, tags, "private", save_name, None)

        # release any resources used by the video
        final_clip.close()

        return True
    
    def check_time(self, clip, target_time):
        if (clip.duration < target_time):
            return False
        return True
    
    # filter the clips to not include time periods where the streamer is not talking
    def filter_clips(self, clip_dir, text_data):
        # load the clip 
        clip_video = VideoFileClip(clip_dir)

        print("Clip length before trim: " + str(clip_video.duration))

        # don't trim already short clips
        if (clip_video.duration < LENGTH_TO_TRIM):
            print("Clip started short skipping filter...")
            return clip_video

        # trim the clip to remove silence at the beginning and end
        clip_video = self.trim_clip(clip_video, text_data)

        # calculate the total time that the streamer is talking
        total_talking_percentage = 0
        for text in text_data:
            total_talking_percentage += text["end"] - text["start"]
        total_talking_percentage = total_talking_percentage / clip_video.duration

        print("Total talking percentage: " + str(total_talking_percentage))

        # if the streamer is not talking enough reject the clip
        if (total_talking_percentage < TALKING_THRESHOLD):
            print("Streamers talking time too low rejecting clip...")
            return None

        # if the clip was rejected then return None
        if clip_video == None:
            print("Clip to short after trimming rejecting...")
            return None
        print("Clip length after trim: " + str(clip_video.duration))

        return clip_video
    
    # trims the clip to remove silence at the beginning and to cut of at the end of a sentence
    def trim_clip(self, clip, text_times):
        if clip == None:
            return None

        # the variable to store the desired start and end times
        start_time = 0
        end_time = clip.duration
        
        # start the clip a little before the first word
        start_time = text_times[0]["start"] - EDGE_TRIM_TIME
        
        for i in range(len(text_times) - 1, 0, -1):
            # find the last word with a period and use that as the end time
            word = text_times[i]["text"]
            if "." in word or "?" in word or "!" in word:
                end_time = text_times[i]["end"] + EDGE_TRIM_TIME
                break

        # if the start and end times are to close then we reject the clip
        clip = clip.subclip(self.clamp(start_time, 0, clip.duration), self.clamp(end_time, 0, clip.duration))
        if (clip.duration < MIN_CLIP_LENGTH):
            return None
        
        return clip
    
    def write_channel_info(self, channel_name, title, description, tags):
        pass

    # sorts the clips by time and then moves some short ones to the front
    @staticmethod
    def sort_clips(clips, key=lambda x: x.time, reverse=False):
        clips.sort(key=key, reverse=reverse)

        # if multiple clips have the same title then move those to the end of the list
        rejects = []
        for i in range(len(clips)):
            for j in range(i + 1, len(clips)):
                if clips[i].title == clips[j].title:
                    rejects.append(clips[j])
                    break

        for reject in rejects:
            clips.remove(reject)
            clips.append(reject)

        # get the shortest three clips move them to the front of the list
        clips_copy = deepcopy(clips)

        # sort the clips by length
        clips_copy.sort(key=lambda x: x.duration, reverse=False)

        # get the shortest three clips
        shortest_clips = clips_copy[:3]

        # add at the front
        for clip in shortest_clips:
            # find the clip with the same id and remove it
            for c in clips:
                if c.clip_id == clip.clip_id:
                    clips.pop(clips.index(c))
                    break
        clips = shortest_clips + clips

        return clips
    
    def clamp(self, n, minn, maxn):
        return max(min(maxn, n), minn)
                
    # makes a video from a directory of clips and uses the default transition and content for the channel 
    # specified by channel_name
    @staticmethod
    async def make_from_channel(channel_name, clip_count=VIDEOS_TO_FETCH, output_dir=DEFAULT_OUTPUT_DIR, transition_dir=DEFAULT_TRANSITION_DIR, time=LOOK_BACK_TIME, sort_by_views=SORT_BY_TIME):
        # init the twitch authenticator
        authenticator = TwitchAuthenticator()

        # authenticate the bot
        await authenticator.authenticate()

        # get user ids
        users = authenticator.get_users_from_names([channel_name])

        if not users:
            print("Could not find uPser " + channel_name)
            return False

        clipGetter = ClipGetter()

        print("Getting clips for " + users[0].display_name)

        clips = clipGetter.get_clips(users[0], authenticator.get_client(), time=time, clip_dir=DEFAULT_CLIP_DIR, clip_count=clip_count)

        if len(clips) == 0:
            print("No clips found")
            return False

        print("\nGot clips... making video")

        # sort all the clips
        if sort_by_views:
            clips = VideoMaker.sort_clips(clips)

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
            clips = VideoMaker.sort_clips(clips)          

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