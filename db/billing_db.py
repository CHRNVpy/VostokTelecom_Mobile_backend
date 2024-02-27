import calendar
import json
import os
from datetime import datetime, timedelta

import aiomysql
import asyncio
from dotenv import load_dotenv

load_dotenv()

USER = os.getenv('billing_db_user')
PASS = os.getenv('billing_db_pass')
DB_NAME = os.getenv('billing_db_name')
DB_HOST = os.getenv('billing_db_host')
DB_PORT = int(os.getenv('billing_db_port'))

db_config = {
    'user': USER,
    'password': PASS,
    'db': DB_NAME,
    'host': DB_HOST,
    'port': DB_PORT,
}


def penultimate_date_of_current_month():
    # Get the current date
    today = datetime.now()
    # Get the last day of the current month
    _, last_day = calendar.monthrange(today.year, today.month)
    # Calculate the penultimate date by subtracting one day from the last day
    penultimate_date = today.replace(day=last_day) - timedelta(days=1)
    formatted_date = penultimate_date.strftime("%d.%m.%Y")
    return formatted_date


async def get_user(login: str):
    query = 'SELECT title, pswd FROM contract WHERE title = %s'
    async with aiomysql.create_pool(**db_config) as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (login,))
                result = await cur.fetchone()  # is not None
                if result is not None:
                    return {'username': result[0], 'password': result[1]}
                else:
                    return False


async def get_balance(account):
    # SQL query
    balance_sql = """
    SELECT
            (summa1 + summa2 - summa3 - summa4) AS sum_result
        FROM
            contract_balance
        WHERE
            cid = (SELECT id FROM contract WHERE title = %s)
        ORDER BY
            yy DESC, mm DESC
        LIMIT 1;
    """

    async with aiomysql.create_pool(**db_config) as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(balance_sql, (account,))
                result = await cur.fetchone()
                if result is not None:
                    return float(result[0])
                else:
                    return 0.00


async def get_minimal_payment(account):
    balance_info = {}
    rate_cost = {
        'Минимальный-15': 3550,
        'Стартовый-50': 4990,
        'Оптимальный-100': 5990,
        'Ускоренный-300': 6990
    }
    balance_sql = """
        SELECT
                (summa1 + summa2 - summa3 - summa4) AS sum_result
            FROM
                contract_balance
            WHERE
                cid = (SELECT id FROM contract WHERE title = %s)
            ORDER BY
                yy DESC, mm DESC
            LIMIT 1;
        """
    rate_name_sql = """SELECT title_web FROM tariff_plan 
        WHERE id = (SELECT tpid FROM contract_tariff 
                    WHERE cid = (SELECT id FROM contract WHERE title = %s) 
                    ORDER BY id DESC LIMIT 1)"""

    async with aiomysql.create_pool(**db_config) as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(balance_sql, (account,))
                balance = await cur.fetchone()
                balance_info['balance'] = float(balance[0])
                await cur.execute(rate_name_sql, (account,))
                rate_name = await cur.fetchone()
                min_payment = rate_cost[rate_name[0]] - balance[0] if rate_name is not None else 0
                balance_info['min_pay'] = float(min_payment) if float(min_payment) > 0 else 0.00
                balance_info['pay_day'] = penultimate_date_of_current_month()
    return balance_info


async def get_payments(account):
    def date_90_days_ago():
        # Get the current date
        today = datetime.now()
        # Calculate the date 90 days ago
        date_90_days_ago = today - timedelta(days=90)
        return date_90_days_ago

    payments_sql = """
    SELECT summa, lm FROM contract_payment WHERE cid =
    (SELECT id FROM contract WHERE title = %s) 
    AND dt > %s
    ORDER BY dt DESC"""

    async with aiomysql.create_pool(**db_config) as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(payments_sql, (account, date_90_days_ago()))
                payments = await cur.fetchall()
                payment = '\n'.join(
                    [f'Сумма: {float(pay[0])}, Дата: {pay[1].strftime("%d.%m.%y %H:%M:%S")}' for pay in payments])
                return payment


async def check_login(login):
    # SQL query
    sql = """
    SELECT title FROM contract WHERE title = %s
    """

    async with aiomysql.create_pool(**db_config) as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (login,))
                result = await cur.fetchone()
                if result is not None:
                    return True
                else:
                    return False


async def check_password(password):
    # SQL query
    sql = """
    SELECT pswd FROM contract WHERE pswd = %s
    """

    async with aiomysql.create_pool(**db_config) as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (password,))
                result = await cur.fetchone()
                if result is not None:
                    return True
                else:
                    return False


