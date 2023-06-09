# a class that reads the config file for the given channel and uploads the video to youtube 
# with the title tags and description specified in the config file

from simple_youtube_api.Channel import Channel
from simple_youtube_api.LocalVideo import LocalVideo
from src.UserInput import get_bool

class YoutubeUploader:
    def __init__(self, secretPath="googleConfig.json", credentialsPath="credentials.json"):
        self.channel = Channel()
        self.channel.login(secretPath, credentialsPath)

    def upload(self, title, description, tags, privacyStatus, videoPath, thumbnailPath, category=None, publishAt=None):
        # setting up the video that is going to be uploaded
        video = LocalVideo(file_path=videoPath)

        # setting snippet
        video.set_title(title)
        video.set_description(description)
        video.set_tags(tags)

        if category is not None:
            video.set_category(category)


        # set publish time
        if publishAt is not None:
            video.set_publish_at(publishAt.astimezone().isoformat())

        # setting status
        video.set_embeddable(True)
        video.set_license("creativeCommon")
        video.set_privacy_status(privacyStatus)
        video.set_public_stats_viewable(True)
        video.set_default_language("en-US")
        video.set_made_for_kids(False)

        # setting thumbnail
        if thumbnailPath is not None:
            video.set_thumbnail_path(thumbnailPath)

        # uploading video and printing the results
        val = get_bool("Upload video? (y/n): ")
        if not val:
            print("aborting upload...")
            return False
        

        video = self.channel.upload_video(video)
        print(video.id)
        print(video)

        # liking video
        video.like()

        return True
        
if __name__ == "__main__":
    uploader = YoutubeUploader()
