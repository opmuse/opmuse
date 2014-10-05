#!/bin/sh

. /etc/default/opmuse

if ! getent group $GROUP > /dev/null ; then
    addgroup --system $GROUP
fi

if ! getent passwd $USER > /dev/null ; then
    adduser --quiet --system --no-create-home --ingroup $GROUP --home $CACHEDIR \
        --shell /usr/sbin/nologin $USER
fi

. /usr/share/debconf/confmodule
. /usr/share/dbconfig-common/dpkg/postinst.mysql

if ! dbc_go opmuse $@ ; then
    echo 'Automatic configuration using dbconfig-common failed!'
fi

if [ "$1" = "configure" ]; then
    db_version 2.0

    # only on a new install
    if [ "$2" = "" ]; then
        db_get opmuse/user_name
        user_name=$RET

        db_get opmuse/user_mail
        user_mail=$RET

        db_get opmuse/user_pass
        user_pass=$RET

        opmuse-console user add_role admin
        opmuse-console user add "$user_name" "$user_pass" "$user_mail" admin
    fi

    if ! dpkg-statoverride --list $LOGDIR > /dev/null ; then
        dpkg-statoverride --update --add $USER $GROUP 0750 $LOGDIR
    fi

    if ! dpkg-statoverride --list $CACHEDIR > /dev/null ; then
        dpkg-statoverride --update --add $USER $GROUP 0750 $CACHEDIR
    fi

    if ! dpkg-statoverride --list /etc/opmuse/opmuse.ini > /dev/null ; then
        dpkg-statoverride --update --add $USER $GROUP 0640 /etc/opmuse/opmuse.ini
    fi
fi

update-rc.d opmuse defaults
invoke-rc.d opmuse start

db_stop
