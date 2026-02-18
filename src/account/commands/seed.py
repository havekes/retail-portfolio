import asyncio
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from src.account.enum import AccountTypeEnum, InstitutionEnum
from src.account.model import (
    AccountModel,
    AccountTypeModel,
    InstitutionModel,
    PortfolioAccountModel,
    PortfolioModel,
    PositionModel,
)
from src.auth.model import UserModel
from src.config.database import sessionmanager
from src.market.model import SecurityModel


async def _seed_user(session):
    print("Seeding user...")
    user_email = "test@example.com"
    user_password = "test"

    result = await session.execute(
        select(UserModel).where(UserModel.email == user_email)
    )
    user = result.scalar_one_or_none()

    if not user:
        user = UserModel(
            id=uuid.uuid4(),
            email=user_email,
            created_at=datetime.now(UTC),
        )
        user.password = user_password
        session.add(user)
        await session.flush()
        print(f"Created user: {user_email}")
    else:
        print(f"User {user_email} already exists")
    return user


async def _seed_account_types(session):
    print("Seeding account types...")
    account_types_data = [
        {
            "id": AccountTypeEnum.RRSP,
            "name": "RRSP",
            "country": "CA",
            "tax_advantaged": True,
        },
        {
            "id": AccountTypeEnum.TFSA,
            "name": "TFSA",
            "country": "CA",
            "tax_advantaged": True,
        },
        {
            "id": AccountTypeEnum.FHSA,
            "name": "FHSA",
            "country": "CA",
            "tax_advantaged": True,
        },
        {
            "id": AccountTypeEnum.NON_REGISTERED,
            "name": "Non-Registered",
            "country": "CA",
            "tax_advantaged": False,
        },
    ]

    account_types = {}
    for at_data in account_types_data:
        result = await session.execute(
            select(AccountTypeModel).where(AccountTypeModel.id == at_data["id"])
        )
        at = result.scalar_one_or_none()

        if not at:
            result = await session.execute(
                select(AccountTypeModel).where(
                    AccountTypeModel.name == at_data["name"],
                    AccountTypeModel.country == at_data["country"],
                )
            )
            at = result.scalar_one_or_none()

        if not at:
            at = AccountTypeModel(**at_data)
            session.add(at)
            await session.flush()

        account_types[at_data["id"]] = at
    print(f"Seeded {len(account_types)} account types")
    return account_types


async def _seed_institutions(session):
    print("Seeding institutions...")
    institutions_data = [
        {
            "id": InstitutionEnum.QUESTRADE,
            "name": "Questrade",
            "country": "CA",
            "website": "https://www.questrade.com",
        },
        {
            "id": InstitutionEnum.WEALTHSIMPLE,
            "name": "Wealthsimple",
            "country": "CA",
            "website": "https://www.wealthsimple.com",
        },
    ]

    institutions = {}
    for inst_data in institutions_data:
        result = await session.execute(
            select(InstitutionModel).where(InstitutionModel.id == inst_data["id"])
        )
        inst = result.scalar_one_or_none()

        if not inst:
            result = await session.execute(
                select(InstitutionModel).where(
                    InstitutionModel.name == inst_data["name"],
                    InstitutionModel.country == inst_data["country"],
                )
            )
            inst = result.scalar_one_or_none()

        if not inst:
            inst = InstitutionModel(**inst_data)
            session.add(inst)
            await session.flush()
        institutions[inst_data["id"]] = inst
    print(f"Seeded {len(institutions)} institutions")
    return institutions


async def _seed_securities(session):
    print("Seeding securities...")
    securities_data = [
        {
            "symbol": "AAPL",
            "exchange": "NASDAQ",
            "currency": "USD",
            "name": "Apple Inc.",
        },
        {
            "symbol": "MSFT",
            "exchange": "NASDAQ",
            "currency": "USD",
            "name": "Microsoft Corporation",
        },
        {
            "symbol": "VGRO.TO",
            "exchange": "TSX",
            "currency": "CAD",
            "name": "Vanguard Growth ETF Portfolio",
        },
        {
            "symbol": "XIU.TO",
            "exchange": "TSX",
            "currency": "CAD",
            "name": "iShares S&P/TSX 60 Index ETF",
        },
    ]

    securities = {}
    for sec_data in securities_data:
        result = await session.execute(
            select(SecurityModel).where(
                SecurityModel.symbol == sec_data["symbol"],
                SecurityModel.exchange == sec_data["exchange"],
            )
        )
        sec = result.scalar_one_or_none()
        if not sec:
            sec = SecurityModel(**sec_data)
            session.add(sec)
            await session.flush()
        securities[sec_data["symbol"]] = sec
    print(f"Seeded {len(securities)} securities")
    return securities


