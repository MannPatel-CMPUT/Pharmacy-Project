# Fix: "no such file or directory" Error

## Problem:
The path has a space: `PHarmacy project`
When you type: `cd /Users/mannpatel/Desktop/PHarmacy project`
The shell thinks it's two separate paths!

## Solution: Quote the Path

### Option 1: Use Quotes (Recommended)
```bash
cd "/Users/mannpatel/Desktop/PHarmacy project"
```

### Option 2: Escape the Space
```bash
cd /Users/mannpatel/Desktop/PHarmacy\ project
```

### Option 3: You're Already There!
Since you're already in the `PHarmacy project` directory (based on your prompt), you don't need to cd at all!

Just run:
```bash
git init
git remote add origin https://github.com/MannPatel-CMPUT/Pharmacy-Project.git
git add .
git commit -m "Pharmacy workflow automation app - Initial commit"
git branch -M main
git push -u origin main
```

## Quick Fix for Your Current Situation:

You're already in the right directory! Just run:

```bash
# You're already here, so skip the cd command
git init
git remote add origin https://github.com/MannPatel-CMPUT/Pharmacy-Project.git
git add .
git status  # Verify files
git commit -m "Pharmacy workflow automation app - Initial commit"
git branch -M main
git push -u origin main
```

## General Rule:
**Always quote paths with spaces!**

✅ Good: `cd "/Users/mannpatel/Desktop/PHarmacy project"`
❌ Bad: `cd /Users/mannpatel/Desktop/PHarmacy project`
