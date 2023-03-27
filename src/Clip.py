# a class that manages a single clip

class Clip:
    def __init__(self, clip_dir, clip_id, streamer_id, streamer_name, view_count=None):
        self.clip_dir = clip_dir
        self.clip_id = clip_id
        self.streamer_id = streamer_id
        self.streamer_name = streamer_name
        self.view_count = view_count

    def to_string(self):
        return f'{self.clip_dir}, {self.clip_id}, {self.streamer_id}, {self.streamer_name}, {self.view_count}'
    
    def from_string(self, string):
        split = string.split(', ')
        self.clip_dir = split[0]
        self.clip_id = split[1]
        self.streamer_id = split[2]
        self.streamer_name = split[3]
        self.view_count = split[4]
        self.messages = split[5]