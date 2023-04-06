
import os
import requests
import datetime
from datetime import timezone

# handles getting and downloading clips
class ClipGetter:
    # takes a clip and a user object and downloads the clip to the clips folder
    def download_clip(self, clip, user, clip_dir='clips'):
        # download the clip
        index = clip['thumbnail_url'].find('-preview')
        clip_url = clip['thumbnail_url'][:index] + '.mp4'
        clip_name = f'{clip_dir}/{user.display_name}_{clip.id}.mp4'
        r = requests.get(clip_url)
        if r.headers['Content-Type'] == 'binary/octet-stream':
            if not os.path.exists('clips'):
                os.mkdir('clips')
            with open(clip_name, 'wb') as f:
                f.write(r.content)

        return f'{clip_dir}/{user.display_name}_{clip.id}.mp4'

    # get the most popular clips from a stream in the last time hours and downloads them to a subfolder
    def get_clips(self, user, client, time=24, clip_dir='temp/clips', clip_count=15, sort_by_time=True):
        # get the clips from the last time hours
        start_time = (datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=time)).astimezone().isoformat()
        
        # clips are ordered by view count
        clips = client.get_clips(user.id, started_at=start_time)

        # put the clips in to a list
        clips_temp = []
        for clip in clips[:clip_count]:
            clips_temp.append(clip)
        clips = clips_temp
        
        # sort the clips by time
        if (sort_by_time):
            clips.sort(key=lambda x: x.created_at)

        # create a folder for the clips
        if not os.path.exists(clip_dir):
            os.makedirs(clip_dir, exist_ok=True)

        print(f'Found {len(clips)} clips for {user.display_name} in the last {time} hours')
        
        # download the clips
        for clip in clips[:clip_count]:
            self.download_clip(clip, user, clip_dir)

        # TODO combine any overlapping clips

        # return a list of the clips directory
        return [f'{clip_dir}/{user.display_name}_{clip.id}.mp4' for clip in clips[:clip_count]]
    
    async def get_clips_delay(self, delay, user, client, time=24, clip_dir='temp/clips', clip_count=15):
        pass


