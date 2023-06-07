# handles the saving and loading the the latest youtube video created by the bot 
# is usful for automatic scheduling of the videos

import json


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
        with open(YoutubeHistory.SAVE_PATH, 'w') as f:
            json.dump(self.history, f)

    def addVideo(self, relevant_clips, upload_time):
        if type(relevant_clips) != list:
            Exception("relevant_clips must be a list")
        self.history.append({"clips" : relevant_clips, "upload_time" : upload_time})
        self.saveHistory()

    def getLatestVideo(self):
        if len(self.history) > 0:
            return self.history[-1]
        else:
            return None
        
    # checks that the clip in question has not already been uploaded
    def checkForClip(self, clip):
        for video in self.history:
            if clip in video["clips"]:
                return True
        return False