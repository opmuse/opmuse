#!/bin/bash -e
#
# Script for fixing systemd during docker builds
#

systemctl=$(type -p systemctl)

if [ -f ${systemctl}.real ]; then
    echo "Restoring systemctl"
    mv ${systemctl}.real ${systemctl}
else
    echo "Replacing systemctl with docker-systemctl-replacement"
    systemctl3=$(mktemp)

    wget -q https://raw.githubusercontent.com/gdraheim/docker-systemctl-replacement/master/files/docker/systemctl3.py \
        -O $systemctl3

    mv ${systemctl} ${systemctl}.real
    cp ${systemctl3} ${systemctl}
    chmod +rx ${systemctl}
fi
