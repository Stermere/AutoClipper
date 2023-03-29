# a class that turns a list that may be out of order and overlapping into a list of clips that are not overlapping

from moviepy.editor import *
import cv2
import numpy as np
from src.Clip import Clip
import datetime

class ClipCompiler:
    # given a csv file of clips cluster them into groups where clips overlap and merge them
    def merge_clips(self, csv_file_dir):
        # check if the file exists
        if not os.path.exists(csv_file_dir):
            return

        # if the difference between two clips is less than GUANANTEED_CLIP_LENGTH then merge them
        while True:
            # open the csv file
            clips = self.open_csv(csv_file_dir)

            # get two overlapping clips
            clips_to_merge = self.find_overlapping_clip(clips)
            
            # if there are none then break
            if clips_to_merge == None:
                break

            print('Found overlapping clips attempting merge...')
            
            # merge the clips
            merged_clip = self.merge_clip(clips_to_merge[0], clips_to_merge[1])

            # generate the new clip name
            new_clip_name = clips_to_merge[0].clip_dir.split('_')[0] + '_' + datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S') + '.mp4'

            # write the merged clip to file with the file name of the first clip
            if (merged_clip == None):
                break

            merged_clip.write_videofile(new_clip_name)

            # remove the clips from the list
            clips.remove(clips_to_merge[0])
            clips.remove(clips_to_merge[1])

            # remove the old clips from file
            os.remove(clips_to_merge[0].clip_dir)
            os.remove(clips_to_merge[1].clip_dir)


            # create the new clip object
            new_clip = Clip(new_clip_name, None, clips_to_merge[1].streamer_id, clips_to_merge[1].streamer_name, 
                            clips_to_merge[0].time, merged_clip.duration, None
                           )

            # add the merged clip to the list
            clips.append(new_clip)

            # print the two clips that were merged and the new clip that was created TODO remove this line
            print(f'Merged {clips_to_merge[0].clip_dir} and {clips_to_merge[1].clip_dir} into {new_clip.clip_dir}')

            # rewrite the csv file
            self.write_csv(csv_file_dir, clips_to_merge, [new_clip])

    # merges two clips together
    def merge_clip(self, clip1, clip2):
        # find the merge point
        merge_point_1, merge_point_2, vid_fps_1, vid_fps_2 = self.get_merge_point(clip1, clip2)

        if (merge_point_1 == None or merge_point_2 == None):
            print('Error: merge point not found')
            print(f'Clip 1: {clip1.clip_dir}, Clip 2: {clip2.clip_dir}')
            return

        # using the merge point use moviepy to merge the clips
        clip1 = VideoFileClip(clip1.clip_dir)
        clip2 = VideoFileClip(clip2.clip_dir)

        # compute the time of the merge point for each clip
        merge_time_1 = merge_point_1 / vid_fps_1
        merge_time_2 = merge_point_2 / vid_fps_2

        # merge the clips
        merged_clip = concatenate_videoclips([clip1, clip2.subclip(t_start=merge_time_2)])

        return merged_clip

    # given two np arrays of video files find the exact frame where they should be merged and return it
    def get_merge_point(self, clip1, clip2):
        entry1, fps1, frame_count_1 = self.get_frame(clip1)

        # merge poing vars
        merge_point_1 = frame_count_1 - 1
        merge_point_2 = None

        # prepare the stream for the seconds clip
        cap = cv2.VideoCapture(clip2.clip_dir)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frameWidth = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frameHeight = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps2 = cap.get(cv2.CAP_PROP_FPS)
        entry2 = np.empty((frameHeight, frameWidth, 3), np.dtype('uint8'))

        # read the first frame
        ret, entry2 = cap.read()

        # loop until the same frame is found
        frame = 1
        best_sum = 0
        while (ret and frame < frame_count):
            ret, entry2 = cap.read()

            sum_ = np.sum(entry2 == entry1)
            if (sum_ > best_sum):
                merge_point_2 = frame
                best_sum = sum_
            frame += 1

        cap.release()

        return merge_point_1, merge_point_2, fps1, fps2
    
    # given a clip object return a numpy array of the frames
    def get_frame(self, clip):
        cap = cv2.VideoCapture(clip.clip_dir)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        fps = cap.get(cv2.CAP_PROP_FPS)

        buf = np.empty((frame_height, frame_width, 3), np.dtype('uint8'))

        fc = 0
        for i in range(0, frame_count - 1):
            ret, buf = cap.read()
            fc += 1

        cap.release()

        return buf, fps, frame_count

    # given a list of clips find the ones that overlap
    # returns a tuple of the two clips that overlap
    # the first clip in the tuple is the one that comes first chronologically
    # returns None if no clips overlap
    def find_overlapping_clip(self, clips):
        for i, clip in enumerate(clips):
            for j, clip2 in enumerate(clips):
                if i != j:
                    if clip.time < clip2.time:
                        if clip.time + datetime.timedelta(seconds=clip.duration) > clip2.time:
                            return (clip, clip2)
                    else:
                        if clip2.time + datetime.timedelta(seconds=clip2.duration) > clip.time:
                            return (clip2, clip)  
        return None
    
    def open_csv(self, csv_file_dir):
        clips = []
        # each line in the csv file is a clip
        with open(csv_file_dir, 'r') as f:
            clip_str = f.readlines()

        for clip in clip_str:
            clips.append(Clip.from_string(clip))

        return clips
    
    def write_csv(self, csv_file_dir, clips_removed, clips_added):
        # open the csv file
        clips = self.open_csv(csv_file_dir)

        # remove the clips that were removed
        for clip in clips_removed:
            if clip in clips:
                clips.remove(clip)

        # add the clips that were added
        for clip in clips_added:
            if clip not in clips:
                clips.append(clip)

        with open(csv_file_dir, 'w') as f:
            for clip in clips:
                f.write(clip.to_string() + '\n')