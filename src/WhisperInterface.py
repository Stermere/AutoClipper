# handles all the interaction with WhisperX for transcriptions and uderance times

import whisperx

from moviepy.editor import VideoFileClip

TEMP_AUDIO_FILE = "temp/audio.wav"
DEFAULT_LANGUAGE = "en"
DEFAULT_DEVICE = "cuda"
COMPUTE_TYPE = "float16"

class WhisperInterface:
    def __init__(self, device=DEFAULT_DEVICE):
        self.device = device
        self.model = whisperx.load_model("large-v2", self.device, compute_type=COMPUTE_TYPE, language=DEFAULT_LANGUAGE)

    # returns a touple with the first element being the word segments and the second being the no speech probability
    def transcription(self, audio_file):
        # transcribe with original whisper
        result = self.model.transcribe(audio_file, batch_size=16)

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
