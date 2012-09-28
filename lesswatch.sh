#!/bin/sh

BASE=$(realpath $(dirname $0))

export PATH=$PATH:$BASE/vendor/less.js/bin

cd $BASE/public/styles

# run it once at boot if didn't exist prior or has changed since last run
lessc main.less > main.css

$BASE/vendor/watchr/bin/watchr \
    -e 'watch(".*\.less$") { |f| system("lessc main.less > main.css") }'


