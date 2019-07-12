#!/bin/zsh

set -e

if [[ $# -ne 15 && $# -ne 16 && $# -ne 17 && $# -ne 18 ]]; then
    echo -n "Usage: $(basename $0) repo dist package_file package_name package_version "
    echo -n "package_before package_after package_deps package_confs package_init package_default "
    echo -n "package_debconf package_templates package_before_remove package_after_remove [--no-prefix] "
    echo "[input_type] [version]"
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
package_templates=$13
package_before_remove=$14
package_after_remove=$15

if [[ $16 == "--no-prefix" ]]; then
    prefix=0
else
    prefix=1
fi

input_type=$17
version=$18

if [[ $input_type = "" ]]; then
    input_type=python
fi

args=(
    --python-package-name-prefix python3
    --python-install-bin /usr/bin
    --python-install-lib /usr/lib/python3/dist-packages/
    --python-bin /usr/bin/python3
    --python-pip /usr/bin/pip3
)

if [[ $version != "" ]]; then
    args+=(-v $version)
fi

if [[ $prefix -eq 1 ]]; then
    full_package_name=python3-${package_name#python-}
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

if [[ $package_templates != "none" ]]; then
    args+=(
        --deb-templates $package_templates
    )
fi

if [[ $package_before_remove != "none" ]]; then
    args+=(
        --before-remove $package_before_remove
    )
fi

if [[ $package_after_remove != "none" ]]; then
    args+=(
        --after-remove $package_after_remove
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

if [[ $input_type == "empty" ]]; then
    package_install=(-n $package_install)
fi

args+=(-s $input_type -t deb)
args+=($package_install)

rm ${full_package_name}*.deb > /dev/null 2>&1 || true

reprepro -b $repo remove $dist $full_package_name

fpm $args

reprepro -b $repo includedeb $dist ${full_package_name}*.deb
