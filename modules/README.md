# beancount-scripts

自用 Beancount 脚本。仓库 Fork 自：[zsxsoft/my-beancount-scripts](https://github.com/zsxsoft/my-beancount-scripts)

## 增加导入器

### 天天基金

匹配 `TTJJ` 开头的 CSV 文件。文件内容是 Table Capture 捕获的[对账单的历史交易明细](https://trade.1234567.com.cn/Query/bill?spm=S)。
由于网页不能右键，因此需要点击工具栏的插件图标然后选择表格。

导入器要求按照特定规则开户，请参考相关博客。

### 东方财富

匹配 `DFCF` 开头的 CSV 文件。文件内容是 Table Capture 捕获的[历史交易](https://jy.xzsec.com/Search/HisDeal)。

导入器要求按照特定规则开户，请参考相关博客。

## 附加脚本

### ttjj_balance.py

Table Capture 导出天天基金对账单历史持仓明细的表格，粘贴进脚本标准输入。
输出 balance 至 out.bean
