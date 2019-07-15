#!/bin/zsh

set -e

if [[ $# -ne 1 && $# -ne 2 ]]; then
    echo "Usage: $(basename $0) repo [--debug]"
    exit 1
fi

if [[ $2 = "--debug" ]]; then
    export debug=yes
else
    export debug=no
fi

repo=$1

reprepro -b $repo deleteunreferenced

# build deb packages from requirements.txt files except the broken ones, they're
# built further down from their git repos. we build dev-requirements.txt even if
# they're not dependencies but so you can use them for debuging.
#
# note that we skip building mako, Sphinx and sphinx_rtd_theme altogether.
# instead we use the os-provided ones
grep -hiEv "Sphinx|sphinx_rtd_theme|colorlog|pytest|^#" \
    requirements.txt mysql-requirements.txt dev-requirements.txt | \
while read -A req; do
    if [[ -f $req[1] ]]; then
        if [[ $req[1] =~ "\.zip$" ]]; then
            dir=${req[1]/\//_}

            if [[ -d $dir ]]; then
                rm -rf $dir
            fi

            unzip $req[1] -d $dir

            name=$(echo ${req[1]:t} | sed "s/^\([^-]\+\)-.*/\1/")

            if [[ -f $(print $dir/**/setup.py) ]]; then
                ./scripts/build-python-deb.sh $repo master $dir/**/setup.py $name \
                    none none none none none none none none none none none
            else
                echo "Couldn't find setup.py for $req"
                exit 1
            fi
        else
            echo "Don't know how to build $req"
            exit 1
        fi
    else
        ./scripts/build-python-deb.sh $repo master none $req[1] $req[2] none \
            none none none none none none none none none
    fi
done

# build an empty package for python3-pyyaml with python3-yaml as dep as watchdog
# depends on python3-pyyaml and not python3-yaml as debian calls it
./scripts/build-python-deb.sh $repo master none python3-pyyaml none none \
    none "python3-yaml (>= 3.13)" none none none none none none none --no-prefix empty "3.13"

# build opmuse deb package
./scripts/build-python-deb.sh $repo master setup.py opmuse none scripts/debian-before-install.sh \
    scripts/debian-after-install.sh python3,ffmpeg,imagemagick,unrar,default-mysql-server,debconf,dbconfig-common,rsync \
    /etc/opmuse/opmuse.ini scripts/debian-init/opmuse scripts/debian-default/opmuse scripts/debian-debconf \
    scripts/debian-templates scripts/debian-before-remove scripts/debian-after-remove --no-prefix

