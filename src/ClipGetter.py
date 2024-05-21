
import os
import requests
import datetime
import re
from datetime import timezone
from src.ClipCompiler import ClipCompiler
from src.Clip import Clip
from src.Config import Config
from src.UserInput import get_int

# handles getting and downloading clips
class ClipGetter:
    def __init__(self, authenticator):
        self.authenticator = authenticator

    def set_authenticator(self, authenticator):
        self.authenticator = authenticator

    # takes a clip and a user object and downloads the clip to the clips folder
    def download_clip(self, clip, user, clip_dir=Config().getValue('DEFAULT_CLIP_DIR')):
        if (clip == None):
            print('Clip is None')
            return None

        # download the clip
        index = clip.thumbnail_url.find('-preview')
        clip_url = clip.thumbnail_url[:index] + '.mp4'
        clip_name = f'{clip_dir}/{user.display_name}_{clip.vod_offset}_{clip.id}.mp4'
        r = requests.get(clip_url)
        if r.headers['Content-Type'] == 'binary/octet-stream':
            if not os.path.exists(clip_dir):
                os.mkdirs(clip_dir, exist_ok=True)
            with open(clip_name, 'wb') as f:
                f.write(r.content)

        return clip_name
    
    def parse_duration(self, duration_str):
        pattern = r'(\d+)h(\d+)m(\d+)s'
        match = re.match(pattern, duration_str)
        if match:
            hours, minutes, seconds = map(int, match.groups())
            return datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)
        else:
            raise ValueError("Invalid duration string format")
        
    def parse_date_time(self, date_time_str):
        date = date_time_str[:10]
        time = date_time_str[11:19]
        date_time_str = date + ' ' + time

        return datetime.datetime.fromisoformat(date_time_str)

    # get the most popular clips from a streamer and download them. designed to be used when making compilation videos
    async def get_clips_from_stream(self, user, clip_dir=Config().getValue('DEFAULT_CLIP_DIR'), clip_count=15, vods_back=0):
        # get the video id's of the streams that occured in the last streams streams
        videos = user.videos()

        # convert the Cursor object to a list
        videos = list(videos)

        # sort the videos by creation time
        videos.sort(key=lambda x: x.created_at, reverse=True)

        video = videos[vods_back]
        video_id = video.id
        video_duration = self.parse_duration(video.duration)
        video_created_at = video.created_at
        print(f'Video duration: {video_duration}')

        # the start time for getting clips should be the origin of the video
        start_time = (self.parse_date_time(video_created_at) - (video_duration + datetime.timedelta(hours=2))).astimezone()

        # get clips from this user's streams in the time after the stream started
        clips = await self.authenticator.get_clips(user.id, started_at=start_time)

        # filter to only include clips that are from the most recent stream
        clips_temp = []
        for i in range(min(len(clips), clip_count)):
            # if vod offset is none then the video is not up or to recent
            # so fall back to time based filtering
            if clips[i].vod_offset == None:
                if clips[i].created_at.astimezone() > start_time:
                    clips_temp.append(clips[i])
            else:
                if video_id == clips[i].video_id:
                    clips_temp.append(clips[i])

        clips = clips_temp

        # create a folder for the clips
        if not os.path.exists(clip_dir):
            os.makedirs(clip_dir, exist_ok=True)

        print(f'Found {min(len(clips), clip_count)} clips for {user.display_name}\'s stream ({video_id}) looking back to {start_time}')

        # get user input 
        clip_count = get_int("How many clips would you like to use?", 1, min(len(clips), clip_count))

        # print how long its been since the stream started
        print(f'Time since stream ended: {(datetime.datetime.now().astimezone() - start_time.astimezone()).total_seconds() / 60 / 60:.2f} hours')

        if len(clips) == 0:
            return []
        
        # download the clips and create a list of clip objects
        print(f'Downloading {min(len(clips), clip_count)} clips')
        clips_temp = []
        for clip in clips[:clip_count]:
            dir_ = self.download_clip(clip, user, clip_dir)
            clips_temp.append(Clip.from_twitch_api_clip(clip, dir_))
        clips = clips_temp

        print("\nClips downloaded...\n")

        # combine any overlapping clips
        #clip_compiler = ClipCompiler()
        #clips = clip_compiler.merge_clips(clips)

        # return the clips
        return clips
    
    # get the most popular clip from a streamer that is not in the provided history. designed to be used when making single clip videos
    def get_popular_clips(self, user, history, days_back=2, clip_dir=Config().getValue('DEFAULT_CLIP_DIR'), clip_count=1):
        # get clips that have the highest view count from the last days_back days
        clips = self.authenticator.client.get_clips(user.id, started_at=(datetime.datetime.now().astimezone() - datetime.timedelta(days=days_back)).isoformat(), page_size=50)

        # filter out clips that are in the history
        clips_temp = []
        i = 0
        for clip in clips:
            clip_temp = Clip.from_twitch_api_clip(clip, "tempDir")
            i += 1
            if i >= 50:
                break

            # check if the clip is in the history
            if not history.checkForClip(clip_temp):
                clips_temp.append(clip)
        clips = clips_temp

        # sort the clips by view count
        clips.sort(key=lambda x: x['view_count'], reverse=True)

        if not os.path.exists(clip_dir):
            os.makedirs(clip_dir, exist_ok=True)

        # download the clips and create a list of clip objects
        clips_temp = []
        for clip in clips[:clip_count]:
            dir_ = self.download_clip(clip, user, clip_dir)
            clips_temp.append(Clip.from_twitch_api_clip(clip, dir_))
        clips = clips_temp

        return clips