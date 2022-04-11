# beancount-scripts

自用 Beancount 脚本。仓库 Fork 自：[zsxsoft/my-beancount-scripts](https://github.com/zsxsoft/my-beancount-scripts)

## 增加导入器

### 天天基金

匹配 `TTJJ` 开头的 CSV 文件。文件内容是 Table Capture 捕获的[对账单的历史交易明细](https://trade.1234567.com.cn/Query/bill?spm=S)。
由于网页不能右键，因此需要点击工具栏的插件图标然后选择表格。

导入器要求按照特定规则开户，请参考相关博客。

### 东方财富

匹配 `DFCF` 开头的 CSV 文件。文件内容是 Table Capture 捕获的[交割单](https://jy.xzsec.com/Search/FundsFlow)。

导入器要求按照特定规则开户，请参考相关博客。

### 交通银行借记卡

匹配交通银行[我的账户-账户查询-账户明细查询](https://pbank.95559.com.cn/personbank/system/syVerifyCustomerNewControl.do)下载的 `XLS` 记录。需要在 `accounts.py` 里面设置卡号对应的账户。

## 修改部分

### 账单去重

1. 账单去重会同时考虑金额的正、负两种情况
2. 发现重复账单，会补全如下信息
   - 替换旧的交易对象
   - 追加交易描述
   - 追加交易元数据

### 民生银行信用卡

修正了一些 BUG，增加了外币消费增加汇率的功能。

## 附加脚本

### ttjj_balance.py

Table Capture 导出天天基金[对账单-历史持仓明细](https://trade.1234567.com.cn/Query/bill?spm=S)的表格，复制后粘贴进脚本标准输入。
输出 balance 至 out.bean

### dfcf_balance.py

Table Capture 导出[东方财富持仓情况](https://jy.xzsec.com/Search/Position)的表格，复制后粘贴进脚本标准输入。
输出 balance 至 out.bean

## 插件

### modules.plugins.tag_pending

支持自定义零和账户的 tag_pending 插件。需要在脚本中修改 `zero_sum_accounts`：

```python
zero_sum_accounts = {
    # 在相同 Link 以 “Switch” 开头的交易中
    # 如果 Assets:Tangibles:ACG:Switch 之和不为 0，则标记为 #PENDING
    'Switch': ['Assets:Tangibles:ACG:Switch'],
}
```
