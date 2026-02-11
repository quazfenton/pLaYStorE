"""
GitHub Project Explorer Service for AltStore.

Provides intelligent repository discovery, analysis, and one-click app wrapping.
Integrates with GitHub API for real-time project metadata, release management,
and automated manifest generation.
"""

import asyncio
import json
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import aiohttp
from enum import Enum


class RepoType(Enum):
    """Repository classification types"""
    CLI_TOOL = "cli_tool"
    SERVER_APP = "server_app"
    DESKTOP_APP = "desktop_app"
    WEB_APP = "web_app"
    LIBRARY = "library"
    AI_MODEL = "ai_model"
    GAME = "game"
    UNKNOWN = "unknown"


@dataclass
class GitHubRepo:
    """GitHub repository metadata"""
    owner: str
    name: str
    full_name: str
    url: str
    description: str
    stars: int
    language: str
    topics: List[str]
    has_releases: bool
    latest_release: Optional[str] = None
    last_updated: Optional[str] = None
    license: Optional[str] = None
    forks: int = 0
    watchers: int = 0


@dataclass
class RepositoryAnalysis:
    """Analysis results for a GitHub repository"""
    repo: GitHubRepo
    repo_type: RepoType
    confidence: float
    build_strategy: str
    runtime_type: str
    ports_detected: List[int]
    long_running: bool
    wasm_compatible: float
    is_safe: bool
    risk_score: float
    suggested_manifest: Dict[str, Any]
    analysis_timestamp: str


