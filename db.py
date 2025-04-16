import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, BigInteger, select
from sqlalchemy.exc import IntegrityError

DATABASE_URL = os.getenv("DATABASE_URL").replace("postgresql://", "postgresql+asyncpg://")

Base = declarative_base()
engine = create_async_engine(DATABASE_URL, echo=False)
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
            await session.rollback()  # Группа уже есть

async def get_all_groups():
    async with async_session() as session:
        result = await session.execute(select(Group.id))
        return [row[0] for row in result.all()]
