import calendar
import csv
import re
from zipfile import ZipFile
from datetime import date
from io import BytesIO, StringIO

import dateparser
from beancount.core import data
from beancount.core.data import Note, Transaction

from .private_rules import wechat_rules
from ..accounts import accounts
from . import (DictReaderStrip, get_account_by_guess,
               get_income_account_by_guess, replace_flag, get_account_by_name)
from .base import Base
from .deduplicate import Deduplicate

Account零钱通 = 'Assets:FinTech:LQT'
Account收入红包 = 'Income:Gift:RedPack'
Account支出红包 = 'Expenses:Social:Gift:RedPack'
Account余额 = 'Assets:Digital:Wechat'


class WeChat(Base):

    def __init__(self, filename, byte_content, entries, option_map):
        if re.search(r'微信支付账单.*\.zip$', filename):
            password = input('微信账单密码：')
            z = ZipFile(BytesIO(byte_content), 'r')
            z.setpassword(bytes(password, 'utf-8'))
            filelist = z.namelist()
            if len(filelist) == 2 and re.search(r'微信支付.*\.csv$', filelist[1]):
                byte_content = z.read(filelist[1])
        content = byte_content.decode("utf-8-sig")
        lines = content.split("\n")
        if ('微信支付账单明细' not in lines[0].replace(',', '')):
            raise ValueError('Not WeChat Trade Record!')

        print('Import WeChat: ' + lines[2])
        content = "\n".join(lines[16:len(lines)])
        self.content = content
        self.deduplicate = Deduplicate(entries, option_map)

    def parse(self):
        content = self.content
        f = StringIO(content)
        reader = DictReaderStrip(f, delimiter=',')
        transactions = []
        for row in reader:
            print("Importing {} at {}".format(row['商品'], row['交易时间']))
            meta = {}
            time = dateparser.parse(row['交易时间'])
            meta['wechat_trade_no'] = row['交易单号']
            meta['trade_time'] = row['交易时间']
            meta['timestamp'] = str(time.timestamp()).replace('.0', '')
            account = get_account_by_guess(row['交易对方'], row['商品'], time)
            flag = "*"
            amount_string = row['金额(元)'].replace('¥', '')
            amount = float(amount_string)

            if row['商户单号'] != '/':
                meta['shop_trade_no'] = row['商户单号']

            if row['备注'] != '/':
                meta['note'] = row['备注']

            meta = data.new_metadata(
                'beancount/core/testing.beancount',
                12345,
                meta
            )
            entry = Transaction(
                meta,
                date(time.year, time.month, time.day),
                '*',
                row['交易对方'],
                row['商品'],
                data.EMPTY_SET,
                data.EMPTY_SET, []
            )

            status = row['当前状态']

            if status == '支付成功' or '已收钱' in status or status == '已全额退款' or '已退款' in status or status == '已转账' or status == '充值成功':
                if '转入零钱通' in row['交易类型']:
                    entry = entry._replace(payee='')
                    entry = entry._replace(narration='转入零钱通')
                    data.create_simple_posting(
                        entry, Account零钱通, amount_string, 'CNY')
                else:
                    if '微信红包' in row['交易类型']:
                        account = Account支出红包
                        if entry.narration == '/':
                            entry = entry._replace(narration=row['交易类型'])
                    else:
                        account = get_account_by_guess(
                            row['交易对方'], row['商品'], time)
                    if account == "Expenses:Unknown":
                        entry = replace_flag(entry, '!')
                    if (status == '已全额退款' or '已退款' in status) and row['收/支'] != '支出':
                        amount_string = '-' + amount_string
                    elif row['收/支'] == '收入':
                        amount_string = '-' + amount_string
                    data.create_simple_posting(
                        entry, account, amount_string, 'CNY')
                # 支付方式
                if row['支付方式'] != '/':
                    pay_account = accounts[row['支付方式']]
                else:
                    if status == '充值成功':
                        # 我也不知道对不对，但是现在充值成功账户是 /
                        pay_account = Account余额
                    pay_account = 'Assets:Unknown'
                data.create_simple_posting(
                    entry, pay_account, None, None)
            elif row['当前状态'] == '已存入零钱' or row['当前状态'] == '已收钱':
                if '微信红包' in row['交易类型']:
                    if entry.narration == '/':
                        entry = entry._replace(narration=row['交易类型'])
                    data.create_simple_posting(entry, Account收入红包, None, 'CNY')
                else:
                    income = get_income_account_by_guess(
                        row['交易对方'], row['商品'], time)
                    if income == 'Income:Unknown':
                        entry = replace_flag(entry, '!')
                    data.create_simple_posting(entry, income, None, 'CNY')
                data.create_simple_posting(
                    entry, Account余额, amount_string, 'CNY')
            elif row['交易类型'] == '零钱充值':
                data.create_simple_posting(entry, get_account_by_name(row['交易对方']), None, 'CNY')
                data.create_simple_posting(
                    entry, Account余额, amount_string, 'CNY')
            else:
                print('Unknown row', row)

            # 运行特殊规则
            entry = wechat_rules(entry)

            if not self.deduplicate.find_duplicate(entry, amount, 'wechat_trade_no'):
                transactions.append(entry)

        self.deduplicate.apply_beans()
        return transactions
