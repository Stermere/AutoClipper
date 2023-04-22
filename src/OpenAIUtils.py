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
    def get_video_info(self, channel, transcript, clip_titles=[]):
        # remove duplicate titles and make it a string
        clip_titles = list(set(clip_titles))
        clip_titles = '\n'.join(clip_titles)
        clip_titles = "Titles:\n" + clip_titles

        # load the streamer info from the config file
        with open('creator_info.json') as f:
            streamer_info = json.load(f)["creators"]

        # get the streamer info
        streamer_info = streamer_info[channel.lower()]

        # TODO add a try catch here
        name = streamer_info["name"]
        twitch_link = streamer_info["twitchLink"]
        youtube_link = streamer_info["youtubeLink"]
        description = streamer_info["description"]
        catagory = streamer_info["catagory"]

        info = f"Name: {name}\nCatagory:{catagory}\nDescription: {description}"

        # build the prompt
        prompt = f"\"{transcript}\"\n\"{clip_titles}\"\n\"{info}\"\
                Above is the transcript and name of each clip from\
                a set of clips from the twitch streamer\
                {name}. There is also some info about the streamer. Use this info to complete the task.\n\
                Make sure to include a title, description, and tags in the format:\
                \"Title: your answer here\nDescription: your answer here\nTags: your \
                answer here\" capitalization is important\
                The title must end with \"| {name} clips\", the description must be\
                quite short just a quote from the video that is funny out of context.\
                Make sure to add '{name}' in the appropriate places!\
                Also the title should be similar to the titles of the clips in style, length, and\
                word choice, you may use the titles of the clips verbatim."
        
        response = self.get_response(prompt)

        print(response + "\n\n")

        # parse the response (this needs to be improved to handle the llm deciding to go off the rails)
        title = response.split('Title: ')[-1]
        description = title.split('Description: ')[-1]
        tags = description.split('Tags: ')[-1].replace('.', '')
        title = title.split('Description: ')[0]
        description = description.split('Tags: ')[0]
        tags = tags.split(', ')

        # add a link to the description since the llm is not good at this
        description = f"{name}'s Socials\n -- Twitch: {twitch_link}\n -- Youtube: {youtube_link}\n\n" + description

        return title, description, tags
    
    # takes a list of clip titles and returns the order the LLM thinks they should be in
    def get_video_order(titles):
        # TODO
        pass

    # generate a set of time stamps for each clip in the video
    def get_time_stamps(self, channel, transcript, clip_titles=[]):
        # TODO
        pass

if __name__ == "__main__":
    openai_utils = OpenAIUtils()

        