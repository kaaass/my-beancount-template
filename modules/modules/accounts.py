import re


def get_eating_account(from_user, description, time=None):
    if time is None or not hasattr(time, 'hour'):
        return 'Expenses:Food:Dinner'
    elif time.hour <= 3 or time.hour >= 21:
        return 'Expenses:Food:Extra'
    elif time.hour <= 10:
        return 'Expenses:Food:Dinner:Breakfast'
    elif time.hour <= 16:
        return 'Expenses:Food:Dinner:Lunch'
    else:
        return 'Expenses:Food:Dinner:Supper'


def get_credit_return(from_user, description, time=None):
    for key, value in credit_cards.items():
        if key == from_user:
            return value
    return "Unknown"


# 需要被替换的账户
public_accounts = [
    'Assets:Unknown',
]

credit_cards = {
}

accounts = {
    "余额宝": 'Assets:FinTech:Alipay',
    '花呗': 'Liabilities:ConsumptionCredit:Alipay',
    '白条': 'Liabilities:ConsumptionCredit:JD',
    '零钱': 'Assets:Digital:Wechat',
    '支付宝余额': 'Assets:Digital:Alipay'，
}

# 匹配账单备注
descriptions = {
    '滴滴打车|滴滴快车': 'Expenses:Transport:Taxi',
    '余额宝.*收益发放': 'Assets:FinTech:Alipay',
    '花呗收钱服务费': 'Expenses:Fee',
    '.*还款-花呗.*账单': 'Liabilities:ConsumptionCredit:Alipay',
    '信用卡自动还款|信用卡还款': get_credit_return,
    '外卖订单': get_eating_account,
    '美团订单': get_eating_account,
}

# 匹配商家
anothers = {
    '饿了么': get_eating_account,
}

incomes = {
    '余额宝.*收益发放': 'Income:Interest:YEB',
}

description_res = dict([(key, re.compile(key)) for key in descriptions])
another_res = dict([(key, re.compile(key)) for key in anothers])
income_res = dict([(key, re.compile(key)) for key in incomes])
