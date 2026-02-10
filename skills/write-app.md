# Write App

> How to write AgentOS apps and components using the primitive system

AgentOS has a CSS primitive system for consistent, themeable UI. **Always use these instead of custom styles.**

## Quick Reference

| Element | Attribute | Variants |
|---------|-----------|----------|
| Button | `data-component="button"` | `data-variant="primary\|secondary\|ghost"` `data-size="sm\|md\|lg"` |
| Input | `data-component="input"` | `data-variant="textarea"` |
| Select | `data-component="select"` | `data-size="sm\|md\|lg"` |
| Checkbox | `data-component="checkbox"` | `data-checked="true\|false"` `data-size="sm\|md\|lg"` |
| Toggle | `data-component="toggle"` | (for checkbox inputs in settings) |

## Usage Examples

### Buttons

```tsx
// Primary action (submit, save, confirm)
<button data-component="button" data-variant="primary">Save</button>

// Secondary action (cancel, back)
<button data-component="button" data-variant="secondary">Cancel</button>

// Ghost/minimal (remove, clear, subtle actions)
<button data-component="button" data-variant="ghost" data-size="sm">×</button>

// Disabled state
<button data-component="button" data-variant="primary" disabled>Saving...</button>
```

### Inputs

```tsx
// Text input
<input type="text" data-component="input" placeholder="Enter value..." />

// Textarea (multi-line)
<textarea data-component="input" data-variant="textarea" rows={4} />

// Number input
<input type="number" data-component="input" />

// Password
<input type="password" data-component="input" />
```

### Selects

```tsx
// Dropdown select
<select data-component="select" value={selected} onChange={...}>
  <option value="a">Option A</option>
  <option value="b">Option B</option>
</select>

// Small size
<select data-component="select" data-size="sm">...</select>
```

### Checkboxes & Toggles

```tsx
// Inline checkbox (in tables, lists)
<input type="checkbox" data-component="toggle" checked={value} onChange={...} />

// Styled checkbox div (for custom checkboxes)
<div data-component="checkbox" data-checked={selected} onClick={...}>
  {selected && '✓'}
</div>
```

## States

All primitives support these state attributes:

```tsx
// Disabled
<button data-component="button" disabled>...</button>
<input data-component="input" disabled />

// Loading (buttons only - combine with disabled)
<button data-component="button" data-state="loading" disabled>Loading...</button>
```

## Why Use Primitives?

1. **Theming** - Themes style primitives via `[data-component="button"]` selectors
2. **Consistency** - Same look across all components
3. **Accessibility** - Proper focus states, disabled states built in
4. **Less CSS** - No need to write custom styles

## Don't Do This

```tsx
// ❌ Wrong - custom className that won't be themed
<button className="my-custom-button">Save</button>
<input className="my-input-field" />

// ✅ Right - use primitives
<button data-component="button" data-variant="primary">Save</button>
<input data-component="input" />
```

## Wrapper Components

For YAML layouts, use these wrapper components that internally use primitives:

- `toggle` - Checkbox with label and optional description
- `text-input` - Input with loading state, clear button, submit handling

```yaml
# In app.yaml
- component: toggle
  props:
    label: Enable feature
    checked: "{{settings.feature_enabled}}"

- component: text-input
  props:
    placeholder: Search...
    value: "{{query}}"
  on_submit: search
```

## Adding New Primitives

Primitives are defined in `web/src/styles/base.css`. To add a new one:

1. Add CSS with `[data-component="name"]` selector
2. Support variants via `[data-variant="x"]`
3. Support states via `[data-state="x"]` or standard attributes
4. Document in this skill file
