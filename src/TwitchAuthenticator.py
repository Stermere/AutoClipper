# a class that handles authentication with the twitch api

import twitch 
from twitchAPI import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.types import AuthScope
import json

class TwitchAuthenticator:
    # load the app credentials from a file named app_credentials.txt
    # first line the app id, second line the app secret
    with open('config.json', 'r') as f:
        config = json.load(f)
    APP_ID = config['TWITCH_APP_ID']
    APP_SECRET = config['TWITCH_APP_SECRET']
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
        self.client = twitch.TwitchHelix(client_id=TwitchAuthenticator.APP_ID, oauth_token=self.token)

        # set up the refresh callbacks
        self.twitch.app_auth_refresh_callback = self.app_refresh
        self.twitch.user_auth_refresh_callback = self.user_refresh

    async def user_refresh(self, token, refresh_token):
        self.token = token
        self.refresh_token = refresh_token
        await self.twitch.set_user_authentication(self.token, TwitchAuthenticator.USER_SCOPE, self.refresh_token)
        self.client = twitch.TwitchHelix(client_id=TwitchAuthenticator.APP_ID, oauth_token=self.token)

        print(f'New user token: {token}')

    async def app_refresh(self, token):
        self.token = token
        print(f'New app token: {token}')

    async def end_session(self):
        # end the user session
        await self.twitch.close()

    def get_users_from_names(self, usernames):
        # get the user id from the username
        user = self.client.get_users(login_names=usernames)
        return user
    
    def get_users_from_ids(self, user_ids):
        # get the username from the user id
        user = self.client.get_users(ids=user_ids)
        return user
    
    def get_streams(self, user_ids):
        # get the streams for the user
        streams = self.client.get_streams(user_ids=user_ids)
        return streams

    def get_token(self):
        return self.token
    
    def get_client(self):
        return self.client
    
    def get_twitch(self):
        return self.twitch