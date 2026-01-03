# 🎯 Advanced Sync Guide - Select Specific Places

## ✅ NEW FEATURE: Granular Place Selection

You can now select **exactly which places to sync** using cascading dropdowns and checkboxes!

---

## 🚀 How to Use

### Step 1: Go to Manage Page

Navigate to: **http://127.0.0.1:5000/manage** → **WordPress Sync** tab

Scroll down to: **"Advanced Sync (Select Specific Places)"**

---

### Step 2: Select Location (Cascading Dropdowns)

#### **1. Select Country**
- Dropdown shows all countries in your database
- Shows count of places per country
- Example: `United States (767)`

#### **2. Select State/Province**
- Automatically loads states for selected country
- Shows count of places per state
- Example: `California (250)`

#### **3. Select City**
- Automatically loads cities for selected state
- Shows count of places per city
- Example: `Santa Barbara (120)`

**Cascading Logic:**
```
Country → State → City
   ↓        ↓       ↓
Loads   Loads   Loads
States  Cities  Places
```

---

### Step 3: View & Select Places

Once you select a city, all places are displayed with:

#### **Place Information Shown:**
- ✅ Business name
- ✅ Category (if available)
- ✅ Address
- ✅ Phone number
- ✅ Sync status badge:
  - 🟢 **Green "Synced"** - Already in WordPress
  - 🟠 **Orange "Not Synced"** - Not yet synced

#### **Selection Options:**
- **Individual checkboxes** - Select specific places
- **"Select All"** button - Check all places at once
- **"Deselect All"** button - Uncheck all

#### **Filter Option:**
- ☑️ **"Show unsynced only"** - Hide places already synced

---

### Step 4: Sync Selected Places

1. **Select places** using checkboxes
2. Button shows: **"Sync Selected Places (5)"** ← number of selected places
3. **Click** the sync button
4. **Confirm** the sync
5. **Wait** for completion
6. **Done!** Places are synced to WordPress

---

## 📊 Example Workflow

### Scenario: Sync 10 specific places from Santa Barbara

```
Step 1: Select Location
→ Country: United States
→ State: California
→ City: Santa Barbara
→ Shows: 120 places

Step 2: Filter (optional)
☑️ Check "Show unsynced only"
→ Shows: 93 unsynced places

Step 3: Select Places
→ Check 10 specific places you want
   ✓ Center for Autism & Related Disorders
   ✓ Koegel Autism Center
   ✓ Tri-Counties Regional Center
   ... (7 more)

Step 4: Sync
→ Click "Sync Selected Places (10)"
→ Confirm
→ Wait ~5 seconds
→ Done! 10 places synced
```

---

## 🎯 Use Cases

### Use Case 1: Sync Only New Autism Centers

```
1. Select: United States > California > Los Angeles
2. Check: "Show unsynced only"
3. Select: Only places with "Autism" in the name
4. Sync: Selected places
```

### Use Case 2: Update Specific Locations

```
1. Select: United States > Texas > Houston
2. Don't filter (show all)
3. Select: 20 specific places you want to update
4. Sync Mode: "Update Existing"
5. Sync: Selected places
```

### Use Case 3: Sync All from Multiple Cities

```
1. Select: United Arab Emirates > Dubai > Dubai
2. Select All: All places
3. Sync: All Dubai places

4. Select: United Arab Emirates > Abu Dhabi > Abu Dhabi
5. Select All: All places
6. Sync: All Abu Dhabi places
```

---

## 📡 API Endpoints

### Get Countries
```bash
GET /api/locations/countries

Response:
[
  {"name": "United States", "count": 767},
  {"name": "United Arab Emirates", "count": 67}
]
```

### Get States by Country
```bash
GET /api/locations/states?country=United%20States

Response:
[
  {"name": "California", "count": 350},
  {"name": "Texas", "count": 200}
]
```

### Get Cities by State
```bash
GET /api/locations/cities?country=United%20States&state=California

Response:
[
  {"name": "Santa Barbara", "count": 120},
  {"name": "Los Angeles", "count": 180}
]
```

### Get Places by Location
```bash
GET /api/locations/places?country=United%20States&state=California&city=Santa%20Barbara

Optional parameter:
&unsynced_only=true

Response:
[
  {
    "place_id": "ChIJ...",
    "title": "Center for Autism",
    "category": "Autism Services",
    "address": "123 Main St...",
    "location": "United States > California > Santa Barbara",
    "wp_synced": 0,
    "phone": "555-1234",
    "website": "https://..."
  }
]
```

