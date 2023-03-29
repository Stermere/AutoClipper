# a simple script to make a Youtube video from the most popular clips of a streamer 
# and or a list of clips

import asyncio
from twitchAPI import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.types import AuthScope
from twitch import TwitchHelix
from twitch import TwitchClient
import twitch
from src.ClipGetter import ClipGetter
import sys
import os

# app credentials (I should not hardcode this)
APP_ID = 'lgsocblmqju7q5g2ipm9ixww1jwkbx'
APP_SECRET = 'ttyixaqh5gpuc9z8e2fl4qasb3uxot'
USER_SCOPE = [AuthScope.CHAT_READ, AuthScope.CLIPS_EDIT]

async def main(argv):
    if len(argv) < 2 or argv[1] == '-h' or argv[1] == '--help':
        print('Usage: python3 MakeVideo.py <channel_name>')
        return

    # set up twitch api instance and add user authentication with some scopes
    twitch_ = await Twitch(APP_ID, APP_SECRET)
    auth = UserAuthenticator(twitch_, USER_SCOPE)
    token, refresh_token = await auth.authenticate()
    await twitch_.set_user_authentication(token, USER_SCOPE, refresh_token)

    # create helix instance to get user id
    client = twitch.TwitchHelix(client_id=APP_ID, oauth_token=token)

    # get user ids
    users = client.get_users(login_names=[argv[1]])

    clipGetter = ClipGetter()

    dirs = clipGetter.get_clips(users[0], client, clip_dir='temp/clips', clip_count=10)

    print(dirs)

    # now that we have the clips, we can hand it off to the video maker
    # TODO make the video maker

    # delete the clips and temp folder
    for dir_ in dirs:
        os.remove(dir_)
        
if __name__ == '__main__':
    asyncio.run(main(sys.argv))