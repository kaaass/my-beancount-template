from datetime import datetime

import beancount.core.data

__author__ = 'KAAAsS'
__license__ = "GNU GPLv2"
__plugins__ = ('do_nothing',)


def entry_sortkey(entry):
    accurate_time = datetime.combine(entry.date, datetime.min.time())
    if 'timestamp' in entry.meta:
        ts = int(entry.meta['timestamp'])
        accurate_time = datetime.fromtimestamp(ts)

    return (entry.date,
            beancount.core.data.SORT_ORDER.get(type(entry), 0),
            accurate_time,
            entry.meta["lineno"])


beancount.core.data.entry_sortkey = entry_sortkey


def do_nothing(entries, options_map):
    return entries, []
