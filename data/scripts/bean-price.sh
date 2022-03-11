#!/bin/sh

basedir=$(dirname "$0")
cd $basedir/../
$basedir/run.sh bean-price $basedir/../main.bean $@
