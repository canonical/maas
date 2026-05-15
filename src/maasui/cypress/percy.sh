#! /usr/bin/env bash

if [ -f ../.env.test.local ]; then
    source ../.env.test.local
elif [ -f ../.env.test ]; then
    source ../.env.test
fi

PERCY_TOKEN=$PERCY_TOKEN PERCY_BRANCH=local percy exec -- cypress run --config integrationFolder=percy
