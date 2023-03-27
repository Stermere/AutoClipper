# a class that attempts to find the most exiting parts of a twitch stream and clip them
from twitchAPI import Twitch
from twitchAPI.types import TwitchResourceNotFound, TwitchBackendException
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.types import AuthScope, ChatEvent
from twitchAPI.chat import Chat, EventData, ChatMessage, ChatSub, ChatCommand
import twitch
import asyncio
import datetime
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from src.ChatStats import ChatStats
from src.ClipGetter import ClipGetter
from src.Clip import Clip
import concurrent.futures
import os

# app credentials (I should not hardcode this)
# TODO TODO - put this in a config file
APP_ID = 'lgsocblmqju7q5g2ipm9ixww1jwkbx'
APP_SECRET = 'ttyixaqh5gpuc9z8e2fl4qasb3uxot'
USER_SCOPE = [AuthScope.CHAT_READ, AuthScope.CLIPS_EDIT]
TARGET_CHANNELS = ['miyune', 'vedal987', 'filian', 'shylily', 'moistcr1tikal', 'lirik', 'timthetatman', 'sykkuno', 'sinder', 'ironmouse', 'vei']
STAT_INTERVAL = 10

LLM_STRING = 'Lets play a game! The above list is a set of twitch chats on a channel, these chats come from the previous 30 seconds of the stream. From that I need you to identify if the previous 30 seconds are a exiting part of the stream or not. You should be selective about what parts are exiting. You will reply with a yes if its is exiting and no otherwise, After the yes or no response you may write a Youtube video title that describes what happened during these chats. Please format your response in the following way: decision, Video title. You should ignore inappropriate chats and do not mention them as they are better off forgotten, also Do NOT reply with anything else!'

PRINT_CHAT = False

