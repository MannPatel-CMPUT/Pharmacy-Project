#!/bin/bash

# Script to push pharmacy project to GitHub
# Repository: https://github.com/MannPatel-CMPUT/Pharmacy-Project

cd "$(dirname "$0")"

echo "🚀 Setting up Git repository..."
echo ""

# Initialize git if not already
if [ ! -d ".git" ]; then
    echo "📦 Initializing git repository..."
    git init
    echo "✅ Git initialized"
else
    echo "✅ Git repository already exists"
fi

# Add remote
echo ""
echo "🔗 Adding remote repository..."
git remote remove origin 2>/dev/null
git remote add origin https://github.com/MannPatel-CMPUT/Pharmacy-Project.git
echo "✅ Remote added: https://github.com/MannPatel-CMPUT/Pharmacy-Project.git"

# Check what will be added
echo ""
echo "📋 Files that will be committed (documentation excluded):"
git add .
git status --short

echo ""
read -p "Continue with commit? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Commit
    echo ""
    echo "💾 Committing files..."
    git commit -m "Pharmacy workflow automation app - Initial commit"
    echo "✅ Files committed"
    
    # Set branch to main
    echo ""
    echo "🌿 Setting branch to main..."
    git branch -M main
    echo "✅ Branch set to main"
    
    # Push
    echo ""
    echo "📤 Pushing to GitHub..."
    git push -u origin main
    echo ""
    echo "✅ Done! Your code is now on GitHub!"
    echo ""
    echo "🔗 Repository: https://github.com/MannPatel-CMPUT/Pharmacy-Project"
else
    echo "❌ Cancelled. Files staged but not committed."
    echo "Run 'git commit' and 'git push' manually when ready."
fi
