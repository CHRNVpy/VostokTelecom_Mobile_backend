import calendar
import json
import os
from datetime import datetime, timedelta
from pprint import pprint

import aiomysql
import asyncio
from dotenv import load_dotenv

load_dotenv()

USER = os.getenv('billing_db_user')
PASS = os.getenv('billing_db_pass')
DB_NAME = os.getenv('billing_db_name')
DB_HOST = os.getenv('billing_db_host')
DB_PORT = int(os.getenv('billing_db_port'))

OLD_USER = os.getenv('old_billing_db_user')
OLD_PASS = os.getenv('old_billing_db_pass')
OLD_DB_NAME = os.getenv('old_billing_db_name')
OLD_DB_HOST = os.getenv('old_billing_db_host')

db_config = {
    'user': USER,
    'password': PASS,
    'db': DB_NAME,
    'host': DB_HOST,
    'port': DB_PORT,
}

old_db_config = {
    'user': OLD_USER,
    'password': OLD_PASS,
    'db': OLD_DB_NAME,
    'host': OLD_DB_HOST,
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


async def get_user_new(login: str):
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


async def get_user_old(login: str | int):
    query = 'SELECT login, passwd1 FROM account WHERE login = %s'
    async with aiomysql.create_pool(**old_db_config) as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (login,))
                result = await cur.fetchone()  # is not None
                if result is not None:
                    return {'username': result[0], 'password': result[1]}
                else:
                    return False


async def get_user(account):
    user = {}
    match len(account):
        case 4:
            user = await get_user_old(account)
        case 5:
            user = await get_user_new(account)
    return user


async def get_payments_new(account):
    def date_90_days_ago():
        # Get the current date
        today = datetime.now()
        # Calculate the date 90 days ago
        date_90_days_ago = today - timedelta(days=90)
        return date_90_days_ago

    payments_sql = """
    SELECT id, summa, lm FROM contract_payment WHERE cid =
    (SELECT id FROM contract WHERE title = %s) 
    AND dt > %s
    ORDER BY dt DESC"""

    async with aiomysql.create_pool(**db_config) as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(payments_sql, (account, date_90_days_ago()))
                payments = await cur.fetchall()
                history = [{'id': pay[0],
                            'date': pay[2].strftime("%d.%m.%y %H:%M:%S"),
                            'summ': float(pay[1])} for pay in payments if payments]
                return history


async def get_payments_old(account):
    def date_90_days_ago():
        # Get the current date
        today = datetime.now()
        # Calculate the date 90 days ago
        date_90_days_ago = today - timedelta(days=90)
        return date_90_days_ago.timestamp()

    payments_sql = """
    SELECT id, sum, date_add FROM deposit WHERE account_id =
    (SELECT id FROM account WHERE login = %s) 
    AND date_add > %s
    ORDER BY date_add DESC"""

    async with aiomysql.create_pool(**old_db_config) as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(payments_sql, (account, date_90_days_ago()))
                payments = await cur.fetchall()
                history = [{'id': pay[0],
                            'date': datetime.fromtimestamp(pay[2]).strftime("%d.%m.%Y %H:%M:%S"),
                            'summ': float(pay[1])} for pay in payments if payments]
                return history


async def get_payments(account):
    payments = []
    match len(account):
        case 4:
            payments = await get_payments_old(account)
        case 5:
            payments = await get_payments_new(account)
    return payments


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


async def update_password(account, new_password):
    # SQL query
    query = """
    UPDATE contract SET pswd = %s WHERE title = %s
    """
    async with aiomysql.create_pool(**db_config) as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (new_password, account))
                await conn.commit()


async def get_all_alerted_accounts(zone_id):
    # SQL query
    sql = """SELECT title FROM contract WHERE gr = %s"""

    async with aiomysql.create_pool(**db_config) as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (zone_id,))
                result = await cur.fetchall()

    return [int(res[0]) for res in result if res[0].isdigit()]


async def get_user_data_new(account):
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
    (SELECT cid, MAX(yy) AS max_year, MAX(mm) AS max_month
     FROM contract_balance
     GROUP BY cid) AS max_balance ON contract.id = max_balance.cid
	LEFT JOIN
	    contract_balance ON contract.id = contract_balance.cid 
	                     AND contract_balance.yy = max_balance.max_year 
	                     AND contract_balance.mm = max_balance.max_month
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
                    min_payment = rate_cost_int[user_info['rate_name']] - user_info['balance'] if user_info[
                        'rate_name'] else 0
                    user_info['min_pay'] = float(min_payment) if float(min_payment) > 0 else 0.00
                    user_info['pay_day'] = penultimate_date_of_current_month()
    return user_info


async def get_user_data_old(account: str | int):
    user_info = {'account': account}
    user_query = """
    SELECT 
        CONCAT(account.last_name, ' ', account.first_name, ' ', account.patronymic) AS full_name,
        account.cell_phone1 AS phone, 
        account.email AS email, 
        account.balance AS balance,
        tariff.name AS rate_name,
        tariff.price AS rate_cost
    FROM 
        account
    LEFT JOIN 
        account_service ON account_service.account_id = account.id
    LEFT JOIN 
        tariff ON tariff.id = account_service.tariff_id
    WHERE 
        account.login = %s
    LIMIT 1;
    """
    async with aiomysql.create_pool(**old_db_config) as pool:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(user_query, (account,))
                user_data = await cur.fetchone()
                # print(user_data)
                if user_data:
                    user_info['full_name'] = user_data['full_name'] if user_data['full_name'] else ''
                    user_info['phone'] = user_data['phone'] if user_data['phone'] else ''
                    user_info['address'] = ''  # user_data['address'] if user_data['address'] else ''
                    user_info['email'] = user_data['email'] if user_data['email'] else ''
                    user_info['rate_name'] = user_data['rate_name'] if user_data['rate_name'] else ''
                    user_info['rate_speed'] = ''  # user_data['rate_name'].split("-")[1] + 'Мбит/с' if user_data[
                    # 'rate_name'] else ''
                    user_info['rate_cost'] = user_data['rate_cost'] if user_data['rate_cost'] else ''
                    user_info['balance'] = round(user_data['balance'], 2) if user_data['balance'] else 0.00
                    min_payment = user_info['rate_cost'] - user_info['balance'] if user_info['rate_cost'] else 0
                    user_info['min_pay'] = min_payment if min_payment > 0 else 0.00
                    user_info['pay_day'] = penultimate_date_of_current_month()
            return user_info


async def get_user_data(account):
    user = {}
    match len(account):
        case 4:
            user = await get_user_data_old(account)
        case 5:
            user = await get_user_data_new(account)
    return user

# async def update_balance_old():

# pprint(asyncio.run(get_user_data('11310')))
# print(asyncio.run(get_payments(11816)))
# print(asyncio.run(get_user_data_old('0010')))
