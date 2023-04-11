# a class that handles the OpenAI API
import openai
import json


with open('config.json') as f:
    config = json.load(f)

API_KEY = config['OPENAI_API_KEY']
DEFAULT_MODEL = config['DEFAULT_MODEL']

class OpenAIUtils:
    def __init__(self, api_key=API_KEY):
        openai.api_key = api_key

    def get_response(self, prompt):
        completion = openai.ChatCompletion.create(model=DEFAULT_MODEL, messages=[{"role": "user", "content": prompt}], max_tokens=100)
        print(completion.choices[0].message.content)
    
    def get_title_and_description(self, channel, activity):
        # TODO build the prompt
        pass

    def get_tags(self, channel, activity):
        # TODO build the prompt
        pass
        

if __name__ == "__main__":
    openai_utils = OpenAIUtils()
    openai_utils.get_response("Welcome to world instance 498")
        