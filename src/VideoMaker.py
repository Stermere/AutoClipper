# a class that takes edits clips in to videos it is assumed that the clips are already edited and ready to be slaped together
from moviepy.editor import *

from src.ClipGetter import ClipGetter
from src.Clip import Clip
from src.ClipCompiler import ClipCompiler
from src.TwitchAuthenticator import TwitchAuthenticator
from src.WhisperInterface import WhisperInterface
from src.OpenAIUtils import OpenAIUtils
from src.YoutubeUploader import YoutubeUploader
from src.cutFinder import find_cut_point
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
START_TRIM_TIME = config['START_TRIM_TIME'] # the time to add to the start of the first word in a clip
VIDEOS_TO_FETCH = config['VIDEOS_TO_FETCH'] # the number of videos to fetch from the api
FADE_TIME = config['FADE_TIME'] # the time a fade in and out and the begining and end of a video will take
TRANSITION_FADE_TIME = config['TRANSITION_FADE_TIME'] # the time a fade in and out will take for a transition
SHORT_CLIP_IN_FRONT = config['SHORT_CLIP_IN_FRONT'] # the number of the short clips to add to the front of the video

# these are likly not going to change so they are not in the config file
MIN_CLIP_LENGTH = 3.0
LENGTH_TO_TRIM = 15.0
TEMP_AUDIO_FILE = "temp/audio.wav"
TALKING_THRESHOLD = 0.2 # the percentage of the clip that needs to be talking to be considered a talking clip
TRANSCRIPTS_IN_PROMPT = 4 # the number of transcripts to add to the prompt


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
        streamer_name = self.clips[0].clip_dir.split('/')[-1].split('_')[0]

        # TODO filter the stream titles out of clip titles and remove those clips
        text_times = []
        audio_loc = []
        transcriptions = []
        titles = []
        durations = []
        used_clips = []

        # open the temp clips file in the file manager
        os.startfile(os.path.abspath(DEFAULT_CLIP_DIR))
        input("Delete any clips you dont want in the video then press enter to continue...")

        # repolulate the clip info
        for clip in self.clips:
            if not os.path.exists(clip.clip_dir):
                print("Clip " + clip.clip_dir + " removed...")
                self.clips.remove(clip)
                continue

        # populate transcriptions and titles
        print("Transcribing clips...")
        for clip in self.clips:
            # check if the clip exists
            if not os.path.exists(clip.clip_dir):
                print("Clip " + clip.clip_dir + " does not exist removing...")
                self.clips.remove(clip)
                continue

            # get the text and time stamps
            text_data = self.audio_to_text.transcribe_from_video(clip.clip_dir)

            if text_data == None:
                print("Clip " + clip.clip_dir + " has problematic audio removing...")
                self.clips.remove(clip)
                continue

            # populate the transcription titles and text data
            clip_text = ""
            for text in text_data:
                clip_text += text["text"] + " "
            clip_text += "\n"

            transcriptions.append(clip_text)
            titles.append(clip.title)
            text_times.append(text_data)
            durations.append(clip.duration)

        # now let the LLM choose the order of the clips
        print("Choosing order of clips...")
        order = self.ml_models.get_video_order(titles, transcriptions, durations)

        # ask the user if they want to override the LLM order
        self.clips, text_times, transcriptions, titles, durations, order = self.modify_clip_order(self.clips, text_times, transcriptions, titles, durations, order)

        # build the video from the clips
        for i, clip in enumerate(self.clips):
            # get the text data
            text_data = text_times[i]

            # run the video through the filter to get the subclip we want
            filter_result = self.filter_clips(clip.clip_dir, text_data)

            # if None the clip was completely rejected
            if filter_result == None:
                continue

            # add a sound fade in and out to the clip
            filter_result = filter_result.fx(vfx.fadein, TRANSITION_FADE_TIME)
            filter_result = filter_result.audio_fadeout(TRANSITION_FADE_TIME)

            # add the clip to the list of clips
            videos.append(filter_result)
            used_clips.append(clip)

            added_transition = False

            # if the resulting video is longer than the max length then stop
            if (sum([video.duration for video in videos]) > MAX_VIDEO_LENGTH):
                break

            # if the two clips are close together do not add a transition
            if (i != len(self.clips) - 1 and clip.video_id == self.clips[i + 1].video_id):
                if (self.clips[i + 1].vod_offset == None or clip.vod_offset == None):
                    pass
                elif (self.clips[i + 1].vod_offset - clip.vod_offset < TRANSITION_THRESHOLD):
                    continue
            
            added_transition = True
            videos.append(VideoFileClip(self.transition_dir).volumex(TRANSITION_VOLUME).subclip(TRANSITION_SUBCLIP[0], TRANSITION_SUBCLIP[1]))

        # if we added a transition at the end remove it
        if added_transition:
            videos.remove(videos[-1])

        # remove any clips that are not in the video
        self.clips = used_clips

        # now lets add the intro and outro clips
        if (self.intro_clip_dir != None):
            videos.insert(0, VideoFileClip(self.intro_clip_dir))

        if (self.outro_clip_dir != None):
            videos.append(VideoFileClip(self.outro_clip_dir))

        # resize all videos to 1080p
        for i in range(len(videos)):
            videos[i] = videos[i].resize(OUTPUT_RESOLUTION)

        # get the combined video
        if (len(videos) == 0):
            print("No clips were added to the video aborting...")
            return False

        final_clip = concatenate_videoclips(videos, method="compose")
    
        # check the length of the video
        if not self.check_time(final_clip, REQUIRED_VIDEO_LENGTH):
            print("The video is only " + str(final_clip.duration) + " seconds long aborting...")
            return False
        
        # add a fade in and out to the video
        final_clip = final_clip.fx(vfx.fadein, FADE_TIME).fx(vfx.fadeout, FADE_TIME)

        # make the audio also fade out
        final_clip = final_clip.audio_fadeout(FADE_TIME)

        # get the save name
        save_name = self.output_dir + streamer_name + datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S") + '.mp4'

        # render the video
        final_clip.write_videofile(save_name, threads=4)

        # release any resources used by the video
        final_clip.close()

        # query the language model for the title, description, and tags (loop until we get a good result)
        while True:
            title, description, tags = self.ml_models.get_video_info(streamer_name, "Transcripts: ".join(transcriptions[:TRANSCRIPTS_IN_PROMPT]), clip_titles=[clip.title for clip in self.clips])
            print(f"Title: {title}\nDescription: {description}\nTags: {tags}\n")

            ans = input("Is this good? (y/n): ")
            if ans.lower() == "y":
                break

        # add some extra info to the description
        # if the clips are provided add the time stamps to the description
        description += "\nTime stamps (UTC+0 time):\n"
        for i, clip in enumerate(self.clips):
            description += f"\t{i + 1}. {clip.time}\n"

        # TODO save info to a file so we can use it later if we want to
        # ie if we want to make a video with the same title just increment the number at the end
        # or if we want to make sure we don't make a video to soon after another one

        # upload the video to youtube
        youtube = YoutubeUploader()
        youtube.upload(title, description, tags, "private", save_name, None)

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
            print("Clip started short skipping filter...\n")
            return clip_video

        # trim the clip to remove silence at the beginning and end
        clip_video = self.trim_clip(clip_video, text_data, clip_dir)

        # if the clip was rejected then return None
        if clip_video == None:
            print("Clip to short after trimming rejecting...\n")
            return None
        print("Clip length after trim: " + str(clip_video.duration) + "\n")

        return clip_video
    
    # trims the clip to remove silence at the beginning and to cut of at the end of a sentence
    def trim_clip(self, clip, text_times, clip_dir):
        if clip == None:
            return None
        
        # start the clip a little before the first word
        start_time = text_times[0]["start"] - START_TRIM_TIME
        end_time = text_times[-1]["end"] + EDGE_TRIM_TIME
        
        # only search the last 1/3 of the clip for the end time (sometimes the transcript forgets to add a period at the end)
        for i in range(len(text_times) - 1, int(len(text_times) / 2), -1):
            # TODO make this more robustn
            # find the last word with a period and use that as the end time
            word = text_times[i]["text"]
            if "." in word or "?" in word or "!" in word:
                end_time = text_times[i]["end"] + EDGE_TRIM_TIME
                break

        # find a better cut point
        end_time = find_cut_point(clip_dir, end_time)

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
    
    # allows the user to modify the order of the clips in the video
    def modify_clip_order(self, clips, text_times, transcriptions, titles, durations, order=None):
        while True:
            # reorder the clips and text data
            if order != None:
                temp = list(zip(clips, text_times, transcriptions, titles, durations))
                temp = [temp[i] for i in order]
                clips, text_times, transcriptions, titles, durations = zip(*temp)

            for i, title in enumerate(titles):
                print(f"Clip {i} {title} Duration: {clips[i].duration}")
            print("\n")

            # if the LLM failed of the user wants to override the order
            if order == None:
                order = input("Please enter the order of the clips:")
                order = order.split(' ')
                
                # check if the user entered a valid order
                # if not ask them to enter it again
                try:
                    order = [int(i) for i in order]
                    for i in order:
                        if i < 0 or i >= len(clips):
                            raise ValueError
                except ValueError:
                    print("Invalid format entered please try again")
                    order = None
                continue

            user_override = input("Would you like to modify the order (y/n):")
            if user_override == 'y':
                order = None
            elif user_override == 'n':
                break

        return clips, text_times, transcriptions, titles, durations, order
    
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

        print("\nGot clips... making video\n")

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

        # delete all clips in the clip dir
        for dir_ in os.listdir(DEFAULT_CLIP_DIR):
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