#!/bin/sh

### BEGIN INIT INFO
# Provides:          opmuse
# Required-Start:    $remote_fs $syslog $network
# Required-Stop:     $remote_fs $syslog $network
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: opmuse
### END INIT INFO

set -e

. /etc/default/opmuse

. /lib/lsb/init-functions

waitpid() {
    while kill -0 $1 > /dev/null 2>&1; do
        sleep .5
    done
}

waitkill() {
    if [ -f $1 ]; then
        PID=$(cat $1)
        kill $PID
        waitpid $PID
    fi
}

start() {
    opmuse-boot --daemon --user $USER \
        --log $LOGDIR/access.log --errorlog $LOGDIR/error.log \
        --pidfile $PIDFILE --env $ENVIRONMENT
}

stop() {
    waitkill $PIDFILE
}

reload() {
    kill -HUP $(cat $PIDFILE)
}

case $1 in
    start)
        log_daemon_msg "Starting opmuse" "opmuse"
        start
        log_end_msg 0
        ;;
    stop)
        log_daemon_msg "Stopping opmuse" "opmuse"
        stop
        log_end_msg 0
        ;;
    reload)
        log_daemon_msg "Reloading opmuse" "opmuse"
        reload
        log_end_msg 0
        ;;
    restart)
        log_daemon_msg "Stopping opmuse" "opmuse"
        stop
        log_daemon_msg "Starting opmuse" "opmuse"
        start
        log_end_msg 0
        ;;
    *)
        log_action_msg "Usage: /etc/init.d/opmuse {start|stop|reload|restart}" || true
        exit 1
esac
