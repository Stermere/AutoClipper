# a class that turns a list that may be out of order and overlapping into a list of clips that are not overlapping

from moviepy.editor import *
import cv2
import numpy as np
from src.Clip import Clip
import datetime

SIMILARITY_PERCENTAGE = 0.5
MAX_CLIP_LENGTH = 60

class ClipCompiler:
    # given a csv file of clips cluster them into groups where clips overlap and merge them
    # takes a csv file or a list of clips and returns a list of clips that are not overlapping
    def merge_clips(self, csv_or_cliplist):
        # check if the file exists
        if not isinstance(csv_or_cliplist, list) and not os.path.exists(csv_or_cliplist):
            print(f'Error: {csv_or_cliplist} does not exist or is not a list')
            return 
        
        if isinstance(csv_or_cliplist, list):
            clips = csv_or_cliplist
        else:
            # open the csv file
            clips = self.open_csv(csv_or_cliplist)

        # compare each clip to the next clip and merge them if they overlap
        i = 0
        while i < len(clips) - 1:
            # sort the clips by time
            clips.sort(key=lambda x: x.time)

            # get two possible clips to merge
            clips_to_merge = self.get_clips_to_merge(clips, i)

            print('Attempting merge...')

            # if the time is more than MAX_CLIP_LENGTH seconds apart skip
            if (clips_to_merge[1].time - clips_to_merge[0].time > datetime.timedelta(seconds=MAX_CLIP_LENGTH)):
                print('Time difference too large, skipping...')
                i += 1
                continue
            
            # merge the clips
            merged_clip = self.merge_clip(clips_to_merge[0], clips_to_merge[1])

            if (merged_clip == None):
                i += 1
                continue

            # generate the new clip name
            new_clip_name = clips_to_merge[0].clip_dir.split('_')[0] + '_' + datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S') + '.mp4'

            # write the merged clip to file with the file name of the first clip
            merged_clip.write_videofile(new_clip_name)

            # remove the clips from the list
            clips.remove(clips_to_merge[0])
            clips.remove(clips_to_merge[1])

            # remove the old clips from file
            os.remove(clips_to_merge[0].clip_dir)
            os.remove(clips_to_merge[1].clip_dir)


            # create the new clip object
            new_clip = Clip(new_clip_name, None, clips_to_merge[1].streamer_id, clips_to_merge[1].game_id, clips_to_merge[1].streamer_name, 
                            clips_to_merge[0].time, merged_clip.duration
                           )

            # add the merged clip to the list
            clips.append(new_clip)

            # print the two clips that were merged and the new clip that was created TODO remove this line
            print(f'Merged {clips_to_merge[0].clip_dir} and {clips_to_merge[1].clip_dir} into {new_clip.clip_dir}')

            # rewrite the csv file
            if not isinstance(csv_or_cliplist, list):
                self.write_csv(csv_or_cliplist, clips_to_merge, [new_clip])

        return clips

    # merges two clips together
    def merge_clip(self, clip1, clip2):
        # find the merge point
        merge_point_1, merge_point_2, vid_fps_1, vid_fps_2 = self.get_merge_point(clip1, clip2)

        if (merge_point_1 == None or merge_point_2 == None):
            return None

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
        entry1, fps1, frame_count_1 = self.get_last_frame(clip1)

        merge_point_1 = frame_count_1
        merge_point_2 = None

        # prepare the stream for the seconds clip
        cap = cv2.VideoCapture(clip2.clip_dir)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frameWidth = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frameHeight = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps2 = cap.get(cv2.CAP_PROP_FPS)
        entry2 = np.empty((frameHeight, frameWidth, 3), np.dtype('uint8'))
        pixel_count = frameHeight * frameWidth * 3

        # read the first frame
        ret, entry2 = cap.read()

        # loop until the same frame is found
        frame = 0
        best_score = 0
        while (frame < frame_count):
            ret, entry2 = cap.read()

            if (entry2 is None or entry1 is None or ret is False):
                break

            # compute the difference between the two frames
            sum_ = np.sum(entry1 == entry2)
            score = sum_ / pixel_count

            # if the difference is less than the best difference so far update the best difference
            if (score > best_score):
                merge_point_2 = frame
                best_score = score
                print(f'New best frame: {frame} with score: {best_score}')
            frame += 1

        cap.release()

        # if the score is to low return None
        if (best_score < SIMILARITY_PERCENTAGE):
            print('Score too low, skipping...')
            return None, None, None, None

        return merge_point_1, merge_point_2, fps1, fps2
    
    # given a clip object return a numpy array of the last frame in the clip
    # TODO can this be done without reading the entire clip?
    def get_last_frame(self, clip):
        cap = cv2.VideoCapture(clip.clip_dir)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)

        buf1 = np.empty((frame_height, frame_width, 3), np.dtype('uint8'))
        buf2 = np.empty((frame_height, frame_width, 3), np.dtype('uint8'))

        for i in range(0, frame_count):
            ret, buf1 = cap.read()

            if (ret == False):
                break
            buftemp = buf2
            buf2 = buf1
            buf1 = buftemp

        cap.release()

        return buf2, fps, frame_count

    # gives the next two clips that should be checked for a merge
    def get_clips_to_merge(self, clips, index):
        return clips[index], clips[index + 1]
    
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