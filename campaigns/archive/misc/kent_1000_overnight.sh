#!/bin/bash
# KENT LE - 1000 JOB OVERNIGHT CAMPAIGN
# Runs with nohup for overnight execution

set -e

# Load environment
export $(cat /Users/tech4/Downloads/botworkieslocsl/botworgies/.env | xargs)

# Set CapSolver API key
export CAPSOLVER_API_KEY="CAP-REDACTED"

# Change to project directory
cd /Users/tech4/Downloads/botworkieslocsl/botworgies

# Create log directory
mkdir -p campaigns/logs

# Timestamp for logs
TIMESTAMP=$(date +%Y%m%d_%H%M)
LOGFILE="campaigns/logs/kent_1000_overnight_${TIMESTAMP}.log"

echo "========================================" | tee -a "$LOGFILE"
echo "🌙 KENT LE - 1000 JOB OVERNIGHT CAMPAIGN" | tee -a "$LOGFILE"
echo "========================================" | tee -a "$LOGFILE"
echo "Started: $(date)" | tee -a "$LOGFILE"
echo "Log file: $LOGFILE" | tee -a "$LOGFILE"
echo "" | tee -a "$LOGFILE"

# Run campaign with auto-confirmation
echo "CAPSOLVER1000" | python3 campaigns/kent_1000_capsolver.py 2>&1 | tee -a "$LOGFILE"

echo "" | tee -a "$LOGFILE"
echo "========================================" | tee -a "$LOGFILE"
echo "Campaign completed: $(date)" | tee -a "$LOGFILE"
echo "========================================" | tee -a "$LOGFILE"
