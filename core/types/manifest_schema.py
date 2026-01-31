"""
Manifest schema definition and validation for the alternative app store platform.
Based on the scouts.md specification for universal app manifests.
"""
from typing import Dict, List, Optional, Union
from enum import Enum
from dataclasses import dataclass
import yaml
import json
try:
    from jsonschema import validate, ValidationError
except ImportError:
    # Fallback if jsonschema is not available
    def validate(instance, schema):
        # Basic validation without jsonschema
        return True

    class ValidationError(Exception):
        pass


class RuntimeType(Enum):
    """Runtime type enumeration"""
    CLI = "cli"
    SERVER = "server"
    DESKTOP = "desktop"
    WEB = "web"
    LIBRARY = "library"
    DEMO = "demo"
    INFRA = "infra"
    WASM = "wasm"


class ReproducibilityLevel(Enum):
    """Reproducibility levels"""
    R0 = "R0"  # Not reproducible
    R1 = "R1"  # Deterministic inputs
    R2 = "R2"  # Bit-for-bit identical
    R3 = "R3"  # Signed + reproducible


class NetworkPolicy(Enum):
    """Network access policies"""
    NONE = "none"
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class FilesystemPolicy(Enum):
    """Filesystem access policies"""
    READONLY = "readonly"
    USER_HOME = "user_home"
    TEMP = "temp"


@dataclass
class Publisher:
    """Publisher information"""
    name: str
    verified_domains: List[str]
    contact: Optional[str] = None


@dataclass
class Source:
    """Source information"""
    type: str  # github_repo, github_release, official_url
    repo: Optional[str] = None
    url: Optional[str] = None
    asset_regex: Optional[str] = None


@dataclass
class Versions:
    """Version management"""
    strategy: str  # semver, date
    auto_update: bool = True
    allow_prerelease: bool = False


@dataclass
class Build:
    """Build configuration"""
    strategy: str  # docker, native, script, none
    commands: Optional[List[str]] = None
    base_image: Optional[str] = None
    environment: Optional[Dict] = None


@dataclass
class Run:
    """Runtime configuration"""
    type: RuntimeType
    entrypoint: str
    args: Optional[List[str]] = None
    ports: Optional[List[int]] = None
    expose: Optional[Dict] = None


@dataclass
class Security:
    """Security configuration"""
    sandbox: str  # strict, relaxed
    network: NetworkPolicy
    filesystem: FilesystemPolicy
    allow_gpu: bool = False


@dataclass
class Trust:
    """Trust configuration"""
    verification: str  # signed, reproducible, none
    checksums: Optional[Dict[str, str]] = None  # algorithm -> hash


@dataclass
class Resources:
    """Resource limits"""
    cpu_limit: Optional[float] = None  # Fraction of CPU cores
    memory_limit_mb: Optional[int] = None


@dataclass
class AppManifest:
    """Main application manifest"""
    api_version: str
    kind: str
    metadata: Dict[str, str]
    publisher: Publisher
    source: Source
    versions: Versions
    build: Build
    run: Run
    security: Security
    trust: Trust
    resources: Optional[Resources] = None
    permissions: Optional[Dict] = None
    storage: Optional[Dict] = None
    wasm_compatibility: Optional[float] = 0.0
    dependencies: Optional[List[str]] = None
    
    def to_dict(self) -> Dict:
        """Convert manifest to dictionary representation"""
        result = {
            'apiVersion': self.api_version,
            'kind': self.kind,
            'metadata': self.metadata,
            'publisher': {
                'name': self.publisher.name,
                'verified_domains': self.publisher.verified_domains,
                'contact': self.publisher.contact
            },
            'source': {
                'type': self.source.type,
                'repo': self.source.repo,
                'url': self.source.url,
                'asset_regex': self.source.asset_regex
            },
            'versions': {
                'strategy': self.versions.strategy,
                'auto_update': self.versions.auto_update,
                'allow_prerelease': self.versions.allow_prerelease
            },
            'build': {
                'strategy': self.build.strategy,
                'commands': self.build.commands,
                'base_image': self.build.base_image,
                'environment': self.build.environment
            },
            'run': {
                'type': self.run.type.value,
                'entrypoint': self.run.entrypoint,
                'args': self.run.args,
                'ports': self.run.ports,
                'expose': self.run.expose
            },
            'security': {
                'sandbox': self.security.sandbox,
                'network': self.security.network.value,
                'filesystem': self.security.filesystem.value,
                'allow_gpu': self.security.allow_gpu
            },
            'trust': {
                'verification': self.trust.verification,
                'checksums': self.trust.checksums
            }
        }
        
        if self.resources:
            result['resources'] = {
                'cpu_limit': self.resources.cpu_limit,
                'memory_limit_mb': self.resources.memory_limit_mb
            }
            
        if self.permissions:
            result['permissions'] = self.permissions
            
        if self.storage:
            result['storage'] = self.storage
            
        if self.wasm_compatibility is not None:
            result['wasm_compatibility'] = self.wasm_compatibility
            
        if self.dependencies:
            result['dependencies'] = self.dependencies
            
        return result


