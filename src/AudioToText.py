# given a video clip returns the text in the clip 
import speech_recognition as sr
import noisereduce as nr
from pydub import AudioSegment
from scipy.io import wavfile as wav
from moviepy.editor import VideoFileClip
import os
import numpy as np

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

        # convert the audio to mono
        sound = AudioSegment.from_file(TEMP_AUDIO_FILE, format="wav")
        sound = sound.set_channels(1)

        # match the target amplitude
        sound = self.match_target_amplitude(sound, -20.0)

        # export the audio file
        sound.export(TEMP_AUDIO_FILE, format="wav")

        # reshape the data so that it can be fed into the noise reduction algorithm
        rate, data = wav.read(TEMP_AUDIO_FILE)
        orig_shape = data.shape 
        data = np.reshape(data, (1, -1))

        # perform noise reduction
        reduced_noise = nr.reduce_noise(y=data, sr=rate, n_fft=512)

        # rewrite the audio file
        reduced_noise = np.reshape(reduced_noise, orig_shape)
        wav.write(TEMP_AUDIO_FILE, rate, reduced_noise)


        with sr.AudioFile(TEMP_AUDIO_FILE) as source:
            # listen for the data (load audio to memory)
            audio_data = self.recognizer.record(source)

        try:
            self.text = self.recognize_vosk(audio_data)
        finally:
            # delete the temp audio file
            os.remove(TEMP_AUDIO_FILE)

        return self.text
    
    # yoinked from a library I found but it didn't quite do what I needed so I modified it
    # TODO instead of yoinking I should make a PR to the library
    def recognize_vosk(self, audio_data):
        from vosk import Model, KaldiRecognizer
        
        if not hasattr(self, 'vosk_model'):
            if not os.path.exists("model"):
                return "Please download the model from https://github.com/alphacep/vosk-api/blob/master/doc/models.md and unpack as 'model' in the current folder."
            self.vosk_model = Model("model")

        rec = KaldiRecognizer(self.vosk_model, 16000)
        rec.SetWords(True)

        rec.AcceptWaveform(audio_data.get_raw_data(convert_rate=16000, convert_width=2))
        result = rec.Result()
        
        return result
    
    # a helper function to match the target amplitude of the audio file
    def match_target_amplitude(self, sound, target_dBFS):
        change_in_dBFS = target_dBFS - sound.dBFS
        return sound.apply_gain(change_in_dBFS)
    
# test the class
if __name__ == "__main__":
    audio_to_text = AudioToText()
    text = audio_to_text.convert_video_to_text("temp/output/filian2023-04-05-17-54-25.mp4")
    print(text)
