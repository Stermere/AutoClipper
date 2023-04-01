# a class that takes edits clips in to videos it is assumed that the clips are already edited and ready to be slaped together
from moviepy.editor import *

import asyncio
from twitchAPI import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.types import AuthScope
import twitch
from src.ClipGetter import ClipGetter

TRANSITION_VOLUME = 0.2

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
        for (i, clip_dir) in enumerate(self.clip_dirs):
            videos.append(VideoFileClip(clip_dir))
            videos.append(VideoFileClip(self.transition_dir).volumex(TRANSITION_VOLUME))

        # now lets add the intro and outro clips
        if (self.intro_clip_dir != None):
            videos.insert(0, VideoFileClip(self.intro_clip_dir))

        if (self.outro_clip_dir != None):
            videos.append(VideoFileClip(self.outro_clip_dir))

        # get the combined video
        final_clip = concatenate_videoclips(videos, method="compose")

        # now that we have all the clips lets add some visual effects
        # TODO 

        # render the video
        final_clip.write_videofile(self.output_dir)

        return True
    
    # makes a video from a directory of clips and uses the default transition and content for the channel 
    # specified by channel_name
    @staticmethod
    async def make_from_channel(channel_name, clip_count=10, output_dir='temp/output.mp4', transition_dir='video_assets/transition.mp4'):
        # load the app credentials from a file named app_credentials.txt
        # first line the app id, second line the app secret
        with open('app_credentials.txt', 'r') as f:
            APP_ID = f.readline().strip()
            APP_SECRET = f.readline().strip()
        USER_SCOPE = [AuthScope.CHAT_READ, AuthScope.CLIPS_EDIT]

        # first lets get the top ten clips of the last day
        # set up twitch api instance and add user authentication with some scopes
        twitch_ = await Twitch(APP_ID, APP_SECRET)
        auth = UserAuthenticator(twitch_, USER_SCOPE)
        token, refresh_token = await auth.authenticate()
        await twitch_.set_user_authentication(token, USER_SCOPE, refresh_token)

        # create helix instance to get user id
        client = twitch.TwitchHelix(client_id=APP_ID, oauth_token=token)

        # get user ids
        users = client.get_users(login_names=[channel_name])

        clipGetter = ClipGetter()

        dirs = clipGetter.get_clips(users[0], client, clip_dir='temp/clips', clip_count=clip_count)

        # now lets make the video
        video_maker = VideoMaker(dirs, output_dir, transition_dir=transition_dir)

        video_maker.make_video()




