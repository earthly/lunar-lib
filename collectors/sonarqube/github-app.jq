# Picks this pull request's SonarQube check runs out of a commit's check runs
# and reads the quality gate and the PR's new-code numbers from them.
#
# Input: an array of GitHub check runs (every page, filter=all).
# Args:  $sha  the commit, $pr  the pull request number,
#        $key  the project key to read, or "" for whichever projects reported.
# Output: {done: false, waiting: "<why>"} until every project's newest check
# run has completed, then {done: true, summary: "<log line>", code_quality: {…}}.

def urldecode:
  gsub("%(?<h>[0-9A-Fa-f]{2})";
    .h | ascii_downcase | explode | map(if . >= 97 then . - 87 else . - 48 end)
    | [.[0] * 16 + .[1]] | implode);

def param($name):
  (capture("[?&]" + $name + "=(?<v>[^&#]*)") | .v | urldecode) // null;

# SonarQube Server and Cloud name their PR check "SonarQube Code Analysis" /
# "SonarCloud Code Analysis", prefixed "[<project>] " in a monorepo, and link it
# to the project's dashboard (?id=<key>). That rules out CI jobs and
# code-scanning checks that only have "Sonar" in their name.
def sonarqube_check:
  ((.name // "") | test("^(\\[.+\\] )?Sonar\\w*( \\w+)? Code Analysis$"))
  and ((.details_url // "") | test("[?&]id=[^&#]"));

def project: .details_url | param("id");
def analysis: .details_url | (param("pullRequest") | if . then "pull request " + . else empty end)
  // (param("branch") | if . then "branch " + . else empty end) // "an unknown analysis";

# The summary as plain lines: images, link targets, list and heading markers gone.
def lines:
  (.output.summary // "") | split("\n") | map(
    gsub("!\\[[^\\]]*\\]\\([^)]*\\)"; "")
    | gsub("\\[\\s*\\]\\([^)]*\\)"; "")
    | gsub("\\[(?<t>[^\\]]*)\\]\\([^)]*\\)"; .t)
    | gsub("\\*\\*"; "")
    | sub("^\\s*(#+|[-*])\\s+"; "")
    | gsub("^\\s+|\\s+$"; ""));

# Each line under "Failed conditions" (SonarQube Server/Cloud), or under the
# "Quality Gate failed" heading (the community branch plugin).
def failed_conditions:
  reduce lines[] as $l ({in: false, out: []};
    if ($l | test("^(failed conditions|quality gate failed)$"; "i")) then .in = true
    elif $l == "" or ($l | test("^(issues|measures|quality gate passed)$"; "i")) then .in = false
    elif .in then .out += [$l]
    else . end)
  | .out
  | map(. as $text
      | ((capture("^(?<m>.*?)\\s*\\(required (?<r>[^()]*)\\)$")) // {m: $text, r: null}) as $p
      | (($p.m | capture("^(?<v>[0-9][0-9.,]*%?|[A-E]) (?<metric>.+?)( \\([^()]*\\))?$")) // {v: null, metric: $p.m}) as $q
      | {text: $text, metric: $q.metric}
        + (if $q.v then {value: $q.v} else {} end)
        + (if $p.r then {required: $p.r} else {} end));

# A number SonarQube printed, from a measure line or a failed condition. Lines
# such as "No data about Coverage" match nothing, so absent data stays absent.
def measure($re):
  first(lines[] | sub("\\s*\\((required|is) [^()]*\\)$"; "") | capture($re; "i") | .n | gsub(","; "") | tonumber) // null;
def count($label): measure("^(?<n>[0-9][0-9,]*) " + $label + "$");
def percent($labels): measure("^(?<n>[0-9]+(\\.[0-9]+)?)% (" + $labels + ")( \\([^()]*estimated after merge\\))?$");

def new_code: {
    new_issues: count("new issues?"),
    fixed_issues: count("fixed issues?"),
    accepted_issues: count("accepted issues?"),
    security_hotspots: count("security hotspots?"),
    coverage_percentage: percent("coverage on new code|coverage"),
    duplication_percentage: percent("duplication on new code|duplicated lines \\(%\\) on new code|duplicated code|duplication")
  } | with_entries(select(.value != null));

def verdict:
  (.output.title // "") as $t
  | if ($t | test("analysis (has )?failed"; "i")) or ((.output.summary // "") | test("last analysis has failed"; "i")) then null
    elif $t | test("quality gate (passed|success|ok)\\b"; "i") then "passed"
    elif $t | test("quality gate (failed|failure|error)\\b"; "i") then "failed"
    elif .conclusion == "success" then "passed"
    elif .conclusion == "failure" then "failed"
    else null end;

[.[] | select(sonarqube_check and .head_sha == $sha)] as $sonar
| [$sonar[] | select((.details_url | param("pullRequest")) == $pr)] as $pull
| [$pull[] | select($key == "" or project == $key)] as $wanted
| ($wanted | group_by(project) | map(max_by(.id))) as $latest
| if ($sonar | length) == 0 then
    {done: false, waiting: "no SonarQube check run on the commit yet"}
  elif ($pull | length) == 0 then
    {done: false, waiting: "the SonarQube check runs on the commit are for \($sonar | map(analysis) | unique | join(", ")), not pull request \($pr)"}
  elif ($wanted | length) == 0 then
    {done: false, waiting: "no SonarQube check run for project \($key) (found \($pull | map(project) | unique | join(", ")))"}
  elif any($latest[]; .status != "completed") then
    {done: false, waiting: ($latest | map(select(.status != "completed") | "\(.name) is \(.status)") | join(", "))}
  else
    ($latest | map(. as $run | {
        name, project_key: project, conclusion, title: .output.title, url: .details_url, completed_at,
        verdict: verdict,
        failed: (if verdict == "failed" then failed_conditions | map(. + {project_key: ($run | project)}) else [] end),
        new_code: new_code,
        server: ((.details_url | capture("^(?<s>[^?#]*)/dashboard[?]") | .s) // null)
      })) as $checks
    | ($checks | map(.verdict)) as $v
    | (if any($v[]; . == "failed") then false elif all($v[]; . == "passed") then true else null end) as $passing
    | ($checks | map(select(.verdict == "failed"))) as $failed
    | {
        done: true,
        summary: ($checks | map("\(.name): \(.title // .conclusion)" + (if .failed != [] then " (\(.failed | length) failed condition(s))" else "" end)) | join("; ")),
        code_quality: (
          {source: ({tool: "sonarqube", integration: "github_app"}
              + (if ($checks | length) == 1 then {project_key: $checks[0].project_key} else {} end)
              + ($checks | map(.server) | unique | if length == 1 and .[0] != null then {api_url: .[0]} else {} end)),
            native: {sonarqube: (
              {github_app: {status: "complete", check_runs: ($checks | map(
                {name, project_key, conclusion, title, url, completed_at}
                + (if .verdict then {quality_gate: .verdict} else {} end)))}}
              + if $passing == null then {}
                elif $passing then {quality_gate: {status: "OK", conditions_failed: 0}}
                else {quality_gate: ({status: "ERROR"}
                  + ($failed | map(.failed[]) | if . != [] then {failed_conditions: .} else {} end)
                  + (if all($failed[]; .failed != []) then {conditions_failed: ($failed | map(.failed | length) | add)} else {} end))}
                end)}}
          + (if $passing == null then {} else {passing: $passing} end)
          + (if ($checks | length) == 1 and ($checks[0].new_code != {}) then {pr: $checks[0].new_code} else {} end))
      }
  end
