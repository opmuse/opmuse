#!/bin/sh

. /etc/default/opmuse

getent passwd $USER > /dev/null

if [[ $? -ne 0 ]]; then
    adduser --quiet --system --no-create-home --home $CACHEDIR --shell /usr/sbin/nologin $USER
fi

chown $USER $LOGDIR $CACHEDIR

/etc/init.d/opmuse start
