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
                input("OpenAI be struggling. Press enter to try again. (wait a few minutes if this keeps happening!)")
        return completion.choices[0].message.content
    
    # given a prompt with {}'s in it fill them with the args passed in
    def fill_prompt(self, prompt, *args):
        # parse the prompt for the {}'s
        args = list(args)
        count = prompt.count('{}')
        if count != len(args):
            raise Exception("The number of args must match the number of {}'s in the prompt")

        for i in range(count):
            prompt = prompt.replace('{}', args[i], 1)

        return prompt
        
    
    # given a channel and the transcript of the clip return the video info
    def get_video_info(self, channel, transcript, clip_titles):
        if type(clip_titles) != list:
            raise Exception("clip_titles must be a list")

        # remove duplicate titles and make it a string
        clip_titles = list(set(clip_titles))
        clip_titles = ''.join(clip_titles)

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


        info = f"Name - {name}\nCatagory - {catagory}\nDescription - {description}"
        # build the prompt
        with open("src/prompts/GetVideoInfo.txt") as f:
            prompt = f.readlines()
        prompt = ''.join(prompt)
        prompt = self.fill_prompt(prompt, transcript, clip_titles, info, name)
        response = self.get_response(prompt, allow_reprompt=True)

        # parse the response (this needs to be improved to handle the llm deciding to go off the rails)
        title = response.split('Title: ')[-1]
        description = title.split('Description: ')[-1]
        tags = description.split('Tags: ')[-1].replace('.', '')
        title = title.split('Description: ')[0].replace('\n', '')
        description = description.split('Tags: ')[0]
        tags = tags.split(', ')

        # add the postfix to the title
        title += f" | {name} funny moments"

        # add a link to the description since the llm is not good at this TODO move this out of here
        promo = f"If you enjoyed this video please consider checking out {name}'s channels!\n\n"
        description = f"{name}'s Socials\n -- Twitch: {twitch_link}\n -- Youtube: {youtube_link}\n" + promo + description

        return title, description, tags
    
    # takes a list of clip titles and returns the order the LLM thinks they should be in
    # titles and transcripts must have the same number of items
    def get_video_order(self, clips):
        clip_info = [f"Clip {i} - Title: {clip.title} - Duration: {clip.duration} - Transcript: {clip.transcript}\n" for i, clip in enumerate(clips)]

        # build the prompt
        with open("src/prompts/GetVideoOrder.txt") as f:
            prompt = f.readlines()
        prompt = "".join(prompt)
        prompt = self.fill_prompt(prompt, "".join(clip_info))
        
        response = self.get_response(prompt)

        print(response + "\n")

        if not "[" in response:
            print("ERROR: LLM did not respond with a list of numbers")
            return None

        # parse the response
        response = response.split('[')[-1].split(']')[0].split(',')
        response = [int(i) for i in response]

        return response

if __name__ == "__main__":
    openai_utils = OpenAIUtils()


        