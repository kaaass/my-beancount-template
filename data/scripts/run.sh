#!/bin/sh

# Usage: ./run.sh [executable] [params...]

basedir=$(dirname "$0")

if [[ $# -lt 1 ]]; then
  echo "Usage: ./run.sh [executable] [params...]" >&2
  exit 1
fi

source $basedir/env.sh

exe=$1
shift 1
$exe $@
