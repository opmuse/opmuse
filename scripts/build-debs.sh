#!/bin/zsh

set -e

if [[ $# -ne 2 && $# -ne 3 ]]; then
    echo "Usage: $(basename $0) repo dist [--debug]"
    exit 1
fi

if [[ $3 = "--debug" ]]; then
    export debug=yes
else
    export debug=no
fi

repo=$1
dist=$2

reprepro -b $repo deleteunreferenced

# build deb packages from requirements.txt files.
#grep -hiEv "^#" requirements.txt | \
#while read -A req; do
#    package_name=$req[1]
#    package_version=$req[2]
#
#    ./scripts/build-python-deb.sh $repo $dist none $package_name $package_version none \
#        none none none none none none none none none none
#done

# build opmuse deb package
./scripts/build-python-deb.sh $repo $dist setup.py opmuse none scripts/debian-before-install.sh \
    scripts/debian-after-install.sh python3,ffmpeg,imagemagick,unrar,default-mysql-server,debconf,dbconfig-common,rsync,python3-mysqldb \
    /etc/opmuse/opmuse.ini scripts/debian-init/opmuse scripts/debian-default/opmuse scripts/debian-debconf \
    scripts/debian-templates scripts/debian-before-remove scripts/debian-after-remove none --no-prefix

