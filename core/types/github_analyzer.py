"""
GitHub repository auto-detection and classification system for the alternative app store platform.
Implements intelligent detection of runnable applications from GitHub repositories.
Based on the scouts.md specification for GitHub auto-detection.
"""
import os
import re
import json
import yaml
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum
from dataclasses import dataclass
import requests
from pathlib import Path
import subprocess
from ..core.types.manifest_schema import RuntimeType, AppManifest, Publisher, Source, Versions, Build, Run, Security, Trust


class RepoArchetype(Enum):
    """Repository archetype classifications"""
    CLI_TOOL = "cli"
    SERVER_APP = "server"
    DESKTOP_GUI = "desktop"
    MODEL_AI_APP = "model_ai"
    LIBRARY = "library"
    DEMO_PLAYGROUND = "demo"
    INFRA_CONFIG = "infra"


@dataclass
class RepoSignals:
    """Signals extracted from repository analysis"""
    has_release_binary: bool = False
    has_dockerfile: bool = False
    has_run_command: bool = False
    readme_signals: List[str] = None
    language_breakdown: Dict[str, int] = None
    build_files: List[str] = None
    config_files: List[str] = None
    ports_mentioned: List[int] = None
    network_indicators: List[str] = None
    
    def __post_init__(self):
        if self.readme_signals is None:
            self.readme_signals = []
        if self.language_breakdown is None:
            self.language_breakdown = {}
        if self.build_files is None:
            self.build_files = []
        if self.config_files is None:
            self.config_files = []
        if self.ports_mentioned is None:
            self.ports_mentioned = []
        if self.network_indicators is None:
            self.network_indicators = []


@dataclass
class ClassificationResult:
    """Result of repository classification"""
    archetype: RepoArchetype
    confidence: float
    reasons: List[str]
    signals: RepoSignals
    build_strategy: Optional[Dict] = None


