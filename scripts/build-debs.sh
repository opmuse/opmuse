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
# note that we skip building mako, six and firepy altogether
grep -hiEv "SQLAlchemy-Utils|repoze\.who|jinja2|alembic|zope\.interface|six|mako|firepy|watchdog|WebOb|^#" \
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
build_git repoze.who 2.2 https://github.com/repoze/repoze.who.git
build_git jinja2 2.7.2 https://github.com/mitsuhiko/jinja2.git
build_git alembic rel_0_6_5 https://bitbucket.org/zzzeek/alembic.git
build_git zope.interface 4.0.5 https://github.com/zopefoundation/zope.interface.git
build_git watchdog v0.7.1 https://github.com/gorakhargosh/watchdog.git
build_git sqlalchemy-utils 5b00373f https://github.com/kvesteri/sqlalchemy-utils.git # v0.26
build_git webob 1.4 https://github.com/Pylons/webob.git 1.4-2 # bump version to override broken package in jessie

# build opmuse deb package
./scripts/build-python-deb.sh $repo master setup.py opmuse none scripts/debian-before-install.sh \
    scripts/debian-after-install.sh python3.3,ffmpeg,imagemagick,unrar,mysql-server,debconf,dbconfig-common \
    /etc/opmuse/opmuse.ini scripts/debian-init/opmuse scripts/debian-default/opmuse scripts/debian-debconf \
    scripts/debian-templates scripts/debian-before-remove scripts/debian-after-remove --no-prefix

