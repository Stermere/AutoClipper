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
from src.ClipCompiler import ClipCompiler
from src.Clip import Clip
from src.TwitchAuthenticator import TwitchAuthenticator
import concurrent.futures
import os

# load the app credentials from a file named app_credentials.txt
# first line the app id, second line the app secret
with open('app_credentials.txt', 'r') as f:
    APP_ID = f.readline().strip()
    APP_SECRET = f.readline().strip()

# load the target channels from a file named target_channels.txt
# each channel should be on a new line
with open('target_channels.txt', 'r') as f:
    TARGET_CHANNELS = f.readlines()
    TARGET_CHANNELS = [channel.strip() for channel in TARGET_CHANNELS]
#TARGET_CHANNELS = ['filian']

USER_SCOPE = [AuthScope.CHAT_READ, AuthScope.CLIPS_EDIT]
DEFAULT_READY_CHANNEL_CSV = 'clip_info/saturated_channels.csv'
TIME_WINDOW = 10
STAT_INTERVAL = 1
PRINT_CHAT = False

# this is the main class that will handle the chat bot
class ChatClassifier:
    # takes a twitch user object and returns the path to the csv file that stores the clip info for that user
    CLIP_INFO_SAVE_NAME = lambda x : f'clip_info/{x.display_name}.csv'
    CLIP_INFO_DIR = 'clip_info'

    # prepare a dictionary to store the messages in by channel
    def __init__(self):
        self.chats = {}
        for channel in TARGET_CHANNELS:
            self.chats[channel] = ChatStats(channel, time_window=TIME_WINDOW, stat_interval=STAT_INTERVAL)
        self.live_channels = []

        # we will store the twitch api instance, the authentication instance, the chat instance and the tokens here
        self.chat = None
        self.users = None

        # authenticator 
        self.authenticator = None

        # initialize the sentiment analyzer (VADER)
        self.analyzer = SentimentIntensityAnalyzer()

        # clip getter
        self.clip_getter = ClipGetter()

        # clip compiler
        self.clipCompiler = ClipCompiler()

        # loops 
        self.second_loop_task = None
        self.minute_loop_task = None


    # return a list of messages in a channel between start_time and end_time
    # each message is a tuple of (ChatMessage, sentiment, datetime)
    def get_messages(self, start_time, end_time, channel):
        return [msg for msg in self.chats[channel] if start_time <= msg[2] <= end_time]
        
    async def quit(self):
        # now we can close the chat bot and the twitch api client
        self.chat.stop()
        await self.authenticator.end_session()
        
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
            print(('\r' + msg.text)[:50], end='')

    async def second_loop(self):
        while True:
            # wait a second
            await asyncio.sleep(1)

            # check if any channel should be clipped
            await self.check_for_clip()

    # runs once per minute
    async def minute_loop(self):
        while True:
            # wait a minute
            await asyncio.sleep(60)

             # check who is live and only clip those who are live
            streams = self.authenticator.get_streams(user_ids=[user.id for user in self.users])
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
            with open(DEFAULT_READY_CHANNEL_CSV, 'a') as f:
                for channel in old:
                    # write the csv file directory
                    user = self.authenticator.get_users_from_names([channel])[0]
                    f.write(ChatClassifier.CLIP_INFO_SAVE_NAME(user) + '\n')
            
    # gets called every time there is a subscription event
    async def on_sub(self, sub: ChatSub):
       pass

    # this will be called whenever the !reply command is issued
    async def test_command(self, cmd: ChatCommand):
        print(f'Command {cmd.command} was issued by {cmd.user.name} in {cmd.room.name}')

    # checks if any channel should be clipped and clips it if so
    # TODO make this better (make it so all clips are clipped at the same time)
    async def check_for_clip(self):
        clips = []
        for channel in TARGET_CHANNELS:
            # check if the channel is live
            if not (channel in self.live_channels):
                continue

            # skip if the channel should not be clipped
            if not self.chats[channel].get_should_clip():
                continue

            # get the user object of the channel
            user = None
            for u in self.users:
                if u['login'] == channel:
                    user = u
                    break

            # check if we found the user object
            if user is None:
                print(f'Failed to find user object for {channel}')
                continue

            # try to create a clip until it works or a fatal error occurs
            try:
                clip = await self.authenticator.get_twitch().create_clip(user.id, has_delay=True)

            # exception handling
            except TwitchResourceNotFound as e:
                print(f'Failed to create clip for {user.display_name} (Streamer not live)')
                continue
            except TwitchBackendException as e:
                print(f'Failed to create clip for {user.display_name} (Twitch backend error)')
                continue
            except KeyError as e:
                print(f'Failed to create clip for {user.display_name} (Probably don\'t have perms)')
                continue

            print(f'Clip created ({user.display_name}): {clip.edit_url}')

            # add the clip to the list of clips to download
            clips.append((clip, user))

            # update the should clip value
            self.chats[channel].set_should_clip(False)

            with open('clip_edit_urls.csv', 'a') as f:
                f.write(f'{clip.edit_url}, {self.chats[channel].stats[-1].message_count}\n')

        # get the clip from the twitch api and store its info in a file
        # if after 15 seconds the clip is still not ready, assume it failed (this is from twitch them selves but
        # seems to be a bit untrue sometimes)
        if (clips != []):
            await asyncio.sleep(30)
            # clip_info is the clips objects from the twitch api not Clip.py
            clip_info = self.authenticator.get_client().get_clips(clip_ids=[clip.id for clip, user in clips])

            # replace the clip objects with the clip objects from the twitch api
            for i in range(len(clips)):
                clip = None
                for c in clip_info:
                    if c['broadcaster_id'] == clips[i][1]['id']:
                        clip = c
                        break
                clips[i] = (clip, clips[i][1])

            for clip, user in clips:
                # download the clip
                clip_dir = self.clip_getter.download_clip(clip, user)

                # convert to a clip object for easy saving and loading
                clip_obj = Clip(clip_dir, clip['id'], clip['broadcaster_id'], clip['broadcaster_name'], datetime.datetime.fromisoformat(str(clip['created_at'])), clip['duration'], clip['view_count'])

                # add the clip info to the csv file for that streamer
                save_name = ChatClassifier.CLIP_INFO_SAVE_NAME(user)
                if not os.path.exists(ChatClassifier.CLIP_INFO_DIR):
                    os.makedirs(ChatClassifier.CLIP_INFO_DIR, exist_ok=True)

                with open(save_name, 'a') as f:
                    f.write(clip_obj.to_string() + '\n')
                
    # this is where we set up the bot
    async def run(self):
        # initialize the twitch authenticator
        self.authenticator = TwitchAuthenticator()

        # authenticate the bot
        await self.authenticator.authenticate()

        # get user ids
        self.users = self.authenticator.get_users_from_names(TARGET_CHANNELS)

        # check who is live and only clip those who are live
        streams = self.authenticator.get_streams([user.id for user in self.users])
        self.live_channels = [stream['user_login'] for stream in streams]
        print(f'Live channels: {self.live_channels}')

        # create some loops
        self.minute_loop_task = asyncio.create_task(self.minute_loop())
        self.second_loop_task = asyncio.create_task(self.second_loop())

        # create chat instance
        self.chat = await Chat(self.authenticator.get_twitch())

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


#   TODO's  DONE 1. make the video maker class
#           2. make a config file for all the settings            

# entry point
def main(args):
    reader = ChatClassifier()
    asyncio.run(reader.run())

    # before we quit, we need to save the data
    for channel in TARGET_CHANNELS:
        reader.chats[channel].to_csv()

    asyncio.run(reader.quit())

