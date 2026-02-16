#!/bin/bash
# REST API client for Jira Cloud — fallback when MCP tools are unavailable
# Uses curl + Basic auth (email:apiToken)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

# ── Credentials ──────────────────────────────────────────────────────────────

jira_load_creds() {
  local root="$1"
  local local_config="$root/.claude/jira-tracker.local.json"
  local config="$root/.claude/jira-tracker.json"

  [[ ! -f "$local_config" ]] && { echo "ERROR: Missing $local_config — run /jira-setup" >&2; return 1; }
  [[ ! -f "$config" ]] && { echo "ERROR: Missing $config — run /jira-setup" >&2; return 1; }

  JIRA_EMAIL=$(json_get "$local_config" "email")
  JIRA_API_TOKEN=$(json_get "$local_config" "apiToken")
  JIRA_BASE_URL=$(json_get "$local_config" "baseUrl")
  JIRA_CLOUD_ID=$(json_get "$config" "cloudId")
  JIRA_PROJECT_KEY=$(json_get "$config" "projectKey")

  [[ -z "$JIRA_EMAIL" || -z "$JIRA_API_TOKEN" || -z "$JIRA_BASE_URL" ]] && {
    echo "ERROR: Incomplete credentials in $local_config" >&2; return 1;
  }
}

# ── Helpers ──────────────────────────────────────────────────────────────────

_jira_curl() {
  local method="$1" path="$2" data="${3:-}"
  local url="${JIRA_BASE_URL}/rest/api/3${path}"
  local -a args=(-s -w "\n%{http_code}" -u "${JIRA_EMAIL}:${JIRA_API_TOKEN}"
                 -H "Content-Type: application/json" -H "Accept: application/json"
                 -X "$method")
  [[ -n "$data" ]] && args+=(-d "$data")
  curl "${args[@]}" "$url"
}

# Parse curl response: body on stdout, returns non-zero if HTTP >= 400
_jira_parse() {
  local response="$1"
  local body http_code
  http_code=$(echo "$response" | tail -1)
  body=$(echo "$response" | sed '$d')
  echo "$body"
  [[ "$http_code" -ge 200 && "$http_code" -lt 400 ]]
}

# Convert plain text to Atlassian Document Format JSON
text_to_adf() {
  local text="$1"
  python3 -c "
import json, sys
text = sys.argv[1]
paragraphs = []
for line in text.split('\n'):
    if line.strip():
        paragraphs.append({
            'type': 'paragraph',
            'content': [{'type': 'text', 'text': line}]
        })
    else:
        paragraphs.append({'type': 'paragraph', 'content': []})
doc = {'version': 1, 'type': 'doc', 'content': paragraphs}
print(json.dumps(doc))
" "$text"
}

# ── API Functions ────────────────────────────────────────────────────────────

jira_test_connection() {
  local response
  response=$(_jira_curl GET "/myself")
  _jira_parse "$response"
}

jira_get_issue() {
  local issue_key="$1"
  local response
  response=$(_jira_curl GET "/issue/${issue_key}?fields=summary,status,assignee")
  _jira_parse "$response"
}

jira_create_issue() {
  local project_key="$1" summary="$2" description_text="${3:-}"
  local desc_adf
  if [[ -n "$description_text" ]]; then
    desc_adf=$(text_to_adf "$description_text")
  else
    desc_adf='{"version":1,"type":"doc","content":[{"type":"paragraph","content":[]}]}'
  fi

  local payload
  payload=$(python3 -c "
import json, sys
data = {
    'fields': {
        'project': {'key': sys.argv[1]},
        'summary': sys.argv[2],
        'issuetype': {'name': 'Task'},
        'description': json.loads(sys.argv[3])
    }
}
print(json.dumps(data))
" "$project_key" "$summary" "$desc_adf")

  local response
  response=$(_jira_curl POST "/issue" "$payload")
  _jira_parse "$response"
}

jira_log_time() {
  local issue_key="$1" seconds="$2"
  local payload="{\"timeSpentSeconds\": ${seconds}}"
  local response
  response=$(_jira_curl POST "/issue/${issue_key}/worklog" "$payload")
  _jira_parse "$response"
}

jira_add_comment() {
  local issue_key="$1" text="$2"
  local adf
  adf=$(text_to_adf "$text")
  local payload="{\"body\": ${adf}}"
  local response
  response=$(_jira_curl POST "/issue/${issue_key}/comment" "$payload")
  _jira_parse "$response"
}

jira_get_cloud_id() {
  local base_url="$1"
  local response
  response=$(curl -s -w "\n%{http_code}" "${base_url}/_edge/tenant_info")
  local body http_code
  http_code=$(echo "$response" | tail -1)
  body=$(echo "$response" | sed '$d')
  if [[ "$http_code" -ge 200 && "$http_code" -lt 400 ]]; then
    echo "$body" | python3 -c "import json,sys; print(json.load(sys.stdin).get('cloudId',''))" 2>/dev/null
  else
    return 1
  fi
}
