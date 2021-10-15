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

STOCK_ACCOUNT = 'Assets:Trade:ETFund:S{}'
STOCK_UNIT = 'S{}'
STOCK_PNL = 'Income:Trade:ETFund:S{}:PnL'
STOCK_EXCHANGE = 'Income:Trade:ETFund:S{}:Exchange'


class Dfcf(Base):
    """
    东方财富
    """

    def __init__(self, filename, byte_content, entries, option_map):
        if 'DFCF' not in filename:
            raise ValueError("不是东方财富数据")
        self.content = byte_content.decode('gbk')
        self.deduplicate = Deduplicate(entries, option_map)

    def parse(self):
        content = self.content
        f = StringIO(content)
        reader = DictReaderStrip(f, delimiter=',')
        transactions = []
        for row in reader:
            # 解析信息
            time = f"{row['成交日期']} {row['成交时间']}"
            trade_no = row['成交编号']
            stock_code = row['证券代码']
            stock_name = row['证券名称']
            trade_type = row['委托方向']
            amount = row['成交数量']
            cny_price = row['成交价格']
            print("导入 {}： {} {} {}".format(time, trade_no, stock_name, trade_type))
            # 元数据
            meta = {}
            time = dateparser.parse(time)
            meta['dfcf_trade_no'] = trade_no
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
                f"{trade_type} {amount}",
                data.EMPTY_SET,
                data.EMPTY_SET, []
            )

            # 证券账目
            stock_account = STOCK_ACCOUNT.format(stock_code)
            stock_unit = STOCK_UNIT.format(stock_code)
            stock_pnl = STOCK_PNL.format(stock_code)
            stock_exchange = STOCK_EXCHANGE.format(stock_code)

            if trade_type == '证券买入':
                # 证券买入
                data.create_simple_posting(entry, accounts['东方财富'], None, None)
                units = Amount(D(amount), stock_unit)
                cost = Cost(D(cny_price), 'CNY', None, None)
                entry.postings.append(Posting(stock_account, units, cost, None, None, None))
            elif trade_type == '证券卖出':
                # 证券卖出
                units = Amount(D(f'-{amount}'), stock_unit)
                cost = Cost(None, None, None, None)
                entry.postings.append(Posting(stock_account, units, cost, None, None, None))
                data.create_simple_posting(entry, accounts['东方财富'], row['成交金额'], 'CNY')
                data.create_simple_posting(entry, stock_pnl, None, None)
            else:
                print("未知！", row)
                exit(1)

            # 服务费相关计算
            if row['佣金'] != '0':
                data.create_simple_posting(
                    entry, stock_exchange, row['佣金'], 'CNY')
            if row['交易规费'] != '0':
                data.create_simple_posting(
                    entry, stock_exchange, row['交易规费'], 'CNY')
            if row['印花税'] != '0':
                data.create_simple_posting(
                    entry, stock_exchange, row['印花税'], 'CNY')
            if row['过户费'] != '0':
                data.create_simple_posting(
                    entry, stock_exchange, row['过户费'], 'CNY')

            b = printer.format_entry(entry)
            print(b)
            if not self.deduplicate.find_duplicate(entry, amount, 'dfcf_trade_no'):
                transactions.append(entry)

        self.deduplicate.apply_beans()
        return transactions
