# a class that handles the OpenAI API
import openai
import json


with open('config.json') as f:
    config = json.load(f)

API_KEY = config['OPENAI_API_KEY']
DEFAULT_MODEL = config['DEFAULT_MODEL']

# define the system message
SYSTEM_MESSAGE = {"role": "system", "content": "You are a Youtube video editor assistant. You must complete the task layed out by your user."}

class LanguageModel:
    def __init__(self, api_key=API_KEY):
        openai.api_key = api_key

    # given a prompt return the response
    def get_response(self, prompt, allow_reprompt=False, max_tokens=300):
        # create the message list
        chats = [SYSTEM_MESSAGE, {"role": "user", "content": prompt}]
        while True:
            try:
                completion = openai.ChatCompletion.create(model=DEFAULT_MODEL, messages=chats, max_tokens=max_tokens)
                if not allow_reprompt:
                    break

                chats.append({"role": "assistant", "content": completion.choices[0].message.content})

                print(completion.choices[0].message.content + "\n")

                # ask the user for a reprompt
                prompt = input("Enter a reprompt (n or nothing to quit): ")
                if prompt == 'n' or prompt == '':
                    break
                chats.append({"role": "user", "content": prompt})

            except (openai.error.RateLimitError, openai.error.ServiceUnavailableError) as e:
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
    # The prompt that goes with this function is in GetVideoInfo.txt but can be overriden as 
    # long as the new prompt has the same requested return response
    def get_video_info(self, channel, transcript, clip_titles, default_prompt="src/prompts/GetVideoInfo.txt"):
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

        name = streamer_info["name"]
        twitch_link = streamer_info["twitchLink"]
        youtube_link = streamer_info["youtubeLink"]
        description = streamer_info["description"]
        catagory = streamer_info["catagory"]


        info = f"Name - {name}\nCatagory - {catagory}\nDescription - {description}"
        # build the prompt
        with open(default_prompt) as f:
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

        # add a link to the description since the llm is not good at this
        promo = f"If you enjoyed this video please consider checking out {name}'s channels!\n\n"
        description = f"{name}'s Socials\n -- Twitch: {twitch_link}\n -- Youtube: {youtube_link}\n" + promo + description

        return title, description, tags
    
    # takes a list of clip titles and returns the order the LLM thinks they should be in
    # titles and transcripts must have the same number of items
    # The prompt that goes with this function is in GetVideoOrder.txt
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
    
    # takes a list of clips and returns a refined list of clips
    # The prompt that goes with this function is in FilterClips.txt
    def filter_out_clips(self, clips, num_returned):
        # for each clip get a description of it and the reasoning for it being an important clip
        responses = []
        for clip in clips:
            with open("src/prompts/GetClipWorth.txt") as f:
                prompt = f.readlines()
            prompt = ''.join(prompt)
            prompt = self.fill_prompt(prompt, clip.title, clip.transcript)
            responses.append(self.get_response(prompt))

        for r in responses:
            print(r + "\n") 

        # convert the responses to a string with the clip numbers
        responses = [f"Clip {i} - {responses[i]}\n\n" for i in range(len(responses))]

        with open("src/prompts/FilterClips.txt") as f:
            prompt = f.readlines()
        prompt = ''.join(prompt)
        prompt = self.fill_prompt(prompt, ''.join(responses), str(num_returned))
        response = self.get_response(prompt, max_tokens=600)

        print(response + "\n")

        input("Press enter to continue...")

        # parse the response (note this could be bad if the user is allowed to reprompt)
        response = response.split('[')[-1].split(']')[0]
        output = eval(response)

        return [clips[int(i)] for i in output]


if __name__ == "__main__":
    openai_utils = LanguageModel()


        