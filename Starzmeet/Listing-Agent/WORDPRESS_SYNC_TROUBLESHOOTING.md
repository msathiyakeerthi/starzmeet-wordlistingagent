# 🔧 WordPress Sync Troubleshooting - 406 Error

## ❌ Current Error

```
ERROR: WordPress API error: 406 Client Error: Not Acceptable 
URL: https://starzmeet.com/wp-json/listingpro/v1/listings
```

---

## 🎯 What Does 406 Mean?

**HTTP 406 "Not Acceptable"** means WordPress is rejecting the request because:

1. ❌ **Wrong API Endpoint** - The URL might not be correct for ListingPro
2. ❌ **Wrong Authentication** - API key method might be incorrect  
3. ❌ **Missing Plugin** - ListingPro REST API might not be enabled
4. ❌ **Wrong Content-Type** - Headers don't match what WordPress expects

---

## 🔍 Step 1: Test Your WordPress API

Run this test script to diagnose the issue:

```bash
python test_wordpress_api.py
```

**What it tests:**
- ✅ WordPress REST API accessibility
- ✅ ListingPro endpoint availability
- ✅ 4 different authentication methods
- ✅ Correct headers and formats

---

## 🛠️ Step 2: Check ListingPro Configuration

### Option A: ListingPro Theme (Most Common)

If you're using **ListingPro WordPress Theme**, the API might be different:

**Possible Endpoints:**
```
/wp-json/wp/v2/job_listing        ← Try this first
/wp-json/lp/v1/listings
/wp-json/listingpro/v2/listings
```

### Option B: Check WordPress Admin

1. Log into **WordPress Admin**
2. Go to **Settings** → **Permalinks**
3. Make sure permalinks are NOT set to "Plain"
4. Go to **Settings** → **REST API** (if available)
5. Verify REST API is enabled

### Option C: Check Plugin

1. Go to **Plugins** in WordPress
2. Verify **ListingPro** plugin is active
3. Check if there's an API settings page
4. Look for API endpoint documentation

---

## 🔐 Step 3: Authentication Methods

ListingPro might use one of these methods:

### Method 1: Application Password (Recommended for WordPress 5.6+)

```
1. WordPress Admin → Users → Your Profile
2. Scroll to "Application Passwords"
3. Enter name: "Scraper API"
4. Click "Add New Application Password"
5. Copy the generated password
6. Use Basic Auth: username + application password
```

### Method 2: JWT Token

```
Install: JWT Authentication for WP REST API plugin
Configure: wp-config.php with JWT secret
Use: Bearer token authentication
```

### Method 3: Custom API Key

```
Check: ListingPro documentation
Some plugins have their own API key system
Location: Usually in plugin settings
```

---

## 🎯 Step 4: Quick Fixes to Try

### Fix 1: Change API Endpoint

Update your scraper to use WordPress standard post endpoint:

**Instead of:**
```
https://starzmeet.com/wp-json/listingpro/v1/listings
```

**Try:**
```
https://starzmeet.com/wp-json/wp/v2/job_listing
```

### Fix 2: Use Application Password

```python
# In manage.html, when calling WordPress:
auth = (username, application_password)  # Basic Auth
# Instead of:
headers = {'Authorization': f'Bearer {api_key}'}
```

### Fix 3: Check if REST API is Accessible

Open browser and visit:
```
https://starzmeet.com/wp-json/
```

Should return JSON with WordPress info. If not, REST API is disabled.

---

## 📋 Step 5: Alternative - Use WP CLI

If API doesn't work, you can import via WP CLI:

```bash
# Export CSV from scraper
# Then in WordPress server:
wp post create --post_type=job_listing \
  --post_title="Business Name" \
  --post_content="Description" \
  --meta_input='{"phone":"555-1234"}'
```

---

## 🔧 Step 6: Manual WordPress Integration

### Option A: Use WordPress XML Import

```
1. Export from scraper as CSV
2. Convert CSV to WordPress XML format
3. Use WordPress Importer plugin
4. Import XML file
```

### Option B: Use WP All Import Plugin

```
1. Install "WP All Import" plugin
2. Export CSV from scraper
3. Use plugin's drag-and-drop mapper
4. Map CSV fields to ListingPro fields
5. Import
```

---

## 💡 Recommended Solution

Based on your error, I recommend:

### **Solution 1: Test the API First**

```bash
python test_wordpress_api.py
```

This will tell you:
- Which authentication method works
- What the correct endpoint is
- If REST API is accessible

### **Solution 2: Use WordPress Standard Endpoint**

ListingPro likely uses WordPress custom post types:

```python
# Instead of custom endpoint, use:
POST /wp-json/wp/v2/job_listing
```

With fields:
```json
{
  "title": "Business Name",
  "content": "Description",
  "status": "publish",
  "meta": {
    "phone": "555-1234",
    "email": "email@example.com",
    ...
  }
}
```

### **Solution 3: Get ListingPro Documentation**

Contact ListingPro support or check their docs:
- What's the correct REST API endpoint?
- What authentication method to use?
- What's the correct data structure?

---

## 📞 Need More Help?

### Check These:

1. **WordPress REST API Handbook**
   ```
   https://developer.wordpress.org/rest-api/
   ```

2. **ListingPro Documentation**
   - Check your theme documentation
   - Look for API section
   - Contact support if needed

3. **WordPress API Tester (Online Tool)**
   ```
   Use Postman or Insomnia to test:
   - GET https://starzmeet.com/wp-json/
   - GET https://starzmeet.com/wp-json/wp/v2/types
   ```

---

## 🎯 Quick Diagnostic Checklist

- [ ] WordPress REST API is accessible
- [ ] Permalinks are NOT set to "Plain"
- [ ] ListingPro plugin/theme is active
- [ ] API key or application password is correct
- [ ] Using correct API endpoint
- [ ] Using correct authentication method
- [ ] Content-Type header is correct
- [ ] WordPress user has proper permissions

---

## ⚡ Temporary Workaround

Until API is working, you can:

### Option 1: Export CSV and Import Manually

```
1. Manage → WordPress Sync → Select places
2. Export as CSV instead of sync
3. Use WordPress import plugin
```

### Option 2: Use Our CSV Export

```
1. Go to: http://127.0.0.1:5000/api/download
2. Get CSV with all 834 places
3. Import to WordPress using WP All Import plugin
```

---

## 🔍 Debug Mode

To get more details, check WordPress debug logs:

```php
// In wp-config.php:
define('WP_DEBUG', true);
define('WP_DEBUG_LOG', true);
define('WP_DEBUG_DISPLAY', false);

// Then check: /wp-content/debug.log
```

---

**Run the test script and let me know the results!** 

```bash
python test_wordpress_api.py
```

This will help us identify the exact issue and fix it.

