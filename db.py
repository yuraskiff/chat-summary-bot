import os
import ssl
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, BigInteger, select
from sqlalchemy.exc import IntegrityError

# Преобразуем обычный URL в asyncpg-совместимый
DATABASE_URL = os.getenv("DATABASE_URL").replace("postgresql://", "postgresql+asyncpg://")

# Создаём SSL-контекст (обязателен для Render PostgreSQL)
ssl_context = ssl.create_default_context()

# Создаём движок подключения к базе
engine = create_async_engine(
    DATABASE_URL,
    connect_args={"ssl": ssl_context},
    echo=False
)

# Основные настройки ORM
Base = declarative_base()
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Модель таблицы групп
class Group(Base):
    __tablename__ = 'groups'
    id = Column(BigInteger, primary_key=True)

# Инициализация базы
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Добавить группу
async def add_group(chat_id: int):
    async with async_session() as session:
        group = Group(id=chat_id)
        session.add(group)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()

# Получить все группы
async def get_all_groups():
    async with async_session() as session:
        result = await session.execute(select(Group.id))
        return [row[0] for row in result.all()]

# Получить количество групп
async def count_groups():
    async with async_session() as session:
        result = await session.execute(select(Group.id))
        return len(result.all())
