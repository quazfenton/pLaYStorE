"""
WASM fallback execution engine for the alternative app store platform.
Provides a secure, sandboxed execution environment for applications that can't run natively.
Based on the scouts.md specification for WASM fallback builds.
"""
import os
import tempfile
import subprocess
import json
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
import requests
from pathlib import Path
from ..core.types.manifest_schema import AppManifest, RuntimeType, Security


class WASMEngine(Enum):
    """Supported WASM runtimes"""
    WASMTIME = "wasmtime"
    WASMER = "wasmer"
    WAVM = "wavm"
    NODE_WASI = "node-wasi"


@dataclass
class WASMConfig:
    """Configuration for WASM execution"""
    engine: WASMEngine
    allowed_imports: List[str]
    filesystem_access: str  # none, readonly, readwrite
    network_access: str     # none, outbound
    allowed_env_vars: List[str]
    memory_limit: int       # in MB
    cpu_limit: float        # fraction of CPU


class WASMCompatibilityChecker:
    """Checks if an application is compatible with WASM execution"""
    
    def __init__(self):
        self.language_support = {
            'rust': 0.9,      # Excellent WASM support
            'assemblyscript': 0.8,  # Good WASM support
            'c': 0.7,         # Good with Emscripten
            'c++': 0.6,       # Good with Emscripten
            'go': 0.5,        # Limited WASM support
            'swift': 0.4,     # Experimental WASM support
            'python': 0.3,    # Possible with Pyodide
            'java': 0.2,      # Limited WASM support
        }
    
    def check_compatibility(self, manifest: AppManifest) -> float:
        """
        Check WASM compatibility of an application.
        
        Args:
            manifest: App manifest to check
            
        Returns:
            Compatibility score (0.0 to 1.0)
        """
        score = 0.0
        
        # Check build strategy
        if manifest.build.strategy == "docker":
            # Docker-based apps may not be WASM-compatible
            score += 0.2
        else:
            # Native build strategies more likely to be compatible
            score += 0.5
        
        # Check runtime type
        if manifest.run.type in [RuntimeType.CLI, RuntimeType.SERVER]:
            # CLI and server apps are more likely to be WASM-compatible
            score += 0.3
        
        # Check for system dependencies
        if manifest.security.allow_gpu:
            # GPU access not available in WASM
            score -= 0.3
        
        from ..core.types.manifest_schema import NetworkPolicy, FilesystemPolicy

        if manifest.security.network != NetworkPolicy.NONE:
            # Network access possible but limited in WASM
            score += 0.1

        # Check for file system access
        if manifest.security.filesystem == FilesystemPolicy.READONLY:
            # Read-only access is fine for WASM
            score += 0.2
        elif manifest.security.filesystem == FilesystemPolicy.USER_HOME:
            # User home access is possible in WASM
            score += 0.1
        
        # Apply upper bound
        return max(0.0, min(1.0, score))


