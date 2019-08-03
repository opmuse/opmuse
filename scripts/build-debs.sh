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
grep -hiEv "^#" requirements.txt mysql-requirements.txt | \
while read -A req; do
    ./scripts/build-python-deb.sh $repo $dist none $req[1] $req[2] none \
        none none none none none none none none none
done

# build an empty package for python3-pyyaml with python3-yaml as dep as watchdog
# depends on python3-pyyaml and not python3-yaml as debian calls it
./scripts/build-python-deb.sh $repo $dist none python3-pyyaml none none \
    none "python3-yaml (>= 3.13)" none none none none none none none --no-prefix empty "3.13"

# build opmuse deb package
./scripts/build-python-deb.sh $repo $dist setup.py opmuse none scripts/debian-before-install.sh \
    scripts/debian-after-install.sh python3,ffmpeg,imagemagick,unrar,default-mysql-server,debconf,dbconfig-common,rsync \
    /etc/opmuse/opmuse.ini scripts/debian-init/opmuse scripts/debian-default/opmuse scripts/debian-debconf \
    scripts/debian-templates scripts/debian-before-remove scripts/debian-after-remove --no-prefix

