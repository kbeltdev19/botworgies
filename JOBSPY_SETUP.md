# JobSpy Setup Guide

JobSpy is integrated into this project for multi-platform job scraping. It supports:
- LinkedIn
- Indeed
- ZipRecruiter
- Glassdoor
- Google Jobs

## Requirements

JobSpy requires **Python 3.10+** due to its use of modern Python syntax.

### Current Python Version

Check your Python version:
```bash
python3 --version
```

If you have Python 3.9 or lower, you need to upgrade.

## Option 1: Install Python 3.11 via Homebrew (Recommended)

```bash
# Run the installation script
./scripts/install_python311.sh

# Or manually:
brew install python@3.11

# Add to PATH (Apple Silicon)
export PATH="/opt/homebrew/opt/python@3.11/libexec/bin:$PATH"

# Add to PATH (Intel Macs)
export PATH="/usr/local/opt/python@3.11/libexec/bin:$PATH"
```

## Option 2: Install Python 3.11 via pyenv

```bash
# Run the installation script
./scripts/install_python311_pyenv.sh

# Or manually:
curl https://pyenv.run | bash
pyenv install 3.11.7
pyenv local 3.11.7
```

## Option 3: Use Docker (No Local Python Upgrade)

If you prefer not to upgrade Python locally, use Docker:

```bash
# Build the Docker image
docker build -t job-applier .

# Run with JobSpy
docker run -it --rm \
  -e MOONSHOT_API_KEY=your_key \
  -e BROWSERBASE_API_KEY=your_key \
  job-applier python -c "from jobspy import scrape_jobs; print('JobSpy ready!')"
```

## Verification

After installation, verify JobSpy works:

```bash
# Activate virtual environment
source venv/bin/activate

# Test import
python -c "from jobspy import scrape_jobs; print('JobSpy imported successfully!')"

# Run test scrape
python adapters/jobspy_scraper.py
```

## Usage

### Basic Usage

```python
import asyncio
from adapters.jobspy_scraper import JobSpyScraper, JobSpyConfig

async def main():
    scraper = JobSpyScraper()
    
    config = JobSpyConfig(
        site_name=["linkedin", "indeed"],
        search_term="software engineer",
        location="San Francisco",
        results_wanted=50,
        hours_old=72
    )
    
    jobs = await scraper.scrape_jobs(config)
    print(f"Found {len(jobs)} jobs")
    
    for job in jobs[:5]:
        print(f"- {job.title} @ {job.company}")

asyncio.run(main())
```

### Using with SearchBuilder

```python
from adapters.jobspy_scraper import JobSpySearchBuilder

# Get pre-configured searches
configs = JobSpySearchBuilder.for_kent_le()

# Estimate total jobs
estimated = JobSpySearchBuilder.estimate_jobs_available(configs)
print(f"Will scrape approximately {estimated} jobs")
```

## Troubleshooting

### "TypeError: unsupported operand type(s) for |"

This means you're using Python 3.9 or lower. Upgrade to Python 3.10+ using one of the options above.

### "ModuleNotFoundError: No module named 'jobspy'"

Install the dependencies:
```bash
pip install python-jobspy
# or
pip install -r requirements.txt
```

### Rate Limiting

JobSpy may hit rate limits on some sites. To mitigate:
- Use proxies (see JobSpy documentation)
- Reduce `results_wanted`
- Increase delays between requests
- Use different IP addresses

## Environment Variables

Add to your `.env` file:

```bash
# JobSpy settings
JOBSPY_LINKEDIN_COOKIE=your_li_at_cookie  # Optional, for authenticated LinkedIn
JOBSPY_PROXIES=http://proxy1.com:8080,http://proxy2.com:8080  # Optional
```

## Integration with Main System

JobSpy is integrated into the adapter system:

```python
from adapters import get_adapter

# Use JobSpy-powered scraper
adapter = get_adapter("jobspy", browser_manager)
jobs = await adapter.search_jobs(criteria)
```

## Links

- JobSpy GitHub: https://github.com/speedyapply/JobSpy
- JobSpy Documentation: See README in `src/python-jobspy/`
