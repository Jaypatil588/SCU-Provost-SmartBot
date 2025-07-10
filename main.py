# main.py
import os
import json
import glob
from flask import Flask, request, jsonify
from google import genai
from google.genai import types
from dotenv import load_dotenv
from collections import deque
from flask_cors import CORS  # 1. IMPORT THE CORS LIBRARY

#INITs
load_dotenv()
DATA_DIR = "scraped"
my_api_key = os.environ.get("GEMINI_API_KEY")
conversation_history = deque(maxlen=6)

#DEF FUNCTIONS

def searchFx(prompt):
    client = genai.Client(
            api_key = my_api_key
    )
    #this enables live web search, bypassing need for inaccurate embeddings
    grounding_tool = types.Tool(
        google_search=types.GoogleSearch()
    )
    config = types.GenerateContentConfig(
        tools=[grounding_tool]
    )
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=config,
    )

    print(response.text)
    return response.text

def urlSearchFx(query, url,conv):
    conv = "\n".join([f"{item['role']}: {item['content']}" for item in conv])

    prompt = f"""
You are a strict Q&A assistant for the Santa Clara University (SCU) Provost's Office.
Your persona is a busy but helpful administrative assistant. Your responses must be extremely concise, direct, and professional.

**Core Task:** Answer the user's question using ONLY the text from the provided URL: {url}

**Conversation History (for context): Do not give priority to the conversation history, it is only there to guide you as a bot. If a new question is asked, search accordingly.**
---
{conv}
---

**Response Rules (Follow Strictly):**
0. If user's question isnt a question and is a greeting or general conversation, reply accordingly in a casual manner.
1.  **Be Brief:** Provide only the direct answer. Do not use extra words, conversational filler, or pleasantries.
2.  **"Not Found" Handling:** If the requested information (like a person or title) is not on the webpage, state clearly and simply that it is not listed.
    * *Example for a missing title:* "There is no position with that title listed on the Provost's Office webpage."
3.  **General Contact:** If the user asks a general "who to contact" question, provide ONLY the following details, else search the specific webpage for the person/department asked.
    Office of the Provost and Executive Vice President
    Office: 408 554 4533
    Fax: 408 551 6074
    Email: provost@scu.edu
4. Your replies short be as short as possible, with relevant information but not too much. Avoid verbosity.
5. If the user asks for a specific person's contact details, search and provide them accordingly. If you cannot find it on the webpage, check the footer, it will definitely have the contact details for that specific person.

**ABSOLUTELY DO NOT:**
* Do NOT mention that you are a bot or an AI.
* Do NOT mention that you performed a search or looked at a website.
* Do NOT include the URL in your answer.
* Do NOT explain *why* the information is not available.
* This is the most important part - DO NOT say that the url does not list, or that information couldnt be found.

**User's Question:**
{query} in SCU Provost

**Answer:**
"""
    return searchFx(prompt)

def identify_relevant_file(query, all_filenames,conv):
    conv = "\n".join([f"{item['role']}: {item['content']}" for item in conv])
    print("Identifying the most relevant file")

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
{query} in SCU Provost

**Most Relevant Filename:**
"""
    try:
        response = searchFx(prompt)
        if response in all_filenames:
            return response
        else:
            print(f"Warning: Model returned a filename not in the list: '{response}'")
            return None
    except Exception as e:
        print(f"An error occurred during file identification: {e}")
        return None

#FLASK
app = Flask(__name__)
CORS(app)  # 2. INITIALIZE CORS FOR YOUR APP

is_initialized = False
file_to_url_map = {}

def initialize_app():
    global is_initialized, file_to_url_map
    with open('gen.json', 'r', encoding='utf-8') as f:
        file_to_url_map = json.load(f)
    is_initialized = True
    print("\n--- Provost chatbot is ready (loaded from gen.json) ---")
    return True

#Routed to / for home endpoint
@app.route('/', methods=['POST'])
def handle_qa():
    generalConversation = False
    if not is_initialized:
        return jsonify({"error": "Server not initialized."}), 503
    data = request.get_json()
    if not data or 'question' not in data:
        return jsonify({"error": "Request must be JSON with a 'question' field."}), 400
    query = data['question']

    # Get filenames directly from the pre-loaded map
    all_filenames = list(file_to_url_map.keys())
    relevant_filename = identify_relevant_file(query, all_filenames, conversation_history)

    if not relevant_filename:
        # return jsonify({"answer": "General conversation", "source": "File Identification Failed"})
        generalConversation = True
        relevant_filename = "User asked a question outside the scope of chatbot, if its a general conversation, reply accordingly else reply 'I cannot help you with that!"
    
    if not generalConversation:
        url_to_search = file_to_url_map.get(relevant_filename)
        print(url_to_search)
        final_answer = urlSearchFx(query, url_to_search, conversation_history) 
        conversation_history.append({'role': 'User', 'content': query})
        conversation_history.append({'role': 'Assistant', 'content': final_answer})
    
    else:
        final_answer =  searchFx(query)
        generalConversation = False

    # if "not listed" or "not found" or "not available" or "couldn't find" in str(final_answer).lower():
    #     return jsonify({"answer": f"I couldn't find the information you were looking for, but here are more details: {url_to_search}"})
    return jsonify({"answer": final_answer})

if __name__ == '__main__':
    initialize_app()
    app.run(host='0.0.0.0', port=8080)
