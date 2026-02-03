#!/usr/bin/env python3
"""
Patch JobSpy to be compatible with Python 3.9
Converts Python 3.10+ union syntax (X | Y) to 3.9 compatible Optional[X] syntax
"""

import os
import re
from pathlib import Path

def patch_file(filepath):
    """Patch a single file to replace Python 3.10+ syntax with 3.9 compatible syntax."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    original = content
    
    # Add 'from __future__ import annotations' at the top if not present
    if 'from __future__ import annotations' not in content:
        # Find the first import or the start of the file
        lines = content.split('\n')
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                insert_idx = i
                break
        lines.insert(insert_idx, 'from __future__ import annotations')
        content = '\n'.join(lines)
    
    # Replace patterns like "-> Type | None:" with "-> Optional[Type]:"
    # But be careful not to replace in strings or comments
    
    # Pattern for return type annotations
    content = re.sub(
        r'->\s*(\w+(?:\[.*?\])?)\s*\|\s*None\s*:',
        r'-> Optional[\1]:',
        content
    )
    
    # Pattern for parameter type annotations with union types
    content = re.sub(
        r'(\w+):\s*(\w+(?:\[.*?\])?)\s*\|\s*None\s*=',
        r'\1: Optional[\2] =',
        content
    )
    
    # Pattern for variable annotations
    content = re.sub(
        r'^(\s*)(\w+):\s*(\w+(?:\[.*?\])?)\s*\|\s*None\s*$',
        r'\1\2: Optional[\3]',
        content,
        flags=re.MULTILINE
    )
    
    # Add Optional import if needed
    if 'Optional' in content and 'from typing import' not in content:
        content = re.sub(
            r'^(import typing|from typing import)',
            r'from typing import Optional\n\1',
            content
        )
    elif 'Optional' in content:
        # Add Optional to existing typing imports
        content = re.sub(
            r'from typing import ([^\n]+)',
            lambda m: f'from typing import Optional, {m.group(1)}' if 'Optional' not in m.group(1) else m.group(0),
            content
        )
    
    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Patched: {filepath}")
        return True
    return False

def main():
    jobspy_dir = Path(__file__).parent.parent / "src" / "python-jobspy" / "jobspy"
    
    if not jobspy_dir.exists():
        print(f"JobSpy directory not found: {jobspy_dir}")
        return
    
    patched = 0
    for pyfile in jobspy_dir.rglob("*.py"):
        if patch_file(pyfile):
            patched += 1
    
    print(f"\nPatched {patched} files")
    print("\nNote: This is a best-effort patch. Some manual fixes may still be needed.")
    print("Recommended: Install Python 3.11+ for full compatibility.")

if __name__ == "__main__":
    main()
