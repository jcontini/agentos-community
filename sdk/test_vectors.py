#!/usr/bin/env python3
"""Validate spec.yaml test vectors against the Python molt implementation."""

import sys
import yaml
from pathlib import Path

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent))

from agentos import molt


def main():
    spec = yaml.safe_load(Path(__file__).with_name("spec.yaml").read_text())
    vectors = spec["functions"]["molt"]["vectors"]

    passed = 0
    failed = 0
    errors = []

    for i, vec in enumerate(vectors):
        input_val, as_type, expected = vec

        # Map as_type strings to Python types where needed
        py_type = None
        if as_type == "int":
            py_type = int
        elif as_type == "float":
            py_type = float
        elif as_type in ("date", "datetime"):
            py_type = "date"
        elif as_type == "string":
            py_type = str
        elif as_type is None:
            py_type = None

        try:
            actual = molt(input_val, py_type)
        except Exception as e:
            errors.append(f"  #{i+1}: EXCEPTION {vec!r} → {e}")
            failed += 1
            continue

        if actual == expected:
            passed += 1
        else:
            errors.append(f"  #{i+1}: FAIL {vec!r}")
            errors.append(f"         expected: {expected!r}")
            errors.append(f"         actual:   {actual!r}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed out of {len(vectors)} vectors\n")
    if errors:
        print("Failures:")
        for e in errors:
            print(e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
