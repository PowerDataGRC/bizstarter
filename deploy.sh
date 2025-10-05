#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "🔎 Verifying Vercel CLI installation..."
if ! command -v vercel &> /dev/null
then
    echo "❌ Vercel CLI could not be found."
    echo "Please install it globally by running: npm install -g vercel"
    exit 1
fi

echo "🚀 Starting production deployment to Vercel..."

# Deploy to production, Vercel will use vercel.json for build instructions.
vercel --prod