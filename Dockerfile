# This file is used by the build-env github action
ARG SERIES=noble
FROM ubuntu:${SERIES}

ARG MAKE_TARGET="install-dependencies"

ENV MAKE_TARGET=${MAKE_TARGET}
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /work

ADD . checkout

RUN set -ex                                                                                            ;\
    apt-get -q update                                                                                  ;\
    apt-get -q -y upgrade                                                                              ;\
    apt-get -q -y install \
        git \
        make \
        python3-yaml \
        snap \
        socat \
        sudo \
        wget                                                                                           ;\
    apt-get -q clean

RUN set -ex                                                                                            ;\
    make -C /work/checkout ${MAKE_TARGET}                                                              ;\
    rm -rf /work/checkout

