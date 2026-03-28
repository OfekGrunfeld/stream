---
title: Built-in Gyges
description: Reference for all built-in gyge functions available without declaration.
---

# Built-in gyges

Built-in gyges are resolved automatically by name — no declaration or import needed.  They are wired as `FUNCTION`-shape nodes on first activation.

---

## Output

### `|print|` / `|log|` / `|output|`

Prints the incoming value to stdout and passes it through unchanged.

```stream
|message| := "Hello, Stream!"
|message| -> |print|
```

All three names (`print`, `log`, `output`) are aliases for the same function.

---

## Type coercion

### `|str|`

Converts any value to its string representation.

```stream
|n| := 42
|n| -> |str| -> |print|    <-- prints "42"
```

---

### `|int|`

Converts a value to integer.  Returns `0` on failure.

```stream
|raw| := "7"
|raw| -> |int| -> |print|    <-- prints 7
```

---

### `|float|`

Converts a value to float.  Returns `0.0` on failure.

```stream
|raw| := "3.14"
|raw| -> |float| -> |print|
```

---

### `|bytes|`

Converts a value to `bytes`.  Strings are UTF-8 encoded; raw `bytes` values are passed through unchanged.

```stream
|s| := "hello"
|s| -> |bytes| -> |print|    <-- prints b'hello'
```

---

## String transforms

### `|upper|`

Converts the string representation of the incoming value to upper-case.

```stream
|sentence| := "stream language is reactive"
|sentence| -> |upper| -> |print|
<-- prints: STREAM LANGUAGE IS REACTIVE
```

---

### `|lower|`

Converts the string representation to lower-case.

```stream
|shouted| := "QUIET"
|shouted| -> |lower| -> |print|    <-- prints: quiet
```

---

## Measurement

### `|len|`

Returns the length of the incoming value (via Python `len()`).  Returns `0` for non-sized types.

```stream
|items| := "hello"
|items| -> |len| -> |print|    <-- prints 5
```

---

## Summary

| Name | Aliases | Input → Output | Notes |
|------|---------|----------------|-------|
| `print` | `log`, `output` | `any → any` | Side-effect: stdout; passes value through |
| `str` | — | `any → str` | `str(val)` |
| `int` | — | `any → int` | Returns `0` on failure |
| `float` | — | `any → float` | Returns `0.0` on failure |
| `bytes` | — | `any → bytes` | UTF-8 encode for strings |
| `upper` | — | `any → str` | `str(val).upper()` |
| `lower` | — | `any → str` | `str(val).lower()` |
| `len` | — | `any → int` | Returns `0` for unsized types |

---

## Shape resolution

Built-in names are checked in `GyrResolver.get_builtin()` when a node is first activated in Phase 4.  If the name matches, the node's shape is upgraded from `VOID` to `FUNCTION` and the callable is bound as `fn_body`.

User-declared gyges with the same name as a built-in will be overridden by the built-in — avoid naming your gyges `print`, `str`, etc.
