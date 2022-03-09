from datetime import date

import eml_parser
from beancount.core import data
from beancount.core.amount import Amount
from beancount.core.data import Transaction, Posting
from beancount.core.number import D
from bs4 import BeautifulSoup

from . import (get_account_by_guess)
from .deduplicate import Deduplicate

Account民生 = 'Liabilities:CreditCard:MASTER:CMBC'


class CMBCCredit():

    def __init__(self, filename, byte_content, entries, option_map):
        if not filename.endswith('eml'):
            raise 'Not CMBC!'
        parsed_eml = eml_parser.eml_parser.decode_email_b(
            byte_content, include_raw_body=True)
        title = parsed_eml['header']['subject']
        content = ''
        if not '民生信用卡' in title:
            raise 'Not CMBC!'
        for body in parsed_eml['body']:
            content += body['content']
        self.soup = BeautifulSoup(content, 'html.parser')
        self.content = content
        self.deduplicate = Deduplicate(entries, option_map)
        self.year = int(title.split('信用卡')[1].split('年')[0])
        self.month = int(title.split('年')[1].split('月')[0])

    def get_currency(self, currency_text):
        currency = currency_text.split("\xa0")[1].strip()
        if currency == 'RMB':
            return 'CNY'
        return currency

    def get_date(self, detail_date):
        splitted_date = detail_date.split('/')
        year = self.year
        if splitted_date[0] == '12' and self.month < 12:
            year -= 1
        return date(year, int(splitted_date[0]), int(splitted_date[1]))

    def get_currencies_indexes(self, tables):
        ret = []
        # 筛选出币种
        for idx, el in zip(range(len(tables)), tables):
            if el.find('font', text='本期最低还款额\xa0Min.Payment\xa0:') is not None:
                ret.append(idx)
        # 去除空表
        for i in range(len(ret)):
            if i == len(ret) - 1:
                if ret[i] + 4 < len(tables):
                    ret[i] = None
            else:
                if ret[i + 1] - ret[i] < 4:
                    ret[i] = None
        return [x for x in ret if x is not None]

    def parse(self):
        d = self.soup
        tables = d.select('#loopBand2>table>tr')
        transactions = []
        for x in self.get_currencies_indexes(tables):
            title = tables[x]
            contents = tables[x + 3]
            currency = title.select('#fixBand29 td>table td')[1].text.strip()
            currency = self.get_currency(currency)
            # 增加汇率输入，以便自动设置
            unit_price = 1
            if currency != 'CNY':
                input_price = input(f'正在导入外币 {currency}，如果已经购汇请输入汇率（RMB），否则请留空：')
                if input_price:
                    unit_price = D(input_price)
            # 遍历交易
            bands = contents.select('#loopBand3>table>tr')
            for band in bands:
                tds = band.select(
                    'td>table>tr>td #fixBand9>table>tr>td>table>tr>td')
                time = self.get_date(tds[1].text.strip())
                description = tds[3].text.strip()
                price = tds[4].text.strip()
                description = description.replace('\xa0', ' ')
                # 分析账户
                descs = list(filter(lambda z: len(z) > 0, description.split('  ')))
                if len(descs) <= 1:
                    payee = ''
                    description = descs[0]
                else:
                    payee = descs[0]
                    description = ' '.join(descs[1:])
                print("Importing {}/{} at {}".format(payee, description, time))
                account = get_account_by_guess(payee, description, time)
                flag = "*"
                amount = D(price.replace(',', ''))
                if "Unknown" in account:
                    flag = "!"
                meta = {}
                meta = data.new_metadata(
                    'beancount/core/testing.beancount',
                    12345,
                    meta
                )
                entry = Transaction(
                    meta,
                    time,
                    flag,
                    payee,
                    description,
                    data.EMPTY_SET,
                    data.EMPTY_SET, []
                )
                # 卡账户
                units = Amount(-amount, currency)
                price = None
                if unit_price != 1:
                    price = Amount(unit_price, 'CNY')
                entry.postings.append(Posting(Account民生, units, None, price, None, None))
                # 对方账户
                data.create_simple_posting(entry, account, None, None)
                if not self.deduplicate.find_duplicate(entry, -amount, None, Account民生):
                    transactions.append(entry)

        self.deduplicate.apply_beans()
        return transactions