class GitHubRepoAnalyzer:
    """Analyzes GitHub repositories to detect runnable applications"""
    
    def __init__(self, github_token: Optional[str] = None):
        self.github_token = github_token
        self.session = requests.Session()
        if github_token:
            self.session.headers.update({"Authorization": f"Bearer {github_token}"})
        
        # Common file patterns that indicate runnable applications
        self.runnable_indicators = {
            'Dockerfile': 30,
            'docker-compose.yml': 30,
            'requirements.txt': 20,
            'pyproject.toml': 20,
            'package.json': 20,
            'go.mod': 20,
            'Cargo.toml': 20,
            'Makefile': 15,
            '.env.example': 15,
            'setup.py': 10,
            'pom.xml': 10,
            'build.gradle': 10,
            'Gemfile': 10,
            'composer.json': 10,
        }
        
        # Common port indicators for different frameworks
        self.port_indicators = {
            'flask': 5000,
            'fastapi': 8000,
            'gradio': 7860,
            'react': 3000,
            'vue': 8080,
            'angular': 4200,
            'express': 3000,
            'django': 8000,
        }
    
    def analyze_repo(self, repo_url: str) -> ClassificationResult:
        """
        Analyze a GitHub repository to detect if it's a runnable application.
        
        Args:
            repo_url: URL of the GitHub repository
            
        Returns:
            Classification result with archetype and confidence
        """
        # Extract owner and repo name from URL
        repo_parts = repo_url.rstrip('/').split('/')[-2:]
        owner, repo = repo_parts[-2], repo_parts[-1]
        
        # Get repository information
        repo_info = self._get_repo_info(owner, repo)
        if not repo_info:
            raise ValueError(f"Could not access repository: {repo_url}")
        
        # Clone repository temporarily
        temp_dir = self._clone_repo(repo_url)
        try:
            # Extract signals from the repository
            signals = self._extract_signals(temp_dir, repo_info)
            
            # Classify the repository
            classification = self._classify_repo(signals, temp_dir, repo_url)

            # Determine build strategy
            build_strategy = self._determine_build_strategy(signals, temp_dir)
            classification.build_strategy = build_strategy

            return classification
        finally:
            # Clean up temporary directory
            self._cleanup_temp_dir(temp_dir)
    
    def _get_repo_info(self, owner: str, repo: str) -> Optional[Dict]:
        """Get repository information from GitHub API"""
        url = f"https://api.github.com/repos/{owner}/{repo}"
        try:
            response = self.session.get(url)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Warning: Could not fetch repo info: {response.status_code}")
                return None
        except Exception as e:
            print(f"Warning: Error fetching repo info: {e}")
            return None
    
    def _clone_repo(self, repo_url: str) -> str:
        """Clone repository to temporary directory"""
        import tempfile
        temp_dir = tempfile.mkdtemp(prefix="altstore_github_")
        
        try:
            subprocess.run(['git', 'clone', repo_url, temp_dir], 
                         check=True, capture_output=True)
            return temp_dir
        except subprocess.CalledProcessError:
            raise RuntimeError(f"Failed to clone repository: {repo_url}")
    
    def _cleanup_temp_dir(self, temp_dir: str):
        """Clean up temporary directory"""
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    def _extract_signals(self, repo_path: str, repo_info: Dict) -> RepoSignals:
        """Extract signals from repository files"""
        signals = RepoSignals()
        
        # Analyze file structure
        for root, dirs, files in os.walk(repo_path):
            for file in files:
                filepath = os.path.join(root, file)
                
                # Check for runnable indicators
                if file in self.runnable_indicators:
                    signals.build_files.append(file)
                
                # Check for Dockerfile
                if file.lower() == 'dockerfile':
                    signals.has_dockerfile = True
                
                # Check for common config files
                if file in ['.env.example', 'config.json', 'settings.yaml']:
                    signals.config_files.append(file)
                
                # Analyze README for run instructions
                if file.lower().startswith('readme'):
                    readme_content = self._read_file(filepath)
                    signals.readme_signals.extend(self._parse_readme(readme_content))
        
        # Analyze language breakdown
        signals.language_breakdown = self._analyze_languages(repo_path)
        
        # Check for release binaries in GitHub info
        # This would typically come from GitHub API for releases
        # For now, we'll simulate based on file analysis
        signals.has_release_binary = any(
            ext in ['.exe', '.deb', '.rpm', '.dmg', '.pkg', '.zip', '.tar.gz'] 
            for ext in self._get_file_extensions(repo_path)
        )
        
        # Extract run commands from README
        readme_path = os.path.join(repo_path, 'README.md')
        if os.path.exists(readme_path):
            with open(readme_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                signals.has_run_command = bool(self._extract_run_commands(content))
        
        return signals
    
    def _parse_readme(self, content: str) -> List[str]:
        """Parse README content for runnable signals"""
        signals = []
        
        # Look for common run patterns
        run_patterns = [
            r'```(?:bash|sh|console)?\s*(?:\$\s*)?(npm start|npm run|yarn start|python.*\.py|go run|cargo run|make run)',
            r'(?:to )?(?:run|start|execute).*?(?:with|using|by).*?(?:`|")([^`\n"]+)(?:`|")',
            r'(?:usage|quick start|getting started).*?\n\s*(```[\s\S]*?```)',
            r'(?:installation|setup|quickstart).*?\n\s*(```[\s\S]*?```)',
        ]
        
        for pattern in run_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            signals.extend(matches)
        
        # Look for port mentions
        port_pattern = r'(?:port|listen on|running on|serving at).*?(\d{4,5})'
        port_matches = re.findall(port_pattern, content, re.IGNORECASE)
        for match in port_matches:
            try:
                signals.append(f"port:{match}")
            except ValueError:
                pass
        
        return signals
    
    def _analyze_languages(self, repo_path: str) -> Dict[str, int]:
        """Analyze language breakdown in repository"""
        languages = {}
        
        # Count files by extension
        for root, dirs, files in os.walk(repo_path):
            for file in files:
                _, ext = os.path.splitext(file)
                if ext:
                    languages[ext] = languages.get(ext, 0) + 1
        
        return languages
    
    def _get_file_extensions(self, repo_path: str) -> List[str]:
        """Get all file extensions in repository"""
        extensions = set()
        for root, dirs, files in os.walk(repo_path):
            for file in files:
                _, ext = os.path.splitext(file)
                if ext:
                    extensions.add(ext)
        return list(extensions)
    
    def _read_file(self, filepath: str) -> str:
        """Safely read a file"""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except:
            return ""
    
    def _extract_run_commands(self, content: str) -> List[str]:
        """Extract potential run commands from content"""
        commands = []
        
        # Patterns for common run commands
        patterns = [
            r'```(?:bash|sh|console)?\s*(?:\$\s*)?((?:npm|yarn|pip|python|go|cargo|make)\s+(?:start|run|install|build)[^\n]*)',
            r'`(npm\s+start|yarn\s+start|python\s+.*\.py|go\s+run.*|cargo\s+run.*)`',
            r'^\s*(npm\s+start|yarn\s+start|python\s+.*\.py|go\s+run.*|cargo\s+run.*)\s*$',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
            commands.extend(matches)
        
        return list(set(commands))  # Remove duplicates
    
    def _classify_repo(self, signals: RepoSignals, repo_path: str, repo_url: str = "") -> ClassificationResult:
        """Classify repository based on extracted signals"""
        scores = {
            RepoArchetype.CLI_TOOL: 0,
            RepoArchetype.SERVER_APP: 0,
            RepoArchetype.DESKTOP_GUI: 0,
            RepoArchetype.MODEL_AI_APP: 0,
            RepoArchetype.LIBRARY: 0,
            RepoArchetype.DEMO_PLAYGROUND: 0,
            RepoArchetype.INFRA_CONFIG: 0,
        }
        
        reasons = []
        
        # Score based on file indicators
        if signals.has_dockerfile:
            scores[RepoArchetype.SERVER_APP] += 20
            reasons.append("Dockerfile detected")
        
        if 'requirements.txt' in signals.build_files or 'pyproject.toml' in signals.build_files:
            scores[RepoArchetype.SERVER_APP] += 10
            scores[RepoArchetype.MODEL_AI_APP] += 15
            reasons.append("Python dependencies detected")
        
        if 'package.json' in signals.build_files:
            scores[RepoArchetype.SERVER_APP] += 15
            scores[RepoArchetype.DESKTOP_GUI] += 10  # Could be Electron
            reasons.append("Node.js dependencies detected")
        
        if 'go.mod' in signals.build_files:
            scores[RepoArchetype.CLI_TOOL] += 15
            scores[RepoArchetype.SERVER_APP] += 10
            reasons.append("Go module detected")
        
        if 'Cargo.toml' in signals.build_files:
            scores[RepoArchetype.CLI_TOOL] += 20
            reasons.append("Rust crate detected")
        
        if signals.has_run_command:
            scores[RepoArchetype.CLI_TOOL] += 10
            scores[RepoArchetype.SERVER_APP] += 10
            reasons.append("Run command detected in README")
        
        # Score based on language breakdown
        lang_counts = signals.language_breakdown
        if '.py' in lang_counts:
            scores[RepoArchetype.MODEL_AI_APP] += min(lang_counts['.py'] * 2, 20)
            scores[RepoArchetype.SERVER_APP] += min(lang_counts['.py'], 15)
        
        if '.js' in lang_counts or '.ts' in lang_counts:
            scores[RepoArchetype.SERVER_APP] += min((lang_counts.get('.js', 0) + lang_counts.get('.ts', 0)), 15)
            scores[RepoArchetype.DESKTOP_GUI] += min((lang_counts.get('.js', 0) + lang_counts.get('.ts', 0)) // 2, 10)
        
        if '.rs' in lang_counts:
            scores[RepoArchetype.CLI_TOOL] += min(lang_counts['.rs'] * 3, 30)
        
        if '.go' in lang_counts:
            scores[RepoArchetype.CLI_TOOL] += min(lang_counts['.go'] * 2, 20)
        
        # Check for library indicators
        if any(lib_file in signals.build_files for lib_file in ['setup.py', 'pom.xml', 'build.gradle']):
            scores[RepoArchetype.LIBRARY] += 25
            reasons.append("Library build file detected")
        
        # Check for demo/tutorial indicators
        # Use the actual repo name from the URL instead of the temp directory name
        repo_parts = repo_url.rstrip('/').split('/')[-2:]
        actual_repo_name = repo_parts[-1].lower()
        if any(indicator in actual_repo_name for indicator in ['demo', 'tutorial', 'example', 'sample']):
            scores[RepoArchetype.DEMO_PLAYGROUND] += 30
            reasons.append("Repository name suggests demo/example")
        
        # Check for infrastructure indicators
        if any(infra_file in signals.build_files for infra_file in ['Dockerfile', 'docker-compose.yml', 'terraform.tf', 'main.tf']):
            scores[RepoArchetype.INFRA_CONFIG] += 20
            reasons.append("Infrastructure configuration detected")
        
        # Adjust scores based on negative signals
        # If mostly documentation, likely a library or demo
        doc_files = [f for f in os.listdir(repo_path) if f.lower().startswith('readme') or f.lower().endswith('.md')]
        code_files = [f for f in os.listdir(repo_path) if f.endswith(('.py', '.js', '.ts', '.go', '.rs', '.java', '.cpp', '.c'))]
        
        if len(doc_files) > len(code_files) * 2:
            scores[RepoArchetype.LIBRARY] += 15
            scores[RepoArchetype.DEMO_PLAYGROUND] += 10
        
        # Find the archetype with the highest score
        best_archetype = max(scores, key=scores.get)
        confidence = min(scores[best_archetype] / 100.0, 1.0)  # Normalize to 0-1
        
        # Special handling for libraries
        if scores[RepoArchetype.LIBRARY] > scores[best_archetype]:
            best_archetype = RepoArchetype.LIBRARY
            confidence = min(scores[RepoArchetype.LIBRARY] / 100.0, 1.0)
        
        return ClassificationResult(
            archetype=best_archetype,
            confidence=confidence,
            reasons=reasons,
            signals=signals
        )
    
    def _determine_build_strategy(self, signals: RepoSignals, repo_path: str) -> Dict:
        """Determine the appropriate build strategy for the repository"""
        strategy = {
            "type": "script",
            "base_image": None,
            "steps": [],
            "environment": {}
        }
        
        # If Dockerfile exists, use Docker strategy
        if signals.has_dockerfile:
            strategy["type"] = "docker"
            strategy["base_image"] = self._infer_base_image_from_dockerfile(repo_path)
            return strategy
        
        # Determine strategy based on primary language
        lang_breakdown = signals.language_breakdown
        
        if '.py' in lang_breakdown:
            strategy["type"] = "script"
            strategy["steps"] = [
                "pip install -r requirements.txt",
                "python app.py"  # This would be more sophisticated in practice
            ]
            strategy["environment"]["type"] = "python:3.11"
        
        elif '.js' in lang_breakdown or '.ts' in lang_breakdown:
            strategy["type"] = "script"
            strategy["steps"] = [
                "npm install",
                "npm start"
            ]
            strategy["environment"]["type"] = "node:18"
        
        elif '.go' in lang_breakdown:
            strategy["type"] = "native"
            strategy["steps"] = [
                "go build -o app .",
                "./app"
            ]
            strategy["environment"]["type"] = "golang:1.21"
        
        elif '.rs' in lang_breakdown:
            strategy["type"] = "native"
            strategy["steps"] = [
                "cargo build --release",
                "./target/release/app"
            ]
            strategy["environment"]["type"] = "rust:1.70"
        
        else:
            # Default to generic approach
            strategy["type"] = "script"
            strategy["steps"] = ["echo 'No specific build strategy detected'"]
        
        return strategy
    
    def _infer_base_image_from_dockerfile(self, repo_path: str) -> Optional[str]:
        """Infer base image from Dockerfile"""
        dockerfile_path = os.path.join(repo_path, 'Dockerfile')
        if not os.path.exists(dockerfile_path):
            dockerfile_path = os.path.join(repo_path, 'dockerfile')
        
        if os.path.exists(dockerfile_path):
            with open(dockerfile_path, 'r') as f:
                content = f.read()
                # Look for FROM instruction
                match = re.search(r'^FROM\s+(.+)', content, re.MULTILINE | re.IGNORECASE)
                if match:
                    return match.group(1).strip()
        
        return None


class GitHubAutoWrapper:
    """Main class for GitHub auto-wrapping functionality"""
    
    def __init__(self, github_token: Optional[str] = None):
        self.analyzer = GitHubRepoAnalyzer(github_token)
    
    def create_manifest_from_repo(self, repo_url: str) -> Optional[AppManifest]:
        """
        Create an AppManifest from a GitHub repository.
        
        Args:
            repo_url: URL of the GitHub repository
            
        Returns:
            AppManifest if the repo appears to be a runnable application, None otherwise
        """
        try:
            classification = self.analyzer.analyze_repo(repo_url)
            
            # Only create manifest for non-library archetypes with sufficient confidence
            if classification.archetype == RepoArchetype.LIBRARY:
                print(f"Repository {repo_url} classified as library, skipping manifest creation")
                return None
            
            if classification.confidence < 0.3:
                print(f"Repository {repo_url} has low confidence ({classification.confidence}), skipping")
                return None
            
            # Extract owner and repo name from URL
            repo_parts = repo_url.rstrip('/').split('/')[-2:]
            owner, repo = repo_parts[-2], repo_parts[-1]
            
            # Map archetype to runtime type
            runtime_map = {
                RepoArchetype.CLI_TOOL: RuntimeType.CLI,
                RepoArchetype.SERVER_APP: RuntimeType.SERVER,
                RepoArchetype.DESKTOP_GUI: RuntimeType.DESKTOP,
                RepoArchetype.MODEL_AI_APP: RuntimeType.SERVER,  # Usually serves an API
                RepoArchetype.DEMO_PLAYGROUND: RuntimeType.DEMO,
                RepoArchetype.INFRA_CONFIG: RuntimeType.INFRA,
            }
            
            # Determine runtime type
            runtime_type = runtime_map.get(classification.archetype, RuntimeType.CLI)
            
            # Determine security settings based on confidence
            if classification.confidence >= 0.8:
                sandbox_level = "relaxed"
                network_policy = "outbound" if runtime_type in [RuntimeType.SERVER, RuntimeType.DESKTOP] else "none"
            else:
                sandbox_level = "strict"
                network_policy = "none"  # Default to no network for lower confidence
            
            # Create the manifest
            manifest = AppManifest(
                api_version="appstore.dev/v1",
                kind="Application",
                metadata={
                    "app_id": f"github.{owner}.{repo}",
                    "name": repo,
                    "description": f"Auto-wrapped application from {repo_url}",
                    "homepage": repo_url
                },
                publisher=Publisher(
                    name=owner,
                    verified_domains=[]  # Would need verification in real implementation
                ),
                source=Source(
                    type="github_repo",
                    repo=f"{owner}/{repo}"
                ),
                versions=Versions(
                    strategy="semver",
                    auto_update=True
                ),
                build=Build(
                    strategy=classification.build_strategy.get("type", "script"),
                    commands=classification.build_strategy.get("steps", []),
                    base_image=classification.build_strategy.get("base_image"),
                    environment=classification.build_strategy.get("environment", {})
                ),
                run=Run(
                    type=runtime_type,
                    entrypoint=self._determine_entrypoint(temp_dir),  # Use temp_dir instead of undefined repo_path
                    args=[]
                ),
                security=Security(
                    sandbox=sandbox_level,
                    network=network_policy,
                    filesystem="readonly" if classification.confidence < 0.6 else "user_home",
                    allow_gpu=False
                ),
                trust=Trust(
                    verification="reproducible" if classification.confidence >= 0.7 else "none"
                ),
                wasm_compatibility=self._calculate_wasm_compatibility(classification.signals)
            )
            
            return manifest
            
        except Exception as e:
            print(f"Error creating manifest for {repo_url}: {e}")
            return None
    
    def _determine_entrypoint(self, repo_path: str) -> str:
        """Determine the entrypoint for the application"""
        # This would be more sophisticated in practice
        # Look for common entrypoints based on language
        if os.path.exists(os.path.join(repo_path, 'main.py')):
            return 'main.py'
        elif os.path.exists(os.path.join(repo_path, 'app.py')):
            return 'app.py'
        elif os.path.exists(os.path.join(repo_path, 'server.js')):
            return 'server.js'
        elif os.path.exists(os.path.join(repo_path, 'main.go')):
            return 'main.go'
        elif os.path.exists(os.path.join(repo_path, 'src/main.rs')):
            return 'src/main.rs'
        else:
            return 'app'  # Generic fallback
    
    def _calculate_wasm_compatibility(self, signals: RepoSignals) -> float:
        """Calculate WASM compatibility score"""
        score = 0.0
        
        # Languages that are more WASM-friendly
        if '.rs' in signals.language_breakdown:
            score += 0.8  # Rust has excellent WASM support
        if '.go' in signals.language_breakdown:
            score += 0.3  # Go has limited WASM support
        if '.js' in signals.language_breakdown or '.ts' in signals.language_breakdown:
            score += 0.7  # JavaScript/TypeScript is WASM native
        
        # Projects with Dockerfiles might be less WASM-compatible
        if signals.has_dockerfile:
            score *= 0.7  # Reduce score if Docker is expected
        
        return min(score, 1.0)


# Example usage and test
if __name__ == "__main__":
    # Example: Analyze a sample repository
    # Note: For this example, we'll create a mock analysis since we can't actually clone repos
    
    # Create a mock analyzer
    analyzer = GitHubRepoAnalyzer()
    
    # Print the available file indicators
    print("Runnable file indicators:")
    for file, score in analyzer.runnable_indicators.items():
        print(f"  {file}: {score}")
    
    # Show port indicators
    print("\nCommon port indicators:")
    for framework, port in analyzer.port_indicators.items():
        print(f"  {framework}: {port}")