# handles the saving and loading the the latest youtube video created by the bot 
# is usful for automatic scheduling of the videos

import json
import datetime
from src.Clip import Clip


class YoutubeHistory:
    SAVE_PATH = 'clip_info/uploadedVideos.json'

    def __init__(self) -> None:
        self.history = []
        self.loadHistory()

    def loadHistory(self):
        try:
            with open(YoutubeHistory.SAVE_PATH, 'r') as f:
                self.history = json.load(f)
        except:
            print("No history file found")
        
    def saveHistory(self):
        # only save entries newer than 1 month
        self.history = [video for video in self.history if datetime.datetime.fromisoformat(video["upload_time"]) > datetime.datetime.today() - datetime.timedelta(days=30)]
        with open(YoutubeHistory.SAVE_PATH, 'w') as f:
            json.dump(self.history, f)

    def addVideo(self, relevant_clips, upload_time):
        if type(relevant_clips) != list or len(relevant_clips) == 0:
            Exception("relevant_clips must be a non-empty list")
        if type(relevant_clips[0]) != Clip:
            Exception("relevant_clips must be a list of Clip objects")

        relevant_clips = [clip.to_string() for clip in relevant_clips]

        self.history.append({"clips" : relevant_clips, "upload_time" : upload_time.isoformat()})
        self.saveHistory()

    def getLatestVideo(self):
        if len(self.history) > 0:
            self.history[-1]
            return [Clip.from_string(clip) for clip in self.history[-1]["clips"]], datetime.datetime.fromisoformat(self.history[-1]["upload_time"])
        else:
            return None
        
    # checks that the clip in question has not already been uploaded
    def checkForClip(self, clip):
        for video in self.history:
            if clip.to_string() in video["clips"]:
                return True
        return False