### Sync Selected Places
```bash
POST /api/wordpress/sync-bulk

Body:
{
  "wp_url": "https://yoursite.com",
  "api_key": "your_key",
  "sync_mode": "update",
  "place_ids": [
    "ChIJabc123...",
    "ChIJdef456...",
    "ChIJghi789..."
  ]
}

Response:
{
  "total": 3,
  "synced": 3,
  "skipped": 0,
  "failed": 0,
  "errors": []
}
```

---

## 🎨 UI Features

### Cascading Dropdowns
- ✅ Country loads automatically on page load
- ✅ State dropdown enables when country selected
- ✅ City dropdown enables when state selected
- ✅ Places load automatically when city selected
- ✅ All dropdowns show counts

### Places List
- ✅ Beautiful card layout with checkboxes
- ✅ Color-coded sync status badges
- ✅ Shows business info (name, category, address, phone)
- ✅ Hover effect on cards
- ✅ Scrollable list (max height: 96)

### Selection Controls
- ✅ "Select All" button
- ✅ "Deselect All" button
- ✅ Counter shows selected count: "Sync Selected Places (15)"
- ✅ Button disabled when no places selected

### Filter
- ✅ "Show unsynced only" checkbox
- ✅ Instantly filters places list
- ✅ Shows count: "93 places found"

---

## 💡 Pro Tips

### 1. Use "Show Unsynced Only" to Focus

```
Before: 120 places (mix of synced/unsynced)
After checking filter: 93 places (only unsynced)
→ Easier to see what needs syncing!
```

### 2. Select All Then Deselect Unwanted

```
1. Click "Select All" (checks all 50 places)
2. Manually uncheck 5 you don't want
3. Sync remaining 45
→ Faster than checking 45 individually!
```

### 3. Sync by Category

```
1. Load all places for a city
2. Visually scan for specific category (e.g., "ABA Therapy")
3. Check only those places
4. Sync selected
→ Organized syncing by service type!
```

### 4. Progressive Syncing

```
Day 1: Sync California cities (100 places)
Day 2: Sync Texas cities (150 places)
Day 3: Sync Florida cities (80 places)
→ Spread the load, easier to verify!
```

---

## 🔄 Comparison: Simple vs Advanced Sync

### Simple Sync (Location Text Input)

```
✅ Fast for syncing all places from location
❌ Can't select specific places
❌ Syncs everything matching text
❌ Less control

Example:
Input: "Santa Barbara"
Result: Syncs ALL 120 places
```

### Advanced Sync (Cascading Selection)

```
✅ Full control over what to sync
✅ Select specific places
✅ Filter by sync status
✅ Visual place selection
❌ Takes more clicks

Example:
Input: US > CA > Santa Barbara → Select 10 specific
Result: Syncs ONLY 10 selected places
```

---

## 📊 Your Database Overview

Based on your 834 places:

### By Country
- **United States:** ~750+ places
- **United Arab Emirates:** ~70+ places
- **Singapore:** ~10+ places

### Popular States
- **California:** 350+ places
  - Santa Barbara: 120 places
  - Los Angeles: 180+ places
  - San Diego: 50+ places

### Popular Cities
- **Santa Barbara, CA:** 120 places
- **Dubai, UAE:** 67 places
- **Frisco, TX:** 50+ places

---

## ⚡ Quick Actions

### Sync All Santa Barbara Places
```
1. Country: United States
2. State: California
3. City: Santa Barbara
4. Click: "Select All"
5. Click: "Sync Selected Places (120)"
```

### Sync Only Unsynced from Dubai
```
1. Country: United Arab Emirates
2. State: Dubai
3. City: Dubai
4. Check: "Show unsynced only"
5. Click: "Select All"
6. Click: "Sync Selected Places (X)"
```

### Cherry-Pick 5 Specific Places
```
1. Navigate to any city
2. Browse the list
3. Check 5 specific places
4. Click: "Sync Selected Places (5)"
```

---

## 🎊 Benefits

### Precision Control
- ✅ Select exactly what you need
- ✅ No accidental syncing
- ✅ Visual confirmation before sync

### Organization
- ✅ Work city by city
- ✅ Group by category
- ✅ Progressive syncing

### Efficiency
- ✅ Filter unsynced only
- ✅ Skip already synced places
- ✅ Batch operations with selection

### Transparency
- ✅ See all places before syncing
- ✅ Know sync status at a glance
- ✅ Track progress per location

---

## 🚀 Start Using It Now!

**URL:** http://127.0.0.1:5000/manage

**Steps:**
1. Click WordPress Sync tab
2. Scroll to "Advanced Sync"
3. Select Country → State → City
4. Choose your places
5. Sync!

**Perfect for:**
- Syncing specific services/categories
- Working location by location
- Cherry-picking high-quality listings
- Avoiding re-sync of existing places

---

**Enjoy your granular control! 🎉**

