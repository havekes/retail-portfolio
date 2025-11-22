from src.database import sessionmanager
from src.repositories.sqlalchemy_account import SqlAlchemyAccountRepostory


async def get_sqlalchemy_account_repository():
    async with sessionmanager.session() as session:
        yield SqlAlchemyAccountRepostory(session)
