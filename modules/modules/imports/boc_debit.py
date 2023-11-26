from datetime import date
from io import StringIO

import dateparser
from beancount.core import data
from beancount.core.data import Transaction
from beancount.core.number import D

from . import (DictReaderStrip, get_account_by_guess, get_income_account_by_guess)
from .base import Base
from .deduplicate import Deduplicate
from ..accounts import accounts


class BOCDebit(Base):
    """
    中国银行借记卡
    """

    def __init__(self, filename, byte_content, entries, option_map):
        if 'BOC' not in filename:
            raise ValueError("不是中国银行数据")
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
            time = row["交易日期"]
            tx_type = row["业务摘要"]
            payee = row["对方账户名称"]
            payee_account = row["对方账户账号"]
            amount_income = row["收入金额"]
            amount_expense = row["支出金额"]
            bank = row["交易渠道/场所"]
            narration = row["附言"]
            print("导入 {}： {} / {} / {} / {} / {}".format(time, tx_type, payee, narration, amount_income, amount_expense))
            if narration:
                narration = f'{tx_type} {narration}'
            else:
                narration = tx_type
            # 元数据
            meta = {}
            time = dateparser.parse(time)
            meta['payee_account'] = payee_account
            meta['tx_bank'] = bank
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
                payee,
                narration,
                data.EMPTY_SET,
                data.EMPTY_SET, []
            )

            assets_account = accounts["中国银行"]

            # 判断资金方向
            if amount_income:
                # 收入金额
                income_account = get_income_account_by_guess(payee, narration, time)

                # 结息收入
                if tx_type == '结息':
                    income_account = accounts["中国银行-利息收入"]
                    entry = entry._replace(payee="中国银行")

                amount = D(amount_income)
                data.create_simple_posting(entry, assets_account, amount, 'CNY')
                data.create_simple_posting(entry, income_account, None, None)
            else:
                # 支出金额
                expense_account = get_account_by_guess(payee, narration, time)
                amount = D(amount_expense)
                data.create_simple_posting(entry, assets_account, -amount, 'CNY')
                data.create_simple_posting(entry, expense_account, None, None)

            # 检查特殊规则
            for posting in entry.postings:
                # 没能识别账户，记不确定项
                if 'Unknown' in posting.account:
                    entry = entry._replace(flag='!')

            if not self.deduplicate.find_duplicate(entry, amount, None):
                transactions.append(entry)

        self.deduplicate.apply_beans()
        return transactions
