# a class that reads the config file for the given channel and uploads the video to youtube 
# with the title tags and description specified in the config file

from simple_youtube_api.Channel import Channel
from simple_youtube_api.LocalVideo import LocalVideo

class YoutubeUploader:
    def __init__(self, secretPath="config.json", credentialsPath="credentials.json"):
        self.channel = Channel()
        self.channel.login(secretPath, credentialsPath)

    def upload(self, channelName, title, description, tags, category, privacyStatus, videoPath, thumbnailPath, publishAt=None):
        # setting up the video that is going to be uploaded
        video = LocalVideo(file_path=videoPath)

        # setting snippet
        video.set_title(title)
        video.set_description(description)
        video.set_tags(tags)
        video.set_category(category)
        video.set_default_language("en-US")

        # set publish time
        if publishAt is not None:
            video.set_publish_at(publishAt)

        # setting status
        video.set_embeddable(True)
        video.set_license("creativeCommon")
        video.set_privacy_status(privacyStatus)
        video.set_public_stats_viewable(True)

        # setting thumbnail
        video.set_thumbnail_path(thumbnailPath)

        # uploading video and printing the results
        video = self.channel.upload_video(video)
        print(video.id)
        print(video)

        # liking video
        video.like()   
