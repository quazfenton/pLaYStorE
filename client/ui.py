"""
Client UI for desktop and mobile for the alternative app store platform.
Provides interfaces for browsing, installing, and managing applications.
Based on the scouts.md specification for client UI.
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum
import threading
import time
from ..core.types.manifest_schema import AppManifest
from ..storage.indexes.federated import FederatedIndexManager
from ..core.security.trust_model import SecurityManager


class ViewMode(Enum):
    """Different view modes for the UI"""
    CATALOG = "catalog"
    INSTALLED = "installed"
    SEARCH = "search"
    DETAILS = "details"


@dataclass
class UIAppInfo:
    """UI representation of an app"""
    app_id: str
    name: str
    description: str
    publisher: str
    version: str
    trust_score: float
    download_size: str
    icon_url: Optional[str] = None
    is_installed: bool = False
    install_path: Optional[str] = None


class AppStoreUI:
    """Main UI for the alternative app store"""
    
    def __init__(self, index_manager: FederatedIndexManager, 
                 security_manager: SecurityManager):
        self.index_manager = index_manager
        self.security_manager = security_manager
        self.root = tk.Tk()
        self.root.title("Alternative App Store")
        self.root.geometry("1000x700")
        
        # Current view mode
        self.current_view = ViewMode.CATALOG
        self.selected_app: Optional[UIAppInfo] = None
        
        # Search term
        self.search_term = tk.StringVar()
        
        self.setup_ui()
        self.refresh_catalog()
    
    def setup_ui(self):
        """Set up the main UI elements"""
        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Top toolbar
        toolbar_frame = ttk.Frame(main_frame)
        toolbar_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Search bar
        search_label = ttk.Label(toolbar_frame, text="Search:")
        search_label.pack(side=tk.LEFT, padx=(0, 5))
        
        search_entry = ttk.Entry(toolbar_frame, textvariable=self.search_term, width=30)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        search_entry.bind("<Return>", lambda e: self.perform_search())
        
        search_button = ttk.Button(toolbar_frame, text="Search", command=self.perform_search)
        search_button.pack(side=tk.LEFT, padx=(5, 0))
        
        refresh_button = ttk.Button(toolbar_frame, text="Refresh", command=self.refresh_catalog)
        refresh_button.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Main content area
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left sidebar for navigation
        sidebar_frame = ttk.Frame(content_frame)
        sidebar_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # Navigation buttons
        nav_buttons = [
            ("Catalog", self.show_catalog),
            ("Installed", self.show_installed),
            ("Updates", self.show_updates),
            ("Settings", self.show_settings)
        ]
        
        for text, command in nav_buttons:
            btn = ttk.Button(sidebar_frame, text=text, command=command)
            btn.pack(fill=tk.X, pady=2)
        
        # Main content area (right side)
        self.content_area = ttk.Frame(content_frame)
        self.content_area.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def show_catalog(self):
        """Show the app catalog"""
        self.current_view = ViewMode.CATALOG
        self.clear_content_area()
        self.display_app_grid()
    
    def show_installed(self):
        """Show installed apps"""
        self.current_view = ViewMode.INSTALLED
        self.clear_content_area()
        self.display_installed_apps()
    
    def show_updates(self):
        """Show available updates"""
        self.current_view = ViewMode.SEARCH  # Reusing search view for updates
        self.clear_content_area()
        self.display_updates()
    
    def show_settings(self):
        """Show settings"""
        self.current_view = ViewMode.SEARCH  # Reusing search view for settings
        self.clear_content_area()
        self.display_settings()
    
    def perform_search(self):
        """Perform search based on search term"""
        self.current_view = ViewMode.SEARCH
        self.clear_content_area()
        self.display_search_results()
    
    def clear_content_area(self):
        """Clear the content area"""
        for widget in self.content_area.winfo_children():
            widget.destroy()
    
    def display_app_grid(self):
        """Display app catalog in a grid layout"""
        # Title
        title_label = ttk.Label(self.content_area, text="App Catalog", font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Create scrollable frame for apps
        canvas = tk.Canvas(self.content_area)
        scrollbar = ttk.Scrollbar(self.content_area, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Get apps from index
        apps = self.get_apps_for_display()
        
        # Display apps in grid
        row, col = 0, 0
        for i, app in enumerate(apps):
            app_frame = ttk.LabelFrame(scrollable_frame, text=f"{app.name} v{app.version}", padding=10)
            app_frame.grid(row=row, column=col, padx=10, pady=10, sticky="ew")
            
            # Trust indicator
            trust_color = self.get_trust_color(app.trust_score)
            trust_label = ttk.Label(app_frame, text=f"Trust: {app.trust_score:.2f}", 
                                   foreground=trust_color, font=("Arial", 9, "bold"))
            trust_label.pack(anchor="w")
            
            # Description
            desc_label = ttk.Label(app_frame, text=app.description[:100] + "..." if len(app.description) > 100 else app.description,
                                  wraplength=200, justify=tk.LEFT)
            desc_label.pack(anchor="w", pady=(5, 10))
            
            # Publisher
            pub_label = ttk.Label(app_frame, text=f"by {app.publisher}", font=("Arial", 8))
            pub_label.pack(anchor="w")
            
            # Buttons
            button_frame = ttk.Frame(app_frame)
            button_frame.pack(fill=tk.X, pady=(10, 0))
            
            if app.is_installed:
                status_label = ttk.Label(button_frame, text="INSTALLED", foreground="green")
                status_label.pack(side=tk.LEFT)
                uninstall_btn = ttk.Button(button_frame, text="Uninstall", 
                                         command=lambda a=app: self.uninstall_app(a))
                uninstall_btn.pack(side=tk.RIGHT)
            else:
                install_btn = ttk.Button(button_frame, text="Install", 
                                       command=lambda a=app: self.install_app(a))
                install_btn.pack(side=tk.RIGHT)
            
            details_btn = ttk.Button(button_frame, text="Details", 
                                   command=lambda a=app: self.show_app_details(a))
            details_btn.pack(side=tk.RIGHT, padx=(0, 5))
            
            # Move to next position in grid
            col += 1
            if col >= 3:  # 3 columns
                col = 0
                row += 1
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def display_installed_apps(self):
        """Display installed applications"""
        title_label = ttk.Label(self.content_area, text="Installed Applications", font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Get installed apps (for now, just show apps from index that are marked as installed)
        installed_apps = [app for app in self.get_apps_for_display() if app.is_installed]
        
        if not installed_apps:
            no_apps_label = ttk.Label(self.content_area, text="No applications installed", font=("Arial", 12))
            no_apps_label.pack(expand=True)
            return
        
        # Create list of installed apps
        listbox = tk.Listbox(self.content_area)
        listbox.pack(fill=tk.BOTH, expand=True, pady=10)
        
        for app in installed_apps:
            listbox.insert(tk.END, f"{app.name} v{app.version} - {app.publisher}")
        
        # Buttons frame
        buttons_frame = ttk.Frame(self.content_area)
        buttons_frame.pack(fill=tk.X, pady=10)
        
        refresh_btn = ttk.Button(buttons_frame, text="Refresh", command=self.refresh_installed)
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        listbox.bind("<<ListboxSelect>>", lambda e: self.on_installed_select(listbox))
    
    def display_search_results(self):
        """Display search results"""
        title_label = ttk.Label(self.content_area, text=f"Search Results for: '{self.search_term.get()}'", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 10))
        
        # For now, just show all apps that match the search term
        search_term = self.search_term.get().lower()
        all_apps = self.get_apps_for_display()
        filtered_apps = [
            app for app in all_apps 
            if search_term in app.name.lower() or search_term in app.description.lower()
        ]
        
        if not filtered_apps:
            no_results_label = ttk.Label(self.content_area, text="No results found", font=("Arial", 12))
            no_results_label.pack(expand=True)
            return
        
        # Display results similar to catalog
        canvas = tk.Canvas(self.content_area)
        scrollbar = ttk.Scrollbar(self.content_area, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        row, col = 0, 0
        for i, app in enumerate(filtered_apps):
            app_frame = ttk.LabelFrame(scrollable_frame, text=f"{app.name} v{app.version}", padding=10)
            app_frame.grid(row=row, column=col, padx=10, pady=10, sticky="ew")
            
            trust_color = self.get_trust_color(app.trust_score)
            trust_label = ttk.Label(app_frame, text=f"Trust: {app.trust_score:.2f}", 
                                   foreground=trust_color, font=("Arial", 9, "bold"))
            trust_label.pack(anchor="w")
            
            desc_label = ttk.Label(app_frame, text=app.description[:100] + "..." if len(app.description) > 100 else app.description,
                                  wraplength=200, justify=tk.LEFT)
            desc_label.pack(anchor="w", pady=(5, 10))
            
            pub_label = ttk.Label(app_frame, text=f"by {app.publisher}", font=("Arial", 8))
            pub_label.pack(anchor="w")
            
            button_frame = ttk.Frame(app_frame)
            button_frame.pack(fill=tk.X, pady=(10, 0))
            
            if app.is_installed:
                status_label = ttk.Label(button_frame, text="INSTALLED", foreground="green")
                status_label.pack(side=tk.LEFT)
                uninstall_btn = ttk.Button(button_frame, text="Uninstall", 
                                         command=lambda a=app: self.uninstall_app(a))
                uninstall_btn.pack(side=tk.RIGHT)
            else:
                install_btn = ttk.Button(button_frame, text="Install", 
                                       command=lambda a=app: self.install_app(a))
                install_btn.pack(side=tk.RIGHT)
            
            details_btn = ttk.Button(button_frame, text="Details", 
                                   command=lambda a=app: self.show_app_details(a))
            details_btn.pack(side=tk.RIGHT, padx=(0, 5))
            
            col += 1
            if col >= 3:
                col = 0
                row += 1
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def display_updates(self):
        """Display available updates"""
        title_label = ttk.Label(self.content_area, text="Available Updates", font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 10))
        
        # For now, just show a message
        updates_label = ttk.Label(self.content_area, text="Checking for updates...", font=("Arial", 12))
        updates_label.pack(expand=True)
        
        # In a real implementation, this would check for newer versions of installed apps
        # For demo purposes, we'll just show a message after a delay
        def check_for_updates():
            time.sleep(2)  # Simulate checking
            # Schedule UI update on main thread
            self.root.after(0, lambda: updates_label.config(text="No updates available"))

        threading.Thread(target=check_for_updates, daemon=True).start()
    
    def display_settings(self):
        """Display settings"""
        title_label = ttk.Label(self.content_area, text="Settings", font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Settings options
        settings_frame = ttk.Frame(self.content_area)
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Auto-update option
        auto_update_var = tk.BooleanVar(value=True)
        auto_update_check = ttk.Checkbutton(settings_frame, text="Auto-check for updates", 
                                          variable=auto_update_var)
        auto_update_check.pack(anchor="w", pady=5)
        
        # Offline mode option
        offline_var = tk.BooleanVar(value=False)
        offline_check = ttk.Checkbutton(settings_frame, text="Offline mode", 
                                      variable=offline_var)
        offline_check.pack(anchor="w", pady=5)
        
        # Security level
        ttk.Label(settings_frame, text="Security Level:", font=("Arial", 10, "bold")).pack(anchor="w", pady=(20, 5))
        
        security_var = tk.StringVar(value="Standard")
        security_combo = ttk.Combobox(settings_frame, textvariable=security_var, 
                                    values=["Relaxed", "Standard", "Strict"])
        security_combo.pack(anchor="w", pady=5)
        
        # Save button
        save_btn = ttk.Button(settings_frame, text="Save Settings")
        save_btn.pack(pady=20)
    
    def get_apps_for_display(self) -> List[UIAppInfo]:
        """Get apps from the index for display"""
        # In a real implementation, this would come from the federated index
        # For now, we'll create some mock apps
        apps = []
        
        # Get apps from index manager
        index_apps = self.index_manager.get_all_apps()
        
        for idx_app in index_apps:
            # Convert to UIAppInfo
            app_info = UIAppInfo(
                app_id=idx_app.app_id,
                name=idx_app.app_id.split('.')[-1].title(),  # Simple name derivation
                description=f"Description for {idx_app.app_id}",
                publisher=idx_app.publisher,
                version=idx_app.version,
                trust_score=idx_app.trust_score,
                download_size="10 MB",  # Placeholder
                is_installed=False  # Placeholder
            )
            apps.append(app_info)
        
        # Add some mock apps if index is empty
        if not apps:
            mock_apps = [
                UIAppInfo("com.example.app1", "Example App 1", "A great example application", 
                         "Example Publisher", "1.0.0", 0.92, "15 MB", is_installed=False),
                UIAppInfo("com.example.app2", "Another App", "Another useful application", 
                         "Another Publisher", "2.1.0", 0.87, "22 MB", is_installed=True),
                UIAppInfo("org.test.utility", "Test Utility", "A handy utility tool", 
                         "Test Developer", "1.5.3", 0.78, "8 MB", is_installed=False),
            ]
            apps.extend(mock_apps)
        
        return apps
    
    def get_trust_color(self, trust_score: float) -> str:
        """Get color based on trust score"""
        if trust_score >= 0.8:
            return "green"
        elif trust_score >= 0.5:
            return "orange"
        else:
            return "red"
    
    def install_app(self, app: UIAppInfo):
        """Install an application"""
        self.status_var.set(f"Installing {app.name}...")
        
        def do_install():
            try:
                # In a real implementation, this would:
                # 1. Download the app from the federated index
                # 2. Verify its integrity and trust
                # 3. Install it to the appropriate location
                # 4. Update the UI
                
                time.sleep(2)  # Simulate installation
                
                # Update app as installed
                app.is_installed = True
                app.install_path = f"/opt/apps/{app.app_id}"
<<<<<<< Updated upstream
                
                def update_ui():
                    self.status_var.set(f"Successfully installed {app.name}")
                    messagebox.showinfo("Success", f"{app.name} installed successfully!")
                    if self.current_view == ViewMode.CATALOG:
                        self.show_catalog()
                    elif self.current_view == ViewMode.SEARCH:
                        self.display_search_results()
                
                self.root.after(0, update_ui)
                    
            except Exception as e:
                self.root.after(0, lambda: self.status_var.set("Installation failed"))
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to install {app.name}: {e!s}"))
        
=======

                # Schedule all UI updates on main thread
                self.root.after(0, lambda: self.status_var.set(f"Successfully installed {app.name}"))
                self.root.after(0, lambda: messagebox.showinfo("Success", f"{app.name} installed successfully!"))

                # Schedule UI updates on main thread
                if self.current_view == ViewMode.CATALOG:
                    self.root.after(0, self.show_catalog)
                elif self.current_view == ViewMode.SEARCH:
                    self.root.after(0, self.display_search_results)

            except Exception as e:
                # Schedule error message on main thread
                self.root.after(0, lambda: self.status_var.set("Installation failed"))
                # Show error dialog on main thread
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to install {app.name}: {str(e)}"))

>>>>>>> Stashed changes
        threading.Thread(target=do_install, daemon=True).start()
    
    def uninstall_app(self, app: UIAppInfo):
        """Uninstall an application"""
        if not messagebox.askyesno("Confirm Uninstall",
                                   f"Are you sure you want to uninstall {app.name}?"):
            return
        
        self.status_var.set(f"Uninstalling {app.name}...")
        
        def do_uninstall():
            try:
                # In a real implementation, this would:
                # 1. Remove the app files
                # 2. Update the registry
                # 3. Update the UI
                
                time.sleep(1)  # Simulate uninstallation
                
                # Update app as uninstalled
                app.is_installed = False
                app.install_path = None
                
                self.status_var.set(f"Successfully uninstalled {app.name}")
                messagebox.showinfo("Success", f"{app.name} uninstalled successfully!")
                
                # Schedule UI updates on main thread
                if self.current_view == ViewMode.INSTALLED:
                    self.root.after(0, self.show_installed)
                elif self.current_view == ViewMode.CATALOG:
                    self.root.after(0, self.show_catalog)

            except Exception as e:
                # Schedule error message on main thread
                self.root.after(0, lambda: self.status_var.set("Uninstallation failed"))
                # Show error dialog on main thread
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to uninstall {app.name}: {str(e)}"))
        
        threading.Thread(target=do_uninstall, daemon=True).start()
    
    def show_app_details(self, app: UIAppInfo):
        """Show detailed information about an app"""
        self.selected_app = app
        self.current_view = ViewMode.DETAILS
        self.clear_content_area()
        
        # Title
        title_label = ttk.Label(self.content_area, text=app.name, font=("Arial", 18, "bold"))
        title_label.pack(pady=(0, 5))
        
        # Subtitle with version and publisher
        subtitle = ttk.Label(self.content_area, 
                           text=f"Version {app.version} by {app.publisher}", 
                           font=("Arial", 10))
        subtitle.pack(pady=(0, 15))
        
        # Trust indicator
        trust_frame = ttk.Frame(self.content_area)
        trust_frame.pack(fill=tk.X, pady=5)
        
        trust_color = self.get_trust_color(app.trust_score)
        trust_label = ttk.Label(trust_frame, text=f"Trust Score: {app.trust_score:.2f}", 
                               foreground=trust_color, font=("Arial", 12, "bold"))
        trust_label.pack(side=tk.LEFT)
        
        # Security details
        sec_frame = ttk.LabelFrame(self.content_area, text="Security Details", padding=10)
        sec_frame.pack(fill=tk.X, pady=10)
        
        # In a real implementation, this would show actual security details
        sec_details = [
            ("Network Access", "Restricted"),
            ("File System", "Sandboxed"),
            ("Permissions", "Minimal"),
            ("Verification", "Signed & Reproducible")
        ]
        
        for label, value in sec_details:
            detail_frame = ttk.Frame(sec_frame)
            detail_frame.pack(fill=tk.X, pady=2)
            
            label_widget = ttk.Label(detail_frame, text=label + ":", width=15)
            label_widget.pack(side=tk.LEFT)
            
            value_widget = ttk.Label(detail_frame, text=value)
            value_widget.pack(side=tk.LEFT)
        
        # Description
        desc_frame = ttk.LabelFrame(self.content_area, text="Description", padding=10)
        desc_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        desc_text = scrolledtext.ScrolledText(desc_frame, wrap=tk.WORD)
        desc_text.insert(tk.END, app.description)
        desc_text.config(state=tk.DISABLED)
        desc_text.pack(fill=tk.BOTH, expand=True)
        
        # Action buttons
        action_frame = ttk.Frame(self.content_area)
        action_frame.pack(fill=tk.X, pady=10)
        
        if app.is_installed:
            uninstall_btn = ttk.Button(action_frame, text="Uninstall", 
                                     command=lambda: self.uninstall_app(app))
            uninstall_btn.pack(side=tk.RIGHT, padx=5)
            
            launch_btn = ttk.Button(action_frame, text="Launch", 
                                  command=lambda: self.launch_app(app))
            launch_btn.pack(side=tk.RIGHT, padx=5)
        else:
            install_btn = ttk.Button(action_frame, text="Install", 
                                   command=lambda: self.install_app(app))
            install_btn.pack(side=tk.RIGHT, padx=5)
        
        back_btn = ttk.Button(action_frame, text="Back", command=self.back_to_previous_view)
        back_btn.pack(side=tk.LEFT, padx=5)
    
    def launch_app(self, app: UIAppInfo):
        """Launch an installed application"""
        # In a real implementation, this would launch the app
        messagebox.showinfo("Launch", f"Launching {app.name}...")
    
    def back_to_previous_view(self):
        """Go back to the previous view"""
        if self.current_view == ViewMode.DETAILS:
            if hasattr(self, '_previous_view'):
                self.current_view = self._previous_view
            else:
                self.current_view = ViewMode.CATALOG
        
        if self.current_view == ViewMode.CATALOG:
            self.show_catalog()
        elif self.current_view == ViewMode.INSTALLED:
            self.show_installed()
        elif self.current_view == ViewMode.SEARCH:
            self.display_search_results()
    
    def refresh_catalog(self):
        """Refresh the app catalog"""
        self.status_var.set("Refreshing catalog...")

        def do_refresh():
            # In a real implementation, this would sync with federated indexes
            time.sleep(1)  # Simulate refresh

            # Schedule UI updates on main thread
            self.root.after(0, lambda: self.status_var.set("Catalog refreshed"))
            self.root.after(0, self.show_catalog)

        threading.Thread(target=do_refresh, daemon=True).start()
    
    def refresh_installed(self):
        """Refresh the installed apps view"""
        self.show_installed()
    
    def on_installed_select(self, listbox):
        """Handle selection in installed apps list"""
        selection = listbox.curselection()
        if selection:
            selected_idx = selection[0]
            # In a real implementation, show details for selected app
            pass
    
    def run(self):
        """Start the UI"""
        self.root.mainloop()


# Mobile UI would be implemented separately using a framework like Kivy
# For now, we'll just define the structure
class MobileAppStoreUI:
    """Mobile UI for the alternative app store (conceptual)"""
    
    def __init__(self, index_manager, security_manager):
        self.index_manager = index_manager
        self.security_manager = security_manager
        # Mobile UI would use Kivy or similar framework
        pass
    
    def setup_mobile_ui(self):
        """Set up mobile-specific UI elements"""
        # This would implement mobile-specific interface
        pass
    
    def run(self):
        """Start the mobile UI"""
        # This would start the mobile application
        pass


# Example usage and test
if __name__ == "__main__":
    # Create managers for the UI
    index_manager = FederatedIndexManager("ui-test-node")
    security_manager = SecurityManager()
    
    # Add a test app to the index
    from ..storage.indexes.federated import AppEntry
    test_app = AppEntry(
        app_id="test.ui-app",
        manifest_hash="sha256:abc123",
        artifact_hash="sha256:def456",
        trust_score=0.92,
        publisher="did:test:123",
        version="1.0.0",
        timestamp="2026-01-20T10:00:00Z",
        signature=""
    )
    index_manager.add_app(test_app)
    
    # Create and run the UI
    print("Starting App Store UI...")
    print("Note: This requires tkinter to be available on your system")
    
    try:
        ui = AppStoreUI(index_manager, security_manager)
        ui.run()
    except tk.TclError as e:
        print(f"Tkinter error (UI may not be available in this environment): {e}")
        print("The UI code is implemented but cannot run in this environment")
    except Exception as e:
        print(f"Error starting UI: {e}")