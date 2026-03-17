#!/usr/bin/env bash
set -euo pipefail

PARAM_ID="${1:-}"
PARAM_COMMENT_LIMIT="${2:-}"

curl -s -A "AgentOS/1.0" "https://www.reddit.com/comments/${PARAM_ID}.json?limit=${PARAM_COMMENT_LIMIT}" | jq '
  def flatten_tree:
    (. + { parent_id: (.parent_id | split("_") | .[1:] | join("_")) }),
    (
      if .replies == "" then empty
      else (.replies.data.children[] | select(.kind == "t1") | .data | flatten_tree)
      end
    );

  .[0].data.children[0].data as $post |
  [$post] + [.[1].data.children[] | select(.kind == "t1") | .data | flatten_tree]
'
