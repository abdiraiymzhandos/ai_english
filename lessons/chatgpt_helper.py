import openai
from openai import OpenAI

client = OpenAI(api_key=settings.OPENAI_API_KEY)
from django.conf import settings

# Initialize OpenAI API key globally

def explain_lesson(content: str) -> str:
    try:
        response = client.chat.completions.create(model="gpt-4o",
        messages=[
            {"role": "system", "content": "Сен ағылшын тілі мұғалімісін. Сабақты қазақ тілінде түсіндір әрбір ағылшынша сөзді қазақша аударып, оның мағынасын түсіндіріп беруің керек."},
            {"role": "user", "content": content}
        ],
        temperature=0.7)
        return response.choices[0].message.content
    except openai.OpenAIError as e:
        return f"OpenAI қателігі: {str(e)}"
