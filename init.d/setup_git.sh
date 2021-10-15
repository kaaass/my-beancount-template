#!/bin/sh

mkdir -p ~/.ssh
cp /init.d/tgbot ~/.ssh/id_rsa
cp /init.d/known_hosts ~/.ssh
chmod 755 ~/.ssh/  
chmod 600 ~/.ssh/id_rsa
chmod 644 ~/.ssh/known_hosts
git config --global user.name "Beancount Bot"
git config --global user.email "noreply@kaaass.net"