async def _seed_accounts(session, user, account_types, institutions):
    print("Seeding accounts...")
    accounts_data = [
        {
            "external_id": "ACC-001",
            "name": "My RRSP",
            "user_id": user.id,
            "account_type_id": account_types[AccountTypeEnum.RRSP].id,
            "institution_id": institutions[InstitutionEnum.QUESTRADE].id,
            "currency": "CAD",
        },
        {
            "external_id": "ACC-002",
            "name": "Main TFSA",
            "user_id": user.id,
            "account_type_id": account_types[AccountTypeEnum.TFSA].id,
            "institution_id": institutions[InstitutionEnum.WEALTHSIMPLE].id,
            "currency": "CAD",
        },
        {
            "external_id": "ACC-003",
            "name": "Side Trading",
            "user_id": user.id,
            "account_type_id": account_types[AccountTypeEnum.NON_REGISTERED].id,
            "institution_id": institutions[InstitutionEnum.QUESTRADE].id,
            "currency": "USD",
        },
    ]

    accounts = []
    for acc_data in accounts_data:
        result = await session.execute(
            select(AccountModel).where(
                AccountModel.user_id == user.id,
                AccountModel.external_id == acc_data["external_id"],
                AccountModel.institution_id == acc_data["institution_id"],
            )
        )
        acc = result.scalar_one_or_none()
        if not acc:
            acc = AccountModel(**acc_data)
            session.add(acc)
            await session.flush()
        accounts.append(acc)
    print(f"Seeded {len(accounts)} accounts")
    return accounts


async def _seed_positions(session, accounts, securities):
    print("Seeding positions...")
    positions_to_add = [
        {
            "account_id": accounts[0].id,
            "security_id": securities["VGRO.TO"].id,
            "quantity": Decimal("100.5"),
            "average_cost": 30.25,
        },
        {
            "account_id": accounts[0].id,
            "security_id": securities["XIU.TO"].id,
            "quantity": Decimal("50.0"),
            "average_cost": 28.10,
        },
        {
            "account_id": accounts[1].id,
            "security_id": securities["VGRO.TO"].id,
            "quantity": Decimal("200.0"),
            "average_cost": 31.00,
        },
        {
            "account_id": accounts[2].id,
            "security_id": securities["AAPL"].id,
            "quantity": Decimal("10.0"),
            "average_cost": 150.00,
        },
        {
            "account_id": accounts[2].id,
            "security_id": securities["MSFT"].id,
            "quantity": Decimal("5.0"),
            "average_cost": 280.00,
        },
    ]

    for pos_data in positions_to_add:
        result = await session.execute(
            select(PositionModel).where(
                PositionModel.account_id == pos_data["account_id"],
                PositionModel.security_id == pos_data["security_id"],
            )
        )
        pos = result.scalar_one_or_none()
        if not pos:
            pos = PositionModel(**pos_data)
            session.add(pos)
    print(f"Seeded {len(positions_to_add)} positions")


async def _seed_portfolios(session, user, accounts):
    print("Seeding portfolios...")
    portfolios_data = [
        {"name": "Long Term Retirement", "user_id": user.id},
        {"name": "Tech Speculation", "user_id": user.id},
    ]

    seeded_portfolios = []
    for port_data in portfolios_data:
        result = await session.execute(
            select(PortfolioModel).where(
                PortfolioModel.user_id == user.id,
                PortfolioModel.name == port_data["name"],
            )
        )
        port = result.scalar_one_or_none()
        if not port:
            port = PortfolioModel(**port_data)
            session.add(port)
            await session.flush()
        seeded_portfolios.append(port)

    portfolio_links = [
        {"portfolio_id": seeded_portfolios[0].id, "account_id": accounts[0].id},
        {"portfolio_id": seeded_portfolios[0].id, "account_id": accounts[1].id},
        {"portfolio_id": seeded_portfolios[1].id, "account_id": accounts[2].id},
    ]

    for link_data in portfolio_links:
        result = await session.execute(
            select(PortfolioAccountModel).where(
                PortfolioAccountModel.portfolio_id == link_data["portfolio_id"],
                PortfolioAccountModel.account_id == link_data["account_id"],
            )
        )
        link = result.scalar_one_or_none()
        if not link:
            link = PortfolioAccountModel(**link_data)
            session.add(link)

    print(f"Seeded {len(seeded_portfolios)} portfolios and linked them to accounts")


async def seed_data():
    async with sessionmanager.session() as session:
        user = await _seed_user(session)
        account_types = await _seed_account_types(session)
        institutions = await _seed_institutions(session)
        securities = await _seed_securities(session)
        accounts = await _seed_accounts(session, user, account_types, institutions)
        await _seed_positions(session, accounts, securities)
        await _seed_portfolios(session, user, accounts)

        await session.commit()
        print("Seeding completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed_data())
