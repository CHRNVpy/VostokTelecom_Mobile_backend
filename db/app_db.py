import asyncio
import calendar
import os
from datetime import datetime, timedelta

import aiosqlite
from dotenv import load_dotenv

load_dotenv()

DB_NAME = os.getenv('app_db')


def penultimate_date_of_current_month():
    # Get the current date
    today = datetime.now()
    # Get the last day of the current month
    _, last_day = calendar.monthrange(today.year, today.month)
    # Calculate the penultimate date by subtracting one day from the last day
    penultimate_date = today.replace(day=last_day) - timedelta(days=1)
    # formatted_date = penultimate_date.strftime("%d.%m.%Y")
    return penultimate_date


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS refresh_tokens ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "user TEXT UNIQUE, "
            "password TEXT, "
            "token TEXT UNIQUE)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS autopayments ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "user TEXT UNIQUE, "
            "bindingId TEXT, "
            "payment_summ INTEGER, "
            "ip TEXT, "
            "updated DATETIME, "
            "FOREIGN KEY(user) REFERENCES refresh_tokens(user))"
        )

        await db.execute(
            "CREATE TABLE IF NOT EXISTS alerts ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "user TEXT, "
            "status INTEGER, "
            "FOREIGN KEY(user) REFERENCES refresh_tokens(user))"
        )
        await db.commit()


async def add_user(user: str, password: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO refresh_tokens (user, password) VALUES (?, ?)",
                         (user, password))
        await db.commit()


async def store_refresh_token(user: str, password: str, refresh_token: str):
    async with aiosqlite.connect(DB_NAME) as db:
        # await db.execute("INSERT INTO refresh_tokens (user, password, token) VALUES (?, ?, ?)",
        #                  (user, password, refresh_token))
        await db.execute("UPDATE refresh_tokens SET token = ? WHERE user = ? AND password = ?",
                         (refresh_token, user, password))
        await db.commit()


async def is_refresh_token_valid(refresh_token: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM refresh_tokens WHERE token = ?", (refresh_token,)) as cursor:
            return await cursor.fetchone() is not None


async def is_autopaid(user_id: str) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM autopayments WHERE user = ?", (user_id, )) as cur:
            result = await cur.fetchone()
            if result is not None:
                return True
            return False


async def set_autopay(user_id: str, binding_id: str, payment_summ: int | float, ip: str):
    last_updated = datetime.now()
    async with aiosqlite.connect(DB_NAME) as db:
        if await is_autopaid(user_id):
            await db.execute("UPDATE autopayments SET bindingId = ?, payment_summ = ?, ip = ?, updated = ? "
                             "WHERE user = ?", (binding_id, payment_summ, ip, last_updated, user_id))
        else:
            await db.execute("INSERT OR IGNORE INTO autopayments (user, bindingId, payment_summ, ip, updated) "
                             "VALUES (?, ?, ?, ?, ?)", (user_id, binding_id, payment_summ, ip, last_updated))
        await db.commit()


async def get_autopay(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM autopayments WHERE user = ?", (user_id,)) as cursor:
            result = await cursor.fetchone()
            if result is not None and result[2] is not None:
                return {"enabled": True,
                        "pay_day": penultimate_date_of_current_month().strftime("%d.%m.%Y"),
                        "pay_summ": result[3]}
            else:
                return {"enabled": False,
                        "pay_day": '',
                        "pay_summ": 0.0}


async def get_autopay_users():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM autopayments WHERE bindingId IS NOT NULL") as cur:
            result = await cur.fetchall()
            return result


async def delete_autopay(user_id: str):
    async with aiosqlite.connect(DB_NAME) as db:
        last_updated = datetime.now()
        await db.execute("UPDATE autopayments SET bindingId = ?, payment_summ = ?, updated = ? WHERE user = ?",
                         (None, None, last_updated, user_id))
        await db.commit()


async def get_accounts():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user FROM refresh_tokens") as cursor:
            users = await cursor.fetchall()
            old_accounts = [user[0] for user in users if len(user[0]) == 4]
            new_accounts = [user[0] for user in users if len(user[0]) == 5]
            return {"old": old_accounts, "new": new_accounts}


async def get_accident_status(account: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT status FROM alerts WHERE user = ?",
                         (account, )) as cursor:
            status = await cursor.fetchone()
            if status is not None and status[0]:
                return True
            else:
                return False


async def set_accident_status(accounts: list) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE alerts SET status = ?", (0, ))
        for account in accounts:
            current_status = await get_accident_status(account)
            if not current_status:
                await db.execute("INSERT OR IGNORE INTO alerts (user, status) VALUES (?, ?)",
                                 (account, 1))
            else:
                await db.execute("UPDATE alerts SET status = ? WHERE user = ?",
                                 (1, account))
        await db.commit()


# async def add_room(user: str):
#     async with aiosqlite.connect(DB_NAME) as db:
#         await db.execute("INSERT OR IGNORE INTO rooms (created_by) VALUES (?)",
#                          (user, ))
#         await db.commit()
#
#
# async def get_rooms():
#     async with aiosqlite.connect(DB_NAME) as db:
#         async with await db.execute("SELECT * FROM rooms") as cursor:
#             return await cursor.fetchall()


# print(asyncio.run(get_autopay('11310')))
# print(asyncio.run(get_accounts()))
# print(asyncio.run(is_autopaid('0001')))
