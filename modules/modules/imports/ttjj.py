from datetime import date
from io import StringIO

import dateparser
from beancount.core import data
from beancount.core.amount import Amount
from beancount.core.data import Transaction, Posting
from beancount.core.number import D
from beancount.core.position import Cost
from beancount.parser import printer

from . import (DictReaderStrip)
from .base import Base
from .deduplicate import Deduplicate
from ..accounts import accounts

STOCK_ACCOUNT = 'Assets:Trade:Fund:F{}'
STOCK_UNIT = 'F{}'
STOCK_PNL = 'Income:Trade:Fund:F{}:PnL'
STOCK_EXCHANGE = 'Income:Trade:Fund:F{}:Exchange'


class Ttjj(Base):
    """
    天天基金
    """

    def __init__(self, filename, byte_content, entries, option_map):
        if 'TTJJ' not in filename:
            raise ValueError("不是天天基金数据")
        try:
            self.content = byte_content.decode('gbk')
        except Exception:
            self.content = byte_content.decode('utf-8')
        self.deduplicate = Deduplicate(entries, option_map)

    def parse(self):
        content = self.content
        f = StringIO(content)
        reader = DictReaderStrip(f, delimiter=',')
        transactions = []
        for row in reader:
            # 解析信息
            time = row['确认日期']
            stock_code = row['基金代码']
            stock_name = row['基金简称']
            trade_type = row['业务类型']
            amount = row['确认份额']
            print("导入 {}： {} {} {}".format(time, stock_name, stock_code, trade_type))
            # 元数据
            meta = {}
            time = dateparser.parse(time)
            meta['ttjj_trade_id'] = str(time) + stock_code + amount
            meta['trade_time'] = str(time)
            meta['timestamp'] = str(time.timestamp()).replace('.0', '')
            # 产生交易
            meta = data.new_metadata(
                'beancount/core/testing.beancount',
                12345,
                meta
            )
            entry = Transaction(
                meta,
                date(time.year, time.month, time.day),
                '*',
                stock_name,
                f"{trade_type} {amount} 份",
                data.EMPTY_SET,
                data.EMPTY_SET, []
            )

            # 证券账目
            stock_account = STOCK_ACCOUNT.format(stock_code)
            stock_unit = STOCK_UNIT.format(stock_code)
            stock_pnl = STOCK_PNL.format(stock_code)
            stock_exchange = STOCK_EXCHANGE.format(stock_code)
            account = accounts[row['关联银行卡']]

            if trade_type == '买基金' or trade_type == '定时定额投资':
                # 证券买入
                data.create_simple_posting(entry, account, f"-{row['确认金额']}", 'CNY')
                units = Amount(D(amount), stock_unit)
                cost = Cost(D(row['确认净值']), 'CNY', None, None)
                entry.postings.append(Posting(stock_account, units, cost, None, None, None))
                data.create_simple_posting(entry, 'Equity:Round-Off', None, None)
                # 定投
                if trade_type == '定时定额投资':
                    entry = entry._replace(tags=entry.tags.union({'Auto-Invest-TTJJ'}))
            elif trade_type == '卖基金':
                # 证券卖出
                units = Amount(D(f'-{amount}'), stock_unit)
                cost = Cost(None, None, None, None)
                entry.postings.append(Posting(stock_account, units, cost, None, None, None))
                data.create_simple_posting(entry, account, row['确认金额'], 'CNY')
                data.create_simple_posting(entry, stock_pnl, None, None)
            else:
                print("未知！", row)
                exit(1)

            # 服务费相关计算
            if row['手续费'] != '0':
                data.create_simple_posting(
                    entry, stock_exchange, row['手续费'], 'CNY')

            b = printer.format_entry(entry)
            print(b)
            if not self.deduplicate.find_duplicate(entry, amount, 'ttjj_trade_id'):
                transactions.append(entry)

        self.deduplicate.apply_beans()
        return transactions
