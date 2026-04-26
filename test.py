from google import genai

# Folosește cheia ta
GOOGLE_API_KEY = "AIzaSyAsdRZFEL12WFeJmGh83IXQVC1u75HHeHQ"
client = genai.Client(api_key=GOOGLE_API_KEY)

print("Modelele disponibile pentru cheia ta sunt:")
for model in client.models.list():
    print(f"- {model.name}")