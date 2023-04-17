# a class that handles the OpenAI API
import openai
import json


with open('config.json') as f:
    config = json.load(f)

API_KEY = config['OPENAI_API_KEY']
DEFAULT_MODEL = config['DEFAULT_MODEL']

# define the system message
SYSTEM_MESSAGE = {"role": "system", "content": "You are a youtube video editor. You must provide the requested info for the video."}

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
        prompt = f"\"{transcript}\"\n\
                The above is the Transcript of a set of clip from the twitch streamer {channel} Your task is outlined below.\n\
                Make sure to include a title, description, and tags in the format:\
                \"Title: your answer here\nDescription: your answer here\nTags: your answer here\" capitalization is important\
                The title should end with \"| {channel} clips\", the description should promote {channel}\
                (The twitch streamer That created these clips) and be quite short just a comment on the video and then a promotion for {channel}, tags are seperated by comma and there should be about 20 of them.\
                Make sure to add '{channel}' in the appropriate places! Also the title should not be generic, for example \"{channel}'s Hilarious Twitch Stream Moments | {channel} clips\" is a bad title.\
                The title should be novel and cleverly clickbaity here are a few examples to reference for the style \
                '{channel} we saw that...' or 'Wait {channel}... say that again?' or '{channel} gets baited'."
    
        response = self.get_response(prompt)

        print(response + "\n\n")

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

        