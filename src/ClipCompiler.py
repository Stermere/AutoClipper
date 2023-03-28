# a class that turns a list that may be out of order and overlapping into a list of clips that are not overlapping

from moviepy.editor import *
import cv2
import numpy as np
from src.Clip import Clip
import datetime

class ClipCompiler:
    # given a csv file of clips cluster them into groups where clips overlap and merge them
    def merge_clips(self, csv_file_dir):
        clips = []

        # check if the file exists
        if not os.path.exists(csv_file_dir):
            return
        
        # each line in the csv file is a clip
        with open(csv_file_dir, 'r') as f:
            clip_str = f.readlines()

        for clip in clip_str:
            clips.append(Clip.from_string(clip))
    
        # if the difference between two clips is less than GUANANTEED_CLIP_LENGTH then merge them
        while True:
            clips_to_merge = self.find_overlapping_clip(clips)
            
            if clips_to_merge == None:
                print('did not find any overlapping clips')
                break

            print('Found overlapping clips merging...')
            
            # merge the clips
            merged_clip = self.merge_clip(clips_to_merge[0], clips_to_merge[1])

            print('Merged')
            merged_clip.write_videofile('output.mp4')
            return;

            # remove the old clips from file
            os.remove(clips_to_merge[0].clip_dir)
            os.remove(clips_to_merge[1].clip_dir)

            # write the merged clip to file with the file name of the first clip
            merged_clip.write_videofile('output.mp4')

            # remove the clips from the list
            clips.remove(clips_to_merge[0])
            clips.remove(clips_to_merge[1])

            # create 

            # add the merged clip to the list
            clips.append(merged_clip)

            # print the two clips that were merged and the new clip that was created TODO remove this line
            print(f'Merged {clips_to_merge[0].clip_dir} and {clips_to_merge[1].clip_dir} into {merged_clip.clip_dir}')

        # once there are no more clips that overlap rewrite the csv file
        with open(csv_file_dir, 'w') as f:
            for clip in clips:
                f.write(clip.to_string())

        print('Done merging clips')

    # merges two clips together
    def merge_clip(self, clip1, clip2):
        # get the np arrays of the frames
        arr1, vid_fps_1 = self.get_np_array(clip1)
        arr2, vid_fps_2 = self.get_np_array(clip2)

        # find the merge point
        merge_point_1, merge_point_2 = self.get_merge_point(arr1, arr2)

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
    def get_merge_point(self, arr1, arr2):
        # find the merge point 
        # (assumes that the merge point is in the second half of the first array)
        merge_point_1 = 0
        merge_point_2 = 0
        # only use the last frame of the first video
        entry = arr1[-1]

        merge_point_1 = len(arr1)
        merge_point_2 = None
        for i, entry2 in enumerate(arr2):
            if (entry2 == entry).all():
                merge_point_2 = i

        if merge_point_2 == None:
            print('Cannot merge videos')


        return merge_point_1, merge_point_2
    
    # given a clip object return a numpy array of the frames
    # TODO don't use the full resolution and or hash each frame
    def get_np_array(self, clip):
        cap = cv2.VideoCapture(clip.clip_dir)
        frameCount = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frameWidth = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frameHeight = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        fps = int(cap.get(cv2.CAP_PROP_FPS))

        buf = np.empty((frameCount, frameHeight, frameWidth, 3), np.dtype('uint8'))

        fc = 0
        ret = True

        while (fc < frameCount  and ret):
            ret, buf[fc] = cap.read()
            fc += 1

        cap.release()

        return buf, fps
    
    # given a list of clips find the ones that overlap
    # returns a tuple of the two clips that overlap
    # the first clip in the tuple is the one that comes first chronologically
    # returns None if no clips overlap
    # TODO check this for robustness (I think this is kinda shitty)
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
    
if __name__ == '__main__':
    clipComp = ClipCompiler()
    clipComp.merge_clips("clip_info\Shylily.csv")

