#!/bin/bash

usage () {
	echo "usage: $0 test_dir [python]" 1>&2
	exit 1
}

cleanup () {
	for name in *.ref; do
		rm -f "$(basename "$name" .ref)"
	done
}

DIR=$1
PYTHON=$2
if ! [ -d "$DIR" -a -e "$DIR/args" ]; then
	usage
fi

SRC_DIR=$(pwd)/$(dirname $BASH_SOURCE)/..
cd $DIR

cleanup
# copy inputs
for name in *.in; do
	cp "$name" "$(basename "$name" .in)"
done

# run the command with the args
${PYTHON} ${SRC_DIR}/primenet.py $(cat args) -t 0 -ddd |& tee stdout.log

# check outputs
EXIT=0
for name in *.ref; do
	diff -q "$name" "$(basename "$name" .ref)"
	EXIT=$(( $EXIT || $? ))
done

if [ $EXIT -eq 0 ]; then
	cleanup
fi
exit $EXIT
