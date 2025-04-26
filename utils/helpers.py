from datetime import datetime, timedelta
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

def greet_user(name: str) -> str:
    return f"Привет, {name}! Добро пожаловать в бота."

async def generate_chat_pdf(file_path: str, chat_id: int, messages: list[dict]):
    doc = SimpleDocTemplate(file_path, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [Paragraph(f"Чат {chat_id}", styles['Title']), Spacer(1, 12)]
    for m in messages:
        ts = m['created_at'].strftime('%Y-%m-%d %H:%M')
        story.append(Paragraph(f"[{ts}] {m['user_name']}: {m['content']}", styles['BodyText']))
        story.append(Spacer(1, 6))
    doc.build(story)
