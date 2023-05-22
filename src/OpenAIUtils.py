# a class that handles the OpenAI API
import openai
import json


with open('config.json') as f:
    config = json.load(f)

API_KEY = config['OPENAI_API_KEY']
DEFAULT_MODEL = config['DEFAULT_MODEL']

# define the system message
SYSTEM_MESSAGE = {"role": "system", "content": "You are a Youtube video editor assistant. You must complete the task layed out by your user."}

class OpenAIUtils:
    def __init__(self, api_key=API_KEY):
        openai.api_key = api_key

    # given a prompt return the response
    def get_response(self, prompt, allow_reprompt=False):
        # create the message list
        chats = [SYSTEM_MESSAGE, {"role": "user", "content": prompt}]
        while True:
            try:
                completion = openai.ChatCompletion.create(model=DEFAULT_MODEL, messages=chats, max_tokens=300)
                if not allow_reprompt:
                    break

                chats.append({"role": "assistant", "content": completion.choices[0].message.content})

                print(completion.choices[0].message.content + "\n")

                # ask the user for a reprompt
                prompt = input("Enter a reprompt (n or nothing to quit): ")
                if prompt == 'n' or prompt == '':
                    break
                chats.append({"role": "user", "content": prompt})

            except openai.error.RateLimitError as e:
                input("OpenAI be struggling. Press enter to try again.")
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
                The description must be quite short just a small description of the video.\
                The tags must be a comma separated list there should be 15 of them.\
                Make sure to add '{name}' in the appropriate places!\
                The title must be eye catching and idealy be a teaser for the content of the first clip.\
                With that being said make sure the title is short and to the point and maximize click through rate\
                and viewer utility."
        
        response = self.get_response(prompt, allow_reprompt=True)

        # parse the response (this needs to be improved to handle the llm deciding to go off the rails)
        title = response.split('Title: ')[-1]
        description = title.split('Description: ')[-1]
        tags = description.split('Tags: ')[-1].replace('.', '')
        title = title.split('Description: ')[0].replace('\n', '')
        description = description.split('Tags: ')[0]
        tags = tags.split(', ')

        # add the postfix to the title
        title += f" | {name} clips"

        # add a link to the description since the llm is not good at this TODO move this out of here
        promo = f"If you enjoyed this video please consider checking out {name}'s channels!\n\n"
        description = f"{name}'s Socials\n -- Twitch: {twitch_link}\n -- Youtube: {youtube_link}\n" + promo + description

        return title, description, tags
    
    # takes a list of clip titles and returns the order the LLM thinks they should be in
    # titles and transcripts must have the same number of items
    def get_video_order(self, titles, transcripts, durations):
        # build a list of tuples where each is a title and transcript
        clips = list(zip(titles, transcripts, durations))

        # TODO limit the number of clips (context length limit)
        
        # build the prompt
        titles = [f"Clip {i} - Title: {clip[0]} - Duration: {clip[2]} - Transcript: {clip[1][:200]}\n" for i, clip in enumerate(clips)]
        prompt = "Above are the titles and transcripts of the clips.\
                Your task is to order them from best to worst. Respond with a comma separated list of numbers enclosed by brackets like this [1, 2, 3].\
                These are clips from a twitch streamer. You must order them to maximixe\
                viwer retention as they will be edited together in the order you respond with.\
                Prioritize the shorter clips as they are more likely to be watched. Make sure clips with the same ID\
                are next to each other as often as possible. Maximize viewer utility."
        
        prompt += "".join(titles) + prompt

        response = self.get_response(prompt)

        print(response)

        if not "[" in response:
            print("ERROR: LLM did not respond with a list of numbers")
            return None

        # parse the response
        response = response.split('[')[-1].split(']')[0].split(',')
        response = [int(i) for i in response]

        return response

if __name__ == "__main__":
    openai_utils = OpenAIUtils()


        