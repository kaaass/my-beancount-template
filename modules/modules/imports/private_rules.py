# private_rules.py -- 个人隐私相关的特定账单处理规则
import time

import dateparser
from beancount.core import data
from beancount.core.data import Transaction, Posting
from beancount.core.number import D

from modules.imports import replace_flag


def have_postings_of_amount(tx: Transaction, amount) -> bool:
    """判断交易是否有指定金额的账目"""
    for posting in tx.postings:
        if posting.units is not None and posting.units.number == amount:
            return True
    return False


def amount_of_transactions(tx: Transaction) -> D:
    """获取交易中账目的正金额。账目金额应该是唯一的。"""
    for posting in tx.postings:
        if posting.units is not None:
            return abs(posting.units.number)
    return None


def time_of_transactions(tx: Transaction) -> time.time:
    """获取交易中账目的时间。优先从 meta timestamp 中获取，若不存在则直接使用 date"""
    if tx.meta is not None and 'timestamp' in tx.meta:
        return dateparser.parse(tx.meta['timestamp'])
    else:
        return dateparser.parse(tx.date)


def remove_postings_with_accounts(tx: Transaction, account_name) -> Transaction:
    """删除交易中指定账户的账目"""
    tx = tx._replace(postings=[posting for posting in tx.postings if posting.account != account_name])
    return tx


def wechat_rules(tx: Transaction) -> Transaction:
    """微信特殊规则"""

    # Rules ...

    return tx


def fudan_rules(tx: Transaction) -> Transaction:
    """复旦学生卡特殊规则"""

    # Rules ...

    return tx


def alipay_rules(tx: Transaction) -> Transaction:
    """支付宝特殊规则"""

    # Rules ...

    return tx
