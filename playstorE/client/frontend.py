"""
Design-Focused Frontend Framework for AltStore.

Provides an intuitive, beautiful UI for discovering, installing, and running apps.
Features:
- GitHub project explorer with live search
- App catalog with rich cards
- One-click install workflow
- Progress visualization
- Trust/security indicators
- Offline status indication

Built with a focus on non-technical users while maintaining transparency.
"""

from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass
import json
import html
from ..core.security.trust_model import TrustLevel as CoreTrustLevel


class TrustLevel(Enum):
    """Visual trust indicators"""
    VERIFIED = "verified"       # 🔒 Green checkmark - signed by publisher
    REPRODUCIBLE = "reproducible"  # 🟡 Amber circle - open source, reproducible
    UNVERIFIED = "unverified"   # 🔴 Red circle - unverified, sandboxed only
    UNKNOWN = "unknown"         # ⚪ Gray circle - trust data not available


def map_trust_for_frontend(trust: CoreTrustLevel) -> TrustLevel:
    """Map core trust level to frontend trust level, handling missing UNKNOWN value"""
    if trust == CoreTrustLevel.VERIFIED:
        return TrustLevel.VERIFIED
    elif trust == CoreTrustLevel.REPRODUCIBLE:
        return TrustLevel.REPRODUCIBLE
    elif trust == CoreTrustLevel.COMMUNITY:
        return TrustLevel.UNKNOWN  # Map COMMUNITY to UNKNOWN for frontend display
    elif trust == CoreTrustLevel.UNVERIFIED:
        return TrustLevel.UNVERIFIED
    else:
        return TrustLevel.UNKNOWN


class InstallationState(Enum):
    """Installation progress states"""
    IDLE = "idle"
    ANALYZING = "analyzing"
    BUILDING = "building"
    DOWNLOADING = "downloading"
    INSTALLING = "installing"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class UITheme:
    """Consistent UI theme for AltStore"""
    # Colors
    primary = "#2563eb"      # Blue
    success = "#16a34a"      # Green
    warning = "#ea580c"      # Orange
    danger = "#dc2626"       # Red
    neutral = "#6b7280"      # Gray
    
    # Dark mode
    dark_bg = "#0f172a"
    dark_surface = "#1e293b"
    dark_text = "#f1f5f9"
    
    # Light mode
    light_bg = "#ffffff"
    light_surface = "#f8fafc"
    light_text = "#0f172a"


