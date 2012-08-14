#!/bin/bash

cd $(dirname $0)

if [ -f ./virtualenv/bin/activate ]; then
    . ./virtualenv/bin/activate
fi

export PYTHONPATH=.:./vendor/WhooshAlchemy/

python ./opmuse/boot.py $@

