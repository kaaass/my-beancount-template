import re
from datetime import date
from io import BytesIO, StringIO

import dateparser
from beancount.core import data
from beancount.core.data import Transaction
from pyzipper import AESZipFile

from . import (DictReaderStrip, get_account_by_guess,
               get_income_account_by_guess)
from .base import Base
from .deduplicate import Deduplicate
from ..accounts import accounts

AccountAssetUnknown = 'Assets:Unknown'
Account余利宝 = accounts['余利宝'] if '余利宝' in accounts else 'Assets:Unknown'
Account余额 = accounts['支付宝余额'] if '支付宝余额' in accounts else 'Assets:Unknown'
Account余额宝 = accounts['余额宝'] if '余额宝' in accounts else 'Assets:Unknown'


class AlipayProve(Base):

    def __init__(self, filename, byte_content, entries, option_map):
        if re.search(r'alipay_record_\d{8}_\d{6}.zip$', filename):
            password = input('支付宝账单密码：')
            z = AESZipFile(BytesIO(byte_content), 'r')
            z.setpassword(bytes(password.strip(), 'utf-8'))
            filelist = z.namelist()
            if len(filelist) == 1 and re.search(r'alipay_record.*\.csv$', filelist[0]):
                byte_content = z.read(filelist[0])
        elif 'debug.csv' in filename:
            with open(filename, 'rb') as f:
                byte_content = f.read()
        content = byte_content.decode("gbk")
        lines = content.split("\n")
        if not re.search(r'支付宝（中国）网络技术有限公司', lines[0]):
            raise ValueError('Not Alipay Proven Record!')

        print('Import Alipay', filename)
        end_line = lines.index('-' * 84 + '\r')
        content = "\n".join(lines[1:end_line])
        self.content = content
        self.deduplicate = Deduplicate(entries, option_map)

    def parse(self):
        content = self.content
        f = StringIO(content)
        reader = DictReaderStrip(f, delimiter=',')
        transactions = []
        for row in reader:
            print("Importing {} at {}".format(row['商品说明'], row['交易时间']))
            meta = {}
            time = dateparser.parse(row['交易时间'])
            meta['alipay_trade_no'] = row['交易订单号']
            meta['trade_time'] = row['交易时间']
            meta['timestamp'] = str(time.timestamp()).replace('.0', '')
            dest_account = get_account_by_guess(row['交易对方'], row['商品说明'], time)
            flag = "*"
            amount_string = row['金额']
            amount = float(amount_string)

            if row['商家订单号'] != '/':
                meta['shop_trade_no'] = row['商家订单号']

            meta = data.new_metadata(
                'beancount/core/testing.beancount',
                12345,
                meta
            )
            entry = Transaction(
                meta,
                date(time.year, time.month, time.day),
                flag,
                row['交易对方'],
                row['商品说明'],
                data.EMPTY_SET,
                data.EMPTY_SET, []
            )

            status = row['交易状态']
            trade_type = row['收/支']
            trade_account_original = row['收/付款方式']
            if trade_account_original == '余额':
                trade_account_original = '支付宝余额'
            trade_account = accounts[
                trade_account_original] if trade_account_original in accounts else AccountAssetUnknown

            if trade_type == '支出':
                # 正常交易
                if status in ['交易成功', '支付成功', '代付成功', '亲情卡付款成功', '等待确认收货', '等待对方发货', '交易关闭']:
                    data.create_simple_posting(
                        entry, trade_account, '-' + amount_string, 'CNY')
                    data.create_simple_posting(
                        entry, dest_account, None, None)
                    # 如果 0 元就忽略
                    if abs(float(amount_string)) < 0.001:
                        print("忽略 0 元交易")
                        continue
                else:
                    print(status)
                    exit(0)
            elif trade_type == '其他':
                if (status == '退款成功' or
                    ('蚂蚁财富' in row['交易对方'] and status == '交易成功') or
                    ('红包' == trade_account_original and status == '交易成功') or
                    ('基金组合' in row['商品说明'] and status == '交易成功') or
                    ('理财赎回' in row['商品说明'] and status == '交易成功') or
                    ('退款资金提取' == row['商品说明'] and status == '提取成功')
                ):
                    # 收款：收付款方式 <-- 交易对方
                    data.create_simple_posting(
                        entry, trade_account, amount_string, 'CNY')
                    data.create_simple_posting(
                        entry, dest_account, None, None)
                elif (trade_account_original == '余额宝') and status == '交易成功':
                    # 余额宝支付
                    data.create_simple_posting(
                        entry, get_income_account_by_guess(
                            row['交易对方'], row['商品说明'], time
                        ), '-' + amount_string, 'CNY')
                    data.create_simple_posting(
                        entry, dest_account, None, None)
                elif '余额宝-转出到余额' in row['商品说明'] and status == '交易成功':
                    data.create_simple_posting(
                        entry, Account余额宝, '-' + amount_string, 'CNY')
                    data.create_simple_posting(
                        entry, Account余额, None, None)
                elif (
                    (status == '交易成功' and '余额宝' in row['商品说明']) or
                    status == '还款成功'
                ):
                    # 还款、存余额宝
                    data.create_simple_posting(
                        entry, dest_account, amount_string, 'CNY')
                    data.create_simple_posting(
                        entry, trade_account, None, None)
                elif '转账到银行卡-转账' in row['商品说明'] and status == '交易成功':
                    # 银行卡转账没有详细的卡信息
                    data.create_simple_posting(
                        entry, trade_account, '-' + amount_string, 'CNY')
                    data.create_simple_posting(
                        entry, AccountAssetUnknown, None, None)
                elif status == '交易关闭' and trade_account_original == '':
                    # 忽略交易关闭
                    continue
                else:
                    print(row)
                    exit(0)
            elif trade_type == '收入':
                if trade_account_original == '':
                    trade_account = Account余额
                if status == '交易成功':
                    data.create_simple_posting(
                        entry, get_income_account_by_guess(
                            row['交易对方'], row['商品说明'], time
                        ), '-' + amount_string, 'CNY')
                    data.create_simple_posting(
                        entry, trade_account, None, None)
                else:
                    print(row)
                    exit(0)
            else:
                print(row)
                exit(0)

            # 检查特殊规则
            for posting in entry.postings:
                # 没能识别账户，记不确定项
                if 'Unknown' in posting.account:
                    entry = entry._replace(flag='!')
                # Switch 卡带购买加 Link
                if 'Assets:Tangibles:ACG:Switch' in posting.account:
                    entry = entry._replace(links={'Switch卡带'})
                # Switch 卡带二手，记待查项
                if 'Expenses:ACG:Game:Switch:Cartridge' in posting.account:
                    entry = entry._replace(flag='!')

            if not self.deduplicate.find_duplicate(entry, amount, 'alipay_trade_no'):
                transactions.append(entry)

        self.deduplicate.apply_beans()
        return transactions
