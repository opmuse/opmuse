#!/bin/zsh

set -e

if [[ $# -ne 1 ]]; then
    echo "Usage: $(basename $0) repo"
    exit 1
fi

repo=$1

function build_git() {
    rm -rf $1
    git clone $3
    cd $1
    git checkout $2
    cd ..

    if [[ -r $1/setup.cfg ]]; then
        # remove dev tags and such
        sed -i 's/tag_build\s*=[^=]*/tag_build=/' $1/setup.cfg
    fi

    if [[ -n $4 ]]; then
        sed -i "s/version\s*=[^=,]*/version='$4'/" $1/setup.py
    fi

    ./scripts/build-python-deb.sh $repo master $1/setup.py $1 none none none \
        none none none none none none none none
}

reprepro -b $repo deleteunreferenced

# build deb packages from requirements.txt files except the broken ones, they're
# built further down from their git repos. we build dev-requirements.txt even if
# they're not dependencies but so you can use them for debuging.
#
# note that we skip building mako, firepy, Sphinx and sphinx_rtd_theme
# altogether. instead we use the os-provided ones
grep -hiEv "repoze\.who|jinja2|alembic|mako|firepy|Sphinx|\
    sphinx_rtd_theme|watchdog|WebOb|CherryPy|deluge-client|colorlog|nose|^#" \
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

# these packages pypi builds are broken but building from git works, so let's
# do that instead.
build_git jinja2 2.7.3 https://github.com/mitsuhiko/jinja2.git
build_git alembic rel_0_7_7 https://bitbucket.org/zzzeek/alembic.git
build_git watchdog v0.7.1 https://github.com/gorakhargosh/watchdog.git
build_git cherrypy 3.8.0 https://github.com/cherrypy/cherrypy.git
build_git deluge-client 1.0.2 https://github.com/JohnDoee/deluge-client.git

# build opmuse deb package
./scripts/build-python-deb.sh $repo master setup.py opmuse none scripts/debian-before-install.sh \
    scripts/debian-after-install.sh python3.4,ffmpeg,imagemagick,unrar,mysql-server,debconf,dbconfig-common,rsync \
    /etc/opmuse/opmuse.ini scripts/debian-init/opmuse scripts/debian-default/opmuse scripts/debian-debconf \
    scripts/debian-templates scripts/debian-before-remove scripts/debian-after-remove --no-prefix