class AppCard:
    """
    Rich app display component.
    
    Shows:
    - App icon/screenshot
    - Name, publisher, description
    - Trust level indicator
    - Star rating
    - Install button
    - More info expandable
    """
    
    def __init__(
        self,
        app_id: str,
        name: str,
        description: str,
        publisher: str,
        icon_url: Optional[str] = None,
        screenshot_url: Optional[str] = None,
        trust_level: TrustLevel = TrustLevel.UNVERIFIED,
        stars: float = 0.0,
        download_count: int = 0,
        tags: List[str] = None
    ):
        self.app_id = app_id
        self.name = name
        self.description = description
        self.publisher = publisher
        self.icon_url = icon_url
        self.screenshot_url = screenshot_url
        self.trust_level = trust_level
        self.stars = stars
        self.download_count = download_count
        self.tags = tags or []
    
    def to_html(self) -> str:
        """Render as HTML card"""
        trust_icons = {
            TrustLevel.VERIFIED: "🔒",
            TrustLevel.REPRODUCIBLE: "🟡",
            TrustLevel.UNVERIFIED: "🔴",
            TrustLevel.UNKNOWN: "⚪"
        }

        trust_colors = {
            TrustLevel.VERIFIED: "#16a34a",
            TrustLevel.REPRODUCIBLE: "#ea580c",
            TrustLevel.UNVERIFIED: "#dc2626",
            TrustLevel.UNKNOWN: "#6b7280"
        }

        # Escape all user-provided data to prevent XSS
        safe_app_id = html.escape(self.app_id, quote=True)
        safe_name = html.escape(self.name, quote=True)
        safe_publisher = html.escape(self.publisher, quote=True)
        safe_description = html.escape(self.description, quote=True)
        safe_tags = [html.escape(tag, quote=True) for tag in self.tags]
        
        # Sanitize icon URL to prevent javascript: or data: URIs
        safe_icon_url = self.icon_url
        if self.icon_url and self.icon_url.startswith(('http://', 'https://')):
            safe_icon_url = html.escape(self.icon_url, quote=True)
        else:
            safe_icon_url = None  # Don't render unsafe URLs

        html_str = f"""
<div class="app-card" data-app-id="{safe_app_id}">
    <div class="app-card-header">
        {'<img src="' + safe_icon_url + '" class="app-icon" />' if safe_icon_url else '<div class="app-icon-placeholder">📦</div>'}
        <div class="app-info">
            <h3 class="app-name">{safe_name}</h3>
            <p class="app-publisher">by {safe_publisher}</p>
            <div class="app-meta">
                <span class="trust-indicator" style="color: {trust_colors[self.trust_level]}">
                    {trust_icons[self.trust_level]} {self.trust_level.value.capitalize()}
                </span>
                <span class="app-stars">⭐ {self.stars:.1f}</span>
                <span class="app-downloads">{self.download_count} downloads</span>
            </div>
        </div>
    </div>

    <p class="app-description">{safe_description}</p>

    {'<div class="app-tags">' + ''.join(f'<span class="tag">{tag}</span>' for tag in safe_tags) + '</div>' if safe_tags else ''}

    <div class="app-actions">
        <button class="btn btn-primary install-btn" onclick="installApp('{safe_app_id}')">
            ⬇️ Install
        </button>
        <button class="btn btn-secondary more-info-btn" onclick="expandCard('{safe_app_id}')">
            More Info
        </button>
    </div>
</div>
"""
        return html_str
    
    def to_json(self) -> Dict:
        """Export as JSON for API"""
        return {
            "app_id": self.app_id,
            "name": self.name,
            "description": self.description,
            "publisher": self.publisher,
            "icon_url": self.icon_url,
            "screenshot_url": self.screenshot_url,
            "trust_level": self.trust_level.value,
            "stars": self.stars,
            "download_count": self.download_count,
            "tags": self.tags
        }


class InstallationProgress:
    """
    Real-time installation progress display.
    
    Shows step-by-step progress with:
    - Progress bar
    - Current step indicator
    - Estimated time
    - Pause/cancel buttons
    """
    
    def __init__(self, app_name: str, app_id: str):
        self.app_name = app_name
        self.app_id = app_id
        self.state = InstallationState.IDLE
        self.progress = 0
        self.current_step = ""
        self.steps_completed = 0
        self.total_steps = 0
    
    def set_state(self, state: InstallationState, step: str = ""):
        """Update installation state"""
        self.state = state
        self.current_step = step
    
    def set_progress(self, progress: int, steps_completed: int, total_steps: int):
        """Update progress percentage"""
        self.progress = max(0, min(100, progress))
        self.steps_completed = steps_completed
        self.total_steps = total_steps
    
    def to_html(self) -> str:
        """Render progress display"""
        state_messages = {
            InstallationState.IDLE: "Ready to install...",
            InstallationState.ANALYZING: "Analyzing repository...",
            InstallationState.BUILDING: "Building application...",
            InstallationState.DOWNLOADING: "Downloading files...",
            InstallationState.INSTALLING: "Installing...",
            InstallationState.COMPLETE: "Installation complete!",
            InstallationState.FAILED: "Installation failed!"
        }

        state_colors = {
            InstallationState.IDLE: "#6b7280",
            InstallationState.ANALYZING: "#2563eb",
            InstallationState.BUILDING: "#2563eb",
            InstallationState.DOWNLOADING: "#2563eb",
            InstallationState.INSTALLING: "#2563eb",
            InstallationState.COMPLETE: "#16a34a",
            InstallationState.FAILED: "#dc2626"
        }

        # Escape user-provided data to prevent XSS
        safe_app_name = html.escape(self.app_name, quote=True)
        safe_current_step = html.escape(self.current_step, quote=True) if self.current_step else ""

        html_str = f"""
<div class="installation-progress">
    <h2>{safe_app_name}</h2>

    <div class="progress-bar-container">
        <div class="progress-bar" style="width: {self.progress}%; background-color: {state_colors[self.state]}">
        </div>
    </div>

    <p class="progress-percentage">{self.progress}% - {self.steps_completed}/{self.total_steps} steps</p>

    <p class="progress-status" style="color: {state_colors[self.state]}">
        {state_messages[self.state]}
    </p>

    {'<p class="progress-detail">' + safe_current_step + '</p>' if self.current_step else ''}

    <div class="progress-actions">
        {'<button class="btn btn-secondary" onclick="pauseInstallation()">⏸️ Pause</button>' if self.state in [InstallationState.DOWNLOADING, InstallationState.BUILDING] else ''}
        {'<button class="btn btn-danger" onclick="cancelInstallation()">✕ Cancel</button>' if self.state not in [InstallationState.IDLE, InstallationState.COMPLETE, InstallationState.FAILED] else ''}
    </div>
</div>
"""
        return html_str


