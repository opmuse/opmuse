FROM debian:stretch
MAINTAINER Mattias Fliesberg <mattias@fliesberg.email>

ENV DEBIAN_FRONTEND noninteractive

RUN sed -i "s/stretch main/stretch main contrib non-free/" /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y curl wget locales apt-transport-https python3-pkg-resources gnupg && \
    echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && \
    echo "export LC_ALL=en_US.utf8" >> /root/.bashrc && \
    dpkg-reconfigure locales && \
    echo "deb https://apt.opmu.se/debian-stretch/ master main" > /etc/apt/sources.list.d/opmuse.list && \
    curl -s https://apt.opmu.se/opmuse.pub | apt-key add - && \
    apt-get update && \
    echo "mysql-server mysql-server/root_password password" | debconf-set-selections && \
    echo "mysql-server mysql-server/root_password_again password" | debconf-set-selections && \
    apt-get install -y default-mysql-server && \
    /etc/init.d/mysql start && \
    apt-get install -y opmuse

VOLUME ["/var/lib/mysql", \
        "/etc/opmuse", \
        "/var/cache/opmuse", \
        "/var/log/opmuse"]

COPY scripts/docker-start.sh /home/opmuse/start.sh

ENTRYPOINT ["/home/opmuse/start.sh"]

EXPOSE 8080
