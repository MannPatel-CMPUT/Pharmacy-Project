# 🧪 Complete Testing Guide - Multi-User Pharmacy System

## 📍 Where Your Data Is Stored

### 1. **User Accounts** 
**Location:** `/app/fastapi/data/portal_users.json`
- Stores all registered users (traditional signup + Google OAuth)
- Contains: username, email, hashed password, user ID
- Auto-created when someone signs up or uses Google OAuth

### 2. **Patient/Prescription Data**
**Location:** `/app/pharmacy.db` (SQLite database)
- **Size:** 55 MB
- **Tables:**
  - `intakes` - All prescriptions/patient data
  - `status_history` - Tracks who changed what and when
  - `drugs` - Drug database
  - `drug_interactions` - Drug interaction data
  - Other supporting tables

### 3. **Current Status**
- ✅ Database: Active (55 MB)
- ⚠️ Users file: Will be created when first user signs up
- ✅ Google OAuth: Working
- ✅ Prescriptions: 0 (clean database, ready for testing)

---

## 🎯 Complete Testing Scenarios

### **Scenario 1: Sign Up with Google OAuth**

#### Test New Google User:
1. **Visit:** https://pharmacy-project-1-7naf.onrender.com/login
2. **Click:** "Continue with Google"
3. **Select:** Your Google account
4. **Result:** 
   - ✅ Account automatically created
   - ✅ Username generated from email (e.g., mannpatel0234 from mannpatel0234@gmail.com)
   - ✅ Redirected to workspace
   - ✅ You're logged in

#### Verify User Creation:
```bash
# Check users file was created
cat /app/fastapi/data/portal_users.json
```

---

### **Scenario 2: Create Multiple User Accounts**

#### Create Traditional Users:
1. **Logout** (click your avatar → Logout)
2. **Click:** "Sign up for free"
3. **Create User 1:**
   - Username: `john`
   - Email: `john@pharmacy.com`
   - Password: `test123`
   - Phone: `555-1234`

4. **Logout and create User 2:**
   - Username: `sarah`
   - Email: `sarah@pharmacy.com`
   - Password: `test123`
   - Phone: `555-5678`

Now you have 3 users:
- Your Google account (e.g., mannpatel0234)
- john
- sarah

---

### **Scenario 3: Create and Assign Prescription**

#### As User 1 (e.g., your Google account):

1. **Click:** "+ New Patient" or "Add Prescription"

2. **Fill Patient Info:**
   - Patient Name: `Robert Johnson`
   - Age: `65`
   - Gender: `Male`
   - Phone: `555-9999`
   - Allergies: `Penicillin`

3. **Add Medications:**
   - New Medications: `warfarin, aspirin`
   - Current Medications: `metformin, lisinopril`

4. **Add Notes:**
   - Notes: `Patient reports dizziness, check blood pressure`

5. **Submit**

6. **Observe:**
   - ✅ Drug interactions detected (warfarin + aspirin = high risk)
   - ✅ Counseling points generated automatically
   - ✅ Prescription shows "Created by: [your-username]"
   - ✅ Status: "New"

---

### **Scenario 4: Test Assignment & Permissions**

#### Assign Prescription:

1. **In the prescription card, click:** "Assign" button

2. **Observe:**
   - ✅ Dropdown appears showing all users:
     - mannpatel0234 (mannpatel0234@gmail.com)
     - john (john@pharmacy.com)
     - sarah (sarah@pharmacy.com)

3. **Select:** `john`

4. **Confirm**

5. **Try to advance stage:**
   - Click "Move to triage" button
   - **Observe:** 🔒 Message appears: "Assigned to john — only they can advance this prescription"
   - ✅ **Permission system working!**

6. **Verify you CAN:**
   - ✅ View prescription details
   - ✅ Search and find the prescription
   - ✅ Reassign to someone else
   - ✅ Re-check drug interactions

---

### **Scenario 5: Test Assigned User Can Advance**

#### Login as John:

1. **Logout** from your Google account

2. **Login:**
   - Username: `john`
   - Password: `test123`

3. **Find the prescription:**
   - Search for "Robert Johnson" OR
   - Look in the prescription list

4. **Advance through workflow:**
   - Click **"Move to triage"**
   - ✅ Observe: Instant loading indicator
   - ✅ Status changes to "Triage"
   
   - Click **"Move to ready_to_fill"**
   - ✅ Status changes to "Ready to Fill"
   
   - Click **"Move to filled"**
   - ✅ Status changes to "Filled"
   
   - Click **"Dispense"** button
   - ✅ Prescription marked as dispensed
   - ✅ Timestamp recorded

5. **Check status history:**
   - Each change tracked with:
     - Who made the change (john)
     - When it was changed
     - From what status to what status

---

### **Scenario 6: Test Search Across All Prescriptions**

#### As Any User:

1. **Login as sarah** (not creator, not assigned)

2. **Search for "Robert Johnson"**

3. **Observe:**
   - ✅ Can find the prescription
   - ✅ Can view all details
   - ✅ Can see counseling points
   - ✅ Can see drug interactions
   - ❌ **Cannot** advance stages (lock message appears)
   - ✅ **Can** reassign

**Result:** All pharmacists have full visibility, but only assigned pharmacist controls workflow.

---

### **Scenario 7: Test Reassignment**

#### As Sarah:

1. **Find Robert Johnson's prescription**

