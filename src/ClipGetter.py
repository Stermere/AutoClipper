
import os
import requests
import datetime
from datetime import timezone
from src.ClipCompiler import ClipCompiler
from src.Clip import Clip

DEFAULT_SAVE_DIR = 'temp/clips'

# handles getting and downloading clips
class ClipGetter:
    # takes a clip and a user object and downloads the clip to the clips folder
    def download_clip(self, clip, user, clip_dir=DEFAULT_SAVE_DIR):
        if (clip == None):
            print('Clip is None')
            return None

        # download the clip
        index = clip['thumbnail_url'].find('-preview')
        clip_url = clip['thumbnail_url'][:index] + '.mp4'
        clip_name = f'{clip_dir}/{user.display_name}_{clip.vod_offset}_{clip.video_id}.mp4'
        r = requests.get(clip_url)
        if r.headers['Content-Type'] == 'binary/octet-stream':
            if not os.path.exists(clip_dir):
                os.mkdirs(clip_dir, exist_ok=True)
            with open(clip_name, 'wb') as f:
                f.write(r.content)

        return clip_name

    # get the most popular clips from a streamer and download them
    def get_clips_recent(self, user, client, rest_time=2, clip_dir=DEFAULT_SAVE_DIR, clip_count=15, vods_back=0):
        # get the video id's of the streams that occured in the last streams streams
        videos = client.get_videos(user_id=user.id)

        # convert the Cursor object to a list
        videos = list(videos)

        # sort the videos by creation time
        videos.sort(key=lambda x: x['created_at'], reverse=True)

        # remove videos that are newer than rest_time hours
        videos = [video for video in videos if video['created_at'] < datetime.datetime.now() - datetime.timedelta(hours=rest_time)]

        # get the video and its id
        video_id = videos[vods_back]['id']

        # the start time for getting clips should be the origin of the video
        start_time = (videos[vods_back]['created_at'].astimezone() - datetime.timedelta(hours=5)).isoformat()
        
        # get clips from this user's streams in the time after the stream started
        clips = client.get_clips(user.id, started_at=start_time, page_size=100)

        # filter to only include clips from streams stream's back
        clips_temp = []
        i = 0
        for clip in clips:
            if video_id == clip['video_id']:
                clips_temp.append(clip)
            if i >= clip_count:
                break
            i += 1
        clips = clips_temp

        # vod offset should always be available here since the video was still up
        clips.sort(key=lambda x: x['vod_offset'], reverse=True)

        # create a folder for the clips
        if not os.path.exists(clip_dir):
            os.makedirs(clip_dir, exist_ok=True)

        print(f'Found {len(clips)} clips for {user.display_name}\'s stream ({video_id}) looking back to {start_time}')

        if len(clips) == 0:
            return []
        
        # download the clips and create a list of clip objects
        clips_temp = []
        for clip in clips[:clip_count]:
            dir_ = self.download_clip(clip, user, clip_dir)
            clips_temp.append(Clip.from_twitch_api_clip(clip, dir_))
        clips = clips_temp


        # combine any overlapping clips
        clip_compiler = ClipCompiler()
        clips = clip_compiler.merge_clips(clips)

        # return the clips
        return clips


