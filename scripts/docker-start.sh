#!/bin/sh

/etc/init.d/mysql start

while `sleep 10`; do
    . /etc/default/opmuse

    /usr/bin/opmuse-boot \
        --user $USER \
        --group $GROUP \
        --log $LOGDIR/access.log \
        --errorlog $LOGDIR/error.log \
        --pidfile $PIDFILE \
        --env $ENVIRONMENT
done
