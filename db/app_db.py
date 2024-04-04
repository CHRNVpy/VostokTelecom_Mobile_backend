import asyncio
import calendar
from datetime import datetime, timedelta

import aiosqlite

from db.billing_db import get_user_data

DB_NAME = "/home/chrnv/PycharmProjects/VostokTelecom_Mobile_backend/vt_mobile_app.db"


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
            "autopay_date DATETIME, "
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


async def set_autopay(user_id, binding_id):
    autopay_date = penultimate_date_of_current_month()
    user_data = await get_autopay(user_id)
    async with aiosqlite.connect(DB_NAME) as db:
        if user_data['enabled']:
            await db.execute("UPDATE autopayments SET bindingId = ?, autopay_date = ? WHERE user = ?",
                             (binding_id, autopay_date, user_id))
        else:
            await db.execute("INSERT OR IGNORE INTO autopayments (user, bindingId, autopay_date) VALUES (?, ?, ?)",
                             (user_id, binding_id, autopay_date))
        await db.commit()


async def get_autopay(user_id):
    user_data = await get_user_data(user_id)
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM autopayments WHERE user = ?", (user_id,)) as cursor:
            result = await cursor.fetchone()
            if result is not None:
                return {"enabled": True,
                        "pay_day": user_data['pay_day'],
                        "pay_summ": user_data['min_pay']}
            else:
                return {"enabled": False,
                        "pay_day": '',
                        "pay_summ": 0.0}


async def delete_autopay(user_id: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM autopayments WHERE user = ?",
                         (user_id,))
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
