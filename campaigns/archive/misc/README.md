# Campaigns Directory

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
`archive/archived_20260205_113246/`

To restore a file:
```bash
cp archive/archived_YYYYMMDD_HHMMSS/MATT_1000_OLD.py .
```

### Benefits of Unified System

- **95% less code**: Campaigns are 50-line YAML files instead of 500-line Python
- **Consistent behavior**: All campaigns use same tested logic
- **Easy configuration**: Non-developers can create campaigns
- **Centralized improvements**: Fix bugs once, all campaigns benefit