class ManifestValidator:
    """Validates application manifests against the schema"""
    
    SCHEMA = {
        "type": "object",
        "required": [
            "apiVersion", "kind", "metadata", "publisher", 
            "source", "versions", "build", "run", "security", "trust"
        ],
        "properties": {
            "apiVersion": {
                "type": "string",
                "pattern": r"^appstore\.dev/v\d+$"
            },
            "kind": {
                "type": "string",
                "enum": ["Application"]
            },
            "metadata": {
                "type": "object",
                "required": ["app_id", "name", "description"],
                "properties": {
                    "app_id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "homepage": {"type": "string", "format": "uri"},
                    "license": {"type": "string"}
                }
            },
            "publisher": {
                "type": "object",
                "required": ["name", "verified_domains"],
                "properties": {
                    "name": {"type": "string"},
                    "verified_domains": {
                        "type": "array",
                        "items": {"type": "string", "format": "hostname"}
                    },
                    "contact": {"type": "string", "format": "email"}
                }
            },
            "source": {
                "type": "object",
                "required": ["type"],
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["github_repo", "github_release", "official_url"]
                    },
                    "repo": {"type": "string"},
                    "url": {"type": "string", "format": "uri"},
                    "asset_regex": {"type": "string"}
                }
            },
            "versions": {
                "type": "object",
                "required": ["strategy"],
                "properties": {
                    "strategy": {
                        "type": "string",
                        "enum": ["semver", "date"]
                    },
                    "allow_prerelease": {"type": "boolean"},
                    "auto_update": {"type": "boolean"}
                }
            },
            "build": {
                "type": "object",
                "required": ["strategy"],
                "properties": {
                    "strategy": {
                        "type": "string",
                        "enum": ["docker", "native", "script", "none"]
                    },
                    "commands": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "base_image": {"type": "string"},
                    "environment": {"type": "object"}
                }
            },
            "run": {
                "type": "object",
                "required": ["type", "entrypoint"],
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["cli", "server", "desktop", "web", "library", "demo", "infra", "wasm"]
                    },
                    "entrypoint": {"type": "string"},
                    "args": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "ports": {
                        "type": "array",
                        "items": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 65535
                        }
                    },
                    "expose": {"type": "object"}
                }
            },
            "security": {
                "type": "object",
                "required": ["sandbox", "network", "filesystem"],
                "properties": {
                    "sandbox": {
                        "type": "string",
                        "enum": ["strict", "relaxed"]
                    },
                    "network": {
                        "type": "string",
                        "enum": ["none", "outbound", "inbound"]
                    },
                    "filesystem": {
                        "type": "string",
                        "enum": ["readonly", "user_home", "temp"]
                    },
                    "allow_gpu": {"type": "boolean"}
                }
            },
            "trust": {
                "type": "object",
                "required": ["verification"],
                "properties": {
                    "verification": {
                        "type": "string",
                        "enum": ["signed", "reproducible", "none"]
                    },
                    "checksums": {"type": "object"}
                }
            },
            "resources": {
                "type": "object",
                "properties": {
                    "cpu_limit": {"type": "number", "minimum": 0},
                    "memory_limit_mb": {"type": "integer", "minimum": 1}
                }
            },
            "permissions": {"type": "object"},
            "storage": {"type": "object"},
            "wasm_compatibility": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "dependencies": {
                "type": "array",
                "items": {"type": "string"}
            }
        }
    }
    
    @classmethod
    def validate(cls, manifest_data: Union[Dict, str]) -> bool:
        """
        Validate a manifest against the schema
        
        Args:
            manifest_data: Either a dict or YAML/JSON string representing the manifest
            
        Returns:
            True if valid, raises ValidationError if invalid
        """
        if isinstance(manifest_data, str):
            # Try to parse as YAML first, then JSON
            try:
                manifest_dict = yaml.safe_load(manifest_data)
            except:
                manifest_dict = json.loads(manifest_data)
        else:
            manifest_dict = manifest_data
            
        try:
            validate(instance=manifest_dict, schema=cls.SCHEMA)
            return True
        except ValidationError as e:
            raise ValidationError(f"Manifest validation failed: {e.message}")
    
    @classmethod
    def from_dict(cls, manifest_dict: Dict) -> AppManifest:
        """Create an AppManifest instance from a dictionary"""
        cls.validate(manifest_dict)
        
        # Create nested objects
        publisher = Publisher(
            name=manifest_dict['publisher']['name'],
            verified_domains=manifest_dict['publisher'].get('verified_domains', []),
            contact=manifest_dict['publisher'].get('contact')
        )
        
        source = Source(
            type=manifest_dict['source']['type'],
            repo=manifest_dict['source'].get('repo'),
            url=manifest_dict['source'].get('url'),
            asset_regex=manifest_dict['source'].get('asset_regex')
        )
        
        versions = Versions(
            strategy=manifest_dict['versions']['strategy'],
            auto_update=manifest_dict['versions'].get('auto_update', True),
            allow_prerelease=manifest_dict['versions'].get('allow_prerelease', False)
        )
        
        build = Build(
            strategy=manifest_dict['build']['strategy'],
            commands=manifest_dict['build'].get('commands'),
            base_image=manifest_dict['build'].get('base_image'),
            environment=manifest_dict['build'].get('environment')
        )
        
        run = Run(
            type=RuntimeType(manifest_dict['run']['type']),
            entrypoint=manifest_dict['run']['entrypoint'],
            args=manifest_dict['run'].get('args'),
            ports=manifest_dict['run'].get('ports'),
            expose=manifest_dict['run'].get('expose')
        )
        
        security = Security(
            sandbox=manifest_dict['security']['sandbox'],
            network=NetworkPolicy(manifest_dict['security']['network']),
            filesystem=FilesystemPolicy(manifest_dict['security']['filesystem']),
            allow_gpu=manifest_dict['security'].get('allow_gpu', False)
        )
        
        trust = Trust(
            verification=manifest_dict['trust']['verification'],
            checksums=manifest_dict['trust'].get('checksums')
        )
        
        resources = None
        if 'resources' in manifest_dict:
            resources = Resources(
                cpu_limit=manifest_dict['resources'].get('cpu_limit'),
                memory_limit_mb=manifest_dict['resources'].get('memory_limit_mb')
            )
        
        return AppManifest(
            api_version=manifest_dict['apiVersion'],
            kind=manifest_dict['kind'],
            metadata=manifest_dict['metadata'],
            publisher=publisher,
            source=source,
            versions=versions,
            build=build,
            run=run,
            security=security,
            trust=trust,
            resources=resources,
            permissions=manifest_dict.get('permissions'),
            storage=manifest_dict.get('storage'),
            wasm_compatibility=manifest_dict.get('wasm_compatibility', 0.0),
            dependencies=manifest_dict.get('dependencies')
        )


