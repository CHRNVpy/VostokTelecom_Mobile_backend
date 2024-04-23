import asyncio
import calendar
import os
from datetime import datetime, timedelta

import aiosqlite
from dotenv import load_dotenv

from db.billing_db import get_group_id
from schemas import MessagesList, Message, Room, Rooms, News, NewsArticle

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

        await db.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "room_id TEXT, "
            "role TEXT, "
            "message TEXT, "
            "created_at INTEGER)"
        )

        await db.execute(
            "CREATE TABLE IF NOT EXISTS news ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "group_id INTEGER, "
            "message TEXT)"
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


async def add_news(group_id, message):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO news (group_id, message) VALUES (?, ?)",
                         (group_id, message))
        await db.commit()


async def get_group_news(account: str) -> News:
    group_id = await get_group_id(account)
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT message FROM news WHERE group_id = ?", (group_id,)) as cur:
            result = await cur.fetchall()
            return News(news=[NewsArticle(article=item[0]) for item in result])


async def is_autopaid(user_id: str) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM autopayments WHERE user = ?", (user_id,)) as cur:
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


async def add_message(room_id: str, role: str, message: str):
    async with aiosqlite.connect(DB_NAME) as db:
        created_at = datetime.now().timestamp()
        await db.execute("INSERT OR IGNORE INTO messages (room_id, role, message, created_at) VALUES (?, ?, ?, ?)",
                         (room_id, role, message, created_at))
        await db.commit()


async def get_messages(room_id: str, from_id: int = None, to_id: int = None):
    query = ("SELECT id AS id, role AS role, message AS message, created_at as created "
             "FROM messages WHERE 1 = 1 AND room_id = ?")
    params = [room_id]

    if from_id is not None:
        query += " AND id > ?"
        params.append(from_id)
    else:
        query += " AND (? IS NULL OR id > ?)"
        params.extend([from_id, from_id])

    if to_id is not None:
        query += " AND id < ?"
        params.append(to_id)
    else:
        query += " AND (? IS NULL OR id < ?)"
        params.extend([to_id, to_id])
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(query, params) as cur:
            result = await cur.fetchall()
    message_instances = [Message(id=id, role=role, message=message, created=int(created))
                         for id, role, message, created in result]
    return MessagesList(messages=message_instances)


async def get_rooms():
    query = "SELECT DISTINCT room_id FROM messages"
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(query, ) as cur:
            result = await cur.fetchall()
    room_instances = [Room(name=room[0])
                      for room in result]
    return Rooms(rooms=room_instances)


# print(asyncio.run(get_rooms()))

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
                              (account,)) as cursor:
            status = await cursor.fetchone()
            if status is not None and status[0]:
                return True
            else:
                return False


async def set_accident_status(accounts: list) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE alerts SET status = ?", (0,))
        for account in accounts:
            current_status = await get_accident_status(account)
            if not current_status:
                await db.execute("INSERT OR IGNORE INTO alerts (user, status) VALUES (?, ?)",
                                 (account, 1))
            else:
                await db.execute("UPDATE alerts SET status = ? WHERE user = ?",
                                 (1, account))
        await db.commit()

# print(asyncio.run(get_autopay('11310')))
# print(asyncio.run(get_accounts()))
# print(asyncio.run(is_autopaid('0001')))
