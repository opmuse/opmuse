#!/bin/sh

. /etc/default/opmuse

if ! getent passwd $USER > /dev/null ; then
    adduser --quiet --system --no-create-home --home $CACHEDIR --shell /usr/sbin/nologin $USER
fi

chown $USER $LOGDIR $CACHEDIR

. /usr/share/debconf/confmodule
. /usr/share/dbconfig-common/dpkg/postinst.mysql

if ! dbc_go opmuse $@ ; then
    echo 'Automatic configuration using dbconfig-common failed!'
fi

/etc/init.d/opmuse start