# this is the main class that will handle the chat bot
class ChatClassifier:
    # prepare a dictionary to store the messages in by channel
    def __init__(self):
        self.chats = {}
        for channel in TARGET_CHANNELS:
            self.chats[channel] = ChatStats(channel, STAT_INTERVAL)
        self.live_channels = []

        # we will store the twitch api instance, the authentication instance, the chat instance and the tokens here
        self.twitch = None
        self.auth = None
        self.chat = None
        self.users = None
        self.token, self.refresh_token = None, None
        self.client = None

        # initialize the sentiment analyzer (VADER)
        self.analyzer = SentimentIntensityAnalyzer()

        # clip getter
        self.clip_getter = ClipGetter()

        # loops 
        self.minute_loop_task = None


    # return a list of messages in a channel between start_time and end_time
    # each message is a tuple of (ChatMessage, sentiment, datetime)
    def get_messages(self, start_time, end_time, channel):
        return [msg for msg in self.chats[channel] if start_time <= msg[2] <= end_time]
        
    async def quit(self):
        # now we can close the chat bot and the twitch api client
        self.chat.stop()
        await self.twitch.close()
        
    # this will be called when the event READY is triggered, which will be on bot start
    async def on_ready(self, ready_event: EventData):
        print('Bot is ready! lurking...')

        # join our target channels
        await ready_event.chat.join_room(TARGET_CHANNELS)

    # this will be called whenever a message in a channel was send by either the bot OR another user
    async def on_message(self, msg: ChatMessage):
        # check if the channel is live
        if not (msg.room.name in self.live_channels):
            return
        
        # analyze the sentiment of the message
        result = self.analyzer.polarity_scores(msg.text)

        # add the message to the chat stats object
        self.chats[msg.room.name].add_message((msg, result, datetime.datetime.now()))

        # print the message and nothing else
        if PRINT_CHAT:
            print(msg.text)

        # check if any channel should be clipped
        await self.check_for_clip()

    async def minute_loop(self):
        while True:
            # wait a minute
            await asyncio.sleep(60)

             # check who is live and only clip those who are live
            streams = self.client.get_streams(user_ids=[user.id for user in self.users])
            live_channels = [stream['user_login'] for stream in streams]

            # get the difference between the live channels and the channels that are currently live
            new = []
            old = []
            for channel in live_channels:
                if not (channel in self.live_channels):
                    new.append(channel)
            for channel in self.live_channels:
                if not (channel in live_channels):
                    old.append(channel)

            # update the live channels
            if len(new) > 0:
                print(f'New channels live: {new}')
            if len(old) > 0:
                print(f'Old channels offline: {old}')
            self.live_channels = live_channels

            # register any channel that went offline as a channel to get clips from in the future
            for channel in old:
                # TODO call a function that does this 
                pass
            
    # gets called every time there is a subscription event
    async def on_sub(self, sub: ChatSub):
       pass

    # this will be called whenever the !reply command is issued
    async def test_command(self, cmd: ChatCommand):
        print(f'Command {cmd.command} was issued by {cmd.user.name} in {cmd.room.name}')

    # checks if any channel should be clipped and clips it if so
    async def check_for_clip(self):
        clips = []
        for i, channel in enumerate(TARGET_CHANNELS):
            # check if the channel is live
            if not (channel in self.live_channels):
                continue

            if self.chats[channel].get_should_clip():
                # get the user object of the channel
                user = None
                for u in self.users:
                    if u['login'] == channel:
                        user = u
                        break
                # check if we found the user object
                if user is None:
                    print(f'\tFailed to find user object for {channel}')
                    continue

                # try to create a clip
                try:
                    clip = await self.twitch.create_clip(user.id, has_delay=True)

                except TwitchResourceNotFound as e:
                    print(f'\tFailed to create clip for {user.display_name} (Streamer not live)')
                    continue
                except TwitchBackendException as e:
                    print(f'\tFailed to create clip for {user.display_name} (Twitch backend error)')
                    continue
                except KeyError as e:
                    print(f'\tFailed to create clip for {user.display_name} (probably don\'t have perms)')
                    continue

                print(f'\tClip created ({user.display_name}): {clip.edit_url}')

                # add the clip to the list of clips to download
                clips.append((clip, user))

                with open('clip_edit_urls.csv', 'a') as f:
                    f.write(f'{clip.edit_url}, {self.chats[channel].stats[-1].message_count}\n')

        # get the clipa from the twitch api and download it
        # if after 15 seconds the clip is still not ready, assume it failed (from twitch themselves)
        if (clips != []):
            print(f'\tWaiting for clips to be ready...')
            await asyncio.sleep(15)
            for clip, user in clips:
                clip = self.client.get_clips(clip_ids=[clip.id])
                if (len(clip) == 0):
                    print(f'\tFailed to download clip of {user.display_name}')
                    continue
                clip = clip[0]
                clip_dir = self.clip_getter.download_clip(clip, user)


                print(f'\tClip downloaded ({user.display_name}): {clip["url"]}')
                
                # convert to a clip object for easy saving and loading
                clip_obj = Clip(clip_dir, clip['id'], clip['broadcaster_id'], clip['broadcaster_name'], clip['view_count'])

                # add the clip info to the csv file for that streamer
                save_loc = f'clip_info'
                save_name = f'clip_info/{user.display_name}.csv'
                if not os.path.exists(save_loc):
                    os.makedirs(save_loc, exist_ok=True)

                with open(save_name, 'a') as f:
                    f.write(clip_obj.to_string() + '\n')


                
    # this is where we set up the bot
    async def run(self):
        # set up twitch api instance and add user authentication with some scopes
        self.twitch = await Twitch(APP_ID, APP_SECRET)
        self.auth = UserAuthenticator(self.twitch, USER_SCOPE)
        self.token, refresh_token = await self.auth.authenticate()
        await self.twitch.set_user_authentication(self.token, USER_SCOPE, refresh_token)

        # create helix instance to get user id
        self.client = twitch.TwitchHelix(client_id=APP_ID, oauth_token=self.token)

        # get user ids
        self.users = self.client.get_users(login_names=TARGET_CHANNELS)

        # check who is live and only clip those who are live
        streams = self.client.get_streams(user_ids=[user.id for user in self.users])
        self.live_channels = [stream['user_login'] for stream in streams]
        print(f'Live channels: {self.live_channels}')

        # create a loop for checking if a channel is live
        self.minute_loop_task = asyncio.create_task(self.minute_loop())

        # create chat instance
        self.chat = await Chat(self.twitch)

        # register the handlers for the events you want to listen to
        # listen to when the bot is done starting up and ready to join channels
        self.chat.register_event(ChatEvent.READY, self.on_ready)

        # listen to chat messages
        self.chat.register_event(ChatEvent.MESSAGE, self.on_message)

        # listen to channel subscriptions
        self.chat.register_event(ChatEvent.SUB, self.on_sub)

        # you can directly register commands and their handlers, this will register the !reply command
        self.chat.register_command('reply', self.test_command)

        # we are done with our setup, lets start this bot up!
        self.chat.start()

        # wait for the user to press enter to exit
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            await loop.run_in_executor(pool, input, "Press enter to exit\n")


#   TODO's  1. DONE decouple checking if a stream is live from the sub event
#           3. DONE Save the clips directory for a specific streamer in a file for later use 

#           2. find a way to automatically name our clips (drastically improves view count)
#           4. The moment a streamer is no longer live, start a timer for n minutes
#              and then download the top 10 clips from the last length of stream
#           5. compile all clips into a video
#           6. upload the video to youtube 

# entry point
def main(args):
    reader = ChatClassifier()
    asyncio.run(reader.run())

    # before we quit, we need to save the data
    for channel in TARGET_CHANNELS:
        reader.chats[channel].to_csv()

    asyncio.run(reader.quit())