class WASMBuilder:
    """Builds applications to WASM when native execution is not possible"""
    
    def __init__(self):
        self.compatibility_checker = WASMCompatibilityChecker()
    
    def can_build_to_wasm(self, manifest: AppManifest) -> bool:
        """
        Determine if the application can be built to WASM.
        
        Args:
            manifest: App manifest
            
        Returns:
            True if WASM build is possible
        """
        compatibility = self.compatibility_checker.check_compatibility(manifest)
        return compatibility >= 0.4  # Threshold for WASM compatibility
    
    def build_to_wasm(self, manifest: AppManifest, source_path: str) -> Optional[str]:
        """
        Build the application to WASM format.
        
        Args:
            manifest: App manifest
            source_path: Path to source code
            
        Returns:
            Path to WASM file if successful, None otherwise
        """
        if not self.can_build_to_wasm(manifest):
            return None
        
        # Create temporary build directory
        build_dir = tempfile.mkdtemp(prefix="altstore_wasm_build_")
        
        try:
            # Determine build approach based on source language
            wasm_file = self._build_by_language(manifest, source_path, build_dir)
            
            if wasm_file and os.path.exists(wasm_file):
                return wasm_file
            else:
                return None
                
        except Exception as e:
            print(f"WASM build failed: {e}")
            return None
        finally:
            # Clean up build directory
            import shutil
            shutil.rmtree(build_dir, ignore_errors=True)
    
    def _build_by_language(self, manifest: AppManifest, source_path: str, build_dir: str) -> Optional[str]:
        """Build WASM based on source language"""
        # Check for Rust project
        if os.path.exists(os.path.join(source_path, "Cargo.toml")):
            return self._build_rust_to_wasm(source_path, build_dir)
        
        # Check for C/C++ project
        if any(os.path.exists(os.path.join(source_path, f)) for f in ["CMakeLists.txt", "Makefile"]):
            return self._build_cpp_to_wasm(source_path, build_dir)
        
        # Check for Go project
        if os.path.exists(os.path.join(source_path, "go.mod")):
            return self._build_go_to_wasm(source_path, build_dir)
        
        # For other languages, we'd need specific build logic
        # This is a simplified implementation
        return None
    
    def _build_rust_to_wasm(self, source_path: str, build_dir: str) -> Optional[str]:
        """Build Rust project to WASM"""
        try:
            # Add WASM target
            subprocess.run([
                "rustup", "target", "add", "wasm32-unknown-unknown"
            ], check=True, capture_output=True)
            
            # Build for WASM
            subprocess.run([
                "cargo", "build", 
                "--target", "wasm32-unknown-unknown",
                "--release"
            ], cwd=source_path, check=True, capture_output=True)
            
            # Find the WASM output
            target_dir = os.path.join(source_path, "target", "wasm32-unknown-unknown", "release")
            for file in os.listdir(target_dir):
                if file.endswith(".wasm"):
                    wasm_path = os.path.join(target_dir, file)
                    # Copy to build directory
                    dest_path = os.path.join(build_dir, "app.wasm")
                    import shutil
                    shutil.copy2(wasm_path, dest_path)
                    return dest_path
            
            return None
        except (subprocess.CalledProcessError, FileNotFoundError):
            # rustc or cargo not available
            return None
    
    def _build_cpp_to_wasm(self, source_path: str, build_dir: str) -> Optional[str]:
        """Build C/C++ project to WASM using Emscripten"""
        try:
            # Check if emscripten is available
            subprocess.run(["emcc", "--version"], 
                         check=True, capture_output=True)
            
            # Find source files
            cpp_files = []
            for root, dirs, files in os.walk(source_path):
                for file in files:
                    if file.endswith(('.c', '.cpp', '.cxx', '.cc')):
                        cpp_files.append(os.path.join(root, file))
            
            if not cpp_files:
                return None
            
            # Compile to WASM
            output_wasm = os.path.join(build_dir, "app.wasm")
            cmd = ["emcc"] + cpp_files + ["-o", output_wasm]
            subprocess.run(cmd, cwd=source_path, check=True, capture_output=True)
            
            return output_wasm
        except (subprocess.CalledProcessError, FileNotFoundError):
            # emscripten not available
            return None
    
    def _build_go_to_wasm(self, source_path: str, build_dir: str) -> Optional[str]:
        """Build Go project to WASM using TinyGo"""
        try:
            # Check if tinygo is available
            subprocess.run(["tinygo", "version"], 
                         check=True, capture_output=True)
            
            # Find main Go file
            main_file = os.path.join(source_path, "main.go")
            if not os.path.exists(main_file):
                # Look for main function in other files
                for file in os.listdir(source_path):
                    if file.endswith(".go"):
                        with open(os.path.join(source_path, file), 'r') as f:
                            content = f.read()
                            if "func main()" in content:
                                main_file = os.path.join(source_path, file)
                                break
            
            if not os.path.exists(main_file):
                return None
            
            # Compile to WASM
            output_wasm = os.path.join(build_dir, "app.wasm")
            subprocess.run([
                "tinygo", "build", 
                "-o", output_wasm,
                "-target", "wasi"
            ], cwd=source_path, check=True, capture_output=True)
            
            return output_wasm
        except (subprocess.CalledProcessError, FileNotFoundError):
            # tinygo not available
            return None


