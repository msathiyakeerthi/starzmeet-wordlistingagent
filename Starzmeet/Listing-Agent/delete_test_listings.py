import requests
import json

wp_url = "https://starzmeet.com"
api_key = "62e30d2c14b4e891ec0745e5c34788fd992ff8c12f191cd7a2cb98d4483fde59"

# Test listing IDs to delete
test_listing_ids = [32049, 32050, 32051]

headers = {
    'X-API-Key': api_key,
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

print("=" * 60)
print("Deleting Test Listings")
print("=" * 60)
print()

deleted = []
failed = []

for listing_id in test_listing_ids:
    print(f"Deleting listing ID: {listing_id}...")
    try:
        # Try DELETE endpoint
        response = requests.delete(
            f"{wp_url}/wp-json/listingpro/v1/listing/{listing_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code in [200, 204]:
            print(f"  [SUCCESS] Deleted listing {listing_id}")
            deleted.append(listing_id)
        elif response.status_code == 404:
            print(f"  [INFO] Listing {listing_id} not found (may already be deleted)")
        else:
            print(f"  [FAIL] Status {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            failed.append(listing_id)
    except Exception as e:
        print(f"  [ERROR] {e}")
        failed.append(listing_id)
    print()

print("=" * 60)
print("Summary")
print("=" * 60)
print(f"Deleted: {len(deleted)} listings")
if deleted:
    print(f"  IDs: {', '.join(map(str, deleted))}")
if failed:
    print(f"Failed: {len(failed)} listings")
    print(f"  IDs: {', '.join(map(str, failed))}")

