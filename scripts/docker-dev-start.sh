#!/bin/sh

/etc/init.d/mysql start

while `sleep 5`; do
    /root/opmuse/console cherrypy
done
