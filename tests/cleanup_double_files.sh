#!/bin/bash

# If .in == .ref, link .ref to .in
for nom in $(find -name *.ref -type f ) ; do
    in=$(dirname $nom)/$(basename $nom .ref).in
    if [ -e $in ] && diff -q $nom $in >/dev/null; then
        echo ln -sf $(basename $nom .ref).in $nom
        ln -sf $(basename $nom .ref).in $nom
    fi
done

sha256sum $(find test_* -type f ) |sort| uniq --check-chars=64 -D | (read prev_hash prev_name;
    while read hash name; do
        if [ $hash == $prev_hash ]; then
            if [ $(dirname $name) == $(dirname $prev_name) ]; then
                echo ln -sf $(basename $prev_name) $name;
                ln -sf $(basename $prev_name) $name;
            else
                echo ln -sf ../$prev_name $name;
                ln -sf ../$prev_name $name;
            fi
        else
            prev_name=$name
            prev_hash=$hash
        fi
    done
)
