# a class that handles the OpenAI API
import openai
import json


with open('config.json') as f:
    config = json.load(f)

API_KEY = config['OPENAI_API_KEY']
DEFAULT_MODEL = config['DEFAULT_MODEL']

# define the system message
SYSTEM_MESSAGE = {"role": "system", "content": "You are a youtube video editor. You are given a channel name and a transcript of a clip. You must respond with a title, description, and tags for the video."}

class OpenAIUtils:
    def __init__(self, api_key=API_KEY):
        openai.api_key = api_key

    # given a prompt return the response
    def get_response(self, prompt):
        completion = openai.ChatCompletion.create(model=DEFAULT_MODEL, messages=[{"role": "user", "content": prompt}, SYSTEM_MESSAGE], max_tokens=300)
        return completion.choices[0].message.content
    
    # given a channel and the transcript of the clip return the video info
    def get_video_info(self, channel, transcript):
        # build the prompt
        prompt = f"The channel is {channel} and the transcript is \"{transcript}\".\
                   Make sure to include a title, description, and tags in the format:\
                   title: <title> description: <description> tags: <tags>. \
                   The title should end with '| {channel}', description should promote {channel}, tags are seperated by comma \
                   Be aware that the transcription may not be accurate and will span multiple clips, so DO NOT mention any location or item in the transcription.\
                   You may click bait as much as needed (try not to be blatant)."
        
        response = self.get_response(prompt)

        # parse the response (this needs to be improved to handle the llm deciding to go off the rails)
        title = response.split('Title: ')[-1]
        description = title.split('Description: ')[-1]
        tags = description.split('Tags: ')[-1].replace('.', '')
        title = title.split('Description: ')[0]
        description = description.split('Tags: ')[0]
        tags = tags.split(', ')

        return title, description, tags

if __name__ == "__main__":
    openai_utils = OpenAIUtils()

        