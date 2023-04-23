# handles all the interaction with WhisperX for transcriptions and uderance times

import whisperx
import whisper

from moviepy.editor import VideoFileClip

TEMP_AUDIO_FILE = "temp/audio.wav"
DEFAULT_LANGUAGE = "en"
DEFAULT_DEVICE = "cuda"

class WhisperInterface:
    def __init__(self, device=DEFAULT_DEVICE):
        self.device = device
        self.model = whisper.load_model("medium", self.device)

    # returns a touple with the first element being the word segments and the second being the no speech probability
    def transcription(self, audio_file):
        # transcribe with original whisper
        result = self.model.transcribe(audio_file, initial_prompt="Umm, let me think like, hmm... Okay, here's what I'm, like, thinking.")

        # load alignment model and metadata TODO fix language not being found all the time
        model_a, metadata = whisperx.load_align_model(language_code=DEFAULT_LANGUAGE, device=self.device)

        # align whisper output
        try:
            result_aligned = whisperx.align(result["segments"], model_a, metadata, audio_file, self.device)
        except ValueError as e:
            print(e)
            return None


        return result_aligned["word_segments"]
    
    # returns the same as transcription but takes a video file instead of an audio file
    def transcribe_from_video(self, video_file):
        audio = VideoFileClip(video_file).audio
        audio.write_audiofile(TEMP_AUDIO_FILE)

        return self.transcription(TEMP_AUDIO_FILE)
    
if __name__ == "__main__":
    wi = WhisperInterface()
    segs = wi.transcription("test.wav")
    print(segs)
