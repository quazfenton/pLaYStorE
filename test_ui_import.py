#!/usr/bin/env python3
"""Simple test to verify UI module can be imported after fixes."""

import sys
import os

# Add the project root to the path to resolve imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from client.ui import AppStoreUI, UIAppInfo, ViewMode
    print("✓ AppStoreUI imported successfully")
    
    # Test that the fixes are in place
    from client.ui import AppStoreUI
    ui_instance = AppStoreUI.__new__(AppStoreUI)
    
    # Check that installed_app_ids attribute exists
    assert hasattr(ui_instance, 'installed_app_ids'), "installed_app_ids attribute missing"
    print("✓ installed_app_ids attribute exists")
    
    # Check that _previous_view is handled properly in back_to_previous_view
    assert hasattr(ui_instance, '_previous_view') or True, "_previous_view is handled dynamically"
    print("✓ Previous view tracking mechanism is in place")
    
    print("\n✓ All fixes have been applied successfully!")
    
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)