#!/bin/zsh

function build_git() {
    rm -rf $1
    git clone -b $2 $3

    if [[ -r $1/setup.cfg ]]; then
        # remove dev tags and such
        sed -i 's/tag_build\s*=[^=]*/tag_build=/' $1/setup.cfg
    fi

    ./scripts/build-python-deb.sh /var/www/apt.opmu.se/apt/debian master $1/setup.py $1 none none none none none none none
}

reprepro -b /var/www/apt.opmu.se/apt/debian/ deleteunreferenced

# build deb packages from requirements.txt except the broken ones, they're
# built further down...
grep -iEv "repoze\.who|jinja2|alembic|zope\.interface|mako|^#" requirements.txt | while read -A req; do
    ./scripts/build-python-deb.sh /var/www/apt.opmu.se/apt/debian master none $req[1] $req[2] none none none none none none
done

# these packages pypi builds are broken but building from git works, so let's
# do that instead.
build_git repoze.who 2.2 https://github.com/repoze/repoze.who.git
build_git jinja2 2.7.2 https://github.com/mitsuhiko/jinja2.git
build_git alembic rel_0_6_2 https://bitbucket.org/zzzeek/alembic.git
build_git zope.interface 4.0.5 https://github.com/zopefoundation/zope.interface.git
build_git mako rel_0_9_1 https://github.com/zzzeek/mako.git

# build opmuse deb package
./scripts/build-python-deb.sh /var/www/apt.opmu.se/apt/debian master setup.py opmuse none \
    scripts/debian-before-install.sh scripts/debian-after-install.sh python3.3,ffmpeg,imagemagick,unrar,debconf \
    /etc/opmuse/opmuse.ini scripts/debian-init.sh scripts/debian-default --no-prefix

