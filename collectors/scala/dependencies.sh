#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Skip when no Scala source — sbt-only-Java projects belong under .lang.java.
if ! is_scala_project; then
    echo "No Scala source files detected, exiting"
    exit 0
fi

direct_json="[]"
transitive_json="[]"
source_tool=""

# build.sbt: libraryDependencies += "group" %% "artifact" % "version"
# Also handles `% Test`, `% "test"`, etc. as version when not literal.
extract_sbt_deps() {
    awk '
        # Match lines containing both %% (or %) and version literal.
        /libraryDependencies/ || /^[[:space:]]*"[a-zA-Z0-9._-]+"[[:space:]]*%%?[[:space:]]*"/ {
            # Find first three quoted tokens: group, artifact, version.
            line=$0
            n=0
            while (match(line, /"[^"]*"/) > 0) {
                tok=substr(line, RSTART+1, RLENGTH-2)
                line=substr(line, RSTART+RLENGTH)
                n++
                if (n==1) group=tok
                else if (n==2) artifact=tok
                else if (n==3) { version=tok; break }
            }
            if (n>=3 && group ~ /^[a-zA-Z0-9._-]+$/ && artifact ~ /^[a-zA-Z0-9._-]+$/) {
                printf "{\"path\":\"%s:%s\",\"version\":\"%s\"}\n", group, artifact, version
            }
            group=""; artifact=""; version=""; n=0
        }
    ' build.sbt 2>/dev/null
}

# build.sc (Mill): ivy"group::artifact:version" or ivy"group:artifact:version"
extract_mill_deps() {
    grep -oE 'ivy"[^"]+"' build.sc 2>/dev/null | sed 's/^ivy"//; s/"$//' | awk -F: '
        {
            # Mill ivy strings come in three shapes:
            #   group:artifact:version           → 3 fields
            #   group::artifact:version          → empty 2nd field, drop it
            #   group:::artifact:version         → empty 2nd & 3rd, drop both
            # Rebuild without empty fields, then take the first three.
            n=0
            for (i=1; i<=NF; i++) {
                if ($i != "") { n++; f[n]=$i }
            }
            if (n>=3) {
                printf "{\"path\":\"%s:%s\",\"version\":\"%s\"}\n", f[1], f[2], f[3]
            }
        }
    '
}

# pom.xml: <dependency><groupId>g</groupId><artifactId>a</artifactId><version>v</version></dependency>
extract_pom_deps() {
    # Use an awk state machine because <groupId>/<artifactId>/<version> can span lines.
    awk '
        /<dependency>/ { in_dep=1; g=""; a=""; v=""; next }
        /<\/dependency>/ {
            if (g != "" && a != "") {
                printf "{\"path\":\"%s:%s\",\"version\":\"%s\"}\n", g, a, v
            }
            in_dep=0; next
        }
        in_dep && /<groupId>/ {
            match($0, /<groupId>([^<]*)<\/groupId>/, m); if (m[1]!="") g=m[1]
        }
        in_dep && /<artifactId>/ {
            match($0, /<artifactId>([^<]*)<\/artifactId>/, m); if (m[1]!="") a=m[1]
        }
        in_dep && /<version>/ {
            match($0, /<version>([^<]*)<\/version>/, m); if (m[1]!="") v=m[1]
        }
    ' pom.xml 2>/dev/null
}

if [[ -f "build.sbt" ]]; then
    source_tool="sbt"
    direct_json=$(extract_sbt_deps | jq -s '. // []')
elif [[ -f "build.sc" ]]; then
    source_tool="mill"
    direct_json=$(extract_mill_deps | jq -s '. // []')
elif pom_has_scala_plugin; then
    source_tool="maven"
    direct_json=$(extract_pom_deps | jq -s '. // []')
fi

# Transitive: build.sbt.lock is JSON with `dependencies[].{org, name, version}`.
if [[ -f "build.sbt.lock" ]]; then
    direct_paths=$(jq '[.[].path]' <<<"$direct_json")
    transitive_json=$(jq --argjson direct "$direct_paths" '
        [
          (.dependencies // [])[]
          | "\(.org):\(.name)" as $p
          | select($direct | index($p) | not)
          | {path: $p, version: .version}
        ]
    ' build.sbt.lock 2>/dev/null || echo "[]")
fi

if [[ -z "$source_tool" ]]; then
    echo "No supported Scala manifest found, skipping dependency emit"
    exit 0
fi

jq -n \
    --argjson direct "$direct_json" \
    --argjson transitive "$transitive_json" \
    --arg source_tool "$source_tool" \
    '{
        direct: $direct,
        transitive: $transitive,
        source: {
            tool: $source_tool,
            integration: "code"
        }
    }' | lunar collect -j ".lang.scala.dependencies" -