class GitHubSearch:
    """
    GitHub repository search interface.
    
    Features:
    - Live search with autocomplete
    - Filter by language, stars, topics
    - Direct GitHub link
    - Analyze button for one-click setup
    """
    
    def __init__(self, on_search: Callable = None, on_select: Callable = None):
        self.on_search = on_search
        self.on_select = on_select
        self.search_results: List[Dict] = []
    
    def to_html(self) -> str:
        """Render search interface"""
        html = """
<div class="github-search">
    <div class="search-header">
        <h2>GitHub Project Explorer</h2>
        <p>Turn any GitHub repo into a one-click app</p>
    </div>
    
    <div class="search-box">
        <input
            type="text"
            class="search-input"
            placeholder="Search GitHub repos (e.g., 'ripgrep', 'fastapi', 'ollama')..."
            onkeyup="searchGitHub(this.value)"
            id="github-search-input"
        />
        <button class="search-btn" onclick="executeSearch()">🔍 Search</button>
    </div>
    
    <div class="search-filters">
        <label>
            Language:
            <select onchange="updateLanguageFilter(this.value)">
                <option value="">All</option>
                <option value="python">Python</option>
                <option value="rust">Rust</option>
                <option value="go">Go</option>
                <option value="javascript">JavaScript</option>
                <option value="typescript">TypeScript</option>
                <option value="c">C</option>
                <option value="java">Java</option>
            </select>
        </label>
        
        <label>
            Min Stars:
            <select onchange="updateStarsFilter(this.value)">
                <option value="">Any</option>
                <option value="10">10+</option>
                <option value="100">100+</option>
                <option value="1000">1000+</option>
                <option value="10000">10000+</option>
            </select>
        </label>
    </div>
    
    <div class="search-results" id="search-results">
        <!-- Results populated dynamically -->
    </div>
</div>

<style>
    .github-search {
        padding: 20px;
        background: #f8fafc;
        border-radius: 12px;
    }
    
    .search-header h2 {
        margin: 0 0 5px 0;
        color: #0f172a;
    }
    
    .search-header p {
        margin: 0 0 20px 0;
        color: #6b7280;
        font-size: 14px;
    }
    
    .search-box {
        display: flex;
        gap: 10px;
        margin-bottom: 15px;
    }
    
    .search-input {
        flex: 1;
        padding: 10px 15px;
        border: 2px solid #e2e8f0;
        border-radius: 8px;
        font-size: 14px;
    }
    
    .search-input:focus {
        outline: none;
        border-color: #2563eb;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
    }
    
    .search-btn {
        padding: 10px 20px;
        background: #2563eb;
        color: white;
        border: none;
        border-radius: 8px;
        cursor: pointer;
        font-weight: 600;
    }
    
    .search-btn:hover {
        background: #1d4ed8;
    }
    
    .search-filters {
        display: flex;
        gap: 15px;
        margin-bottom: 20px;
    }
    
    .search-filters label {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 14px;
    }
    
    .search-filters select {
        padding: 6px 10px;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        font-size: 14px;
    }
</style>
"""
        return html


