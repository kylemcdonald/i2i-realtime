from openai import OpenAI
import os

class SafetyChecker:
    def __init__(self):
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def __call__(self, prompt):
        content = f"""You are a content moderation AI that determines whether user input is safe or NSFW. User input will be used to control a text-to-image generator. For any input that involves nudity, sexuality, violence, or gore, reply "unsafe". For everything else, reply "safe". Evaluate this input: "{prompt}"""""

        response = self.client.chat.completions.create(
            model="gpt-4-1106-preview",
            messages=[
                {"role": "user", "content": content}
            ]
        )
        safe = response.choices[0].message.content == "safe"
        return "safe" if safe else "unsafe"