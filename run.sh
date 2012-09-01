#!/bin/bash

cd $(dirname $0)

if [ -f ./virtualenv/bin/activate ]; then
    . ./virtualenv/bin/activate
fi

python ./opmuse/boot.py $@

