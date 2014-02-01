#!/bin/zsh

if [[ $# -ne 5 && $# -ne 6 ]]; then
    echo "Usage: $(basename $0) repo dist package_file package_name package_version [--no-prefix]"
    exit 1
fi

repo=$1
dist=$2
package_file=$3
package_name=${4:l}
package_version=$5

if [[ $6 == "--no-prefix" ]]; then
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
