# a class that takes edits clips in to videos it is assumed that the clips are already edited and ready to be slaped together
from moviepy.editor import *

from src.ClipGetter import ClipGetter
from src.Clip import Clip
from src.ClipCompiler import ClipCompiler
from src.TwitchAuthenticator import TwitchAuthenticator
from src.OpenAIUtils import OpenAIUtils
from src.YoutubeUploader import YoutubeUploader
from src.CutFinder import find_cut_point
from src.UserInput import get_int, get_bool
from src.YoutubeHistory import YoutubeHistory
import datetime
import json

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
MIN_CLIP_LENGTH = 10.0
LENGTH_TO_TRIM_BACK =15.0
LENGTH_TO_TRIM_FULL = 35.0
TEMP_AUDIO_FILE = "temp/audio.wav"
TALKING_THRESHOLD = 0.2 # the percentage of the clip that needs to be talking to be considered a talking clip
TRANSCRIPTS_IN_PROMPT = 4 # the number of transcripts to add to the prompt


class VideoMaker:
    # TODO update the constructor to be better
    def __init__(self, clips, output_dir, intro_clip_dir=None, outro_clip_dir=None, transition_dir=None, authenticator=None):
        self.intro_clip_dir = intro_clip_dir
        self.outro_clip_dir = outro_clip_dir
        self.clips = clips
        self.output_dir = output_dir
        self.transition_dir = transition_dir
        self.authenticator = authenticator
        self.uploaded_videos = YoutubeHistory()

        # used to get the title, description, and tags using a LLM and a more advanced transcription
        self.ml_models = OpenAIUtils()

        # creator specific settings
        self.cut_adjustment = 0.0 # the amount of time to add to the cut point

    # makes a clip compilation from the clips Returns True if successful
    def make_video(self):
        # check if all the clips have a valid clip dir
        self.verify_clips_exist()

        videos = []
        used_clips = []
        added_transition = False
        streamer_name = self.clips[0].clip_dir.split('/')[-1].split('_')[0]

        # certain creators specifically the ai streamers should not cut at the moment of silence
        if streamer_name.lower() in config["NO_CUT_STREAMERS"]:
            self.cut_adjustment = 100
            print("cut adjustment active for: " + streamer_name)

        text_times, transcriptions, titles, durations = self.get_clip_data()

        # now let the LLM choose the order of the clips
        print("Choosing order of clips...")

        order = [0]
        if len(self.clips) != 1:
            order = self.ml_models.get_video_order(titles, transcriptions, durations)

        # ask the user if they want to override the LLM order
        self.clips, text_times, transcriptions, titles, durations, order = self.modify_clip_order(self.clips, text_times, transcriptions, titles, durations, order)

        # build the video from the clips
        for i, clip in enumerate(self.clips):
            # get the text data
            text_data = text_times[i]

            # run the video through the filter to get the subclip we want
            filter_result = self.filter_clip(clip, text_data)

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
                elif (self.clips[i + 1].vod_offset - clip.vod_offset < TRANSITION_THRESHOLD and self.clips[i + 1].vod_offset - clip.vod_offset > 0.0):
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
        if (final_clip.duration < REQUIRED_VIDEO_LENGTH):
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

        vod_links = ""
        for i, clip in enumerate(self.clips):
            vod_links += f"clip {i+1}: {self.get_vod_link(clip)}\n"


        title, description, tags = self.ml_models.get_video_info(streamer_name, "".join(transcriptions), [clip.title for clip in self.clips])
        description += vod_links
        print(f"\n\nTitle: {title}\nDescription: {description}\nTags: {tags}\n\n")

        os.startfile(os.path.abspath(save_name))

        # upload the video to youtube
        youtube = YoutubeUploader()
        youtube.upload(title, description, tags, "private", save_name, None)

        # add the video to the history
        self.uploaded_videos.addVideo(self.clips, datetime.datetime.now())

        return True
    
    # makes many videos from the clips provided and uploads them to youtube as standalone videos
    def make_videos_from_clips(self):
        # check if all the clips have a valid clip dir
        self.verify_clips_exist()

        youtube = YoutubeUploader()
        text_times, transcriptions, titles, durations = self.get_clip_data()

        # get the time of the last uploaded video and schedule the video to be uploaded after that
        video = self.uploaded_videos.getLatestVideo()
        video_time = datetime.datetime.now()
        if video != None:
            video_time = video["upload_time"]

        # add 6 hours to the video time TODO make this tuneable
        video_time += datetime.timedelta(hours=6)

        for i, clip in enumerate(self.clips):
            if durations[i] < REQUIRED_VIDEO_LENGTH:
                print("Clip to short for standalone video skipping...")
                continue
            streamer_name = self.clips[i].clip_dir.split('/')[-1].split('_')[0]

            # add a fade in and out to the video
            video_clip = VideoFileClip(clip.clip_dir).fx(vfx.fadein, FADE_TIME).fx(vfx.fadeout, FADE_TIME)
            video_clip = video_clip.audio_fadeout(FADE_TIME)

            # get the save name
            save_name = self.output_dir + streamer_name + datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S") + '.mp4'

            # render the video
            video_clip.write_videofile(save_name, threads=4)

            # release any resources used by the video
            video_clip.close()

            vod_link = self.get_vod_link(clip)

            title, description, tags = self.ml_models.get_video_info(streamer_name, "".join(transcriptions[i]), [self.clips[i].title])
            description += "Link to the vod: " + vod_link
            print(f"\n\nTitle: {title}\nDescription: {description}\nTags: {tags}\n\n")

            os.startfile(os.path.abspath(save_name))


            # upload the video to youtube
            res = youtube.upload(title, description, tags, "private", save_name, None, publishAt=video_time)
            if res:
                self.uploaded_videos.addVideo([clip], video_time)
                video_time += datetime.timedelta(hours=6)


    # returns the text data, transcriptions, titles, and durations of the clips
    # this is used to make the LLM prompt
    def get_clip_data(self):
        text_times = []
        transcriptions = []
        titles = []
        durations = []

        # load the whisper model
        print("Transcribing clips... (loading whisper model)")
        from src.WhisperInterface import WhisperInterface
        audio_to_text = WhisperInterface()

        # populate transcriptions and titles
        for clip in self.clips:
            # get the text and time stamps
            text_data = audio_to_text.transcribe_from_video(clip.clip_dir)

            if text_data == None:
                print("Clip " + clip.clip_dir + " has problematic audio removing...")
                self.clips.remove(clip)
                continue

            # populate the transcription titles and text data
            clip_text = ""
            for text in text_data:
                clip_text += text["word"] + " "
            clip_text += "\n"

            transcriptions.append(clip_text)
            titles.append(clip.title + " ID:" + clip.video_id)
            text_times.append(text_data)
            durations.append(clip.duration)

        return text_times, transcriptions, titles, durations
    
    # filter the clips to not include time periods where the streamer is not talking
    def filter_clip(self, clip, text_data):
        # load the clip 
        clip_video = VideoFileClip(clip.clip_dir)

        print("Clip length before trim: " + str(clip_video.duration))

        # don't trim already short clips
        if (clip_video.duration < LENGTH_TO_TRIM_BACK):
            print("Clip started short skipping filter...\n")
            return clip_video

        # trim the clip to remove silence at the beginning and end
        clip_video = self.trim_clip(clip_video, text_data, clip.clip_dir)

        # if the clip was rejected then return None
        if clip_video == None:
            print("Clip to short after trimming rejecting...\n")
            return None

        return clip_video
    
    # trims the clip to remove silence at the beginning and to cut of at the end of a sentence
    def trim_clip(self, video_clip, text_times, clip_dir):
        if video_clip == None:
            return None
        
        # remove any invalid text times
        to_remove = []
        for text_time in text_times:
            if (text_time.keys() != {"word", "start", "end", "score"}):
                print("Invalid text time format detected... fixing")
                to_remove.append(text_time)
                continue
        for text_time in to_remove:
            text_times.remove(text_time)

        # if there are no text times then return None
        if len(text_times) == 0:
            return None
        
        # start the clip a little before the first word
        start_time = text_times[0]["start"] - START_TRIM_TIME
        end_time = video_clip.duration
        
        # only search the last 1/3 of the clip for the end time (sometimes the transcript forgets to add a period at the end)
        for i in range(len(text_times) - 1, int(len(text_times) / 2), -1):
            # TODO make this more robustn
            # find the last word with a period and use that as the end time
            word = text_times[i]["word"]
            if "." in word or "?" in word or "!" in word:
                end_time = text_times[i]["end"] + EDGE_TRIM_TIME
                break
        
        # add the cut_adjustment to the end time
        end_time += self.cut_adjustment

        # find a better cut point
        end_time = find_cut_point(clip_dir, end_time)

        # if the start and end times are to close together default to the start time being 0
        if (video_clip.duration < LENGTH_TO_TRIM_FULL or end_time - start_time < MIN_CLIP_LENGTH):
            start_time = 0

        # print the duration of the clip
        print("Clip duration after trim: " + str(end_time - start_time))

        # if the start and end times are to close then we reject the clip
        video_clip = video_clip.subclip(self.clamp(start_time, 0, video_clip.duration), self.clamp(end_time, 0, video_clip.duration))
        if (video_clip.duration < MIN_CLIP_LENGTH):
            return None
        
        return video_clip
    
    # allows the user to modify the order of the clips in the video
    def modify_clip_order(self, clips, text_times, transcriptions, titles, durations, order=None):
        order_entered = False
        while True:
            # reorder the clips and text data
            if order != None and len(order) <= len(clips):
                temp = list(zip(clips, text_times, transcriptions, titles, durations))
                temp = [temp[i] for i in order]
                clips, text_times, transcriptions, titles, durations = zip(*temp)

            for i, title in enumerate(titles):
                print(f"Clip {i} {title} Duration: {clips[i].duration}")
                print(transcriptions[i])
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
                    order_entered = True
                except ValueError:
                    print("Invalid format entered please try again")
                    order = None
                continue

            if order_entered:
                break

            user_override = input("Would you like to modify the order (y/n):")
            if user_override == 'y':
                order = None
            else:
                break

        return clips, text_times, transcriptions, titles, durations, order
    
    # gets the vod link for the given clip
    def get_vod_link(self, clip):
        if self.authenticator == None:
            raise Exception("Authenticator not set")
        if clip.vod_offset == None:
            return None
        
        video = self.authenticator.get_videos_from_ids([clip.video_id])
        if len(video) == 0:
            return None
        
        video = video[0]
        minutes = clip.vod_offset // 60
        seconds = clip.vod_offset % 60
        vod_offset = f"{minutes}m{seconds}s"
        vod_link = f"{video.url}?t={vod_offset}"

        return vod_link
    
    # checks if the file of each clip exists and if not removes it from the list of clips
    def verify_clips_exist(self):
        new_clips = []
        for i, clip in enumerate(self.clips):
            if not os.path.exists(clip.clip_dir):
                print("Clip " + clip.clip_dir + " removed...")
            else:
                new_clips.append(clip)
        self.clips = new_clips
    
    @staticmethod
    def clamp(n, minn, maxn):
        return max(min(maxn, n), minn)
    
    # opens the clip provided in the default video player for the user to evaluate
    # expects this projects Clip object
    @staticmethod
    def human_eval_clip(clip):
        os.startfile(os.path.abspath(clip.clip_dir))

        # get a yes or no from the user
        return get_bool("Is this clip good? (y/n):")
                
    # makes a video from a directory of clips and uses the default transition and content for the channel 
    # specified by channel_name
    @staticmethod
    async def make_from_channel(channel_name, clip_count=VIDEOS_TO_FETCH, output_dir=DEFAULT_OUTPUT_DIR, transition_dir=DEFAULT_TRANSITION_DIR, sort_by_time=SORT_BY_TIME, vods_back=0):
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

        clips = clipGetter.get_clips_from_stream(users[0], authenticator.get_client(), clip_dir=DEFAULT_CLIP_DIR, clip_count=clip_count, vods_back=vods_back)

        if len(clips) == 0:
            print("No clips found")
            return False

        print("\nClips downloaded...\n")
        print(len(clips))

        # get user input 
        clip_count = get_int("How many clips would you like to use?", 1, len(clips))
        
        # delete any clips that are not in the top clip_count
        del_clips = clips[clip_count:]
        for clip in del_clips:
            try:
                if os.path.exists(clip.clip_dir):
                    os.remove(clip.clip_dir)
            except OSError:
                print("Error while deleting file " + clip.clip_dir)

        clips = clips[:clip_count]

        # have the user evaluate the clips
        temp_clips = []
        for clip in clips:
            result = VideoMaker.human_eval_clip(clip)
            if result:
                temp_clips.append(clip)
        clips = temp_clips

        # sort all the clips
        if sort_by_time:
            clips.sort(key=lambda x: x.time, reverse=True)

        # make sure the output dir exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # now lets make the video
        video_maker = VideoMaker(clips, output_dir, transition_dir=transition_dir, authenticator=authenticator)
        status = video_maker.make_video()

        if not status:
            return False

        # delete all clips in the clip dir
        for clip in clips:
            try:
                if os.path.exists(clip.clip_dir):
                    os.remove(clip.clip_dir)
            except OSError:
                print("Error while deleting file " + clip.clip_dir)

        return True

    # makes many video's from the top few clips on each channel specified
    @staticmethod
    async def make_from_top_clips(channel_names, num_videos, days_back, output_dir=DEFAULT_OUTPUT_DIR):
        if type(channel_names) != list:
            raise Exception("channel_names must be a list")
        
        if len(channel_names) == 0:
            raise Exception("channel_names must have at least one channel")
        
        if num_videos < len(channel_names):
            raise Exception("num_videos must be greater than or equal to channel_names")

        # init the twitch authenticator
        authenticator = TwitchAuthenticator()

        # authenticate the bot
        await authenticator.authenticate()

        # get user ids
        users = authenticator.get_users_from_names(channel_names)

        if len(users) != len(channel_names):
            print("Could not find all users continuing with: ")
            print([user.display_name for user in users])

        # load the history
        youtube_history = YoutubeHistory()

        # get the clips
        clips = []
        clipGetter = ClipGetter()
        for user in users:
            print("Getting clips for " + user.display_name)
            clip = clipGetter.get_popular_clips(user, authenticator.get_client(), youtube_history, days_back=days_back, clip_dir=DEFAULT_CLIP_DIR, clip_count=num_videos // len(users))
            clips.extend(clip)

        if len(clips) == 0:
            print("No clips found")
            return False
        
        # make the videos
        video_maker = VideoMaker(clips, output_dir, authenticator=authenticator)
        status = video_maker.make_videos_from_clips()

        return status

        

