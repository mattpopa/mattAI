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
  # Refactored function to correctly handle image analysis with GPT-4 Vision model
  response = openai.ChatCompletion.create(
      model="gpt-4-vision-preview",
      messages=[
        {"role": "user", "content": user_query},
        {"role": "system", "content": [{"type": "image_url", "image_url": image_url}]}
      ],
      #max_tokens=3000
  )
  return response.choices[0]['message']['content']


def query_openai_for_text(text_content, user_query):
  # Function to analyze text content with GPT-3.5 Turbo model
  response = openai.ChatCompletion.create(
      model="gpt-3.5-turbo-0125",
      messages=[
        {"role": "user", "content": user_query},
        {"role": "system", "content": text_content}
      ],
      #max_tokens=3000
  )
  return response.choices[0]['message']['content']


app = App(token=os.getenv("SLACK_BOT_TOKEN"))


@app.message(re.compile(".*"))
def message_handler(client, message, say):
  # Combined message handler to analyze both text and image content
  channel_id = message['channel']
  thread_ts = message['ts']
  user_query = message['text']

  ts = say(text="Analyzing your request... :mag_right:", channel=channel_id, thread_ts=thread_ts)['ts']

  text_content = fetch_notion_page_text(notion_page_id)
  image_urls = fetch_notion_page_images(notion_page_id)

  text_analysis = query_openai_for_text(text_content, user_query)
  image_analysis = "No image content found." if not image_urls else query_openai_for_image(image_urls[0], user_query)

  combined_analysis = f"Text Analysis: {text_analysis}\nImage Analysis: {image_analysis}"
  client.chat_update(channel=channel_id, ts=ts, text=combined_analysis, thread_ts=thread_ts)


if __name__ == "__main__":
  SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN")).start()
