# Push to GitHub - Step by Step

## Your Repository:
**https://github.com/MannPatel-CMPUT/Pharmacy-Project**

## Quick Method (Automated):

```bash
cd "/Users/mannpatel/Desktop/PHarmacy project"
./push_to_github.sh
```

This script will:
1. Initialize git (if needed)
2. Add remote repository
3. Stage files (respecting .gitignore)
4. Commit
5. Push to GitHub

## Manual Method (Step by Step):

### Step 1: Navigate to project
```bash
cd "/Users/mannpatel/Desktop/PHarmacy project"
```

### Step 2: Initialize git (if not already)
```bash
git init
```

### Step 3: Add remote repository
```bash
git remote add origin https://github.com/MannPatel-CMPUT/Pharmacy-Project.git
```

### Step 4: Add files (only essential files, docs excluded)
```bash
git add .
```

### Step 5: Verify what will be committed
```bash
git status
```

You should see:
- ✅ fastapi/
- ✅ frontend/
- ✅ requirements.txt
- ✅ Procfile
- ✅ render.yaml
- ✅ runtime.txt
- ✅ README.md
- ✅ .gitignore
- ❌ No documentation files (excluded)

### Step 6: Commit
```bash
git commit -m "Pharmacy workflow automation app - Initial commit"
```

### Step 7: Set branch to main
```bash
git branch -M main
```

### Step 8: Push to GitHub
```bash
git push -u origin main
```

## Verify on GitHub:

After pushing, visit:
**https://github.com/MannPatel-CMPUT/Pharmacy-Project**

You should see all your code files there!

## Troubleshooting:

**"Repository not found" or "Permission denied":**
- Make sure you're logged into GitHub
- Check repository name: `MannPatel-CMPUT/Pharmacy-Project`
- Verify you have write access

**"Remote origin already exists":**
```bash
git remote remove origin
git remote add origin https://github.com/MannPatel-CMPUT/Pharmacy-Project.git
```

**"Nothing to commit":**
- Check if files are already committed
- Run `git status` to see current state
