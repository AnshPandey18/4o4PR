# Schema Shape Decision: Class Fields Always Present

**Date:** 2026-10-24  
**Issue:** Class-only fields optimization reverted  
**Decision:** Always emit children, bases, bases_unresolved, attr_types

---

## Problem Identified

The "class-only fields" optimization (only emitting `children`, `bases`, `bases_unresolved`, `attr_types` for classes) was a **breaking shape change**.

### Original Behavior (Schema 1.2):
```json
{
  "kind": "function",
  "name": "hello",
  ...
  "children": [],
  "bases": [],
  "bases_unresolved": [],
  "attr_types": {}
}
```

### With Optimization (would be Schema 1.3):
```json
{
  "kind": "function",
  "name": "hello",
  ...
  // children, bases, bases_unresolved, attr_types NOT PRESENT
}
```

### The Breaking Change

Any code doing `symbol["children"]` would crash on non-class symbols:
```python
# This breaks with optimized version:
for child_id in symbol["children"]:  # KeyError on methods!
    ...
```

---

## Reader Audit Results

### ✅ Current Consumers (None access these fields)
- **Retrieval** (`retrieval/graph.py`): No access to children/bases/attr_types
- **Grouper** (`grouper/group.py`): No access to children/bases/attr_types
- **Context Builder** (`context/builder.py`): No access to children/bases/attr_types
- **Tests**: Only access on classes (safe)

### ⚠️ Future Risk

While no current consumers break, **future code might assume these fields exist**:
- Schema consumers expect consistent shape
- `symbol.get("children", [])` is defensive, but `symbol["children"]` is not
- Schema 1.2 was defined with these fields always present

---

## Decision: Keep Schema 1.2 Shape

**Reverted to always emitting these fields** (empty for non-classes).

### Rationale

1. **Backward Compatibility**: Schema 1.2 already shipped with this shape
2. **Safety**: Readers can safely access `symbol["children"]` on any symbol
3. **Simplicity**: No need for defensive `.get()` calls
4. **Cost**: Minimal (4 empty arrays/objects × 60 non-classes = ~240 bytes)

### Implementation

```python
# indexer/models.py to_dict()
'symbols': {
    sid: {
        ...
        # Schema 1.2 class fields - always emit for shape consistency
        # Empty for non-classes, populated for classes
        'children': sym.children,  # [] for non-classes
        'bases': sym.bases,        # [] for non-classes
        'bases_unresolved': sym.bases_unresolved,  # [] for non-classes
        'attr_types': sym.attr_types  # {} for non-classes
    }
}
```

---

## Alternative: Schema 1.3 with Conditional Fields

If we wanted the optimization, we would need:

### 1. Bump to Schema 1.3
```python
SCHEMA_VERSION = "1.3"  # Shape change
```

### 2. Update All Readers
```python
# Before (assumes fields exist):
children = symbol["children"]

# After (defensive):
children = symbol.get("children", [])
```

### 3. Document Shape Difference
```markdown
Schema 1.2: All symbols have children/bases/attr_types (empty for non-classes)
Schema 1.3: Only classes have children/bases/attr_types
```

### Why Not Chosen

- **No benefit yet**: No consumers access these fields
- **Risk > Reward**: Breaking change for minimal size savings
- **Future work**: Can reconsider in Schema 2.0 with reader updates

---

## Verification

### Shape Consistency Check
```powershell
$index = Get-Content runs/verify/index/index.json | ConvertFrom-Json

# All symbols (67 total)
$all = $index.symbols.PSObject.Properties
$all | ForEach-Object {
    assert $null -ne $_.Value.children
    assert $null -ne $_.Value.bases
    assert $null -ne $_.Value.attr_types
}
# ✅ All pass
```

### Test Results
```
pytest tests/unit/test_indexer_features.py
24 passed in 3.43s ✅
```

---

## For Future Schema Versions

### When to Change Shape

Only change schema shape when:
1. **Benefits justify the migration cost**
2. **All readers are audited and updated**
3. **Schema version is bumped**
4. **Migration guide is provided**

### How to Add Optional Fields

For truly optional fields that aren't universal:
```python
# Good: Optional field that varies by kind
if sym.kind == 'constant':
    data['value_preview'] = sym.value_preview  # Only for constants
```

### How to Remove Fields

1. Bump schema version
2. Update all readers to not use the field
3. Remove from serialization
4. Document in CHANGELOG

---

## Conclusion

**Schema 1.2 shape is preserved.** All symbols have `children`, `bases`, `bases_unresolved`, and `attr_types` fields (empty for non-classes).

This maintains backward compatibility and allows future readers to safely access these fields without defensive code.

**Status:** ✅ Resolved - Shape is consistent