class AppCatalog:
    """
    Main app catalog display.
    
    Shows:
    - Featured apps
    - Recent installations
    - Categories
    - Search results
    """
    
    def __init__(self):
        self.featured_apps: List[AppCard] = []
        self.recent_installs: List[AppCard] = []
        self.categories: Dict[str, List[AppCard]] = {}
    
    def add_featured_app(self, card: AppCard):
        """Add app to featured section"""
        self.featured_apps.append(card)
    
    def add_category(self, category_name: str, apps: List[AppCard]):
        """Add category with apps"""
        self.categories[category_name] = apps
    
    def to_html(self) -> str:
        """Render catalog"""
        output = """
<div class="app-catalog">
    <div class="catalog-section">
        <h2>Featured Apps</h2>
        <div class="apps-grid">
"""
        for app in self.featured_apps:
            output += app.to_html()

        output += """
        </div>
    </div>
"""

        for category, apps in self.categories.items():
            safe_category = html.escape(category)
            output += f"""
    <div class="catalog-section">
        <h2>{safe_category}</h2>
        <div class="apps-grid">
"""
            for app in apps:
                output += app.to_html()
            output += """
        </div>
    </div>
"""

        return output
        
        html += """
</div>

<style>
    .app-catalog {
        padding: 20px;
    }
    
    .catalog-section {
        margin-bottom: 40px;
    }
    
    .catalog-section h2 {
        color: #0f172a;
        margin-bottom: 20px;
    }
    
    .apps-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: 20px;
    }
    
    .app-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px;
        transition: all 0.3s ease;
        cursor: pointer;
    }
    
    .app-card:hover {
        border-color: #2563eb;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.15);
        transform: translateY(-2px);
    }
    
    .app-card-header {
        display: flex;
        gap: 12px;
        margin-bottom: 12px;
    }
    
    .app-icon {
        width: 48px;
        height: 48px;
        border-radius: 8px;
        object-fit: cover;
    }
    
    .app-icon-placeholder {
        width: 48px;
        height: 48px;
        background: #f1f5f9;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
    }
    
    .app-info {
        flex: 1;
    }
    
    .app-name {
        margin: 0;
        font-size: 16px;
        font-weight: 600;
        color: #0f172a;
    }
    
    .app-publisher {
        margin: 4px 0;
        font-size: 12px;
        color: #6b7280;
    }
    
    .app-meta {
        display: flex;
        gap: 12px;
        font-size: 12px;
        color: #6b7280;
        margin-top: 6px;
    }
    
    .trust-indicator {
        font-weight: 600;
    }
    
    .app-description {
        margin: 12px 0;
        font-size: 13px;
        color: #4b5563;
        line-height: 1.5;
    }
    
    .app-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin: 12px 0;
    }
    
    .tag {
        display: inline-block;
        padding: 4px 8px;
        background: #f1f5f9;
        color: #475569;
        border-radius: 4px;
        font-size: 11px;
    }
    
    .app-actions {
        display: flex;
        gap: 8px;
        margin-top: 12px;
    }
    
    .btn {
        flex: 1;
        padding: 8px 12px;
        border: none;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    
    .btn-primary {
        background: #2563eb;
        color: white;
    }
    
    .btn-primary:hover {
        background: #1d4ed8;
    }
    
    .btn-secondary {
        background: #f1f5f9;
        color: #0f172a;
        border: 1px solid #e2e8f0;
    }
    
    .btn-secondary:hover {
        background: #e2e8f0;
    }
    
    .btn-danger {
        background: #dc2626;
        color: white;
    }
    
    .btn-danger:hover {
        background: #b91c1c;
    }
</style>
"""
        return html


