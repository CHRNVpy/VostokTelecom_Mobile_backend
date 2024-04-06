import asyncio
import json
import os
import time
import uuid

import aiohttp
from dotenv import load_dotenv

load_dotenv()

USER = os.getenv('BANK_USER')
PASSWORD = os.getenv('BANK_PASS')


async def pay_request(amount_rubles, auto_payment=False, client_id=None):
    order_number = str(uuid.uuid4())
    amount_kopecks = amount_rubles * 100
    url = 'https://alfa.rbsuat.com/payment/rest/register.do'
    params = {
        'userName': USER,
        'password': PASSWORD,
        'orderNumber': order_number,
        'amount': amount_kopecks,
        'returnUrl': 'http://localhost:3000/top-up/done',
        'failUrl': 'http://localhost:3000/top-up/fail',
        'pageView': 'MOBILE'
    }

    if auto_payment:
        params['clientId'] = client_id

    headers = {'accept': '*/*'}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params, headers=headers) as response:
            print(await response.text())
            return json.loads(await response.text())


async def autopay_request(order_id, binding_id, client_ip):
    url = 'https://alfa.rbsuat.com/payment/rest/paymentOrderBinding.do'
    params = {
        'userName': USER,
        'password': PASSWORD,
        'mdOrder': order_id,
        'bindingId': binding_id,
        'ip': client_ip,
        'tii': 'U',
    }
    headers = {'accept': '*/*'}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params, headers=headers) as response:
            print(response.url)
            print(await response.text())
            return await response.text()


async def get_status_payment(order_id):
    url = 'https://alfa.rbsuat.com/payment/rest/getOrderStatus.do'
    params = {
        'userName': USER,
        'password': PASSWORD,
        'orderId': order_id
    }
    headers = {'accept': '*/*'}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params, headers=headers) as response:
            # print(response.url)
            # print(await response.text())
            return await response.text()


async def get_bindings(client_id):
    url = 'https://alfa.rbsuat.com/payment/rest/getBindings.do'
    params = {
        'userName': USER,
        'password': PASSWORD,
        'clientId': client_id
    }
    headers = {'accept': '*/*'}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params, headers=headers) as response:
            result = await response.text()
            return json.loads(result)


async def delete_binding(session, binding_id):
    url = 'https://alfa.rbsuat.com/payment/rest/unBindCard.do'
    params = {
        'userName': USER,
        'password': PASSWORD,
        'bindingId': binding_id
    }
    headers = {'accept': '*/*'}

    async with session.post(url, params=params, headers=headers) as response:
        print(await response.text())


async def delete_bindings(client_id):
    bindings = await get_bindings(client_id)
    binding_ids = bindings['bindings']

    async with aiohttp.ClientSession() as session:
        tasks = [delete_binding(session, binding_id['bindingId']) for binding_id in binding_ids]
        await asyncio.gather(*tasks)


# asyncio.run(pay_request(1010, str(uuid.uuid4())))
# asyncio.run(get_status_payment('040dfa5c-79d2-7b17-99c3-a1390206770f'))
# asyncio.run(autopay_request(order_id='04048abf-ae22-7016-822a-44400206770f',
#                             binding_id='7ab80967-6178-7829-8f31-616a0206770f',
#                             client_ip='91.105.141.111'))
# asyncio.run(autopay_confirm())
# print(asyncio.run(get_bindings('0000')))
# asyncio.run(delete_bindings('11310'))
# asyncio.run(reccurent_payment('7ab80967-6178-7829-8f31-616a0206770f', 1))
# asyncio.run(is_paid_order('040dfa5c-79d2-7b17-99c3-a1390206770f'))
