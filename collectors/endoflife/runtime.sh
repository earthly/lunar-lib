#!/bin/bash
set -e

API_BASE="${LUNAR_VAR_ENDOFLIFE_BASE_URL:-https://endoflife.date/api}"
JAVA_PRODUCT="${LUNAR_VAR_JAVA_PRODUCT:-eclipse-temurin}"
DOTNET_PRODUCT="${LUNAR_VAR_DOTNET_PRODUCT:-dotnet}"

NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TODAY="$(date -u +%Y-%m-%d)"

# ---------- helpers ----------

# Take a raw version string, strip a leading "v", drop any non-numeric prefix,
# and keep only the leading numeric/dot run.
#   "v20.11.1" -> "20.11.1"; ">=3.10" -> "3.10"; "^8.1" -> "8.1"
normalize_version() {
    local raw="$1"
    [ -z "$raw" ] && return
    echo "$raw" \
        | sed -E 's/^v//' \
        | sed -E 's/^[^0-9]*([0-9][0-9.]*).*/\1/' \
        | sed -E 's/\.+$//'
}

# Pick the lowest concrete version that satisfies a constraint expression.
# Handles "^X.Y", "~X.Y", ">=X.Y", "X.Y.*", "X.Y, <Z" (commas as AND),
# and "^7.4 || ^8.1" (||-separated alternatives). Worst case satisfier is
# the first matched numeric version in each alternative; we pick the
# lowest of the alternatives by version-tuple.
lowest_concrete() {
    python3 "$(dirname "$0")/lowest_concrete.py" "$1"
}

fetch_product() {
    local product="$1" resp status
    set +e
    resp="$(curl -fsS --max-time 15 "${API_BASE}/${product}.json" 2>/dev/null)"
    status=$?
    set -e
    if [ "$status" -ne 0 ] || [ -z "$resp" ]; then
        echo "endoflife: failed to fetch ${API_BASE}/${product}.json (curl exit $status)" >&2
        return 1
    fi
    echo "$resp"
}

# Match a detected version to the most specific cycle whose .cycle is a
# prefix of the version (Go 1.21.5 -> cycle 1.21). Echoes the cycle object,
# returns 1 if no match.
match_cycle() {
    local version="$1" cycles_json="$2"
    echo "$cycles_json" | jq -e --arg v "$version" '
        [.[] | select(.cycle as $c | $v == $c or ($v | startswith($c + ".")))]
        | sort_by(.cycle | length) | reverse
        | first // empty
    '
}

# Emit normalized .lang.<lang>.eol + .native.endoflife. Args:
#   lang, product, detected_version, cycle_json
emit_eol() {
    local lang="$1" product="$2" version="$3" cycle_json="$4"
    local eol_obj
    eol_obj="$(echo "$cycle_json" | \
        NOW="$NOW" TODAY="$TODAY" PRODUCT="$product" DETECTED_VERSION="$version" \
        python3 "$(dirname "$0")/normalize_cycle.py")"

    echo "$eol_obj" | lunar collect -j ".lang.${lang}.eol" -
    echo "$cycle_json" | lunar collect -j ".lang.${lang}.native.endoflife.cycle" -
    lunar collect ".lang.${lang}.native.endoflife.product" "$product"
}

process_language() {
    local lang="$1" product="$2" version="$3"
    [ -z "$version" ] && return 0
    local product_json cycle_json
    product_json="$(fetch_product "$product")" || return 0
    if ! cycle_json="$(match_cycle "$version" "$product_json")"; then
        echo "endoflife: no cycle matched ${lang}=${version} on ${product}" >&2
        return 0
    fi
    emit_eol "$lang" "$product" "$version" "$cycle_json"
}

# ---------- per-language detection ----------

detect_go() {
    if [ -f .go-version ]; then
        normalize_version "$(head -n1 .go-version)"
        return
    fi
    if [ -f go.mod ]; then
        local tc gm
        tc="$(grep -E '^toolchain[[:space:]]+go' go.mod 2>/dev/null | head -n1 | awk '{print $2}' | sed 's/^go//')"
        gm="$(grep -E '^go[[:space:]]+[0-9]' go.mod 2>/dev/null | head -n1 | awk '{print $2}')"
        normalize_version "${tc:-$gm}"
    fi
}

