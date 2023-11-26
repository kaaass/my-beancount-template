import json
from datetime import tzinfo, timedelta
from string import Template

import dateparser
import requests
from beancount.core.number import D
from beancount.prices import source

ZERO = timedelta(0)
BASE_URL_TEMPLATE = Template(
    "https://web-api.coinmarketcap.com/v1/cryptocurrency/ohlcv/historical?convert=$currency&slug=$ticker")
TIME_PARAM_TEMPLATE = Template(
    "&time_end=$date_end&time_start=$date_start")
CURRENCY = "USD"


class UTCtzinfo(tzinfo):
    def utcoffset(self, dt):
        return ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return ZERO


utc = UTCtzinfo()


class CoinmarketcapError(ValueError):
    "An error from the Coinmarketcap API."


class Source(source.Source):
    def _get_price_for_date(self, ticker, date=None):
        paramater = ticker.split("--")
        currency = paramater[1].upper()

        url = BASE_URL_TEMPLATE.substitute(
            ticker=paramater[0],
            currency=currency)

        if date is not None:
            date = date.replace(hour=0, minute=0, second=0)
            end_date = date + timedelta(days=1, hours=1)

            url += TIME_PARAM_TEMPLATE.substitute(
                date_start=int(date.timestamp()),
                date_end=int(end_date.timestamp()))

        content = None
        try:
            content = requests.get(url).content
            ret = json.loads(content)
            quote = ret['data']['quotes'][-1]['quote'][currency]
            price = D(quote['close'])
            quote_time = dateparser.parse(ret['data']['quotes'][-1]['time_open'])
            return source.SourcePrice(price, quote_time, CURRENCY)

        except:
            raise CoinmarketcapError(
                "Invalid response from Coinmarketcap: {}".format(repr(content)))

    def get_latest_price(self, ticker):
        return self._get_price_for_date(ticker, None)

    def get_historical_price(self, ticker, time):
        return self._get_price_for_date(ticker, time)
