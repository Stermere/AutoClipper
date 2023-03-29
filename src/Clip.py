# a class that manages a single clip

import datetime

class Clip:
    def __init__(self, clip_dir, clip_id, streamer_id, streamer_name, time, duration, view_count=None):
        self.clip_dir = clip_dir
        self.clip_id = clip_id
        self.streamer_id = streamer_id
        self.streamer_name = streamer_name
        self.view_count = view_count
        self.time = time
        self.duration = duration

    def to_string(self):
        return f'{self.clip_dir}, {self.clip_id}, {self.streamer_id}, {self.streamer_name}, {self.time}, {self.duration}, {self.view_count}'
    
    # a static method that takes in a string and returns a clip object
    @staticmethod
    def from_string(string):
        split = string.split(', ')

        # convert types
        split[4] = datetime.datetime.strptime(split[4], '%Y-%m-%d %H:%M:%S')
        split[5] = float(split[5])
        split[6] = split[6].strip('\n')

        return Clip(split[0], split[1], split[2], split[3], split[4], split[5], split[6])