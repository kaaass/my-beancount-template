#!/bin/sh

# Run with `source env.sh`

basedir=$(dirname "$0")

export SERVICE_BEANCOUNT_HOME=$basedir/../../
export PYTHONPATH=$SERVICE_BEANCOUNT_HOME/modules
