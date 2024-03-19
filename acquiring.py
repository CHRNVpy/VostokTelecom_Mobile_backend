import asyncio
import json
import time
import uuid

import aiohttp


async def pay_request(amount_rubles, order_number, auto_payment=False, client_id=None):
    amount_kopecks = amount_rubles * 100
    url = 'https://alfa.rbsuat.com/payment/rest/register.do'
    params = {
        'userName': 'vt54_ru-api',
        'password': 'vt54_ru*?1',
        'orderNumber': order_number,
        'amount': amount_kopecks,
        'returnUrl': 'https://localhost:3000/top-up/done',
        'failUrl': 'https://localhost:3000/top-up/fail',
        'pageView': 'MOBILE'
    }

    if auto_payment:
        params['clientId'] = client_id

    headers = {'accept': '*/*'}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params, headers=headers) as response:
            print(await response.text())
            return await response.text()


async def autopay_request(order_id, binding_id, client_ip):
    url = 'https://alfa.rbsuat.com/payment/rest/paymentOrderBinding.do'
    params = {
        'userName': 'vt54_ru-api',
        'password': 'vt54_ru*?1',
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


async def reccurent_payment(binding_id, amount_rubles):
    amount_kopecks = amount_rubles * 100
    url = 'https://alfa.rbsuat.com/payment/rest/recurrentPayment.do'
    params = {
        'userName': 'vt54_ru-api',
        'password': 'vt54_ru*?1',
        'orderNumber': str(uuid.uuid4()),
        'bindingId': binding_id,
        'amount': amount_kopecks
    }
    headers = {'accept': '*/*'}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params, headers=headers) as response:
            print(response.url)
            print(await response.text())
            return await response.text()


async def autopay_confirm():
    url = 'https://alfa.rbsuat.com/payment/rest/finish3ds.do?lang=ru'
    params = {
        'PaRes': 'eJxVUl1TwjAQ/CtM30vSNLSFOcKg6FhnKIziqI8hPaUoAUIqyK834UP07XZzt3e3F+jtFp+NLzSbaqm7QdSkQQO1WpaVfu8GT5PbMAt6AiYzgzh4RFUbFDDEzUa+Y6Mqu0GbYSbTMg0Vm05DLlMeSpph2M6Qx5S1mJJvgYBx/wHXAk6NhOvTZEDO0CkaNZPaCpBqfZUXosWzJI2BnCAs0OQDEbGYt5IkTVocyJECLRcovqxnDiGoZa2t+RYJd/VnALX5FDNrVx1Ctttt0xc0TQ3E80Au/ce1jzZOZ1eVopjnrJgPt8X+Jh4OPnixz6PR4HU/nKguEJ8BpbQoGGWcxjRrUN6Jkw5LgBx4kAs/gIgopW6ZI4CV79H/+/KXAWeycTc4b3BGgLvVUqPLcM79xkAuE1/fef+Udbaotr2P13z89Iyjm7p/r19KPU9objEtvKuHJK9YOXMYj46SHgDxMuR0MHK6tYv+/YEfZL64ZA==',
    }
    headers = {'accept': '*/*'}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params, headers=headers) as response:
            print(await response.text())
            return await response.text()


async def get_status_payment(order_id):
    url = 'https://alfa.rbsuat.com/payment/rest/getOrderStatus.do'
    params = {
        'userName': 'vt54_ru-api',
        'password': 'vt54_ru*?1',
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
        'userName': 'vt54_ru-api',
        'password': 'vt54_ru*?1',
        'clientId': client_id
    }
    headers = {'accept': '*/*'}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params, headers=headers) as response:
            result = await response.text()
            return json.loads(result)


# async def delete_bindings(client_id):
#     bindings = await get_bindings(client_id)
#     binding_ids = bindings['bindings'] # [0]['bindingId']
#     # binding_id = '7ca44e78-268f-762f-bd74-e6440206770f'
#     for binding_id in binding_ids:
#         url = 'https://alfa.rbsuat.com/payment/rest/unBindCard.do'
#         params = {
#             'userName': 'vt54_ru-api',
#             'password': 'vt54_ru*?1',
#             'bindingId': binding_id['bindingId']
#         }
#         headers = {'accept': '*/*'}
#
#         async with aiohttp.ClientSession() as session:
#             async with session.post(url, params=params, headers=headers) as response:
#                 print(await response.text())
#                 # return await response.text()
async def delete_binding(session, binding_id):
    url = 'https://alfa.rbsuat.com/payment/rest/unBindCard.do'
    params = {
        'userName': 'vt54_ru-api',
        'password': 'vt54_ru*?1',
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
# print(asyncio.run(get_bindings('11310')))
# asyncio.run(delete_bindings('11310'))
# asyncio.run(reccurent_payment('7ab80967-6178-7829-8f31-616a0206770f', 1))
# asyncio.run(is_paid_order('040dfa5c-79d2-7b17-99c3-a1390206770f'))
