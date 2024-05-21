import asyncio
import calendar
import datetime
import json
import os
import time
from pprint import pprint

import aiohttp
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from acquiring import get_status_payment, pay_request, autopay_request
from db.app_db import set_autopay, get_accounts, set_accident_status, get_autopay_users, add_news, news_exist, \
    update_news
from db.billing_db import update_user_balance_old, get_user_group_ids
from dotenv import load_dotenv

load_dotenv()


async def check_payment_status(order_id: str, user_id=None, autopay=False) -> None:
    while True:
        json_status = await get_status_payment(order_id)
        status = json.loads(json_status)
        if status.get('OrderStatus'):
            if status['OrderStatus'] == 2:
                # print('Проведена полная авторизация суммы заказа')
                payment_summ = int(status['Amount']) / 100
                if autopay:
                    await set_autopay(user_id, status['bindingId'], payment_summ, status['Ip'])
                txn_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                update_balance_url = (f'https://billing-2.vt54.ru/alfa-pay/1?command=pay&txn_id={order_id}&'
                                      f'txn_date={txn_date}&sum={float(payment_summ)}&account={user_id}')
                match len(user_id):
                    case 4:
                        await update_user_balance_old(user_id, payment_summ, order_id)
                    case 5:
                        async with aiohttp.ClientSession() as session:
                            await session.get(update_balance_url)
                            # print(await response.text())
                break
            elif status['OrderStatus'] in [3, 6]:
                # print('Авторизация отклонена')
                break
            else:
                # print(json.loads(status)['OrderStatus'])
                await asyncio.sleep(5)


async def init_autopay():
    today = datetime.datetime.now()
    _, last_day = calendar.monthrange(today.year, today.month)
    penultimate_date = today.replace(day=last_day) - datetime.timedelta(days=1)
    if today != penultimate_date:
        users = await get_autopay_users()
        for user in users:
            user_id = user[1]
            binding_id = user[2]
            payment_amount = user[3]
            ip = user[4]
            pay_response = await pay_request(amount_rubles=payment_amount, auto_payment=True, client_id=user_id)
            await autopay_request(pay_response['orderId'], binding_id, ip)
            await check_payment_status(pay_response['orderId'], user_id, autopay=True)


async def check_alerts():
    # print("Checking alerts enabled")
    accounts = await get_accounts()
    print(accounts)
    groups = await get_user_group_ids(accounts)
    print(groups)
    url = 'https://zabbix2.vt54.ru/zabbix/api_jsonrpc.php'
    host_group_data = {
        "jsonrpc": "2.0",
        "method": "hostgroup.get",
        "params": {
            "output": ["groupid", "name"],
            "filter": {
                "name": list(groups.keys())
            }
        },
        "auth": os.getenv('zabbix_token'),
        "id": 2
    }

    async def zabbix_request(url, data):
        async with aiohttp.ClientSession() as session:
            async with session.get(url, json=data) as response:
                response_json = await response.json()
                return response_json

    group_id_response = await zabbix_request(url, host_group_data)
    print(group_id_response)
    try:
        host_groups_ids = [int(item['groupid']) for item in group_id_response['result'] if group_id_response['result']]

        status_data = {
            "jsonrpc": "2.0",
            "method": "host.get",
            "params": {
                "output": ["name", "status"],
                "selectHostGroups": "extend",
                "groupids": host_groups_ids
            },
            "auth": os.getenv('zabbix_token'),
            "id": 1
        }

        status_response = await zabbix_request(url, status_data)
        affected_hostgroups = [item for item in status_response['result'] if int(item['status'])]
        felix_names = [group['name'] for d in affected_hostgroups for group in d['hostgroups']
                       if group['name'].startswith('felix')]
        bgbilling_names = [group['name'] for d in affected_hostgroups for group in d['hostgroups']
                           if group['name'].startswith('bgbilling')]
        felix_accounts_to_notify = [account for name in felix_names for account in groups.get(name, [])]
        bgbilling_accounts_to_notify = [account for name in bgbilling_names for account in groups.get(name, [])]
        account_to_notify = felix_accounts_to_notify + bgbilling_accounts_to_notify
        await set_accident_status(account_to_notify)
    except KeyError:
        pass


async def check_news():
    scope = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/drive.file',
             'https://www.googleapis.com/auth/spreadsheets']

    creds = ServiceAccountCredentials.from_json_keyfile_name('peppy-tiger-374003-fa5a704f0d24.json', scope)

    client = gspread.authorize(creds)

    wks = client.open("vt54_news").sheet1
    all_rows = wks.get_all_values()
    if await news_exist():
        for row in all_rows:
            if row[1].isdigit():
                await update_news(int(row[1]), row[0], row[2])
    else:
        for row in all_rows:
            if row[1].isdigit():
                await add_news(int(row[1]), row[0], row[2])

# asyncio.run(check_news())