class WASMExecutor:
    """Executes WASM applications in a secure sandbox"""
    
    def __init__(self):
        self.available_engines = self._detect_available_engines()
    
    def _detect_available_engines(self) -> List[WASMEngine]:
        """Detect which WASM engines are available on the system"""
        available = []
        
        for engine in WASMEngine:
            try:
                if engine == WASMEngine.WASMTIME:
                    subprocess.run(["wasmtime", "--version"], 
                                 check=True, capture_output=True)
                    available.append(WASMEngine.WASMTIME)
                elif engine == WASMEngine.WASMER:
                    subprocess.run(["wasmer", "--version"], 
                                 check=True, capture_output=True)
                    available.append(WASMEngine.WASMER)
                elif engine == WASMEngine.NODE_WASI:
                    subprocess.run(["node", "--version"], 
                                 check=True, capture_output=True)
                    available.append(WASMEngine.NODE_WASI)
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        
        return available
    
    def execute(self, wasm_file: str, config: WASMConfig, args: List[str] = None) -> Tuple[bool, str, str, int]:
        """
        Execute a WASM file with the specified configuration.
        
        Args:
            wasm_file: Path to the WASM file
            config: WASM execution configuration
            args: Arguments to pass to the WASM program
            
        Returns:
            Tuple of (success, stdout, stderr, exit_code)
        """
        if not os.path.exists(wasm_file):
            return False, "", f"WASM file does not exist: {wasm_file}", -1
        
        if config.engine not in self.available_engines:
            return False, "", f"WASM engine not available: {config.engine.value}", -1
        
        # Build execution command based on engine
        if config.engine == WASMEngine.WASMTIME:
            return self._execute_with_wasmtime(wasm_file, config, args or [])
        elif config.engine == WASMEngine.WASMER:
            return self._execute_with_wasmer(wasm_file, config, args or [])
        elif config.engine == WASMEngine.NODE_WASI:
            return self._execute_with_node(wasm_file, config, args or [])
        else:
            return False, "", f"Unsupported WASM engine: {config.engine.value}", -1
    
    def _execute_with_wasmtime(self, wasm_file: str, config: WASMConfig, args: List[str]) -> Tuple[bool, str, str, int]:
        """Execute WASM file using wasmtime"""
        cmd = ["wasmtime", "--allow-preview1"]
        
        # Add resource limits
        if config.memory_limit:
            cmd.extend(["--wasm-max-memory", f"{config.memory_limit * 1024 * 1024}"])  # Convert MB to bytes
        
        # Add filesystem access
        if config.filesystem_access != "none":
            cmd.extend(["--dir", "."])  # Allow access to current directory
        
        # Add network access
        if config.network_access == "none":
            cmd.append("--disable-stdio")  # Disable stdio to prevent network access
        
        # Add the WASM file and arguments
        cmd.append(wasm_file)
        cmd.extend(args)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )
            return True, result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return False, "", "WASM execution timed out", -1
        except Exception as e:
            return False, "", f"WASM execution failed: {str(e)}", -1
    
    def _execute_with_wasmer(self, wasm_file: str, config: WASMConfig, args: List[str]) -> Tuple[bool, str, str, int]:
        """Execute WASM file using wasmer"""
        cmd = ["wasmer"]
        
        # Add filesystem access
        if config.filesystem_access != "none":
            cmd.extend(["--dir", "."])
        
        # Add network access
        if config.network_access == "none":
            cmd.extend(["--no-default-features"])
        
        # Add resource limits
        if config.memory_limit:
            cmd.extend(["--max-memory", str(config.memory_limit)])
        
        # Add the WASM file and arguments
        cmd.append(wasm_file)
        cmd.extend(args)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )
            return True, result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return False, "", "WASM execution timed out", -1
        except Exception as e:
            return False, "", f"WASM execution failed: {str(e)}", -1
    
    def _execute_with_node(self, wasm_file: str, config: WASMConfig, args: List[str]) -> Tuple[bool, str, str, int]:
        """Execute WASM file using Node.js with WASI"""
        # Create a simple Node.js runner script
        runner_script = f"""
const fs = require('fs');
const {{ WASI }} = require('wasi');
const path = require('path');

const wasi = new WASI({{
    args: [...['{json.dumps(wasm_file)}'], ...{json.dumps(args)}],
    env: {{}},
    preopens: {{
        '/sandbox': '.'
    }}
}});

const wasmBuffer = fs.readFileSync({json.dumps(wasm_file)});
const wasmModule = new WebAssembly.Module(wasmBuffer);
const wasmInstance = new WebAssembly.Instance(wasmModule, {{
    wasi_snapshot_preview1: wasi.wasiImport
}});

try {{
    wasi.start(wasmInstance);
    console.log('WASM execution completed successfully');
}} catch (error) {{
    console.error('WASM execution failed:', error.message);
    process.exit(1);
}}
"""
        
        # Write runner script to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(runner_script)
            runner_path = f.name
        
        try:
            cmd = ["node", runner_path]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )
            return True, result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return False, "", "WASM execution timed out", -1
        except Exception as e:
            return False, "", f"WASM execution failed: {str(e)}", -1
        finally:
            # Clean up runner script
            os.unlink(runner_path)


