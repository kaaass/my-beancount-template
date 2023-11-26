# switch_depreciation.py -- NS 卡带折旧实现
#
# ## 使用方式
#
#   1. 打开相关账户，通常需要包含：
#     - 卡带固定资产：Assets:Tangibles:ACG:Switch
#     - 卡带固定资产累计折旧：Assets:Tangibles:ACG:Switch:Depreciation
#     - 卡带支出：Expenses:ACG:Game:Switch:Cartridge
#     - 卡带折旧支出：Expenses:ACG:Game:Switch:Cartridge:Depreciation
#   2. 在账本中启用插件：
#     ```beancount
#     plugin "modules.plugins.switch_depreciation" "[
#       {
#         'link_prefix': 'Switch',                                         # 卡带交易 Link 的前缀
#         'assets': 'Assets:Tangibles:ACG:Switch',                         # 卡带固定资产账户
#         'expense': 'Expenses:ACG:Game:Switch:Cartridge',                 # 卡带支出账户
#         'depreciation_ratio': \"D('0.0456') * m ** D('-0.544')\",        # 卡带折旧率。m 为购买月数
#         'depreciation_tx_tag': 'Depreciation-Switch',                    # 卡带折旧交易的 Tag
#         'depreciation_residual': \"D('50')\",                            # 卡带残值。p 为购买价格
#       },
#     ]"
#     ```
#   3. 增加卡带购买、卖出交易，例如：
#     ```beancount
#     ; 购买交易的备注将被视为卡带名称，Link 用于关联某一张卡带的所有交易
#     2021-01-01 * "塞尔达：旷野之息" ^Switch-zelda-bow
#       Assets:Digital:Alipay
#       Assets:Tangibles:ACG:Switch  300.00 CNY
#
#     ; 卖出交易
#     2022-01-01 * "二手卖出塞尔达：旷野之息" ^Switch-zelda-bow
#       Assets:Digital:Alipay         260.00 CNY
#       Assets:Tangibles:ACG:Switch  -300.00 CNY  ; 卖出时固定资产减少量为购买时的负数
#       Expenses:ACG:Game:Switch:Cartridge
#     ```
#
# Copyright (C) 2022-2023 KAAAsS
import ast
from datetime import datetime, timedelta, date

__author__ = 'KAAAsS'
__license__ = "GNU GPLv2"
__plugins__ = ('switch_depreciation_plugin',)

from beancount.core import data, amount
from beancount.core.number import D

from beancount.ops import basicops

DEFAULT_CONFIG = {
    # 卡带交易 Link 的前缀
    'link_prefix': 'Switch',
    # 卡带固定资产账户
    'assets': 'Assets:Tangibles:Switch',
    # 卡带支出账户
    'expense': 'Expenses:Switch',
    # 卡带折旧率。计算时会乘以卡带购入价格。可用变量：m 为购买月数。浮点数需要用 D() 包裹
    'depreciation_ratio': "D('0.02')",
    # 卡带折旧交易的 Tag
    'depreciation_tx_tag': 'Depreciation-Switch',
    # 卡带残值。为绝对的价格取值。可用变量：p 为购买价格。浮点数需要用 D() 包裹
    'depreciation_residual': "D('0')",
}


def create_depreciation_tx(tx_date, title_name, title_link, price, currency, conf):
    """
    生成折旧交易
    """
    last_second_of_day = datetime(tx_date.year, tx_date.month, tx_date.day, 23, 59, 59)
    meta = data.new_metadata('<卡带折旧>', 0, {
        'timestamp': str(int(last_second_of_day.timestamp())),
    })
    entry = data.Transaction(meta, tx_date, '*', None, f'卡带折旧：{title_name}', {conf['depreciation_tx_tag']},
                             {title_link}, [])
    entry.postings.extend([
        data.Posting(
            f"{conf['assets']}:Depreciation",
            amount.Amount(-price, currency),
            None, None, None, None),
        data.Posting(
            f"{conf['expense']}:Depreciation",
            amount.Amount(price, currency),
            None, None, None, None),
    ])
    return entry


def create_depreciation_carryover_tx(tx_date: datetime, title_name, title_link, price, currency, conf):
    """
    生成折旧结转交易
    """
    meta = data.new_metadata('<卡带折旧>', 0, {
        'timestamp': str(int(tx_date.timestamp())),
    })
    entry = data.Transaction(meta, tx_date.date(), '*', None, f'卡带折旧结转：{title_name}',
                             {conf['depreciation_tx_tag']},
                             {title_link}, [])
    entry.postings.extend([
        data.Posting(
            f"{conf['assets']}:Depreciation",
            amount.Amount(price, currency),
            None, None, None, None),
        data.Posting(
            f"{conf['expense']}:Depreciation",
            amount.Amount(-price, currency),
            None, None, None, None),
    ])
    return entry


