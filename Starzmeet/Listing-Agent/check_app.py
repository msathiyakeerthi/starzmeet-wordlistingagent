"""Check what routes are registered in the Flask app"""
import sys
sys.dont_write_bytecode = True  # Prevent .pyc files

# Import the app
import importlib.util
spec = importlib.util.spec_from_file_location("app", "app-latest-4.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
app = module.app

print("=" * 60)
print("REGISTERED ROUTES IN FLASK APP")
print("=" * 60)

routes = []
for rule in app.url_map.iter_rules():
    routes.append((rule.rule, rule.endpoint, ','.join(rule.methods)))

# Sort by route
routes.sort()

for route, endpoint, methods in routes:
    if not route.startswith('/static'):
        print(f"{route:30} {endpoint:30} {methods}")

print("=" * 60)
print(f"Total routes: {len(routes)}")
print("=" * 60)

# Check specifically for /manage
manage_exists = any(route == '/manage' for route, _, _ in routes)
if manage_exists:
    print("\n✓ /manage route EXISTS in the app!")
else:
    print("\n✗ /manage route NOT FOUND in the app!")
    print("This means the route definition is not being executed.")

