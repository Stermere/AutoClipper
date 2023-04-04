# given a video clip returns the text in the clip 
import speech_recognition as sr
from moviepy.editor import VideoFileClip
import os

TEMP_AUDIO_FILE = "temp/audio.wav"

class AudioToText():
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.text = None
        self.audio = None

    def convert_video_to_text(self, video_path):
        # open the mp4 and extract the audio
        video = VideoFileClip(video_path)
        audio = video.audio

        # save the audio as a wav file
        audio.write_audiofile(TEMP_AUDIO_FILE, codec="pcm_s16le")

        with sr.AudioFile(TEMP_AUDIO_FILE) as source:
            # listen for the data (load audio to memory)
            audio_data = self.recognizer.record(source)

        try:
            self.text = self.recognize_vosk(audio_data)

            # get the time stamp of each word
        finally:
            # delete the temp audio file
            os.remove(TEMP_AUDIO_FILE)

        return self.text
    
    # yoinked from a library I found but it didn't quite do what I needed so I modified it
    def recognize_vosk(self, audio_data):
        from vosk import Model, KaldiRecognizer
        
        if not hasattr(self, 'vosk_model'):
            if not os.path.exists("model"):
                return "Please download the model from https://github.com/alphacep/vosk-api/blob/master/doc/models.md and unpack as 'model' in the current folder."
            self.vosk_model = Model("model")

        rec = KaldiRecognizer(self.vosk_model, 16000)
        rec.SetWords(True)

        result = None
        if rec.AcceptWaveform(audio_data.get_raw_data(convert_rate=16000, convert_width=2)):
            result = rec.Result()
        
        return result
    
# test the class
if __name__ == "__main__":
    audio_to_text = AudioToText()
    text = audio_to_text.convert_video_to_text("clips/Shylily_MushyExuberantAubergineOneHand-KcZIN0OFUdVm7TAm.mp4")
    print(text)
