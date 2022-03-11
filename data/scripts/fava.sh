#!/bin/sh

basedir=$(dirname "$0")
cd $basedir/../
$basedir/run.sh fava $basedir/../main.bean $@
