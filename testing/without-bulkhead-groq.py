from groq import Groq
import json

client = Groq()
article = open('filefile.md').read()

response = client.chat.completions.create(
    model='llama-3.1-8b-instant',
    max_tokens=500,
    messages=[{
        'role': 'user',
        'content': f'Summarise this financial report:\n\n{article}'
    }]
)

print("=== WITHOUT BULKHEAD (Llama 2 via Groq) ===")
print(response.choices[0].message.content)