import os
import ssl
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import String, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# 🔐 SSL-настройки для Render PostgreSQL
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# 🎯 Async SQLAlchemy engine с поддержкой SSL
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"ssl": ssl_context}
)

# 💾 Сессия для взаимодействия с БД
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# 🧱 Базовый класс моделей
class Base(DeclarativeBase):
    pass

# 📋 Модель таблицы для хранения саммари
class Summary(Base):
    __tablename__ = "summaries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    text: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)

# 🚀 Инициализация БД (создание таблиц)
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# 📥 Сохранение саммари в базу
async def save_summary(text: str, summary: str):
    async with async_session() as session:
        session.add(Summary(text=text, summary=summary))
        await session.commit()
