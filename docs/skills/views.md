# Views & Output

The `run` tool accepts:

```yaml
view:
  detail: preview | full
  format: markdown | json
```

Rules:

- `detail` changes data volume
- `format` changes representation
- Default is markdown preview
- Preview keeps canonical fields and truncates long `text`
- Full returns all mapped fields
- JSON returns a `{ data, meta }` envelope

This is why canonical mapping fields matter — the renderer uses them to produce consistent previews across all skills. See [Adapters](adapters.md) for the canonical field table.
