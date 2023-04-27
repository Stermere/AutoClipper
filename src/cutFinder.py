import soundfile as sf
from moviepy.editor import VideoFileClip
import numpy as np

TEMP_AUDIO_FILE = "temp/audio.wav"


def get_loudness(file):
    return sf.read(file) # load audio (with shape (samples, channels))

# given a audio file and a rough cut point, find the exact cut point
def find_cut_point(video_file, current_cut):
    video = VideoFileClip(video_file)
    audio = video.audio
    duration = video.duration
    audio.write_audiofile(TEMP_AUDIO_FILE)

    data = get_loudness(TEMP_AUDIO_FILE)[0]


    # slide a window of 1 second across the data and find a quiet spot
    window_size = int((1 / duration) * len(data))
    hundreth_window_size = int(window_size / 100)

    # now that we have the data find the starting index of the cut and search from there
    start_index = int((current_cut / duration) * len(data)) - int(window_size / 2)
    if start_index < 0:
        start_index = 0

    # find a quiet spot with it one window size of the current cut
    best_sum = 999
    best_index = 999
    weight = [x / window_size for x in range(window_size)]

    end_point = len(data) - window_size
    if start_index + window_size < end_point:
        end_point = start_index + window_size

    for i in range(start_index, end_point, hundreth_window_size):
        # get the sum of the loudness in the window
        window_sum = 0
        for j in range(i, i + window_size):
            window_sum += sum(data[j]) * weight[j - i]

        # check if this is the best window
        if window_sum < best_sum:
            best_sum = window_sum
            best_index = i + window_size - (window_size / 10)

    # return the best cut time
    return best_index / len(data) * duration


if __name__ == "__main__":
    cut = find_cut_point("test.mp4", 4)
    data = get_loudness(TEMP_AUDIO_FILE)[0]

    print(data)
    print(cut)

    # graph the loudness with time on the x axis
    import matplotlib.pyplot as plt
    time_line = []
    data = [sum(x) for x in data]
    for i in range(len(data)):
        time_line.append(i / len(data) * 31)
    data = data[:len(time_line)]
    plt.plot(time_line, data)
    plt.show()
    


