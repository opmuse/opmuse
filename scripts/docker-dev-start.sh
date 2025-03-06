#!/bin/sh

/etc/init.d/mariadb start

while `sleep 5`; do
    /root/opmuse/console cherrypy
done
