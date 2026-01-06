VERSION 0.8

all:
    BUILD +dockerfile-collector-image

dockerfile-collector-image:
    FROM DOCKERFILE ./collectors/dockerfile
    ARG VERSION=latest
    SAVE IMAGE --push earthly/lunar-lib-dockerfile:$VERSION
