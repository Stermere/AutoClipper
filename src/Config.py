# A class that contains all the configuration variables for the clipper
# application. This class is a singleton, so it can be accessed from anywhere

import os
import json

class Config:
    config_path = "config.json"

    default_config = {
        "TRANSITION_VOLUME": 0.1,
        "TRANSITION_SUBCLIP": [2, 2.5],
        "OUTPUT_RESOLUTION": [1920, 1080],
        "DEFAULT_TRANSITION_DIR": "video_assets/transition.mp4",
        "DEFAULT_OUTPUT_DIR": "temp/output/",
        "DEFAULT_CLIP_DIR": "temp/clips/",
        "REQUIRED_VIDEO_LENGTH": 15,
        "MAX_VIDEO_LENGTH": 180,
        "EDGE_TRIM_TIME": 0.4,
        "START_TRIM_TIME": 1.2,
        "TRANSITION_THRESHOLD": 15,
        "VIDEOS_TO_FETCH": 10,
        "TWITCH_APP_ID": "",
        "TWITCH_APP_SECRET": "",
        "OPENAI_API_KEY": "",
        "DEFAULT_MODEL": "gpt-3.5-turbo",
        "USE_OPENAI": False,
        "USE_LLAMA2": True,
        "FADE_TIME": 1.0,
        "TRANSITION_FADE_TIME": 0.3,
        "NO_CUT_STREAMERS": []
    }

    # if the config file doesn't exist create it
    if not os.path.exists(config_path):
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=4)

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(Config, cls).__new__(cls)
            cls.instance._load_config()
        return cls.instance
    
    def _load_config(self):
        with open(self.config_path) as f:
            self.config = json.load(f)

    # get a config value
    def getValue(self, key):
        if key in self.config:
            return self.config[key]
        elif key in self.default_config:
            return self.default_config[key]
        else:
            raise Exception("Key {} not found in config".format(key))
        
    # set a config value
    def setValue(self, key, value):
        self.config[key] = value

        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=4)