class WASMFallbackManager:
    """Manages WASM fallback execution for applications"""
    
    def __init__(self):
        self.builder = WASMBuilder()
        self.executor = WASMExecutor()
        self.compatibility_checker = WASMCompatibilityChecker()
    
    def should_use_wasm_fallback(self, manifest: AppManifest, native_success: bool = False) -> bool:
        """
        Determine if WASM fallback should be used.
        
        Args:
            manifest: App manifest
            native_success: Whether native execution was successful
            
        Returns:
            True if WASM fallback should be used
        """
        if native_success:
            # Native execution worked, no need for WASM
            return False
        
        # Check if the app is WASM-compatible
        compatibility = self.compatibility_checker.check_compatibility(manifest)
        if compatibility < 0.4:
            # Too low compatibility for WASM
            return False
        
        # Check security requirements
        if manifest.security.allow_gpu:
            # WASM doesn't support GPU access
            return False
        
        # WASM is appropriate for this app
        return True
    
    def prepare_wasm_execution(self, manifest: AppManifest, source_path: str) -> Optional[Tuple[str, WASMConfig]]:
        """
        Prepare WASM execution by building the app and creating config.
        
        Args:
            manifest: App manifest
            source_path: Path to source code
            
        Returns:
            Tuple of (wasm_file_path, wasm_config) or None if preparation failed
        """
        # Build to WASM
        wasm_file = self.builder.build_to_wasm(manifest, source_path)
        if not wasm_file:
            return None
        
        # Create WASM configuration based on manifest security settings
        config = WASMConfig(
            engine=self._select_best_engine(),
            allowed_imports=[],  # Will be populated based on app needs
            filesystem_access=manifest.security.filesystem.value,
            network_access=manifest.security.network.value,
            allowed_env_vars=[],  # Will be populated based on app needs
            memory_limit=manifest.resources.memory_limit_mb if manifest.resources else 256,
            cpu_limit=manifest.resources.cpu_limit if manifest.resources else 0.5
        )
        
        return wasm_file, config
    
    def _select_best_engine(self) -> WASMEngine:
        """Select the best available WASM engine"""
        if WASMEngine.WASMTIME in self.executor.available_engines:
            return WASMEngine.WASMTIME
        elif WASMEngine.WASMER in self.executor.available_engines:
            return WASMEngine.WASMER
        elif WASMEngine.NODE_WASI in self.executor.available_engines:
            return WASMEngine.NODE_WASI
        else:
            # Return the first available engine, or WASMTIME as default
            return WASMEngine.WASMTIME
    
    def execute_wasm_fallback(self, wasm_file: str, config: WASMConfig, args: List[str] = None) -> Tuple[bool, str, str, int]:
        """
        Execute the WASM fallback.
        
        Args:
            wasm_file: Path to WASM file
            config: WASM execution configuration
            args: Arguments to pass to the program
            
        Returns:
            Tuple of (success, stdout, stderr, exit_code)
        """
        return self.executor.execute(wasm_file, config, args or [])


# Example usage and test
if __name__ == "__main__":
    from ..core.types.manifest_schema import (
        AppManifest, Publisher, Source, Versions, Build, Run, 
        Security, Trust, Resources
    )
    
    # Create a test manifest for a WASM-compatible app
    test_manifest = AppManifest(
        api_version="appstore.dev/v1",
        kind="Application",
        metadata={
            "app_id": "test.wasm-app",
            "name": "WASM Test App",
            "description": "A test application for WASM execution"
        },
        publisher=Publisher(
            name="Test Publisher",
            verified_domains=["test.com"]
        ),
        source=Source(
            type="github_repo",
            repo="test/wasm-app"
        ),
        versions=Versions(strategy="semver"),
        build=Build(
            strategy="native",
            commands=["cargo build --target wasm32-unknown-unknown --release"]
        ),
        run=Run(
            type="cli",
            entrypoint="app",
            args=["--help"]
        ),
        security=Security(
            sandbox="strict",
            network="none",
            filesystem="readonly",
            allow_gpu=False
        ),
        trust=Trust(verification="reproducible"),
        resources=Resources(cpu_limit=0.5, memory_limit_mb=256)
    )
    
    # Test WASM compatibility checker
    checker = WASMCompatibilityChecker()
    compatibility = checker.check_compatibility(test_manifest)
    print(f"WASM compatibility score: {compatibility}")
    
    # Test WASM fallback manager
    manager = WASMFallbackManager()
    should_use = manager.should_use_wasm_fallback(test_manifest, native_success=False)
    print(f"Should use WASM fallback: {should_use}")
    
    # Print available WASM engines
    print(f"Available WASM engines: {[e.value for e in manager.executor.available_engines]}")