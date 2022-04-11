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
            time = f"{row['发生日期']} {row['发生时间']}"
            trade_no = row['发生日期'] + row['发生时间'] + row['证券代码'] + row['成交数量']
            stock_code = row['证券代码']
            stock_name = row['证券名称']
            trade_type = row['买卖类别']
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
                price = Amount(D(cny_price), 'CNY')
                entry.postings.append(Posting(stock_account, units, cost, price, None, None))
                # 计算账户金额
                account_price = D(row['成交金额']).quantize(D('0.01'))
                # 减去手续费
                reduce_cols = ['佣金', '印花税', '过户费', '交易规费']
                for col in reduce_cols:
                    account_price -= D(row[col]).quantize(D('0.01'))
                # 结果
                data.create_simple_posting(entry, accounts['东方财富'], account_price, 'CNY')
                data.create_simple_posting(entry, stock_pnl, None, None)
            elif trade_type == '利息归本':
                # 利息归本
                entry = entry._replace(payee='东方财富')._replace(narration=trade_type)
                price = -D(row['发生金额']).quantize(D('0.01'))
                data.create_simple_posting(entry, accounts['东方财富利息'], price, 'CNY')
                data.create_simple_posting(entry, accounts['东方财富'], None, None)
            elif trade_type == '银行转证券':
                # 银行转证券
                entry = entry._replace(payee='东方财富')._replace(narration=trade_type)
                price = D(row['发生金额']).quantize(D('0.01'))
                data.create_simple_posting(entry, accounts['东方财富'], price, 'CNY')
                data.create_simple_posting(entry, 'Assets:Unknown', None, None)  # 缺信息，等待银行账单导入
            else:
                print("未知！", row)
                exit(1)

            # 服务费相关计算
            if row['佣金'] != '0':
                data.create_simple_posting(
                    entry, stock_exchange, D(row['佣金']).quantize(D('0.01')), 'CNY')
            if row['交易规费'] != '0':
                data.create_simple_posting(
                    entry, stock_exchange, D(row['交易规费']).quantize(D('0.01')), 'CNY')
            if row['印花税'] != '0':
                data.create_simple_posting(
                    entry, stock_exchange, D(row['印花税']).quantize(D('0.01')), 'CNY')
            if row['过户费'] != '0':
                data.create_simple_posting(
                    entry, stock_exchange, D(row['过户费']).quantize(D('0.01')), 'CNY')

            b = printer.format_entry(entry)
            print(b)
            if not self.deduplicate.find_duplicate(entry, amount, 'dfcf_trade_no'):
                transactions.append(entry)

        self.deduplicate.apply_beans()
        return transactions
