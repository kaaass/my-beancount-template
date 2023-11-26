from datetime import date
from io import StringIO

import dateparser
from beancount.core import data
from beancount.core.amount import Amount
from beancount.core.data import Transaction, Posting
from beancount.core.number import D
from beancount.core.position import Cost
from beancount.parser import printer

from . import (DictReaderStrip, get_account_by_guess)
from .base import Base
from .deduplicate import Deduplicate
from .private_rules import fudan_rules
from ..accounts import accounts

class Fudan(Base):
    """
    复旦一卡通
    """

    def __init__(self, filename, byte_content, entries, option_map):
        if 'FDU' not in filename:
            raise ValueError("不是复旦一卡通数据")
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
            if row["状态"] != "交易成功":
                print("忽略失败交易")
                continue
            # 解析信息
            time = row["创建时间"]
            time = f'{time[:10]} {time[10:12]}:{time[13:15]}:00'
            name = row["名称"].strip()
            tx_no = row["订单号"].strip()
            payee = row["商户"].strip()
            amount = row["金额 | 明细"].strip()
            print("导入 {}： {} / {} / {} / {}".format(time, tx_no, name, payee, amount))
            # 元数据
            meta = {}
            time = dateparser.parse(time)
            meta['fudan_trade_no'] = tx_no
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
                name,
                data.EMPTY_SET,
                data.EMPTY_SET, []
            )

            account = get_account_by_guess(payee, name, time)
            ecard = accounts["复旦一卡通"]

            # 判断资金方向
            if "充值" in name:
                # 充值
                data.create_simple_posting(entry, "Assets:Unknown", None, None)
                data.create_simple_posting(entry, ecard, amount, 'CNY')
            else:
                # 消费
                data.create_simple_posting(entry, ecard, None, None)
                data.create_simple_posting(entry, account, amount, 'CNY')

            # 检查特殊规则
            for posting in entry.postings:
                # 没能识别账户，记不确定项
                if 'Unknown' in posting.account:
                    entry = entry._replace(flag='!')

            # 运行特殊规则
            entry = fudan_rules(entry)

            if not self.deduplicate.find_duplicate(entry, amount, 'fudan_trade_no'):
                transactions.append(entry)

        self.deduplicate.apply_beans()
        return transactions
