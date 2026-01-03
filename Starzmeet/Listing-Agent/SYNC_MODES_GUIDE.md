# 🔄 WordPress Sync Modes Guide

## Overview
The system now supports **3 different modes** for handling existing listings when syncing to WordPress:

---

## 🛡️ Mode 1: Skip Existing Listings (Safest)

### What it does:
- Checks WordPress for existing listings before syncing
- **Skips** any listing that already exists
- Only creates NEW listings

### When to use:
- ✅ First time sync
- ✅ When you want to avoid duplicates
- ✅ When WordPress has manually updated data you want to preserve
- ✅ Default safe option

### How it works:
1. Scraper fetches data from database
2. For each listing, checks WordPress by:
   - Business Name
   - Phone Number
   - Address
3. If match found → **SKIP**
4. If no match → **CREATE NEW**

### UI Selection:
```
○ Skip Existing Listings ← SELECT THIS
○ Update Existing Listings
○ Force Create (May Duplicate)
```

---

## 🔄 Mode 2: Update Existing Listings (Recommended for Refresh)

### What it does:
- Checks WordPress for existing listings
- **Updates** existing listings with fresh scraped data
- Creates new listings for places not found in WordPress

### When to use:
- ✅ **Your use case!** You already have listings in WordPress
- ✅ Want to refresh WordPress data with latest scraped info
- ✅ Business hours changed
- ✅ Contact info updated
- ✅ Want to sync new photos/descriptions from scraper

### How it works:
1. Scraper fetches data from database
2. For each listing, checks WordPress by:
   - Business Name
   - Phone Number  
   - Address
3. If match found → **UPDATE** (sends PUT request with WordPress Post ID)
4. If no match → **CREATE NEW**

### What gets updated:
- ✅ Business description
- ✅ Contact information (phone, email, website)
- ✅ Business hours
- ✅ Categories and features
- ✅ Location/address details
- ✅ Photos (if available)
- ❌ WordPress Post ID (preserved)
- ❌ Publish status (preserved)

### UI Selection:
```
○ Skip Existing Listings
● Update Existing Listings ← SELECT THIS
○ Force Create (May Duplicate)
```

---

## ⚠️ Mode 3: Force Create (Dangerous)

### What it does:
- **Does NOT check** for existing listings
- Creates new listing every time
- **May create duplicates!**

### When to use:
- ⚠️ Only use if you know what you're doing
- ⚠️ Testing purposes
- ⚠️ Different WordPress sites

### UI Selection:
```
○ Skip Existing Listings
○ Update Existing Listings
● Force Create (May Duplicate) ← CAUTION
```

---

## 📊 Sync Results Display

After syncing, you'll see:

```
┌─────────────────────────────────────────┐
│  Sync Results                           │
├─────────┬──────────┬──────────┬─────────┤
│  New    │ Updated  │ Skipped  │ Failed  │
│  15     │ 23       │ 8        │ 0       │
└─────────┴──────────┴──────────┴─────────┘
```

