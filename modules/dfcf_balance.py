import datetime

if __name__ == '__main__':
    print("请输入导出的东方财富持仓（Table Capture）：")
    lines = []
    cur = None
    while True:
        cur = input('')
        if len(cur) < 1:
            break
        else:
            lines.append(cur)
    lines = lines[1:-1]

    result = []
    for line in lines:
        row = line.split('\t')
        date = datetime.date.today().isoformat()
        fund_code = row[0]
        fund_name = row[1]
        amount = row[2]
        print("导入：", fund_code, fund_name, amount)
        result.append(f'{date} balance Assets:Trade:ETFund:S{fund_code} {amount} S{fund_code} ; {fund_name}')

    with open('out.bean', 'w') as f:
        f.write('\n'.join(result))
