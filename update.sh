#!/bin/bash
cd "$(dirname "$0")"
echo "⏳ Pulling latest code..."
git pull
echo "🏺 Starting Glaze Designer..."
python3 app.py
