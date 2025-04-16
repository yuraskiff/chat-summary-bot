import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

def generate_summary(messages):
    prompt = f"""
Проанализируй следующие сообщения и ответь на 4 вопроса:
1. Какие были главные темы обсуждений?
2. Кто показался самым интересным собеседником?
3. Кто был самым бесполезным или токсичным участником?
4. Какие интересные темы можно предложить на завтра?

Вот сообщения:
{messages}
"""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=700
    )
    return response['choices'][0]['message']['content']
