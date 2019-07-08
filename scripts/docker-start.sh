#!/bin/sh

/etc/init.d/mysql start

. /etc/default/opmuse

while `sleep 10`; do
    /usr/bin/opmuse-boot \
        --user $USER \
        --group $GROUP \
        --log $LOGDIR/access.log \
        --errorlog $LOGDIR/error.log \
        --pidfile $PIDFILE \
        --env $ENVIRONMENT
done
