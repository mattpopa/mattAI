import os
import time
from threading import Thread
import re
import requests
from dotenv import load_dotenv
import os
import openai
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

load_dotenv()
notion_page_id = os.getenv("NOTION_PAGE_ID")
openai.api_key = os.getenv("OPENAI_API_KEY")


def fetch_notion_page_blocks(page_id, page_size=100):
  api_key = os.getenv("NOTION_API_KEY")
  url = f'https://api.notion.com/v1/blocks/{page_id}/children'
  headers = {
    'Authorization': f'Bearer {api_key}',
    'Notion-Version': '2022-06-28'
  }

  all_blocks = []
  start_cursor = None

  while True:
    params = {'page_size': page_size}
    if start_cursor:
      params['start_cursor'] = start_cursor

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    json_response = response.json()

    all_blocks.extend(json_response.get('results', []))

    if not json_response.get('has_more', False):
      break

    start_cursor = json_response.get('next_cursor')

  return all_blocks


def extract_documents_from_blocks(blocks):
  documents = []
  for block in blocks:
    block_type = block.get('type')
    if block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3', 'numbered_list_item', 'bulleted_list_item']:
      rich_text = block.get(block_type, {}).get('rich_text', [])
      text_content = ''.join([text.get('text', {}).get('content', '') for text in rich_text])
      if text_content:
        documents.append(text_content)
    elif block_type == 'code':
      code_block = block.get('code', {})
      rich_text = code_block.get('rich_text', [])
      code_content = ''.join([text.get('text', {}).get('content', '') for text in rich_text])
      if code_content:
        documents.append(code_content)
  return documents


def fetch_notion_page_images(page_id):
  """
  Fetch image blocks from a Notion page by its ID.

  Parameters:
      page_id (str): The ID of the Notion page to fetch image blocks for.

  Returns:
      list: A list of image URLs.
  """
  api_key = os.getenv("NOTION_API_KEY")
  url = f'https://api.notion.com/v1/blocks/{page_id}/children'
  headers = {
    'Authorization': f'Bearer {api_key}',
    'Notion-Version': '2022-06-28'
  }

  image_urls = []
  start_cursor = None

  while True:
    params = {'start_cursor': start_cursor} if start_cursor else {}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    json_response = response.json()

    # Loop through the blocks and add image URLs to the list
    for block in json_response.get('results', []):
      if block.get('type') == 'image' and 'file' in block['image']:
        image_urls.append(block['image']['file']['url'])

    if not json_response.get('has_more', False):
      break
    start_cursor = json_response.get('next_cursor')

  return image_urls


def fetch_notion_page_text(page_id):
  blocks = fetch_notion_page_blocks(page_id)
  text_content = extract_documents_from_blocks(blocks)
  return "\n".join(text_content)


def query_openai_for_image(image_url, user_query):
  response = openai.ChatCompletion.create(
      model="gpt-4-vision-preview",
      messages=[
        {"role": "user", "content": user_query},
        {"role": "system", "content": [{"type": "image_url", "image_url": image_url}]}
      ],
      max_tokens=4000
  )
  return response.choices[0]['message']['content']


def query_openai_for_text(text_content, user_query):
  # Function to analyze text content with GPT-3.5 Turbo model
  response = openai.ChatCompletion.create(
      model="gpt-4-turbo-preview",
      messages=[
        {"role": "user", "content": user_query},
        {"role": "system", "content": text_content}
      ],
      max_tokens=4000
  )
  return response.choices[0]['message']['content']


app = App(token=os.getenv("SLACK_BOT_TOKEN"))


def synthesize_response(text_analysis, image_analysis, user_query):
  # Use the analyses as context for a new query to generate a single, concise response
  context = f"Text Analysis: {text_analysis}\nImage Analysis: {image_analysis}"
  prompt = f"Given the analyses, {user_query}"
  response = openai.ChatCompletion.create(
      model="gpt-3.5-turbo-0125",
      messages=[
        {"role": "system", "content": context},
        {"role": "user", "content": prompt}
      ],
      max_tokens=150
  )
  return response.choices[0]['message']['content']

# Update the message_handler to include the synthesis step
@app.message(re.compile(".*"))
def message_handler(client, message, say):
  channel_id = message['channel']
  thread_ts = message['ts']
  user_query = message['text']

  ts = say(text="one moment, please... :eyes:", channel=channel_id, thread_ts=thread_ts)['ts']

  text_content = fetch_notion_page_text(notion_page_id)
  image_urls = fetch_notion_page_images(notion_page_id)

  # Perform text and image analyses
  text_analysis = query_openai_for_text(text_content, user_query) if text_content else "No text content found."
  image_analysis = query_openai_for_image(image_urls[0], user_query) if image_urls else "No image content found."

  # Synthesize a single, concise response from both analyses
  if text_analysis or image_analysis:
    final_response = synthesize_response(text_analysis, image_analysis, user_query)
  else:
    final_response = "I couldn't find any relevant information."

  # Update the initial message with the final, synthesized response
  client.chat_update(channel=channel_id, ts=ts, text=final_response, thread_ts=thread_ts)


def health_check_worker():
  while True:
    try:
      # Touch a file to indicate health
      with open("/tmp/healthz", "w") as f:
        f.write("ok")
    except Exception as e:
      print(f"Health check failed: {e}")
    # Sleep for a specified interval (e.g., 30 seconds)
    time.sleep(30)

if __name__ == "__main__":
  # Start the health check worker in a separate thread
  Thread(target=health_check_worker, daemon=True).start()
  SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN")).start()
