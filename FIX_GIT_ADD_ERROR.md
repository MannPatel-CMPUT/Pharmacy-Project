# Fix: "git add ." Failed - Operation Not Permitted

## Error:
```
fatal: Unable to create '/Users/mannpatel/Desktop/PHarmacy project/.git/index.lock': Operation not permitted
```

## Solution:

This happens when there's a lock file from a previous interrupted git operation.

### Quick Fix:

Run this command to remove the lock file:

```bash
rm -f .git/index.lock
```

Then try again:
```bash
git add .
```

### Alternative: Add Files Selectively

If the lock file issue persists, add files manually:

```bash
# Add essential files one by one
git add .gitignore
git add README.md
git add requirements.txt
git add Procfile
git add render.yaml
git add runtime.txt
git add fastapi/
git add frontend/
```

### If Still Having Issues:

1. **Check permissions:**
   ```bash
   ls -la .git
   ```

2. **Remove and reinitialize (if needed):**
   ```bash
   rm -rf .git
   git init
   git remote add origin https://github.com/MannPatel-CMPUT/Pharmacy-Project.git
   git add .
   ```

3. **Or use sudo (if permission issue):**
   ```bash
   sudo rm -f .git/index.lock
   git add .
   ```

## After Fixing:

Once `git add .` works, continue with:

```bash
git status  # Verify files
git commit -m "Pharmacy workflow automation app - Initial commit"
git branch -M main
git push -u origin main
```