async def get_user_data(account):
    user_info = {'account': account}
    # SQL query
    name_sql = """
    SELECT comment FROM contract WHERE title = %s
    """
    phone_sql = """
    SELECT value FROM contract_parameter_type_phone 
    WHERE cid = (SELECT id FROM contract WHERE title = %s)"""
    address_sql = """
    SELECT address FROM contract_parameter_type_2 
    WHERE cid = (SELECT id FROM contract WHERE title = %s)"""
    email_sql = """
    SELECT email FROM contract_parameter_type_3 
    WHERE cid = (SELECT id FROM contract WHERE title = %s)"""

    async with aiomysql.create_pool(**db_config) as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(name_sql, (account,))
                full_name = await cur.fetchone()
                if full_name is not None:
                    if len(full_name[0].split(' ')) == 4:
                        user_info['fio'] = full_name[0].rsplit(' ', 1)[0]
                    else:
                        user_info['fio'] = full_name[0]
                else:
                    user_info['fio'] = ''
                await cur.execute(phone_sql, (account,))
                phone = await cur.fetchone()
                if phone is not None:
                    user_info['phone'] = phone[0]
                else:
                    user_info['phone'] = ''
                await cur.execute(address_sql, (account,))
                address = await cur.fetchone()
                if address is not None:
                    user_info['address'] = address[0].lstrip(', ')
                else:
                    user_info['address'] = ''
                await cur.execute(email_sql, (account,))
                email = await cur.fetchone()
                if email is not None:
                    user_info['email'] = email[0]
                else:
                    user_info['email'] = ''
    return user_info


async def get_rate(account):
    rate_cost = {
        'Минимальный-15': '3550тг/мес',
        'Стартовый-50': '4990тг/мес',
        'Оптимальный-100': '5990тг/мес',
        'Ускоренный-300': '6990тг/мес'
    }
    rate_info = {}
    # SQL query
    rate_name_sql = """SELECT title_web FROM tariff_plan 
        WHERE id = (SELECT tpid FROM contract_tariff 
                    WHERE cid = (SELECT id FROM contract WHERE title = %s) 
                    ORDER BY id DESC LIMIT 1)"""

    async with aiomysql.create_pool(**db_config) as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(rate_name_sql, (account,))
                rate_name = await cur.fetchone()
                if rate_name is not None:
                    rate_info['rate_name'] = rate_name[0]
                    rate_info['rate_speed'] = f'{rate_name[0].split("-")[1]}Мбит/с'
                    rate_info['rate_cost'] = rate_cost[rate_name[0]]
                else:
                    rate_info['rate_name'] = ''
                    rate_info['rate_speed'] = ''
                    rate_info['rate_cost'] = ''
    return rate_info


async def get_all_alerted_accounts(zone_id):
    # SQL query
    sql = """SELECT title FROM contract WHERE gr = %s"""

    async with aiomysql.create_pool(**db_config) as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (zone_id,))
                result = await cur.fetchall()

    return [int(res[0]) for res in result if res[0].isdigit()]


async def get_full_user_data(account):
    rate_cost = {
        'Минимальный-15': '3550тг/мес',
        'Стартовый-50': '4990тг/мес',
        'Оптимальный-100': '5990тг/мес',
        'Ускоренный-300': '6990тг/мес'
    }

    rate_cost_int = {
        'Минимальный-15': 3550,
        'Стартовый-50': 4990,
        'Оптимальный-100': 5990,
        'Ускоренный-300': 6990
    }

    def _prettify_name(full_name):
        if len(full_name.split(' ')) == 4:
            name = full_name.rsplit(' ', 1)[0]
        else:
            name = full_name
        return name

    user_info = {'account': account}
    # SQL query
    user_sql = """
    SELECT 
        contract.comment AS full_name,
        contract_parameter_type_phone.value AS phone,
        contract_parameter_type_2.address AS address,
        contract_parameter_type_3.email AS email,
        tariff_plan.title_web AS rate_name,
        (contract_balance.summa1 + contract_balance.summa2 - contract_balance.summa3 - contract_balance.summa4) AS balance
    FROM 
        contract
    LEFT JOIN 
        contract_parameter_type_phone ON contract_parameter_type_phone.cid = contract.id
    LEFT JOIN 
        contract_parameter_type_2 ON contract_parameter_type_2.cid = contract.id
    LEFT JOIN 
        contract_parameter_type_3 ON contract_parameter_type_3.cid = contract.id
    LEFT JOIN 
        contract_tariff ON contract_tariff.cid = contract.id
    LEFT JOIN 
        tariff_plan ON contract_tariff.tpid = tariff_plan.id
    LEFT JOIN
        contract_balance ON contract_balance.cid = contract.id
    WHERE 
        contract.title = %s
    ORDER BY 
        contract_tariff.id DESC
    LIMIT 1
    """

    async with aiomysql.create_pool(**db_config) as pool:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(user_sql, (account,))
                user_data = await cur.fetchone()
                if user_data:
                    user_info['full_name'] = _prettify_name(user_data['full_name']) if user_data['full_name'] else ''
                    user_info['phone'] = user_data['phone'] if user_data['phone'] else ''
                    user_info['address'] = user_data['address'] if user_data['address'] else ''
                    user_info['email'] = user_data['email'] if user_data['email'] else ''
                    user_info['rate_name'] = user_data['rate_name'] if user_data['rate_name'] else ''
                    user_info['rate_speed'] = user_data['rate_name'].split("-")[1] + 'Мбит/с' if user_data[
                        'rate_name'] else ''
                    user_info['rate_cost'] = rate_cost[user_data['rate_name']] if user_data['rate_name'] else ''
                    user_info['balance'] = float(user_data['balance']) if user_data['balance'] else 0.00
                    min_payment = rate_cost_int[user_info['rate_name']] - user_info['balance'] if user_info['rate_name'] else 0
                    user_info['min_pay'] = float(min_payment) if float(min_payment) > 0 else 0.00
                    user_info['pay_day'] = penultimate_date_of_current_month()
    return user_info

# print(asyncio.run(get_full_user_data('11529')))
