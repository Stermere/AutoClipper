# a class that handles authentication with the twitch api

import twitch 
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.type import AuthScope
from twitchAPI.helper import limit
from src.Config import Config

class TwitchAuthenticator:
    # load the app credentials from a file named app_credentials.txt
    # first line the app id, second line the app secret
    config = Config()
    APP_ID = config.getValue('TWITCH_APP_ID')
    APP_SECRET = config.getValue('TWITCH_APP_SECRET')
    USER_SCOPE = [AuthScope.CHAT_READ, AuthScope.CLIPS_EDIT]

    def __init__(self):
        # init class variables
        self.twitch = None
        self.auth = None
        self.token, self.refresh_token = None, None
        self.client = None

    # must be called before any other method
    async def authenticate(self):
        # set up twitch api instance and add user authentication with some scopes
        self.twitch = await Twitch(TwitchAuthenticator.APP_ID, TwitchAuthenticator.APP_SECRET)
        self.auth = UserAuthenticator(self.twitch, TwitchAuthenticator.USER_SCOPE)
        self.token, self.refresh_token = await self.auth.authenticate()
        await self.twitch.set_user_authentication(self.token, TwitchAuthenticator.USER_SCOPE, self.refresh_token)

        # create helix instance to get user id
        self.client = twitch.Helix(client_id=TwitchAuthenticator.APP_ID, client_secret=TwitchAuthenticator.APP_SECRET, bearer_token=self.token)

        # set up the refresh callbacks
        self.twitch.app_auth_refresh_callback = self.app_refresh
        self.twitch.user_auth_refresh_callback = self.user_refresh

    async def user_refresh(self, token, refresh_token):
        self.token = token
        self.refresh_token = refresh_token
        await self.twitch.set_user_authentication(self.token, TwitchAuthenticator.USER_SCOPE, self.refresh_token)
        self.client = twitch.Helix(client_id=TwitchAuthenticator.APP_ID, bearer_token=self.token)

        print(f'New user token: {token}')

    async def app_refresh(self, token):
        self.token = token
        print(f'New app token: {token}')

    async def end_session(self):
        # end the user session
        await self.twitch.close()

    def get_users_from_names(self, usernames):
        # get the user id from the username
        user = self.client.users(usernames)
        return user
    
    def get_users_from_ids(self, user_ids):
        # get the username from the user id
        user = self.client.users(user_ids)
        return user
    
    def get_streams(self, user_ids):
        # get the streams for the user
        streams = self.client.get_streams(user_ids=user_ids)
        return streams
    
    def get_videos_from_ids(self, video_ids):
        videos = self.client.videos(user_ids=video_ids)
        return videos
    
    async def get_clips(self, user_id, started_at=None, ended_at=None):    
        # get the clips for the user
        # clips is AsyncGenerator[Clip, None]:
        clips = self.twitch.get_clips(broadcaster_id=user_id, started_at=started_at, ended_at=ended_at)\
            
        # convert the AsyncGenerator to a list
        clip_list = []
        async for clip in limit(clips, Config().getValue('VIDEOS_TO_FETCH')):
            clip_list.append(clip)
        
        return clip_list
    
    def get_token(self):
        return self.token
    
    def get_client(self):
        return self.client
    
    def get_twitch(self):
        return self.twitch