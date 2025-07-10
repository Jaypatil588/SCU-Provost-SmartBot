from google import genai
from google.genai import types

# Configure the client
client = genai.Client(
        api_key = "AIzaSyB4hP-FxNYmzyeOT6zwgfL3LsRd4zpgWjc"

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
    contents="What are the contact details from the following website? Including the text and contacts in the footer of this webpage? https://www.scu.edu/provost/",
    config=config,
)

# Print the grounded response
print(response.text)