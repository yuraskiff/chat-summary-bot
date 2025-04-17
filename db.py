import os
import ssl
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, BigInteger, select
from sqlalchemy.exc import IntegrityError

DATABASE_URL = os.getenv("DATABASE_URL").replace("postgresql://", "postgresql+asyncpg://")
ssl_context = ssl.create_default_context()

engine = create_async_engine(
    DATABASE_URL,
    connect_args={"ssl": ssl_context},
    echo=False
)

Base = declarative_base()
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Group(Base):
    __tablename__ = 'groups'
    id = Column(BigInteger, primary_key=True)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def add_group(chat_id: int):
    async with async_session() as session:
        group = Group(id=chat_id)
        session.add(group)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()

async def get_all_groups():
    async with async_session() as session:
        result = await session.execute(select(Group.id))
        return [row[0] for row in result.all()]

async def count_groups():
    async with async_session() as session:
        result = await session.execute(select(Group.id))
        return len(result.all())
