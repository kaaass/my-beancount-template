import copy
from shutil import copyfile

from beancount.core.data import Transaction, Posting
from beancount.parser import printer
from beancount.query import query

from ..accounts import public_accounts


class Deduplicate:

    def __init__(self, entries, option_map):
        self.entries = entries
        self.option_map = option_map
        self.beans = {}

    def find_duplicate(self, entry, money, unique_no=None, replace_account='', currency='CNY'):
        # 要查询的是实际付款的账户，而不是支出信息
        bql = "SELECT flag, filename, lineno, location, account, year, month, day," \
              " str(entry_meta('timestamp')) as timestamp, metas() as metas " \
              "WHERE year = {} AND month = {} AND day = {} AND " \
              "      (number(convert(units(position), '{}')) = {} or number(convert(units(position), '{}')) = {})" \
              "ORDER BY timestamp ASC".format(entry.date.year, entry.date.month, entry.date.day, currency, money,
                                              currency, str(eval(f'-{money}')))
        items = query.run_query(self.entries, self.option_map, bql)
        length = len(items[1])
        if length == 0:
            return False
        updated_items = []
        for item in items[1]:
            same_trade = False
            item_timestamp = item.timestamp.replace("'", '')
            # 如果已经被录入了，且unique_no相同，则判定为是同导入器导入的同交易，啥都不做
            if unique_no is not None:
                if unique_no in entry.meta and unique_no in item.metas:
                    if item.metas[unique_no] == entry.meta[unique_no]:
                        same_trade = True
                    # unique_no存在但不同，那就绝对不是同一笔交易了
                    # 这个时候就直接返回不存在同订单
                    else:
                        continue
            if same_trade:
                return True
            # 否则，可能是不同账单的同交易，此时判断时间
            # 如果时间戳相同，或某个导入器的数据没有时间戳，则判断其为「还需进一步处理」的同笔交易
            # 例如，手工输入的交易，打上支付宝订单号。
            # 另外因为支付宝的傻逼账单，这里还需要承担支付手段更新的功能
            if (
                ('timestamp' not in entry.meta) or
                item_timestamp == entry.meta['timestamp'] or
                item.timestamp == 'None' or
                item.timestamp == ''
            ):
                tx: Transaction = self.get_tx_of_position(item.filename, item.lineno)
                new_tx: Transaction = copy.deepcopy(tx)
                # 替换需要置换的账户，目前用来补全账单
                if replace_account != '' and item.account in public_accounts:
                    postings = new_tx.postings
                    old_account = item.account
                    for i in range(len(postings)):
                        posting: Posting = postings[i]
                        if posting.account == old_account:
                            postings[i] = posting._replace(account=replace_account)
                            print("Updated account from {} to {}"
                                  .format(old_account, replace_account))
                # 补全元数据
                for key, value in entry.meta.items():
                    if key == 'filename' or key == 'lineno':
                        continue
                    if key not in item.metas:
                        new_tx.meta[key] = value
                        print("Appended meta {}: {}".format(key, value))
                # 补全交易信息
                new_tx = new_tx._replace(narration='{} {}'.format(tx.narration, entry.narration))
                print("Update narration {} to {}".format(tx.narration, new_tx.narration))
                # 补全交易方
                if new_tx.payee is None or len(new_tx.payee) == 0:
                    new_tx = new_tx._replace(payee=entry.payee)
                    print("Update payee {} to {}".format(tx.payee, new_tx.payee))
                # 标记待检查
                new_tx = new_tx._replace(flag='!')
                # 更改
                self.modify_transaction(tx, new_tx)
                updated_items.append(new_tx)
                # 如果有时间戳，且时间戳相同，则判定为同交易
                # 100%确认是同一笔交易后，就没必要再给其他的「金额相同」的交易加信息了
                if 'timestamp' in entry.meta and item_timestamp == entry.meta['timestamp']:
                    break
        return len(updated_items) > 0

    def get_tx_of_position(self, filename, lineno) -> Transaction:
        for entry in self.entries:
            if not isinstance(entry, Transaction):
                continue
            metas = entry.meta
            if metas['filename'] == filename and metas['lineno'] == lineno:
                return entry
        return None

    def read_bean(self, filename):
        if filename in self.beans:
            return self.beans[filename]
        with open(filename, 'r', encoding='utf-8') as f:
            text = f.read()
            self.beans[filename] = list(map(lambda x: f'{x}\n', text.split('\n')))
        return self.beans[filename]

    def modify_transaction(self, old_tx: Transaction, new_tx: Transaction):
        filename = old_tx.meta['filename']
        lineno = old_tx.meta['lineno']
        lines = self.read_bean(filename)
        # 统计要删除的行
        min_line = lineno - 1
        max_line = min_line
        for posting in old_tx.postings:
            max_line = max(max_line, posting.meta['lineno'])
        # 删除
        for i in range(min_line, max_line):
            lines[i] = ''
        # 添加
        lines[min_line] = printer.format_entry(new_tx)
        print("Modify transaction at {}:{}".format(filename, lineno))

    def apply_beans(self):
        for filename in self.beans:
            copyfile(filename, filename + '.bak')
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(''.join(self.beans[filename]))
