#!/bin/sh
time=$(date)

cd /bean
git add . && git commit -m "每日备份 $time"
git push
