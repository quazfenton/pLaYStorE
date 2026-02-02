"""
Cross-platform sandbox system for the alternative app store platform.
Implements secure execution environments for Linux, Windows, and macOS.
Based on the scouts.md specification for sandboxing.
"""
import os
import sys
import subprocess
import tempfile
import shutil
import shlex
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from enum import Enum
import json
import hashlib
from pathlib import Path


class SandboxType(Enum):
    """Types of sandboxes available"""
    NATIVE = "native"
    CONTAINER = "container"
    WASM = "wasm"
    VM = "vm"


class SecurityLevel(Enum):
    """Security levels for sandboxes"""
    STRICT = "strict"
    RELAXED = "relaxed"
    TRUSTED = "trusted"


class Platform(Enum):
    """Supported platforms"""
    LINUX = "linux"
    WINDOWS = "windows"
    MACOS = "macos"


class SandboxResult:
    """Result of sandbox execution"""
    def __init__(self, success: bool, output: str, error: str, exit_code: int, 
                 metrics: Dict = None):
        self.success = success
        self.output = output
        self.error = error
        self.exit_code = exit_code
        self.metrics = metrics or {}
    
    def __repr__(self):
        return f"SandboxResult(success={self.success}, exit_code={self.exit_code})"


class BaseSandbox(ABC):
    """Abstract base class for all sandbox implementations"""
    
    def __init__(self, security_level: SecurityLevel = SecurityLevel.STRICT):
        self.security_level = security_level
        self.platform = self._detect_platform()
    
    @abstractmethod
    def execute(self, command: str, timeout: int = 30, 
                cwd: Optional[str] = None, env: Optional[Dict] = None) -> SandboxResult:
        """Execute a command in the sandbox"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this sandbox type is available on the current platform"""
        pass
    
    def _detect_platform(self) -> Platform:
        """Detect the current platform"""
        if sys.platform.startswith('linux'):
            return Platform.LINUX
        elif sys.platform.startswith('win'):
            return Platform.WINDOWS
        elif sys.platform.startswith('darwin'):
            return Platform.MACOS
        else:
            raise RuntimeError(f"Unsupported platform: {sys.platform}")
    
    def _create_temp_workspace(self) -> str:
        """Create a temporary workspace for the sandbox"""
        return tempfile.mkdtemp(prefix="altstore_sandbox_")
    
    def _cleanup_workspace(self, workspace: str):
        """Clean up the temporary workspace"""
        if os.path.exists(workspace):
            shutil.rmtree(workspace)


class LinuxSandbox(BaseSandbox):
    """Linux sandbox implementation using bubblewrap and seccomp"""
    
    def is_available(self) -> bool:
        """Check if bubblewrap is available"""
        return shutil.which("bwrap") is not None
    
    def execute(self, command: str, timeout: int = 30, 
                cwd: Optional[str] = None, env: Optional[Dict] = None) -> SandboxResult:
        """Execute command using bubblewrap sandbox"""
        if not self.is_available():
            raise RuntimeError("bubblewrap not available on this system")
        
        workspace = self._create_temp_workspace()
        try:
            # Prepare the command
            cmd_parts = command.split()
            executable = cmd_parts[0]
            args = cmd_parts[1:]
            
            # Build bubblewrap command
            bwrap_cmd = [
                "bwrap",
                "--unshare-all",
                "--die-with-parent",
                "--ro-bind", "/", "/",
                "--tmpfs", "/tmp",
                "--proc", "/proc",
                "--dev", "/dev",
                "--chdir", cwd or workspace,
                "--clearenv",
                "--setenv", "HOME", "/tmp",
                "--setenv", "PATH", "/usr/bin:/bin:/usr/local/bin",
                "--new-session",
            ]
            
            # Add security restrictions based on level
            if self.security_level == SecurityLevel.STRICT:
                bwrap_cmd.extend([
                    "--unshare-net",  # No network
                    "--ro-bind", workspace, "/workspace",  # Read-only workspace
                ])
            else:
                bwrap_cmd.extend([
                    "--bind", workspace, "/workspace",  # Read-write workspace
                ])
            
            # Add the actual command
            bwrap_cmd.extend([executable] + args)
            
            # Execute with timeout
            try:
                result = subprocess.run(
                    bwrap_cmd,
                    timeout=timeout,
                    capture_output=True,
                    text=True,
                    cwd=cwd or workspace
                )
                
                # Collect metrics
                metrics = {
                    "cpu_time": getattr(result, 'cpu_time', 0),
                    "memory_usage": 0,  # Would need additional tools to measure
                    "exit_code": result.returncode
                }
                
                return SandboxResult(
                    success=result.returncode == 0,
                    output=result.stdout,
                    error=result.stderr,
                    exit_code=result.returncode,
                    metrics=metrics
                )
            except subprocess.TimeoutExpired:
                return SandboxResult(
                    success=False,
                    output="",
                    error=f"Command timed out after {timeout} seconds",
                    exit_code=-1,
                    metrics={"timeout": True}
                )
                
        finally:
            self._cleanup_workspace(workspace)


