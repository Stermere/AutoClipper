# handles all the interaction with WhisperX for transcriptions and uderance times

import whisperx
import whisper

from moviepy.editor import VideoFileClip

TEMP_AUDIO_FILE = "temp/audio.wav"
DEFAULT_LANGUAGE = "en"

class WhisperInterface:
    def __init__(self, device="cpu"):
        self.device = device
        self.model = whisper.load_model("large", self.device)

    def transcription(self, audio_file):
        # transcribe with original whisper
        result = self.model.transcribe(audio_file)

        # load alignment model and metadata TODO fix language not being found all the time
        model_a, metadata = whisperx.load_align_model(language_code=DEFAULT_LANGUAGE, device=self.device)

        # align whisper output
        result_aligned = whisperx.align(result["segments"], model_a, metadata, audio_file, self.device)

        # print the text alone
        text = ""
        for segment in result_aligned["segments"]:
            text += segment["text"] + " "

        print(text)

        return result_aligned["word_segments"]
    
    def transcribe_from_video(self, video_file):
        audio = VideoFileClip(video_file).audio
        audio.write_audiofile(TEMP_AUDIO_FILE)

        return self.transcription(TEMP_AUDIO_FILE)
    
if __name__ == "__main__":
    wi = WhisperInterface()

    wi.transcription("test.wav")