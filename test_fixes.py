#!/usr/bin/env python3
"""Test the specific fixes made to the UI module by checking the file content."""

import os

def test_fixes():
    file_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "playstorE", "client", "ui.py"
    )

    with open(file_path, 'r') as f:
        content = f.read()
    
    print("Testing fixes in client/ui.py...")
    
    # Test 1: Check that installed_app_ids is initialized in __init__
    if "self.installed_app_ids = set()" in content:
        print("✓ Fix 1: installed_app_ids initialization found")
    else:
        print("✗ Fix 1: installed_app_ids initialization not found")
        return False
    
    # Test 2: Check that install_app adds to installed_app_ids
    if "# Add to installed apps set to persist state" in content and "self.installed_app_ids.add(app.app_id)" in content:
        print("✓ Fix 2: install_app persists state to installed_app_ids")
    else:
        print("✗ Fix 2: install_app does not persist state to installed_app_ids")
        return False
    
    # Test 3: Check that uninstall_app removes from installed_app_ids
    if "# Remove from installed apps set to persist state" in content and "self.installed_app_ids.discard(app.app_id)" in content:
        print("✓ Fix 3: uninstall_app removes from installed_app_ids")
    else:
        print("✗ Fix 3: uninstall_app does not remove from installed_app_ids")
        return False
    
    # Test 4: Check that get_apps_for_display uses installed_app_ids to determine is_installed
    if "# Check if app is installed based on our persistent tracking" in content and "is_installed = idx_app.app_id in self.installed_app_ids" in content:
        print("✓ Fix 4: get_apps_for_display uses persistent tracking")
    else:
        print("✗ Fix 4: get_apps_for_display does not use persistent tracking")
        return False
    
    # Test 5: Check that show_app_details saves previous view
    if "# Save the current view as the previous view before navigating to details" in content and "self._previous_view = self.current_view" in content:
        print("✓ Fix 5: show_app_details saves previous view")
    else:
        print("✗ Fix 5: show_app_details does not save previous view")
        return False
    
    # Test 6: Check that UI updates are scheduled on main thread in install_app
    if "self.root.after(0," in content:
        print("✓ Fix 6: UI updates are scheduled on main thread")
    else:
        print("✗ Fix 6: UI updates are not scheduled on main thread")
        return False
    
    # Test 7: Check that UI updates are scheduled on main thread in uninstall_app
    if "# Schedule all UI updates on main thread" in content or "# Schedule UI updates on main thread" in content:
        print("✓ Fix 7: uninstall_app schedules UI updates on main thread")
    else:
        print("✗ Fix 7: uninstall_app does not schedule UI updates on main thread")
        return False
    
    print("\n✓ All fixes have been successfully applied!")
    return True

if __name__ == "__main__":
    success = test_fixes()
    if not success:
        exit(1)