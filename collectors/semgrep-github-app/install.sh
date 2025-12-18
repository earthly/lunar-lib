#!/bin/bash
if [[ "$(uname -s)" == "Darwin" ]]; then
  brew install postgresql
else
  apt install -y postgresql
fi

echo "Semgrep Github app collector dependencies installed."