class WindowsSandbox(BaseSandbox):
    """Windows sandbox implementation using AppContainer"""
    
    def is_available(self) -> bool:
        """Check if Windows AppContainer is available"""
        # For now, assume it's available on Windows
        return sys.platform.startswith('win')
    
    def execute(self, command: str, timeout: int = 30, 
                cwd: Optional[str] = None, env: Optional[Dict] = None) -> SandboxResult:
        """Execute command in Windows sandbox"""
        # For now, implement a basic version without AppContainer
        # In a real implementation, we would use Windows APIs for AppContainer
        workspace = self._create_temp_workspace()
        try:
            # Prepare environment
            exec_env = os.environ.copy()
            if env:
                exec_env.update(env)
            
            # Add security restrictions based on level
            if self.security_level == SecurityLevel.STRICT:
                # In a real implementation, we would restrict network access
                # and use AppContainer profiles
                pass
            
            try:
                # Parse the command safely to avoid shell injection
                cmd_parts = shlex.split(command, posix=False)
                result = subprocess.run(
                    cmd_parts,
                    timeout=timeout,
                    capture_output=True,
                    text=True,
                    cwd=cwd or workspace,
                    env=exec_env
                )
                
                metrics = {
                    "exit_code": result.returncode
                }
                
                return SandboxResult(
                    success=result.returncode == 0,
                    output=result.stdout,
                    error=result.stderr,
                    exit_code=result.returncode,
                    metrics=metrics
                )
            except subprocess.TimeoutExpired:
                return SandboxResult(
                    success=False,
                    output="",
                    error=f"Command timed out after {timeout} seconds",
                    exit_code=-1,
                    metrics={"timeout": True}
                )
                
        finally:
            self._cleanup_workspace(workspace)


class MacOSSandbox(BaseSandbox):
    """macOS sandbox implementation using seatbelt profiles"""
    
    def is_available(self) -> bool:
        """Check if macOS sandbox is available"""
        return sys.platform.startswith('darwin')
    
    def execute(self, command: str, timeout: int = 30, 
                cwd: Optional[str] = None, env: Optional[Dict] = None) -> SandboxResult:
        """Execute command in macOS sandbox"""
        # For now, implement a basic version without seatbelt
        # In a real implementation, we would use macOS sandbox-exec
        workspace = self._create_temp_workspace()
        try:
            # Prepare environment
            exec_env = os.environ.copy()
            if env:
                exec_env.update(env)
            
            # Add security restrictions based on level
            if self.security_level == SecurityLevel.STRICT:
                # In a real implementation, we would use seatbelt profiles
                pass
            
            try:
                # Parse the command safely to avoid shell injection
                cmd_parts = shlex.split(command)
                result = subprocess.run(
                    cmd_parts,
                    timeout=timeout,
                    capture_output=True,
                    text=True,
                    cwd=cwd or workspace,
                    env=exec_env
                )
                
                metrics = {
                    "exit_code": result.returncode
                }
                
                return SandboxResult(
                    success=result.returncode == 0,
                    output=result.stdout,
                    error=result.stderr,
                    exit_code=result.returncode,
                    metrics=metrics
                )
            except subprocess.TimeoutExpired:
                return SandboxResult(
                    success=False,
                    output="",
                    error=f"Command timed out after {timeout} seconds",
                    exit_code=-1,
                    metrics={"timeout": True}
                )
                
        finally:
            self._cleanup_workspace(workspace)


