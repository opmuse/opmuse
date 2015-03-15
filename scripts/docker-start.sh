#!/bin/sh

/etc/init.d/mysql start

. /etc/default/opmuse

/usr/bin/opmuse-boot \
    --user $USER \
    --group $GROUP \
    --log $LOGDIR/access.log \
    --errorlog $LOGDIR/error.log \
    --pidfile $PIDFILE \
    --env $ENVIRONMENT
