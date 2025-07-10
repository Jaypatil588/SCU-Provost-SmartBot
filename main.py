# main.py
# A QA Chatbot that uses a deliberate, two-step API call process to avoid rate limits.
# Step 1: Identify the most relevant file.
# Step 2: Browse that file's URL for the answer.

import os
import json
import glob
import time
from flask import Flask, request, jsonify
import google.generativeai as genai
from google.api_core import client_options

# --- 1. CONFIGURATION ---
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

# Load variables from .env file into the environment
load_dotenv()

# Now you can access the variable using os.environ.get()
my_api_key = os.environ.get("GEMINI_API_KEY")

#add conversation history:
from collections import deque
conversation_history = deque(maxlen=6)


def searchFx(prompt):

    # Configure the client
    client = genai.Client(
            api_key = my_api_key
    )

    # Define the grounding tool
    grounding_tool = types.Tool(
        google_search=types.GoogleSearch()
    )

    # Configure generation settings
    config = types.GenerateContentConfig(
        tools=[grounding_tool]
    )

    # Make the request
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=config,
    )

    # Print the grounded response
    print(response.text)
    return response.text

def urlSearchFx(query, url,conv):
    conv = "\n".join([f"{item['role']}: {item['content']}" for item in conv])

    prompt = f"""
You are a strict Q&A assistant for the Santa Clara University (SCU) Provost's Office.
Your persona is a busy but helpful administrative assistant. Your responses must be extremely concise, direct, and professional.

**Core Task:** Answer the user's question using ONLY the text from the provided URL: {url}

**Conversation History (for context):**
---
{conv}
---

**Response Rules (Follow Strictly):**
1.  **Be Brief:** Provide only the direct answer. Do not use extra words, conversational filler, or pleasantries.
2.  **"Not Found" Handling:** If the requested information (like a person or title) is not on the webpage, state clearly and simply that it is not listed.
    * *Example for a missing title:* "There is no position with that title listed on the Provost's Office webpage."
3.  **General Contact:** If the user asks a general "who to contact" question, provide ONLY the following details, else search the specific webpage for the person/department asked.
    Office of the Provost and Executive Vice President
    Office: 408 554 4533
    Fax: 408 551 6074
    Email: provost@scu.edu

**ABSOLUTELY DO NOT:**
* Do NOT mention that you are a bot or an AI.
* Do NOT mention that you performed a search or looked at a website.
* Do NOT include the URL in your answer.
* Do NOT explain *why* the information is not available.

**User's Question:**
{query}

**Answer:**
"""
    return searchFx(prompt)

DATA_DIR = "scraped"

def load_file_metadata(directory):
    """
    Loads all JSON files and creates a simple mapping of filename to sourceURL.
    This is a very lightweight operation that runs once at startup.
    """
    print(f"Loading file metadata from '{directory}' directory...")
    file_url_map = {}
    json_files = glob.glob(os.path.join(directory, '*.json'))
    if not json_files:
        print(f"ERROR: No .json files found in '{directory}'.")
        return None
    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                source_url = data.get('metadata', {}).get('sourceURL')
                if source_url:
                    file_url_map[os.path.basename(file_path)] = source_url
        except Exception as e:
            print(f"Warning: Could not process file {file_path}. Error: {e}")
    print(f"Successfully loaded metadata from {len(file_url_map)} files.")
    return file_url_map

# --- 3. CORE LOGIC (DELIBERATE TWO-STEP PROCESS) ---

def identify_relevant_file(query, all_filenames,conv):
    conv = "\n".join([f"{item['role']}: {item['content']}" for item in conv])

    print("Step 1: Identifying the most relevant file via API call...")
    
    # Create a string of all filenames for the prompt
    filenames_str = "\n".join(all_filenames)

    prompt = f"""
You are a file routing assistant. Your task is to identify the single most relevant filename from the provided list to answer the user's question.
---
**Conversation History:**
---
{conv}
---
**Instructions:**
1.  Read the user's question carefully.
2.  Review the list of filenames.
3.  Respond with ONLY the single filename that is most likely to contain the answer. Do not add any other text or explanation.

**List of Filenames:**
---
{filenames_str}
---

**User's Question:**
{query}

**Most Relevant Filename:**
"""
    try:
        response = searchFx(prompt)
        # Clean up the response to ensure it's just the filename
        # A final check to ensure the model returned a valid filename
        if response in all_filenames:
            return response
        else:
            print(f"Warning: Model returned a filename not in the list: '{response}'")
            return None
    except Exception as e:
        print(f"An error occurred during file identification: {e}")
        return None

# --- 4. FLASK API SERVER ---

app = Flask(__name__)
is_initialized = False
# This will hold the mapping of filenames to URLs, loaded once at startup.
file_to_url_map = {}

def initialize_app():
    """One-time initialization for all chatbot data."""
    global is_initialized, file_to_url_map
    # if not setup_api_key(): return False
    # Load all file metadata into a single dictionary at startup.
    loaded_map = load_file_metadata(DATA_DIR)
    if not loaded_map: return False
    file_to_url_map = loaded_map
    is_initialized = True
    print("\n--- QA Chatbot is initialized and ready (Deliberate Two-Step Mode). ---")
    return True

@app.route('/qa', methods=['POST'])
def handle_qa():
    """The main endpoint using the deliberate two-step pipeline."""
    if not is_initialized:
        return jsonify({"error": "Server not initialized."}), 503
    data = request.get_json()
    if not data or 'question' not in data:
        return jsonify({"error": "Request must be JSON with a 'question' field."}), 400
    query = data['question']

    # API Call 1: Identify the most relevant file.
    all_filenames = list(file_to_url_map.keys())
    relevant_filename = identify_relevant_file(query, all_filenames, conversation_history) 

    if not relevant_filename:
        return jsonify({"answer": "I could not identify a relevant document to search.", "source": "File Identification Failed"})

    # # Mandatory 5-second wait as requested.
    # print("Waiting for 1 seconds before the next API call...")
    # time.sleep(1)

    # Look up the URL for the identified file.
    url_to_search = file_to_url_map.get(relevant_filename)
    print(url_to_search)
    # Modified to pass history to the function
    final_answer = urlSearchFx(query, url_to_search, conversation_history) 

    # New: Add the current question and answer to the history
    conversation_history.append({'role': 'User', 'content': query})
    conversation_history.append({'role': 'Assistant', 'content': final_answer})

    if "not listed" in str(final_answer).lower():
        return jsonify({"answer": "I couldn't find that information, but here is the reference webpage: {url_to_search}", "source": f"Live Search on {url_to_search}"})
    return jsonify({"answer": final_answer, "source": f"Live Search on {url_to_search}"})

if __name__ == '__main__':
    initialize_app()
    app.run(host='0.0.0.0', port=8080)
