# a class that manages a single clip

import datetime

class Clip:
    def __init__(self, clip_dir, clip_id, streamer_id, game_id, streamer_name, time, duration, view_count=None, title=None, vod_offset=None, video_id=None):
        self.clip_dir = clip_dir
        self.clip_id = clip_id
        self.streamer_id = streamer_id
        self.game_id = game_id
        self.streamer_name = streamer_name
        self.view_count = view_count
        self.time = time
        self.duration = duration
        self.title = title
        self.vod_offset = vod_offset
        self.video_id = video_id

    def to_string(self):
        return f'{self.clip_dir}, {self.clip_id}, {self.streamer_id}, {self.game_id}, {self.streamer_name}, {self.time}, {self.duration}, {self.view_count}, {self.title}, {self.vod_offset}, {self.video_id}'
    
    # a static method that takes in a string and returns a clip object
    @staticmethod
    def from_string(string):
        split = string.split(', ')

        # convert types
        split[4] = datetime.datetime.strptime(split[4], '%Y-%m-%d %H:%M:%S')
        split[5] = float(split[5])
        split[6] = split[10].strip('\n')

        return Clip(split[0], split[1], split[2], split[3], split[4], split[5], split[6], split[7], split[8], split[9], split[10])
    
    @staticmethod
    def from_twitch_api_clip(clip, clip_dir):
        return Clip(clip_dir, clip['id'], clip['broadcaster_id'], clip['game_id'], clip['broadcaster_name'], datetime.datetime.fromisoformat(str(clip['created_at'])), clip['duration'], clip['view_count'], clip['title'], clip['vod_offset'], clip['video_id'])
