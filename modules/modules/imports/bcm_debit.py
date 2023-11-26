from datetime import date

import dateparser
import xlrd
from beancount.core import data
from beancount.core.data import Transaction

from . import (get_account_by_guess,
               get_income_account_by_guess)
from .base import Base
from .deduplicate import Deduplicate
from ..accounts import accounts


class BCMDebit(Base):

    def __init__(self, filename, byte_content, entries, option_map):
        if not filename.endswith('xls'):
            raise ValueError('不是交行')
        data = xlrd.open_workbook(filename)
        table = data.sheets()[0]
        rows_value = table.row_values(0)
        if rows_value[0] != '交通银行银行卡交易明细查询表':
            raise ValueError('不是交行')
        self.book = data
        self.table = table
        self.deduplicate = Deduplicate(entries, option_map)

    def parse(self):
        table = self.table
        rows = table.nrows
        transactions = []
        # 确定银行卡账户
        card_no = table.cell_value(1, 0)
        card_no = card_no.split('姓名：')[0][5:].replace(' ', '')
        card_account = accounts[card_no]
        print("导入交行 {} {}".format(card_no, card_account))
        # 处理每个交易
        for i in range(3, rows):
            row = table.row_values(i)
            # 行信息解析
            time = dateparser.parse(table.cell_value(rowx=i, colx=1))
            amount_out = row[4]
            amount_in = row[5]
            balance = float(row[6])
            payee = row[7]
            desc = row[10]
            # 判断是否是收入
            is_income = False
            if amount_in == '--':
                amount = repr(amount_out)
            else:
                amount = repr(amount_in)
                is_income = True
            print("导入 {} price = {} balance = {} payee = {}".format(time, amount, balance, payee))
            # 忽略所有天天基金
            if '上海天天基金销售有限公司 基金购买' in desc:
                print("忽略天天基金购买")
                continue
            if '上海天天基金销售有限公司' in desc and '代销赎回' in desc:
                print("忽略天天基金赎回")
                continue
            # 元数据
            meta = {
                'timestamp': str(time.timestamp()).replace('.0', ''),
                'payee_account': row[8],
                'trade_time': row[1],
            }
            # 交易
            entry = Transaction(
                meta,
                date(time.year, time.month, time.day),
                '*',
                payee,
                desc,
                data.EMPTY_SET,
                data.EMPTY_SET, []
            )
            # 增加 postings
            if is_income:
                # 收入
                income_account = get_income_account_by_guess(payee, desc, time)
                data.create_simple_posting(
                    entry, income_account, '-' + amount, 'CNY')
                data.create_simple_posting(
                    entry, card_account, None, None)
            else:
                # 支出
                account = get_account_by_guess(payee, desc, time)
                data.create_simple_posting(
                    entry, card_account, None, None)
                data.create_simple_posting(
                    entry, account, amount, 'CNY')
            # 检查特殊规则
            for posting in entry.postings:
                # 没能识别账户，记不确定项
                if 'Unknown' in posting.account:
                    entry = entry._replace(flag='!')
            # 去重复
            if not self.deduplicate.find_duplicate(entry, amount, None):
                transactions.append(entry)

        self.deduplicate.apply_beans()
        return transactions
