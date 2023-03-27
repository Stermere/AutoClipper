# a class that handles computing statistics from the chat messages
# stats include: average sentiment over the last minute, average message length per minute,
# average message count per minute, and the user count per minute

import datetime
from copy import deepcopy
import os
import numpy as np

USE_FROM_CSV = 200
CLIP_THRESHOLD = 0.80

# one class handles one stream of chat messages
class ChatStats:
    def __init__(self, channel, interval=60):
        # the channel this stats object is for
        self.channel = channel

        # the stats will be computed every interval seconds
        self.interval = interval

        # keep track of the last time we updated the stats
        self.msg_buffer = []

        # keep a window of the current log interval
        self.last_update = datetime.datetime.now()
        self.next_update = self.last_update + datetime.timedelta(seconds=self.interval)

        # store the stats in a list
        self.stats = []

        # load the stats from the file if it exists
        if os.path.exists(f'chat_data'):
            self.stats = self.from_csv(f'chat_data/{self.channel}_chat_stats.csv')


        # keep track of whether we should clip or not (this is only set to true by this class)
        self.should_clip = False


    # returns the boolean value of should_clip
    # and sets should_clip to false
    def get_should_clip(self):
        return_val = self.should_clip 
        self.should_clip = False
        return return_val
    
    
    def set_should_clip(self, should_clip):
        self.should_clip = should_clip

    # get the stats
    def get_stats(self):
        return deepcopy(self.stats)

    # add a message to the buffer
    # the message is a tuple of (ChatMessage, sentiment, datetime)
    def add_message(self, message):
        self.msg_buffer.append(message)

        # update the stats (does nothing if the interval hasn't passed)
        self.update()

    # set the should_clip flag to true if the chat spiked
    def check_for_clip(self):
        if len(self.stats) > 20:
            # TODO - remove these hard coded values
            max_chats = max([stat.message_count for stat in self.stats])
            if self.stats[-1].message_count > max_chats * CLIP_THRESHOLD:
                self.should_clip = True
                print(f'\tregistered clip on: {self.channel} with {self.stats[-1].message_count} messages')

    # update the stats
    def update(self):
        # get the time to cut off the messages
        now = datetime.datetime.now()

        # if the last update was less than LOG_INTERVAL seconds ago, don't update
        if now < self.next_update:
            return

        # get the messages from the buffer
        messages = [msg for msg in self.msg_buffer if (self.next_update - msg[2]).total_seconds() < self.interval]

        # clear old messages from the buffer
        self.msg_buffer = [msg for msg in self.msg_buffer if (self.next_update - msg[2]).total_seconds() >= self.interval]

        # compute the stats
        sentiment = sum([msg[1]['compound'] for msg in messages]) / len(messages)
        message_length = sum([len(msg[0].text) for msg in messages]) / len(messages)
        message_count = len(messages)
        message_count_no_repeats = len(set([msg[0].text for msg in messages]))
        text_data  = [f'{msg[0].text}' for msg in messages]
        text_data = [msg.encode('ascii', 'ignore').decode('ascii') for msg in text_data]

        # add the stats to the list
        self.stats.append(ChatStatsEntry(self.next_update, sentiment, text_data, message_length, message_count, message_count_no_repeats))

        # update the last update time (for loop in case we missed an update due to offline time)
        while now >= self.next_update:
            self.last_update = self.next_update
            self.next_update = self.last_update + datetime.timedelta(seconds=self.interval)

        # check if we should clip
        self.check_for_clip()

    # loads the stats from a file in csv format
    def from_csv(self, filename):
        # check if the file has any data
        if not os.path.exists(filename) or os.stat(filename).st_size == 0:
            return []
        
        # Read in the data from the csv file
        my_dtype = np.dtype([('float_field', float), ('float_field2', float), ('int', int), ('int2', int), ('datetime', 'datetime64[ns]'), ('list', 'U10000')])
        stats = np.genfromtxt(filename, delimiter='\t', dtype=my_dtype, encoding=None, )

        # if the length is 1 just return an empty list
        if len(stats.shape) == 0:
            return []

        # convert the numpy array to a list of ChatStatsEntry objects
        stats = [ChatStatsEntry(stat[4], stat[0], stat[5], stat[1], stat[2], stat[3]) for stat in stats]

        # truncate to the last USE_FROM_CSV entries
        if len(stats) > USE_FROM_CSV:
            stats = stats[-USE_FROM_CSV:]
        
        return stats

    # saves the stats to a file in csv format
    def to_csv(self):
        # create the directory if it doesn't exist
        if not os.path.exists('chat_data'):
            os.makedirs('chat_data')

        with open(f'chat_data/{self.channel}_chat_stats.csv', 'w') as f:
            for stat in self.stats:
                f.write(stat.to_string() + '\n')
        

class ChatStatsEntry:
    def __init__(self, time, sentiment, text_data, message_length, message_count, message_count_no_repeats):
        self.time = time
        self.sentiment = sentiment
        self.message_length = message_length
        self.message_count = message_count
        self.message_count_no_repeats = message_count_no_repeats
        self.text_data = text_data

    def to_string(self):
        return f'{self.sentiment}\t {self.message_length}\t {self.message_count}\t {self.message_count_no_repeats}\t {self.time}\t {self.text_data}'
        

    
        
        
