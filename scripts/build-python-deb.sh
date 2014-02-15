#!/bin/zsh

if [[ $# -ne 12 && $# -ne 13 ]]; then
    echo -n "Usage: $(basename $0) repo dist package_file package_name package_version "
    echo -n "package_before package_after package_deps package_confs package_init "
    echo "package_default package_debconf [--no-prefix]"
    exit 1
fi

# for fpm/pip so it doesn't fail just because we already have
# the requirement globally
export PIP_FORCE_REINSTALL=1

repo=$1
dist=$2
package_file=$3
package_name=${4:l}
package_version=$5
package_before=$6
package_after=$7
package_deps=$8
package_confs=$9
package_init=$10
package_default=$11
package_debconf=$12

if [[ $13 == "--no-prefix" ]]; then
    prefix=0
else
    prefix=1
fi

args=(
    --python-package-name-prefix python3
    --python-install-bin /usr/bin
    --python-install-lib /usr/lib/python3.3/dist-packages/
    --python-bin /usr/bin/python3.3
    --python-pip /usr/bin/pip3
)

if [[ $prefix -eq 1 ]]; then
    full_package_name=python3-$package_name
else
    args+=(
        --no-python-fix-name
    )
    full_package_name=$package_name
fi

if [[ $package_before != "none" ]]; then
    args+=(
        --before-install $package_before
    )
fi

if [[ $package_after != "none" ]]; then
    args+=(
        --after-install $package_after
    )
fi

if [[ $package_deps != "none" ]]; then
    deps=("${(s/,/)package_deps}")

    for dep in $deps; do
        args+=(
            --depends $dep
        )
    done
fi

if [[ $package_confs != "none" ]]; then
    confs=("${(s/,/)package_confs}")

    for conf in $confs; do
        args+=(
            --config-files $conf
        )
    done
fi

if [[ $package_init != "none" ]]; then
    args+=(
        --deb-init $package_init
    )
fi

if [[ $package_default != "none" ]]; then
    args+=(
        --deb-default $package_default
    )
fi

if [[ $package_debconf != "none" ]]; then
    args+=(
        --deb-config $package_debconf
    )
fi

if [[ $package_file == "none" ]]; then
    package_install=$package_name
else
    package_install=$package_file
fi

if [[ $package_version != "none" ]]; then
    package_install=${package_install}${package_version}
fi

args+=(-s python -t deb $package_install)

rm ${full_package_name}*.deb 2> /dev/null

reprepro -b $repo remove $dist $full_package_name

fpm $args

reprepro -b $repo includedeb $dist ${full_package_name}*.deb
