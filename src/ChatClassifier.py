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
import concurrent.futures
from multiprocessing import Process
import os

# load the app credentials from a file named app_credentials.txt
# first line the app id, second line the app secret
with open('app_credentials.txt', 'r') as f:
    APP_ID = f.readline().strip()
    APP_SECRET = f.readline().strip()

USER_SCOPE = [AuthScope.CHAT_READ, AuthScope.CLIPS_EDIT]
TARGET_CHANNELS = ['miyune', 'vedal987', 'shylily', 'filian', 'moistcr1tikal', 'lirik', 'timthetatman', 'sykkuno', 'sinder', 'ironmouse', 'vei'
                   'xqc', 'esl_csgo', 'shroud', 'hasanabi']
#TARGET_CHANNELS = ['shroud']
TIME_WINDOW = 10
STAT_INTERVAL = 1

# optional - print the chat messages to the console but carraige return before each message
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

        # clip compiler
        self.clipCompiler = ClipCompiler()

        # clip editor

        # loops 
        self.second_loop_task = None
        self.minute_loop_task = None
        self.five_minute_loop_task = None


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
                # TODO
                pass

    # calls the clip compiler and makes videos when enough clips have rolled in
    async def video_loop(self):
        while True:
            # start a pool of processes one for each channel
            workers = []
            for i, user in enumerate(self.users):
                workers.append(Process(target=self.clipCompiler.merge_clips, args=(ChatClassifier.CLIP_INFO_SAVE_NAME(user),)))
                workers[i].start()

            await asyncio.sleep(60)

            # join the processes
            for user in self.users:
                workers[i].join()

            # TODO call a function to see if a video should be made

            
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

            self.chats[channel].set_should_clip(False)

            # try to create a clip
            try:
                clip = await self.twitch.create_clip(user.id, has_delay=True)

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

            with open('clip_edit_urls.csv', 'a') as f:
                f.write(f'{clip.edit_url}, {self.chats[channel].stats[-1].message_count}\n')

        # get the clipa from the twitch api and download it
        # if after 15 seconds the clip is still not ready, assume it failed (from twitch themselves)
        if (clips != []):
            print(f'\tWaiting for twitch...')
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
                clip_obj = Clip(clip_dir, clip['id'], clip['broadcaster_id'], clip['broadcaster_name'], datetime.datetime.fromisoformat(str(clip['created_at'])), clip['duration'], clip['view_count'])

                # add the clip info to the csv file for that streamer
                save_name = ChatClassifier.CLIP_INFO_SAVE_NAME(user)
                if not os.path.exists(ChatClassifier.CLIP_INFO_DIR):
                    os.makedirs(ChatClassifier.CLIP_INFO_DIR, exist_ok=True)

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

        # create some loops
        self.minute_loop_task = asyncio.create_task(self.minute_loop())
        self.five_minute_loop_task = asyncio.create_task(self.video_loop())
        self.second_loop_task = asyncio.create_task(self.second_loop())

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


#   TODO's  1. make the video maker class
#           2. The moment a streamer is no longer live, start a timer for n minutes
#              and then download the top 10 clips from the last length of stream (high quality human made clips (presumably))
#           3. upload the video to youtube 
#           4. find a way to automatically name our clips (drastically improves view count)

# entry point
def main(args):
    reader = ChatClassifier()
    asyncio.run(reader.run())

    # before we quit, we need to save the data
    for channel in TARGET_CHANNELS:
        reader.chats[channel].to_csv()

    asyncio.run(reader.quit())