2. **Click:** "Reassign" button

3. **Select:** `sarah` (yourself)

4. **Confirm**

5. **Now try to advance:**
   - ✅ You CAN now advance stages!
   - ✅ John can NO LONGER advance (lock message for him)

**Result:** Assignment controls workflow permission.

---

### **Scenario 8: Test Unassigned Prescription**

#### As Any User:

1. **Create a new prescription** without assigning

2. **Observe:**
   - "Assigned to: Unassigned"

3. **Login as different user**

4. **Try to advance:**
   - ✅ **Any user can advance unassigned prescriptions**

5. **First to assign gets control:**
   - Click "Assign" → Select yourself
   - Now only you can advance

---

### **Scenario 9: Test Multiple Prescriptions**

#### Create Complex Workflow:

1. **Create 5 prescriptions as different users:**
   - 2 assigned to john
   - 2 assigned to sarah
   - 1 unassigned

2. **Login as john:**
   - Can advance only the 2 assigned to him
   - Can view all 5
   - Sees lock icon on others

3. **Login as sarah:**
   - Can advance only the 2 assigned to her + the unassigned one
   - Can view all 5
   - Sees lock icon on john's prescriptions

**Result:** Proper multi-user segregation working!

---

### **Scenario 10: Test Google OAuth + Traditional Auth Together**

1. **Login with Google** → Create prescription
2. **Logout**
3. **Login with traditional account (john)** → Access the prescription
4. **Assign to Google user**
5. **Login with Google again** → Can advance

**Result:** Both auth methods work seamlessly together!

---

## 📊 How to View Your Data

### Check User Accounts:
```bash
cat /app/fastapi/data/portal_users.json | python3 -m json.tool
```

### Check Prescriptions:
```bash
sqlite3 /app/pharmacy.db "SELECT id, patient_name, status, created_by, assigned_to FROM intakes;"
```

### Check Status History:
```bash
sqlite3 /app/pharmacy.db "SELECT * FROM status_history ORDER BY changed_at DESC LIMIT 10;"
```

### Check All Users via API:
```bash
# Must be authenticated
curl https://pharmacy-project-1-7naf.onrender.com/api/auth/users \
  -H "Cookie: [your-session-cookie]"
```

---

## ✅ What to Verify

### Multi-User Features:
- [ ] Google OAuth creates account automatically
- [ ] Traditional signup works
- [ ] Multiple users can be logged in simultaneously
- [ ] Assignment dropdown shows all users
- [ ] Assigned pharmacist can advance stages
- [ ] Other pharmacists see lock message
- [ ] All pharmacists can search and view
- [ ] Reassignment works correctly
- [ ] Unassigned prescriptions accessible to all

### UI/UX Features:
- [ ] Loading indicators appear instantly
- [ ] Success/error toasts display correctly
- [ ] Lock icon shows when user lacks permission
- [ ] "Continue with Google" button visible
- [ ] Assignment modal shows user emails

### Data Persistence:
- [ ] Prescriptions persist across sessions
- [ ] User accounts persist
- [ ] Status history tracked correctly
- [ ] `created_by` field populated
- [ ] `assigned_to` field updates correctly

---

## 🎯 Key Metrics to Check

After testing:

1. **Total Users Created:**
   ```bash
   cat /app/fastapi/data/portal_users.json | grep -c '"username"'
   ```

2. **Total Prescriptions:**
   ```bash
   sqlite3 /app/pharmacy.db "SELECT COUNT(*) FROM intakes;"
   ```

3. **Status History Entries:**
   ```bash
   sqlite3 /app/pharmacy.db "SELECT COUNT(*) FROM status_history;"
   ```

4. **Database Size:**
   ```bash
   du -h /app/pharmacy.db
   ```

---

## 🔒 Security to Verify

- [ ] JWT tokens stored in httpOnly cookies (can't access via JavaScript)
- [ ] Passwords hashed (not stored in plain text)
- [ ] Google OAuth users have no password (secure)
- [ ] Session expires after 7 days
- [ ] CORS only allows configured origins
- [ ] All API endpoints require authentication

---

## 🚀 Production Checklist

Before going live:
- [ ] Test with real pharmacist accounts
- [ ] Verify drug interaction database is complete
- [ ] Test prescription workflow end-to-end
- [ ] Verify backup strategy for database
- [ ] Check logs for errors
- [ ] Test on mobile devices
- [ ] Verify Google OAuth works from production URL

---

## 📝 Test Data Example

After testing, you should have data like:

**Users (portal_users.json):**
```json
{
  "users": [
    {
      "id": 1,
      "username": "mannpatel0234",
      "email": "mannpatel0234@gmail.com",
      "phone": ""
    },
    {
      "id": 2,
      "username": "john",
      "email": "john@pharmacy.com",
      "phone": "555-1234"
    },
    {
      "id": 3,
      "username": "sarah",
      "email": "sarah@pharmacy.com",
      "phone": "555-5678"
    }
  ]
}
```

**Prescriptions (pharmacy.db):**
```
ID | Patient Name    | Status | Created By     | Assigned To
1  | Robert Johnson  | filled | mannpatel0234  | john
2  | Mary Smith      | triage | john           | sarah
3  | James Brown     | new    | sarah          | NULL
```

---

**Happy Testing! Your multi-user pharmacy system is fully operational!** 🎉

Questions? Need help with specific scenarios? Just ask!