def first_date_of_next_month(current: date):
    """
    计算下一个月份的第一天
    """
    next_month = current.replace(day=28) + timedelta(days=4)
    return next_month.replace(day=1)


def last_date_of_month(current: date):
    """
    计算当前日期所在月份的最后一天
    """
    next_month = first_date_of_next_month(current)
    return next_month - timedelta(days=next_month.day)


def append_switch_depreciation(entries, conf):
    """
    增加 NS 卡带折旧交易至 entries 列表
    """
    new_entries = []
    link_groups = basicops.group_entries_by_link(entries)

    for link, link_entries in link_groups.items():

        # 仅处理 NS 卡带
        if not link.startswith(conf['link_prefix']):
            continue

        # 寻找购入卡带的交易，即第一个转入卡带账户的交易
        buy_tx = None
        buy_price = None
        currency = None

        for entry in link_entries:
            for posting in entry.postings:
                if posting.account == conf['assets'] and posting.units.number > 0:
                    buy_tx = entry
                    buy_price = posting.units.number
                    currency = posting.units.currency
                    break
        if buy_tx is None:
            continue

        # 寻找卖出卡带的交易，即第一个转出卡带账户的交易
        sell_tx = None

        for entry in link_entries:
            for posting in entry.postings:
                if posting.account == conf['assets'] and posting.units.number < 0:
                    sell_tx = entry
                    break

        # 计算折旧的开始日期，即购入卡带当月的最后一天
        buy_time = buy_tx.date
        start_date = last_date_of_month(buy_time)

        # 计算折旧的结束日期，由于使用循环判断因此不需要精确到当日
        if sell_tx is None:
            # 如果卡带没有卖出，则折旧到当前月份
            now_date = datetime.now().date()
            end_date = last_date_of_month(now_date)
        else:
            # 如果卡带已经卖出，则折旧到卖出当日
            end_date = sell_tx.date

        # 在卡带持有期间的每月月末生成折旧交易
        current_date = start_date
        accumulated_depreciation = D(0)
        month_count = 1
        title_name = buy_tx.narration
        while current_date < end_date:
            # 计算折旧金额
            depreciation_ratio = eval(conf['depreciation_ratio'], {'D': D}, {'m': month_count})
            depreciation = buy_price * depreciation_ratio
            depreciation = depreciation.quantize(D('0.01'))

            # 检查是否已经折旧完毕
            residual_value = eval(conf['depreciation_residual'], {'D': D}, {'v': buy_price})

            if accumulated_depreciation + depreciation + residual_value > buy_price:
                depreciation = buy_price - accumulated_depreciation - residual_value
                depreciation = depreciation.quantize(D('0.01'))
                if depreciation == 0:
                    break
            accumulated_depreciation += depreciation

            # 增加折旧交易
            entry = create_depreciation_tx(current_date, title_name, link, depreciation, currency, conf)
            new_entries.append(entry)

            # 计算下一个月月末日期
            current_date = last_date_of_month(first_date_of_next_month(current_date))
            month_count += 1

        # 如果卡带已经卖出，则生成折旧结转交易。交易日期为卖出当日，金额为累计折旧金额
        if sell_tx is not None:
            sell_date = datetime(sell_tx.date.year, sell_tx.date.month, sell_tx.date.day, 23, 59, 59)
            if 'timestamp' in sell_tx.meta:
                sell_date = datetime.fromtimestamp(int(sell_tx.meta['timestamp']))
            entry = create_depreciation_carryover_tx(sell_date, title_name, link, accumulated_depreciation, currency,
                                                     conf)
            new_entries.append(entry)

    return entries + new_entries


def switch_depreciation_plugin(entries, options_map, config=None):
    # 解析配置
    try:
        config_list = ast.literal_eval(config)
        assert isinstance(config_list, list)
    except (ValueError, AssertionError):
        config_list = []

    # 遍历运行配置
    for conf in config_list:
        actual_conf = DEFAULT_CONFIG.copy()
        actual_conf.update(conf)
        entries = append_switch_depreciation(entries, actual_conf)
    return entries, []
