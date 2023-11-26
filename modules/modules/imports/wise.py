from datetime import date
from io import StringIO

import dateparser
from beancount.core import data
from beancount.core.amount import Amount
from beancount.core.data import Transaction, Posting
from beancount.core.number import D
from beancount.core.position import Cost
from beancount.parser import printer

from . import (DictReaderStrip, get_income_account_by_guess, get_account_by_guess)
from .base import Base
from .deduplicate import Deduplicate
from ..accounts import accounts

WISE_ACCOUNT = accounts['Wise']
EXPENSE_CURRENCY_CONVERSION = get_account_by_guess('', '货币转换')
EXPENSE_WISE_FEE_TRANSFER = get_account_by_guess('', 'Wise转账手续费')
EXPENSE_WISE_FEE_CONVERSION = get_account_by_guess('', 'Wise货币转换手续费')
META_TRADE_ID = 'wise_trade_id'
MAIN_CURRENCY = 'CNY'


class Wise(Base):
    """
    Wise
    """

    def __init__(self, filename, byte_content, entries, option_map):
        if 'Wise' not in filename:
            raise ValueError("不是 Wise 账单")
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
            time = row['建立日期']
            status = row['狀態']
            trade_id = row['ID']
            direction = row['貨幣流向']
            fee = Amount(D(row['來源費用金額']), row['來源費用貨幣'])
            from_amount = Amount(D('-' + row['來源金額（包含費用）']), row['來源貨幣'])
            to_amount = Amount(D(row['目標金額（扣除費用後）']), row['目標貨幣'])
            rate = D(row['匯率'])
            reference = row['附註']

            if status != 'COMPLETED':
                print("忽略失败交易 {}： {}".format(time, trade_id))
                continue

            print("导入 {}： {} {} {} -({})-> {} {} / {}".format(time, trade_id, direction, from_amount, fee, to_amount,
                                                                rate, reference))

            # 解析交易对手
            if direction == 'IN':
                payee = row['來源名稱']
            else:
                payee = row['目標名稱']

            # 解析账户
            from_account = WISE_ACCOUNT
            to_account = WISE_ACCOUNT
            wise_account = row['來源貨幣']

            if direction == 'IN':
                from_account = get_income_account_by_guess(payee, reference)
                wise_account = row['目標貨幣']
            elif direction == 'OUT':
                to_account = get_account_by_guess(payee, reference)

            # 元数据
            meta = {}
            time = dateparser.parse(time)
            meta[META_TRADE_ID] = trade_id
            meta['trade_time'] = str(time)
            meta['timestamp'] = str(time.timestamp()).replace('.0', '')

            # 产生交易
            meta = data.new_metadata(
                'beancount/core/testing.beancount',
                12345,
                meta
            )
            description = f"{wise_account} 账户 {direction}"
            if reference:
                description += f" / 附言: {reference}"
            entry = Transaction(
                meta,
                date(time.year, time.month, time.day),
                '*',
                payee,
                description,
                data.EMPTY_SET,
                data.EMPTY_SET, []
            )

            # 来源 Posting
            if row['來源貨幣'] != MAIN_CURRENCY:
                # noinspection PyTypeChecker
                cost = Cost(None, None, None, None)  # 流入的货币，自动匹配 cost
            else:
                cost = None
            entry.postings.append(Posting(from_account, from_amount, cost, None, None, None))

            # 去向 Posting
            if row['來源貨幣'] != row['目標貨幣']:
                # 发生货币购买操作，记录 cost
                cost = Cost((1 / rate).quantize(D('0.0001')), row['來源貨幣'], None, None)
                # “汇损”
                data.create_simple_posting(entry, EXPENSE_CURRENCY_CONVERSION, None, None)
            else:
                cost = None
            entry.postings.append(Posting(to_account, to_amount, cost, None, None, None))

            # 服务费
            if row['來源費用金額'] not in ('', '0'):
                account = EXPENSE_WISE_FEE_CONVERSION
                # 进账
                if direction == 'OUT':
                    account = EXPENSE_WISE_FEE_TRANSFER
                entry.postings.append(Posting(account, fee, None, None, None, None))

            # 没能识别账户，记不确定项
            for posting in entry.postings:
                if 'Unknown' in posting.account:
                    entry = entry._replace(flag='!')

            b = printer.format_entry(entry)
            print(b)

            # 去重
            if direction == 'IN':
                dup_amount = row['來源金額（包含費用）']
            else:
                dup_amount = row['目標金額（扣除費用後）']

            if not self.deduplicate.find_duplicate(entry, dup_amount, META_TRADE_ID):
                transactions.append(entry)

        self.deduplicate.apply_beans()
        return transactions
