# my-beancount-template

个人 Beancount 方案的模板仓库

## 相关博客

- [复式记账指北（一）：What and Why？](https://blog.kaaass.net/archives/1659)
- [复式记账指北（二）：做账方法论](https://blog.kaaass.net/archives/1696)
- [复式记账指北（三）：如何打造不半途而废的记账方案](https://blog.kaaass.net/archives/1700)

## 配置

详细配置请参考博客三。必须修改的配置有：

- Bot功能：`data/beancount_bot.yml`
- 备份功能
  - Git SSH配置：`init.d/known_hosts`、密钥 `init.d/tgbot`
  - data 内必须是 git 仓库、位于 bot 分支、已经配置好 upstream

## 部署

`docker-compose up -d`

## See also

[kaaass/beancount_bot](https://github.com/kaaass/beancount_bot)

[zsxsoft/my-beancount-scripts](https://github.com/zsxsoft/my-beancount-scripts)
