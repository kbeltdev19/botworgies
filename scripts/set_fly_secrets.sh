#!/bin/bash
# Set required secrets on Fly.io for job-applier-api

set -e

# Load local secrets
source ~/.clawdbot/secrets/tokens.env

echo "Setting Fly.io secrets for job-applier-api..."

# BrowserBase credentials (required for browser automation)
fly secrets set \
  BROWSERBASE_API_KEY="$BROWSERBASE_API_KEY" \
  BROWSERBASE_PROJECT_ID="$BROWSERBASE_PROJECT_ID" \
  -a job-applier-api

# Moonshot/Kimi AI for resume processing
fly secrets set \
  MOONSHOT_API_KEY="$MOONSHOT_API_KEY" \
  -a job-applier-api

# JWT secret for auth (generate new one if needed)
JWT_SECRET=$(openssl rand -hex 32)
fly secrets set JWT_SECRET="$JWT_SECRET" -a job-applier-api

echo "Done! Secrets set:"
fly secrets list -a job-applier-api
