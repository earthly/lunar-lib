#!/bin/bash

arg="-coverprofile"
# Find the index of such arg
index=$(echo "$LUNAR_CI_COMMAND" | jq -r --arg val "$arg" 'index($val)')

if [[ "$index" == "null" ]]; then
  # No coverage run
  jq -n '{
    run: false,
    percentage: null
  }' | lunar collect -j ".lang.go.tests.coverage" -
  
  # Also collect to .testing (no coverage data)
  jq -n 'null' | lunar collect -j ".testing.coverage" -
else
  next_arg=$(echo "$LUNAR_CI_COMMAND" | jq -r --argjson idx "$index" '.[$idx + 1]')
  # Handle case where there's no next value
  if [[ "$next_arg" == "null" ]]; then
    jq -n '{
      run: false,
      percentage: null
    }' | lunar collect -j ".lang.go.tests.coverage" -
    
    # Also collect to .testing (no coverage data)
    jq -n 'null' | lunar collect -j ".testing.coverage" -
  else
    # Extract coverage percentage
    coverage_pct=$(go tool cover -func="$next_arg" 2>/dev/null | awk '/total:/ {print $NF}' | sed 's/%$//' || echo "")
    
    if [[ -n "$coverage_pct" ]]; then
      # Collect to .lang.go.tests.coverage (language-specific)
      jq -n \
        --argjson run true \
        --argjson percentage "$(echo "$coverage_pct" | jq -r 'tonumber')" \
        '{
          run: $run,
          percentage: $percentage
        }' | lunar collect -j ".lang.go.tests.coverage" -
      
      # Also collect to .testing.coverage (standardized format)
      jq -n \
        --argjson percentage "$(echo "$coverage_pct" | jq -r 'tonumber')" \
        '{
          source: {
            tool: "go cover",
            integration: "ci"
          },
          percentage: $percentage
        }' | lunar collect -j ".testing.coverage" -
    else
      # Coverage file exists but couldn't extract percentage
      jq -n '{
        run: true,
        percentage: null
      }' | lunar collect -j ".lang.go.tests.coverage" -
      
      jq -n 'null' | lunar collect -j ".testing.coverage" -
    fi
  fi
fi

