# a class that turns a list that may be out of order and overlapping into a list of clips that are not overlapping

from moviepy.editor import *
import cv2
import numpy as np
from src.Clip import Clip
import datetime

SIMILARITY_PERCENTAGE = 0.8

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
            # sort the clips by time TODO sort by vod offset if that is possible
            clips = self.sort_clips_by_vod_offset(clips)

            # get two possible clips to merge
            clips_to_merge = self.get_clips_to_merge(clips, i)

            print('Attempting merge...')

            # if there is no vod offset, skip and pray there was no overlap
            if clips_to_merge[0].vod_offset == None or clips_to_merge[1].vod_offset == None:
                print('No vod offset')
                i += 1
                continue

            # if video_id is not the same or the vod offset is not close enough, skip
            if (clips_to_merge[0].video_id != clips_to_merge[1].video_id
                or clips_to_merge[1].vod_offset - clips_to_merge[0].vod_offset > clips_to_merge[0].duration):
                print('Clips do not overlap')
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
                            clips_to_merge[0].time, merged_clip.duration, max([c.view_count for c in clips_to_merge]), clips_to_merge[1].title, clips_to_merge[0].vod_offset, clips_to_merge[1].video_id
                           )

            # add the merged clip to the list
            clips.append(new_clip)

            # print the two clips that were merged and the new clip that was created TODO remove this line
            print(f'Merged {clips_to_merge[0].clip_dir} and {clips_to_merge[1].clip_dir} into {new_clip.clip_dir}')

            # rewrite the csv file
            if not isinstance(csv_or_cliplist, list):
                self.write_csv(csv_or_cliplist, clips_to_merge, [new_clip])

            # release any resources moviepy is using
            merged_clip.close()




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

        # validate the frame sizes

        if (entry2.shape != entry1.shape):
            print('Error: frame sizes do not match, cannot merge clips')
            return None, None, None, None

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
    def get_last_frame(self, clip):
        # prepare the stream
        cap = cv2.VideoCapture(clip.clip_dir)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frameWidth = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frameHeight = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        entry = np.empty((frameHeight, frameWidth, 3), np.dtype('uint8'))

        # read the first frame
        ret, entry = cap.read()

        # loop until the last frame is reached
        frame = 0
        while (frame < frame_count - 2):
            ret, entry = cap.read()
            frame += 1

        cap.release()

        return entry, fps, frame_count

    # gives the next two clips that should be checked for a merge
    def get_clips_to_merge(self, clips, index):
        return clips[index], clips[index + 1]
    
    # sorts the clips by vod offset and video id
    def sort_clips_by_vod_offset(self, clips):
        # group by video id
        clips_by_video_id = {}
        for clip in clips:
            if clip.video_id not in clips_by_video_id:
                clips_by_video_id[clip.video_id] = []
            clips_by_video_id[clip.video_id].append(clip)

        # sort each group by vod offset
        for video_id in clips_by_video_id:
            # if any clip has a None vod offset don't sort this group
            if any(clip.vod_offset is None for clip in clips_by_video_id[video_id]):
                continue

            clips_by_video_id[video_id].sort(key=lambda x: x.vod_offset)

        # combine the groups
        sorted_clips = []
        for video_id in clips_by_video_id:
            sorted_clips.extend(clips_by_video_id[video_id])

        return sorted_clips

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