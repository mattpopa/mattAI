import openai
import os
import base64
import requests

openai.api_key = os.getenv("OPENAI_API_KEY")

with open('/Users/matt/Downloads/IMG_0629.jpeg', 'rb') as file:
  binary_stream = base64.b64encode(file.read()).decode('utf-8')

completion = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[
      {
        "role": "system",
        "content": "You are a helpful assistant and can describe images.",
      },
      {
        "role": "user",
        "content": ["What's in this screenshot?", {"image": binary_stream}],
      },
    ],
)
print(completion["choices"][0]["message"]["content"])