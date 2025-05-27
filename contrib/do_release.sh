#!/bin/sh
# This script can be used to bypass github actions

set -e
# extract the version="x.y.z" from setup.py
VER=$(sed -n -e 's/.*version="\(.*\)".*/\1/p' < setup.py)

function tag_if_not_tagged {
  TAG=v$1
  if git rev-parse --verify --quiet "refs/tags/$TAG" >/dev/null; then
    echo "tag ${TAG} already exists"
  else
    git tag $TAG
    git push --tags
    echo "tagged ${TAG}"
  fi
}

tag_if_not_tagged $VER