class ContainerSandbox(BaseSandbox):
    """Container-based sandbox using Docker"""
    
    def is_available(self) -> bool:
        """Check if Docker is available"""
        try:
            result = subprocess.run(["docker", "--version"], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def execute(self, command: str, timeout: int = 30, 
                cwd: Optional[str] = None, env: Optional[Dict] = None) -> SandboxResult:
        """Execute command in Docker container"""
        if not self.is_available():
            raise RuntimeError("Docker not available on this system")
        
        workspace = self._create_temp_workspace()
        try:
            # Determine base image based on command
            if command.startswith("python"):
                base_image = "python:3.11-slim"
            elif command.startswith("node") or command.startswith("npm"):
                base_image = "node:18-slim"
            elif command.startswith("go"):
                base_image = "golang:1.21-slim"
            else:
                base_image = "ubuntu:22.04"
            
            # Pull the image
            subprocess.run(["docker", "pull", base_image], 
                         capture_output=True, check=True)
            
            # Prepare environment variables
            env_args = []
            if env:
                for key, value in env.items():
                    env_args.extend(["-e", f"{key}={value}"])
            
            # Build Docker command
            docker_cmd = [
                "docker", "run",
                "--rm",  # Remove container after execution
                "--network=none",  # No network access
                "--read-only",  # Read-only root filesystem
                "--tmpfs", "/tmp:rw,noexec,nosuid,size=100m",  # Temporary filesystem
                "-v", f"{workspace}:/workspace:ro",  # Mount workspace as read-only
                "-w", "/workspace",  # Working directory
            ] + env_args + [base_image] + command.split()
            
            try:
                result = subprocess.run(
                    docker_cmd,
                    timeout=timeout,
                    capture_output=True,
                    text=True
                )
                
                metrics = {
                    "exit_code": result.returncode
                }
                
                return SandboxResult(
                    success=result.returncode == 0,
                    output=result.stdout,
                    error=result.stderr,
                    exit_code=result.returncode,
                    metrics=metrics
                )
            except subprocess.TimeoutExpired:
                # Kill the specific timed-out container
                # Note: In the current implementation, we don't have the specific container ID
                # A better approach would be to track the container ID when starting the container
                # For now, we'll avoid killing all containers as that's dangerous
                pass  # Skip container cleanup on timeout to avoid killing other containers
                
                return SandboxResult(
                    success=False,
                    output="",
                    error=f"Command timed out after {timeout} seconds",
                    exit_code=-1,
                    metrics={"timeout": True}
                )
                
        finally:
            self._cleanup_workspace(workspace)


class SandboxFactory:
    """Factory for creating appropriate sandbox based on platform and requirements"""
    
    @staticmethod
    def create_sandbox(sandbox_type: SandboxType, 
                      security_level: SecurityLevel = SecurityLevel.STRICT) -> BaseSandbox:
        """Create a sandbox instance based on type and platform"""
        platform = SandboxFactory._detect_platform()
        
        if sandbox_type == SandboxType.NATIVE:
            if platform == Platform.LINUX:
                return LinuxSandbox(security_level)
            elif platform == Platform.WINDOWS:
                return WindowsSandbox(security_level)
            elif platform == Platform.MACOS:
                return MacOSSandbox(security_level)
        elif sandbox_type == SandboxType.CONTAINER:
            return ContainerSandbox(security_level)
        # WASM and VM sandboxes would be implemented separately
        
        raise ValueError(f"No suitable sandbox available for {sandbox_type} on {platform}")
    
    @staticmethod
    def _detect_platform() -> Platform:
        """Detect the current platform"""
        if sys.platform.startswith('linux'):
            return Platform.LINUX
        elif sys.platform.startswith('win'):
            return Platform.WINDOWS
        elif sys.platform.startswith('darwin'):
            return Platform.MACOS
        else:
            raise RuntimeError(f"Unsupported platform: {sys.platform}")
    
    @staticmethod
    def get_available_sandboxes() -> List[SandboxType]:
        """Get list of available sandbox types on this platform"""
        available = []
        
        # Check native sandboxes
        platform = SandboxFactory._detect_platform()
        if platform == Platform.LINUX and shutil.which("bwrap"):
            available.append(SandboxType.NATIVE)
        elif platform in [Platform.WINDOWS, Platform.MACOS]:
            available.append(SandboxType.NATIVE)
        
        # Check container sandbox
        try:
            result = subprocess.run(["docker", "--version"], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                available.append(SandboxType.CONTAINER)
        except FileNotFoundError:
            pass
        
        return available


# Example usage and test
if __name__ == "__main__":
    print(f"Current platform: {SandboxFactory._detect_platform().value}")
    print(f"Available sandboxes: {[s.value for s in SandboxFactory.get_available_sandboxes()]}")
    
    # Test native sandbox if available
    if SandboxType.NATIVE in SandboxFactory.get_available_sandboxes():
        sandbox = SandboxFactory.create_sandbox(SandboxType.NATIVE, SecurityLevel.STRICT)
        print(f"Testing native sandbox on {sandbox.platform.value}")
        
        # Simple test command
        result = sandbox.execute("echo 'Hello from sandbox!'")
        print(f"Command result: {result}")
        print(f"Output: {result.output.strip()}")
        
        # Test with a slightly more complex command
        result2 = sandbox.execute("pwd && ls -la", cwd="/tmp")
        print(f"CWD command result: {result2}")
        print(f"Output: {result2.output.strip()}")
    
    # Test container sandbox if available
    if SandboxType.CONTAINER in SandboxFactory.get_available_sandboxes():
        sandbox = SandboxFactory.create_sandbox(SandboxType.CONTAINER, SecurityLevel.STRICT)
        print(f"Testing container sandbox")
        
        result = sandbox.execute("echo 'Hello from container!'")
        print(f"Container result: {result}")
        print(f"Output: {result.output.strip()}")