#!/usr/bin/env python3
"""
Archive old campaign Python files

Moves duplicate campaign files to an archive directory,
keeping only the unified campaign runner and YAML configs.
"""

import os
import sys
import shutil
from datetime import datetime
from pathlib import Path

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
CAMPAIGNS_DIR = PROJECT_ROOT / "campaigns"
ARCHIVE_DIR = CAMPAIGNS_DIR / "archive" / f"archived_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

# Files to KEEP (unified system)
KEEP_FILES = {
    # Core unified files
    "run_campaign.py",
    "__init__.py",
    
    # YAML configs
    "configs",
}

# Specific campaign patterns to archive
ARCHIVE_PATTERNS = [
    "MATT_*.py",
    "KEVIN_*.py",
    "KENT_*.py",
    "matt_*.py",
    "kevin_*.py",
    "kent_*.py",
    "test_*.py",
    "*_test.py",
    "*_OLD.py",
    "*_old.py",
    "*_BACKUP.py",
    "*_backup.py",
    "*_.py",  # Files with underscore prefix
]


def should_archive(filename: str) -> bool:
    """Check if a file should be archived."""
    # Keep unified files
    if filename in KEEP_FILES:
        return False
    
    # Keep directories we want to keep
    if filename in ["configs", "output", "utils"]:
        return False
    
    # Archive Python files matching patterns
    if filename.endswith('.py'):
        import fnmatch
        for pattern in ARCHIVE_PATTERNS:
            if fnmatch.fnmatch(filename, pattern):
                return True
        # Archive all other Python files
        return True
    
    return False


def archive_campaigns(dry_run: bool = True):
    """Archive old campaign files."""
    print("=" * 70)
    print("CAMPAIGN ARCHIVE TOOL")
    print("=" * 70)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"Source: {CAMPAIGNS_DIR}")
    print(f"Archive: {ARCHIVE_DIR}")
    print()
    
    # Find files to archive
    files_to_archive = []
    
    for item in CAMPAIGNS_DIR.iterdir():
        if item.is_file() and should_archive(item.name):
            files_to_archive.append(item)
    
    if not files_to_archive:
        print("No files to archive.")
        return
    
    print(f"Found {len(files_to_archive)} files to archive:")
    for f in sorted(files_to_archive):
        size_kb = f.stat().st_size / 1024
        print(f"  - {f.name} ({size_kb:.1f} KB)")
    
    total_size = sum(f.stat().st_size for f in files_to_archive) / 1024 / 1024
    print(f"\nTotal size: {total_size:.2f} MB")
    
    if dry_run:
        print("\n🔍 DRY RUN - No files were moved.")
        print("Run with --live to actually archive files.")
        return
    
    # Confirm
    response = input(f"\n⚠️  Archive {len(files_to_archive)} files? Type 'ARCHIVE' to confirm: ")
    if response.strip() != "ARCHIVE":
        print("Aborted.")
        return
    
    # Create archive directory
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create manifest
    manifest = []
    manifest.append(f"Archive created: {datetime.now().isoformat()}")
    manifest.append(f"Archived files: {len(files_to_archive)}")
    manifest.append("")
    manifest.append("Files archived:")
    
    # Move files
    archived_count = 0
    for file_path in files_to_archive:
        try:
            dest = ARCHIVE_DIR / file_path.name
            shutil.move(str(file_path), str(dest))
            manifest.append(f"  - {file_path.name}")
            archived_count += 1
            print(f"  ✅ Archived: {file_path.name}")
        except Exception as e:
            print(f"  ❌ Failed: {file_path.name} - {e}")
    
    # Write manifest
    manifest_path = ARCHIVE_DIR / "MANIFEST.txt"
    manifest_path.write_text("\n".join(manifest))
    
    # Create README in campaigns dir
    readme_path = CAMPAIGNS_DIR / "README.md"
    readme_content = f"""# Campaigns Directory

## Unified Campaign System

This directory now uses the **unified campaign system**.

### Quick Start

1. **Create a campaign config** (YAML):
   ```bash
   cp configs/example_software_engineer.yaml configs/my_campaign.yaml
   # Edit my_campaign.yaml with your details
   ```

2. **Run the campaign**:
   ```bash
   python run_campaign.py --config configs/my_campaign.yaml
   ```

3. **Production mode** (auto-submit):
   ```bash
   python run_campaign.py --config configs/my_campaign.yaml --auto-submit
   ```

### Directory Structure

```
campaigns/
├── run_campaign.py          # Unified campaign runner
├── configs/                 # Campaign configurations (YAML)
│   ├── example_software_engineer.yaml
│   ├── matt_edwards_production.yaml
│   ├── kevin_beltran_production.yaml
│   └── kent_le_production.yaml
├── output/                  # Campaign results
└── archive/                 # Archived old campaigns
    └── archived_YYYYMMDD_HHMMSS/
```

### Migration

Old Python campaign files have been archived to:
`archive/archived_{datetime.now().strftime('%Y%m%d_%H%M%S')}/`

To restore a file:
```bash
cp archive/archived_YYYYMMDD_HHMMSS/MATT_1000_OLD.py .
```

### Benefits of Unified System

- **95% less code**: Campaigns are 50-line YAML files instead of 500-line Python
- **Consistent behavior**: All campaigns use same tested logic
- **Easy configuration**: Non-developers can create campaigns
- **Centralized improvements**: Fix bugs once, all campaigns benefit
"""
    readme_path.write_text(readme_content)
    
    print("\n" + "=" * 70)
    print(f"✅ Archived {archived_count}/{len(files_to_archive)} files")
    print(f"Archive location: {ARCHIVE_DIR}")
    print(f"Manifest: {manifest_path}")
    print("=" * 70)


def main():
    """Main entry point."""
    dry_run = "--live" not in sys.argv
    
    archive_campaigns(dry_run=dry_run)
    
    if dry_run:
        print("\nTo actually archive files, run:")
        print("  python scripts/archive_campaigns.py --live")


if __name__ == "__main__":
    main()
