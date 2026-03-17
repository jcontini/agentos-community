#!/usr/bin/env bash
set -euo pipefail

PARAM_ID="${1:-}"

curl -s "https://hn.algolia.com/api/v1/items/${PARAM_ID}" | jq '
  def flatten_tree($parent_id):
    {
      objectID: (.id | tostring),
      text: .text,
      author: .author,
      created_at: .created_at,
      parent_id: $parent_id
    },
    (.children[]? | flatten_tree((.id | tostring)));

  (.id | tostring) as $story_id |
  [
    {
      objectID: $story_id,
      title: .title,
      text: .text,
      url: .url,
      author: .author,
      points: .points,
      num_comments: (.children | length),
      created_at: .created_at
    }
  ] + [.children[]? | flatten_tree($story_id)]
'