detect_nodejs() {
    if [ -f .nvmrc ]; then
        normalize_version "$(head -n1 .nvmrc)"
        return
    fi
    if [ -f .node-version ]; then
        normalize_version "$(head -n1 .node-version)"
        return
    fi
    if [ -f package.json ]; then
        local raw
        raw="$(jq -r '.engines.node // empty' package.json 2>/dev/null)"
        [ -n "$raw" ] && lowest_concrete "$raw"
    fi
}

detect_python() {
    if [ -f .python-version ]; then
        normalize_version "$(head -n1 .python-version)"
        return
    fi
    if [ -f runtime.txt ]; then
        normalize_version "$(head -n1 runtime.txt | sed -E 's/^python-//')"
        return
    fi
    if [ -f pyproject.toml ]; then
        local raw
        raw="$(python3 - <<'PY' 2>/dev/null
import sys
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        sys.exit(0)
try:
    with open("pyproject.toml", "rb") as f:
        d = tomllib.load(f)
    print(d.get("project", {}).get("requires-python", "") or "")
except Exception:
    pass
PY
)"
        [ -n "$raw" ] && lowest_concrete "$raw"
    fi
}

detect_ruby() {
    if [ -f .ruby-version ]; then
        normalize_version "$(head -n1 .ruby-version)"
        return
    fi
    if [ -f Gemfile ]; then
        local raw
        raw="$(grep -E "^[[:space:]]*ruby[[:space:]]+['\"]" Gemfile 2>/dev/null \
            | head -n1 \
            | sed -E "s/.*ruby[[:space:]]+['\"]([^'\"]+).*/\1/")"
        [ -n "$raw" ] && normalize_version "$raw"
    fi
}

detect_java() {
    if [ -f .java-version ]; then
        normalize_version "$(head -n1 .java-version)"
        return
    fi
    if [ -f pom.xml ]; then
        local v
        v="$(grep -E '<(java\.version|maven\.compiler\.release|maven\.compiler\.target|maven\.compiler\.source)>' pom.xml 2>/dev/null \
            | head -n1 \
            | sed -E 's/.*>([^<]+)<.*/\1/')"
        if [ -n "$v" ]; then
            normalize_version "$v"
            return
        fi
    fi
    if [ -f build.gradle ] || [ -f build.gradle.kts ]; then
        local v
        v="$(grep -hE '(sourceCompatibility|targetCompatibility|JavaLanguageVersion\.of)' \
            build.gradle build.gradle.kts 2>/dev/null \
            | head -n1 \
            | sed -E 's/.*[^0-9]([0-9]+(\.[0-9]+)*).*/\1/')"
        [ -n "$v" ] && normalize_version "$v"
    fi
}

detect_dotnet() {
    if [ -f global.json ]; then
        local v
        v="$(jq -r '.sdk.version // empty' global.json 2>/dev/null)"
        if [ -n "$v" ]; then
            normalize_version "$v"
            return
        fi
    fi
    local proj
    proj="$(find . -maxdepth 3 \( -name '*.csproj' -o -name '*.fsproj' -o -name '*.vbproj' \) 2>/dev/null | head -n1)"
    if [ -n "$proj" ]; then
        local tfm
        tfm="$(grep -E '<TargetFramework>' "$proj" 2>/dev/null | head -n1 | sed -E 's/.*>([^<]+)<.*/\1/')"
        case "$tfm" in
            netcoreapp*)
                normalize_version "${tfm#netcoreapp}" ;;
            net[0-9].[0-9]*)
                normalize_version "${tfm#net}" ;;
            net4[0-9])
                # net48 -> 4.8
                echo "$tfm" | sed -E 's/^net([0-9])([0-9])/\1.\2/' ;;
            *) ;;
        esac
    fi
}

detect_php() {
    if [ -f composer.json ]; then
        local raw
        raw="$(jq -r '.config.platform.php // .require.php // empty' composer.json 2>/dev/null)"
        [ -n "$raw" ] && lowest_concrete "$raw"
    fi
}

# ---------- main ----------

run_one() {
    local lang="$1" product="$2" detect_fn="$3"
    local version
    version="$($detect_fn 2>/dev/null || true)"
    if [ -n "$version" ]; then
        process_language "$lang" "$product" "$version"
    fi
}

run_one go      "go"               detect_go
run_one nodejs  "nodejs"           detect_nodejs
run_one python  "python"           detect_python
run_one ruby    "ruby"             detect_ruby
run_one java    "$JAVA_PRODUCT"    detect_java
run_one dotnet  "$DOTNET_PRODUCT"  detect_dotnet
run_one php     "php"              detect_php

exit 0
