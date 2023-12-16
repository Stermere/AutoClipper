import torch
import transformers
import os
from transformers import LlamaForCausalLM, LlamaTokenizer

class LlamaWrapper:
    def __init__(self, model_path="llama\llama-2-13b-chat"):
        # check if the model path exists
        if not os.path.isdir(model_path):
            raise Exception(f"Model path {model_path} does not exist! Please download the model before using Llama")


        self.model = LlamaForCausalLM.from_pretrained(model_path)
        self.tokenizer = LlamaTokenizer.from_pretrained(model_path)
        self.pipeline = transformers.pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer,
            torch_dtype=torch.float16,
            device_map="auto",
        )

    def generate(self, prompt, max_length=300):
        sequences = self.pipeline(
            prompt,
            do_sample=True,
            top_k=10,
            num_return_sequences=1,
            eos_token_id=self.tokenizer.eos_token_id,
            max_length=max_length,
        )

        # TODO remove this
        for seq in sequences:
            print(f"{seq['generated_text']}")

        return sequences[0]['generated_text']