# Example usage and test
if __name__ == "__main__":
    # Example manifest
    example_manifest = {
        "apiVersion": "appstore.dev/v1",
        "kind": "Application",
        "metadata": {
            "app_id": "org.blender.blender",
            "name": "Blender",
            "description": "3D creation suite",
            "homepage": "https://blender.org",
            "license": "GPL-3.0"
        },
        "publisher": {
            "name": "Blender Foundation",
            "verified_domains": ["blender.org"]
        },
        "source": {
            "type": "github_release",
            "repo": "blender/blender",
            "asset_regex": "blender-.*windows.*zip"
        },
        "versions": {
            "strategy": "semver",
            "auto_update": True
        },
        "build": {
            "strategy": "none"
        },
        "run": {
            "type": "desktop",
            "entrypoint": "blender.exe",
            "args": []
        },
        "security": {
            "sandbox": "relaxed",
            "network": "outbound",
            "filesystem": "user_home",
            "allow_gpu": True
        },
        "trust": {
            "verification": "signed",
            "checksums": {
                "sha256": "auto"
            }
        }
    }
    
    # Validate the manifest
    try:
        is_valid = ManifestValidator.validate(example_manifest)
        print(f"Manifest is valid: {is_valid}")
        
        # Create manifest object
        manifest_obj = ManifestValidator.from_dict(example_manifest)
        print(f"Created manifest object: {manifest_obj.metadata['name']}")
        
        # Convert back to dict
        manifest_dict = manifest_obj.to_dict()
        print(f"Converted back to dict: {manifest_dict['metadata']['name']}")
        
    except ValidationError as e:
        print(f"Validation error: {e}")