class GitHubExplorer:
    """
    Discovers and analyzes GitHub repositories for AltStore.
    
    Features:
    - Full-text search across GitHub
    - Automated repo classification
    - Manifest generation from source analysis
    - WASM compatibility scoring
    - Security risk assessment
    """
    
    def __init__(self, github_token: Optional[str] = None):
        self.github_token = github_token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        if github_token:
            self.headers["Authorization"] = f"token {github_token}"

        # Cache for repo analysis
        self._analysis_cache: Dict[str, RepositoryAnalysis] = {}
        self._cache_ttl = timedelta(hours=1)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create a shared aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self.headers)
        return self._session

    async def close(self):
        """Close the shared session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def search_repos(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 30
    ) -> List[GitHubRepo]:
        """
        Search GitHub repositories using the GitHub API.
        
        Args:
            query: Search query
            filters: Optional filters (language, min_stars, topics, etc.)
            limit: Maximum results to return
        
        Returns:
            List of matching repositories
        """
        search_query = query
        
        # Add filters to search query
        if filters:
            if "language" in filters:
                search_query += f" language:{filters['language']}"
            if "min_stars" in filters:
                search_query += f" stars:>={filters['min_stars']}"
            if "topics" in filters:
                for topic in filters["topics"]:
                    search_query += f" topic:{topic}"
        
        url = f"{self.base_url}/search/repositories"
        params = {
            "q": search_query,
            "sort": "stars",
            "order": "desc",
            "per_page": min(limit, 100)
        }
        
        session = await self._get_session()
        async with session.get(url, headers=self.headers, params=params) as resp:
            if resp.status != 200:
                raise Exception(f"GitHub API error: {resp.status}")

            data = await resp.json()
            repos = []

            for item in data.get("items", [])[:limit]:
                repo = GitHubRepo(
                    owner=item["owner"]["login"],
                    name=item["name"],
                    full_name=item["full_name"],
                    url=item["html_url"],
                    description=item.get("description", ""),
                    stars=item.get("stargazers_count", 0),
                    language=item.get("language", "Unknown"),
                    topics=item.get("topics", []),
                    has_releases=item.get("has_downloads", False),
                    license=(item.get("license") or {}).get("name"),
                    forks=item.get("forks_count", 0),
                    watchers=item.get("watchers_count", 0),
                    last_updated=item.get("updated_at")
                )

                # Fetch latest release info
                try:
                    repo.latest_release = await self._get_latest_release(item["full_name"])
                except:
                    repo.latest_release = None

                repos.append(repo)

            return repos
    
    async def _get_latest_release(self, repo_full_name: str) -> Optional[str]:
        """Get latest release version for a repository"""
        url = f"{self.base_url}/repos/{repo_full_name}/releases/latest"

        session = await self._get_session()
        async with session.get(url, headers=self.headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("tag_name")
            return None
    
    async def analyze_repo(self, repo_full_name: str) -> RepositoryAnalysis:
        """
        Perform deep analysis of a GitHub repository.

        Returns metadata, classification, and generated manifest.
        """
        # Check cache
        if repo_full_name in self._analysis_cache:
            cached = self._analysis_cache[repo_full_name]
            if datetime.fromisoformat(cached.analysis_timestamp) > datetime.now() - self._cache_ttl:
                return cached

        owner, name = repo_full_name.split("/")

        # Fetch repo metadata
        repo = await self._fetch_repo_metadata(repo_full_name)

        # Analyze source files
        files = await self._fetch_repo_files(repo_full_name)
        readme = await self._fetch_readme(repo_full_name)

        # Perform classification
        repo_type = self._classify_repo(files, readme)
        build_strategy = self._detect_build_strategy(files)
        runtime_type = self._detect_runtime(files, readme)
        ports = self._detect_ports(readme)

        # Check safety
        is_safe, risk_score = await self._assess_safety(files, readme, repo_full_name)

        # Check WASM compatibility
        wasm_compat = self._check_wasm_compatibility(files, repo.language)

        # Generate manifest
        manifest = self._generate_manifest(
            repo, files, readme, repo_type, build_strategy, runtime_type
        )

        # Create analysis result
        analysis = RepositoryAnalysis(
            repo=repo,
            repo_type=repo_type,
            confidence=self._calculate_confidence(repo, files, readme),
            build_strategy=build_strategy,
            runtime_type=runtime_type,
            ports_detected=ports,
            long_running=runtime_type in ["server", "web"],
            wasm_compatible=wasm_compat,
            is_safe=is_safe,
            risk_score=risk_score,
            suggested_manifest=manifest,
            analysis_timestamp=datetime.now().isoformat()
        )

        # Cache result
        self._analysis_cache[repo_full_name] = analysis

        return analysis
    
    async def _fetch_repo_metadata(self, repo_full_name: str) -> GitHubRepo:
        """Fetch repository metadata from GitHub"""
        url = f"{self.base_url}/repos/{repo_full_name}"

        session = await self._get_session()
        async with session.get(url, headers=self.headers) as resp:
            if resp.status != 200:
                raise Exception(f"Failed to fetch repo: {resp.status}")

            data = await resp.json()
            return GitHubRepo(
                owner=data["owner"]["login"],
                name=data["name"],
                full_name=data["full_name"],
                url=data["html_url"],
                description=data.get("description", ""),
                stars=data.get("stargazers_count", 0),
                language=data.get("language", "Unknown"),
                topics=data.get("topics", []),
                has_releases=data.get("has_downloads", False),
                license=(data.get("license") or {}).get("name"),
                forks=data.get("forks_count", 0),
                watchers=data.get("watchers_count", 0),
                last_updated=data.get("updated_at")
            )
    
    async def _fetch_repo_files(self, repo_full_name: str, path: str = "") -> List[str]:
        """Fetch list of files in repository root"""
        url = f"{self.base_url}/repos/{repo_full_name}/contents/{path}"

        session = await self._get_session()
        async with session.get(url, headers=self.headers) as resp:
            if resp.status != 200:
                return []

            data = await resp.json()
            if isinstance(data, list):
                return [item["name"] for item in data if item["type"] == "file"]
            return []
    
    async def _fetch_readme(self, repo_full_name: str) -> str:
        """Fetch README.md content from repository"""
        url = f"{self.base_url}/repos/{repo_full_name}/readme"

        session = await self._get_session()
        async with session.get(url, headers=self.headers) as resp:
            if resp.status == 200:
                # GitHub returns base64-encoded content
                import base64
                data = await resp.json()
                if "content" in data:
                    return base64.b64decode(data["content"]).decode("utf-8")
            return ""
    
    def _classify_repo(self, files: List[str], readme: str) -> RepoType:
        """Classify repository based on file content and README"""
        # Check for specific file types
        has_dockerfile = "Dockerfile" in files or "docker-compose.yml" in files
        has_setup_py = "setup.py" in files
        has_cargo_toml = "Cargo.toml" in files
        has_go_mod = "go.mod" in files
        has_package_json = "package.json" in files
        has_makefile = "Makefile" in files
        has_requirements = "requirements.txt" in files
        
        # Check README content
        readme_lower = readme.lower()
        has_cli_indicators = any(x in readme_lower for x in ["cli", "command-line", "terminal"])
        has_server_indicators = any(x in readme_lower for x in ["server", "api", "http", "rest"])
        has_web_indicators = any(x in readme_lower for x in ["web", "frontend", "react", "vue"])
        has_desktop_indicators = any(x in readme_lower for x in ["gui", "desktop", "electron"])
        has_ai_indicators = any(x in readme_lower for x in ["model", "ai", "neural", "llm", "ml"])
        
        # Score each category
        scores = {
            RepoType.CLI_TOOL: sum([
                int(has_cli_indicators) * 2,
                int(has_setup_py) * 1,
                int(has_cargo_toml) * 2,
                int(has_go_mod) * 2,
                int(has_makefile) * 1
            ]),
            RepoType.SERVER_APP: sum([
                int(has_server_indicators) * 2,
                int(has_dockerfile) * 2
            ]),
            RepoType.LIBRARY: sum([
                int(has_setup_py) * 1.5,
                int(has_cargo_toml) * 1.5,
                int(has_package_json) * 1.5
            ]),
            RepoType.WEB_APP: sum([
                int(has_web_indicators) * 2,
                int(has_package_json) * 1
            ]),
            RepoType.DESKTOP_APP: has_desktop_indicators * 2,
            RepoType.AI_MODEL: has_ai_indicators * 3,
        }
        
        # Filter out libraries (low confidence)
        if scores[RepoType.LIBRARY] > max([scores.get(k, 0) for k in scores if k != RepoType.LIBRARY]):
            return RepoType.LIBRARY
        
        # Return highest scoring type
        return max(scores, key=scores.get) if scores else RepoType.UNKNOWN
    
    def _detect_build_strategy(self, files: List[str]) -> str:
        """Detect appropriate build strategy"""
        if "Dockerfile" in files or "docker-compose.yml" in files:
            return "docker"
        if "Cargo.toml" in files:
            return "cargo"
        if "go.mod" in files:
            return "go"
        if "package.json" in files:
            return "npm"
        if "setup.py" in files or "requirements.txt" in files or "pyproject.toml" in files:
            return "python"
        if "Makefile" in files:
            return "make"
        
        return "script"
    
    def _detect_runtime(self, files: List[str], readme: str) -> str:
        """Detect runtime type (cli, server, desktop, etc.)"""
        readme_lower = readme.lower()
        
        if "server" in readme_lower or "localhost" in readme_lower or "http://" in readme_lower:
            return "server"
        if "gui" in readme_lower or "window" in readme_lower:
            return "desktop"
        if "web" in readme_lower and ("react" in readme_lower or "vue" in readme_lower or "angular" in readme_lower):
            return "web"
        
        return "cli"
    
    def _detect_ports(self, readme: str) -> List[int]:
        """Extract port numbers mentioned in README"""
        pattern = r"(?:port|:)\s*(\d{1,5})"
        matches = re.findall(pattern, readme.lower())
        return [int(m) for m in matches if 1 <= int(m) <= 65535]
    
    async def _assess_safety(self, files: List[str], readme: str, repo_full_name: str) -> Tuple[bool, float]:
        """Assess security risk of repository"""
        risk_score = 0.0

        # Check for suspicious patterns in README
        suspicious_patterns = [
            (r"curl\s+.*\|\s*sh", 0.2),
            (r"wget\s+.*\|\s*sh", 0.2),
            (r"\bcryptomin(?:er|ing)\b", 0.2),
            (r"\b(?:mine|mining)\s+(?:crypto|cryptocurrency|coin|bitcoin|ethereum)\b", 0.2),
            (r"\b(?:wallet|exploit|malware|backdoor)\b", 0.2),
            (r"\b(?:crypto|ethereum|bitcoin)\b", 0.05)
        ]

        readme_lower = readme.lower()
        for pattern, weight in suspicious_patterns:
            if re.search(pattern, readme_lower):
                risk_score += weight

        # Positive safety signals
        has_license = "LICENSE" in files or "COPYING" in files
        has_tests = any("test" in f.lower() for f in files)
        
        # Check for CI files - GitHub Actions workflows are in .github/workflows/
        # Since _fetch_repo_files only gets root directory files, we need to check for CI differently
        # GitHub Actions files are typically YAML files in .github/workflows/
        # For now, we'll check if the repo has .github directory by checking for common CI indicators
        has_github_actions = any(f.endswith('.yml') or f.endswith('.yaml') for f in files if '.github' in f)
        
        # Check for GitHub Actions workflows in .github/workflows directory
        has_github_actions = has_github_actions or await self._has_github_workflows(repo_full_name)
        
        has_gitlab_ci = ".gitlab-ci.yml" in files
        
        # Also check for other CI files that might be in the root
        has_other_ci = any(ci_file in files for ci_file in [
            ".travis.yml", "appveyor.yml", "circle.yml", ".cirrus.yml", 
            "shippable.yml", ".drone.yml", "wercker.yml", "Jenkinsfile"
        ])
        
        has_ci = has_github_actions or has_gitlab_ci or has_other_ci

        if has_license:
            risk_score -= 0.1
        if has_tests:
            risk_score -= 0.1
        if has_ci:
            risk_score -= 0.1

        risk_score = max(0.0, min(1.0, risk_score))
        is_safe = risk_score < 0.5
        
        return is_safe, risk_score

    async def _has_github_workflows(self, repo_full_name: str) -> bool:
        """Check if the repository has GitHub Actions workflows in .github/workflows"""
        url = f"{self.base_url}/repos/{repo_full_name}/contents/.github/workflows"

        try:
            session = await self._get_session()
            async with session.get(url, headers=self.headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Check if there are any workflow files
                    if isinstance(data, list):
                        workflow_files = [item for item in data if item["type"] == "file" and 
                                        (item["name"].endswith(".yml") or item["name"].endswith(".yaml"))]
                        return len(workflow_files) > 0
                return False
        except:
            # If there's an error (e.g., directory doesn't exist), return False
            return False
    
    def _check_wasm_compatibility(self, files: List[str], language: Optional[str]) -> float:
        """Score WASM compatibility"""
        score = 0.0
        
        # Language-based scoring
        lang_map = {
            "rust": 0.9,
            "c": 0.7,
            "c++": 0.6,
            "go": 0.5,
            "python": 0.3,
            "javascript": 0.4,
            "typescript": 0.4,
        }
        
        if language:
            score = lang_map.get(language.lower(), 0.2)
        
        # Build system compatibility
        if "Dockerfile" in files:
            score -= 0.2
        if "Cargo.toml" in files:
            score += 0.2
        
        return max(0.0, min(1.0, score))
    
    def _calculate_confidence(self, repo: GitHubRepo, files: List[str], readme: str) -> float:
        """Calculate overall analysis confidence"""
        confidence = 0.5
        
        # Higher confidence for established projects
        if repo.stars >= 1000:
            confidence += 0.2
        elif repo.stars >= 100:
            confidence += 0.1
        
        # Higher confidence with documentation
        if readme and len(readme) > 500:
            confidence += 0.1
        
        # Higher confidence with releases
        if repo.has_releases:
            confidence += 0.1
        
        return min(1.0, confidence)
    
    def _generate_manifest(
        self,
        repo: GitHubRepo,
        files: List[str],
        readme: str,
        repo_type: RepoType,
        build_strategy: str,
        runtime_type: str
    ) -> Dict[str, Any]:
        """Generate AltStore manifest from repository analysis"""
        return {
            "apiVersion": "appstore.dev/v1",
            "kind": "Application",
            "metadata": {
                "app_id": f"{repo.owner.lower()}.{repo.name.lower()}",
                "name": repo.name,
                "description": repo.description or f"Application from {repo.owner}/{repo.name}",
                "homepage": repo.url,
                "license": repo.license or "Unknown"
            },
            "publisher": {
                "name": repo.owner,
                "verified_domains": []
            },
            "source": {
                "type": "github_repo" if not repo.has_releases else "github_release",
                "repo": repo.full_name,
                "url": repo.url
            },
            "versions": {
                "strategy": "semver",
                "auto_update": True
            },
            "build": {
                "strategy": build_strategy,
                "commands": []
            },
            "run": {
                "type": runtime_type,
                "entrypoint": "app",
                "ports": []
            },
            "security": {
                "sandbox": "strict",
                "network": "none" if runtime_type == "cli" else "outbound",
                "filesystem": "readonly",
                "allow_gpu": False
            },
            "trust": {
                "verification": "none"
            }
        }


class OneClickInstaller:
    """
    Streamlined installation interface for non-technical users.

    Provides a simple "Install -> Run" flow with automatic
    configuration and safety checking.
    """

    def __init__(self):
        self.explorer = GitHubExplorer()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.explorer.close()

    async def close(self):
        await self.explorer.close()

    async def install_repo(
        self,
        repo_full_name: str,
    ) -> Dict[str, Any]:
        """
        One-click installation flow for GitHub repositories.

        Args:
            repo_full_name: Repository in format "owner/name"

        Returns:
            Installation result with status and manifest
        """
        try:
            # Analyze repository
            analysis = await self.explorer.analyze_repo(repo_full_name)

            # Check if safe
            if not analysis.is_safe:
                return {
                    "success": False,
                    "error": f"Repository has safety concerns (risk score: {analysis.risk_score:.2f})",
                    "analysis": asdict(analysis)
                }

            # Check minimum confidence
            if analysis.confidence < 0.4:
                return {
                    "success": False,
                    "error": "Repository analysis confidence too low",
                    "analysis": asdict(analysis)
                }

            # Would continue with actual installation here
            # For now, return the manifest and analysis
            return {
                "success": True,
                "repo": asdict(analysis.repo),
                "analysis": asdict(analysis),
                "manifest": analysis.suggested_manifest,
                "next_step": "review_manifest"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# Example usage
if __name__ == "__main__":
    async def test():
        explorer = GitHubExplorer()

        try:
            # Search for CLI tools
            print("Searching for Python CLI tools...")
            repos = await explorer.search_repos(
                "cli",
                filters={"language": "Python", "min_stars": 100},
                limit=5
            )

            for repo in repos:
                print(f"- {repo.full_name}: {repo.stars} stars")

            # Analyze a specific repo
            print("\nAnalyzing ripgrep...")
            analysis = await explorer.analyze_repo("BurntSushi/ripgrep")
            print(f"Type: {analysis.repo_type}")
            print(f"Confidence: {analysis.confidence:.2f}")
            print(f"WASM Compatible: {analysis.wasm_compatible:.2f}")
            print(f"Safe: {analysis.is_safe}")
        finally:
            await explorer.close()

    # Run async example
    asyncio.run(test())
