#!/bin/bash

PYTHONS="python2.6 python2.7 python3.3 python3.4 python3.6 python3.7 python3.9"

usage () {
	echo "usage: $0 [python]" 1>&2
	exit 1
}

EXIT=0
if [ $# -lt 1 ]; then
	for python in $PYTHONS; do
		echo "$0 $python"
		$0 $python
		EXIT=$(( $EXIT || $? ))
	done
	exit $EXIT
fi

python=$1
if ! $python --version >&/dev/null; then
	echo "$python doesn't exist, skipping" 1>&2
	exit 0
fi

echo "$( $python --version 2>&1 )"

EXIT=0
for testname in $( ls -d test_* ); do
	./run_test.sh $testname $python
	EXITCODE=$?
	EXIT=$(( $EXIT || $EXITCODE ))
done

exit $EXIT
# vim: noexpandtab ts=4 sts=0 sw=0
