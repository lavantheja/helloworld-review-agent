# Utils

A collection of general-purpose utility functions.

---

## Functions

### `calculate_average(numbers)`

Calculates the arithmetic mean of a list of numbers.

**Signature:**
```python
calculate_average(numbers: list[int | float]) -> float
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `numbers` | `list[int \| float]` | A list of numeric values to average. |

**Returns:** `float` — The arithmetic mean of the provided numbers, or `0` if the list is empty.

**Examples:**
```python
calculate_average([1, 2, 3, 4, 5])  # → 3.0
calculate_average([10.5, 20.5])      # → 15.5
calculate_average([])                # → 0
```

---

### `get_user_name(user)`

Retrieves a user's name from a user dictionary and returns it in uppercase.

**Signature:**
```python
get_user_name(user: dict) -> str
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `user` | `dict` | A dictionary expected to contain a `"name"` key with the user's name. |

**Returns:** `str` — The user's name converted to uppercase. Returns an empty string `""` if:
- The `"name"` key is missing or has a falsy value.
- The input is not a dictionary.

**Examples:**
```python
get_user_name({"name": "alice"})   # → "ALICE"
get_user_name({"name": "Bob"})     # → "BOB"
get_user_name({"name": ""})        # → ""
get_user_name({})                  # → ""
get_user_name("not a dict")        # → ""
```