- **New Synced**: Listings created in WordPress (didn't exist before)
- **Updated**: Existing listings refreshed with new data
- **Skipped**: Listings already in WordPress (skip mode only)
- **Failed**: Sync errors

---

## 🎯 Step-by-Step: Update Existing WordPress Listings

### For your situation (manually updated many services in ListingPro):

1. **Open Management Page**
   ```
   http://localhost:5000/manage
   ```

2. **Go to "WordPress Sync" tab**

3. **Configure WordPress settings** (if not done):
   - WordPress URL: `https://yoursite.com`
   - API Key: `your-api-key-here`
   - Click **Save Configuration**

4. **Select Update Mode**:
   ```
   ○ Skip Existing Listings
   ● Update Existing Listings ← SELECT THIS
   ○ Force Create (May Duplicate)
   ```

5. **Choose sync scope**:

   **Option A: Sync ALL**
   ```
   Click: [Sync All Unsynced]
   ```
   
   **Option B: Sync by Location**
   ```
   Enter location: "New York, NY"
   Click: [Sync Location]
   ```

6. **Review Results**:
   - See how many were **Updated** (existing listings refreshed)
   - See how many were **New** (created for first time)
   - Check **Updated Items** list for details

---

## 💡 Matching Logic

The system finds existing listings by checking:

### Priority 1: Business Name
```python
if wordpress_title == scraped_title:
    match = True
```

### Priority 2: Phone Number
```python
if wordpress_phone == scraped_phone:
    match = True
```

### Priority 3: Address
```python
if wordpress_address == scraped_address:
    match = True
```

**Match found?** → Update (in update mode) or Skip (in skip mode)  
**No match?** → Create new listing

---

## 🔍 API Endpoints (Developer Reference)

### Single Place Sync
```javascript
POST /api/wordpress/sync-single
{
    "place_id": "ChIJ...",
    "wp_url": "https://yoursite.com",
    "wp_api_key": "your-key",
    "skip_duplicates": false,
    "update_existing": true  // ← NEW PARAMETER
}
```

### Bulk Sync
```javascript
POST /api/wordpress/sync-bulk
{
    "wp_url": "https://yoursite.com",
    "wp_api_key": "your-key",
    "sync_all": true,
    "location": "New York, NY",  // optional
    "skip_duplicates": false,
    "update_existing": true  // ← NEW PARAMETER
}
```

### Response Format
```json
{
    "total": 50,
    "success": 15,
    "failed": 0,
    "skipped": 12,
    "updated": 23,  // ← NEW FIELD
    "details": [...],
    "skipped_details": [...],
    "updated_details": [  // ← NEW FIELD
        {
            "place_id": "ChIJ...",
            "title": "ABC Autism Center",
            "wp_post_id": 12345,
            "success": true
        }
    ]
}
```

---

## ⚙️ Backend Implementation

### WordPressSyncService Methods

```python
# Single place sync
sync_single_place(place, skip_duplicates=True, update_existing=False)

# Bulk sync
sync_bulk_places(places, skip_duplicates=True, update_existing=False)

# Find duplicate (internal)
find_duplicate(place) → {
    'exists': True/False,
    'wp_post_id': 12345,
    'matched_by': 'title',
    'existing_title': '...'
}
```

### Update Flow
```python
if duplicate_check['exists'] and update_existing:
    # Update existing listing
    url = f"{base_url}/wp-json/listingpro/v1/listing/{wp_post_id}"
    response = requests.put(url, headers=headers, json=wp_data)
    # Mark as updated in database
```

---

## 📝 Database Tracking

After sync, the local database is updated:

```sql
UPDATE places 
SET 
    wp_synced = 1,
    wp_post_id = 12345,
    wp_sync_date = '2025-12-26T10:30:00'
WHERE place_id = 'ChIJ...';
```

This prevents re-syncing on future runs.

---

## 🎯 Recommended Workflow

### First Time Setup:
1. Use **Skip Mode** to sync all new listings
2. Review in WordPress
3. Make manual edits as needed

### Regular Updates (Your Case):
1. Run scraper to fetch latest data
2. Use **Update Mode** to refresh WordPress
3. Only new listings are created, existing ones updated
4. Manually edited WordPress data is overwritten with fresh scraped data

### Testing:
1. Use **Force Mode** on staging site
2. Check results
3. Clean up duplicates
4. Switch to Skip/Update for production

---

## 🚨 Common Questions

### Q: Will update mode overwrite my manual WordPress edits?
**A:** Yes, update mode replaces WordPress data with scraped data. Use skip mode if you want to preserve manual edits.

### Q: How does it match existing listings?
**A:** By business name, phone number, or address. If any match, it's considered a duplicate.

### Q: What if I have duplicate listings in WordPress already?
**A:** The system will match the FIRST listing it finds. You may want to clean up WordPress duplicates first.

### Q: Can I update only specific fields?
**A:** Currently no, update mode replaces all fields. This is a potential future feature.

### Q: Does update preserve WordPress SEO settings?
**A:** Update mode uses PUT request which should preserve post meta. Test on staging first.

---

## 🎬 Quick Start Commands

### Update all existing listings:
```bash
# 1. Start server
python app-latest-4.py

# 2. Open browser
http://localhost:5000/manage

# 3. Select "Update Existing Listings" mode
# 4. Click "Sync All Unsynced"
```

### Check sync status:
```sql
-- In database
SELECT 
    COUNT(*) as total,
    SUM(wp_synced) as synced,
    COUNT(*) - SUM(wp_synced) as unsynced
FROM places;
```

---

## 🔗 Related Documentation

- **DUPLICATE_PREVENTION_GUIDE.md** - Understanding duplicate detection
- **WORDPRESS_SYNC_GUIDE.md** - WordPress API setup
- **QUICK_START.md** - Getting started guide

---

**Need Help?** Open the Management page and hover over the info icons for tooltips!