class MainUI:
    """
    Main AltStore UI framework.
    
    Orchestrates:
    - Navigation
    - App discovery (catalog + GitHub explorer)
    - Installation workflow
    - Library management
    - Settings
    """
    
    def __init__(self):
        self.catalog = AppCatalog()
        self.github_search = GitHubSearch()
        self.current_view = "catalog"
        self.theme = UITheme()
    
    def to_html(self) -> str:
        """Render complete UI"""
        html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AltStore - Universal App Store</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
            background: #f8fafc;
            color: #0f172a;
        }
        
        .main-container {
            display: flex;
            min-height: 100vh;
        }
        
        .sidebar {
            width: 250px;
            background: white;
            border-right: 1px solid #e2e8f0;
            padding: 20px;
            position: fixed;
            height: 100vh;
            overflow-y: auto;
        }
        
        .sidebar-logo {
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 30px;
            color: #2563eb;
        }
        
        .sidebar-nav {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        .nav-item {
            padding: 12px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
            color: #6b7280;
        }
        
        .nav-item:hover {
            background: #f1f5f9;
            color: #2563eb;
        }
        
        .nav-item.active {
            background: #2563eb;
            color: white;
        }
        
        .content {
            margin-left: 250px;
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        
        .header {
            background: white;
            border-bottom: 1px solid #e2e8f0;
            padding: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header-title {
            font-size: 20px;
            font-weight: 600;
        }
        
        .header-status {
            display: flex;
            gap: 15px;
            align-items: center;
            font-size: 12px;
        }
        
        .offline-indicator {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 10px;
            background: #fed7aa;
            color: #92400e;
            border-radius: 6px;
            font-weight: 600;
        }
        
        .main-content {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
        }
        
        .view {
            display: none;
        }
        
        .view.active {
            display: block;
        }
    </style>
</head>
<body>
    <div class="main-container">
        <div class="sidebar">
            <div class="sidebar-logo">📦 AltStore</div>
            <nav class="sidebar-nav">
                <div class="nav-item active" onclick="switchView('catalog')">
                    🏠 Discover
                </div>
                <div class="nav-item" onclick="switchView('github')">
                    <span style="color: #6f42c1;">⚙️</span> GitHub Explorer
                </div>
                <div class="nav-item" onclick="switchView('library')">
                    📚 My Apps
                </div>
                <div class="nav-item" onclick="switchView('settings')">
                    ⚙️ Settings
                </div>
            </nav>
        </div>
        
        <div class="content">
            <div class="header">
                <div class="header-title">AltStore - Universal App Store</div>
                <div class="header-status">
                    <div class="offline-indicator" id="offline-status" style="display: none;">
                        📡 Offline Mode
                    </div>
                </div>
            </div>
            
            <div class="main-content">
                <div id="catalog-view" class="view active">
"""
        html += self.catalog.to_html()
        html += """
                </div>
                
                <div id="github-view" class="view">
"""
        html += self.github_search.to_html()
        html += """
                </div>
                
                <div id="library-view" class="view">
                    <h2>My Installed Apps</h2>
                    <p>Your installed applications will appear here.</p>
                </div>
                
                <div id="settings-view" class="view">
                    <h2>Settings</h2>
                    <p>Settings and preferences coming soon.</p>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        function switchView(viewName) {
            // Hide all views
            document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            
            // Show selected view
            document.getElementById(viewName + '-view').classList.add('active');
            event.currentTarget.classList.add('active');
        }
        
        function installApp(appId) {
            alert('Installing: ' + appId);
            // Would trigger installation workflow
        }
        
        function expandCard(appId) {
            alert('More info for: ' + appId);
            // Would expand card with more details
        }
        
        function searchGitHub(query) {
            console.log('Searching GitHub:', query);
            // Would trigger live search
        }
        
        function executeSearch() {
            const query = document.getElementById('github-search-input').value;
            if (query) {
                console.log('Execute search:', query);
            }
        }
    </script>
</body>
</html>
"""
        return html
    
    def generate_html_file(self, output_path: str = "altstore_ui.html"):
        """Generate standalone HTML file"""
        with open(output_path, "w") as f:
            f.write(self.to_html())
        print(f"Generated UI: {output_path}")


# Example usage
if __name__ == "__main__":
    # Create UI
    ui = MainUI()
    
    # Add featured apps
    ui.catalog.add_featured_app(AppCard(
        app_id="com.ripgrep.ripgrep",
        name="ripgrep",
        description="A line-oriented search tool that recursively searches your codebase",
        publisher="BurntSushi",
        trust_level=TrustLevel.VERIFIED,
        stars=50000,
        download_count=1000000,
        tags=["CLI", "Search", "Rust"]
    ))
    
    ui.catalog.add_featured_app(AppCard(
        app_id="com.ollamahq.ollama",
        name="Ollama",
        description="Get up and running with large language models locally",
        publisher="Ollama",
        trust_level=TrustLevel.REPRODUCIBLE,
        stars=35000,
        download_count=500000,
        tags=["AI", "LLM", "Local"]
    ))
    
    # Generate HTML
    ui.generate_html_file()
