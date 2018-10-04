#!/usr/bin/env bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT="$( cd "$( dirname "${DIR}"/../../)" && pwd )"

cd "${DIR}"/.. || exit

if [ ! -s "static" ]; then
  echo "Compiling web resources"
  yarn compile

  echo "Compiling translated schemas"
  "${DIR}"/translate_schemas.sh

  echo "Testing schemas"
  echo "...bypassing schema tests for census fork"
  # "${DIR}"/test_schemas.sh data/en
  # "${DIR}"/test_schemas.sh data/cy
fi

printf $(git rev-parse HEAD) > .application-version
