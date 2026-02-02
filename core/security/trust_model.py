"""
Security and trust model implementation for the alternative app store platform.
Implements comprehensive security measures and trust scoring based on the scouts.md specification.
"""
import hashlib
import hmac
import time
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
import json
from ..types.manifest_schema import AppManifest
from .reproducible_builds import ReproducibilityLevel
from ...sandbox.dry_run import MalwareDetectionResult


class TrustLevel(Enum):
    """Trust levels for applications"""
    VERIFIED = "verified"      # Signed by publisher
    REPRODUCIBLE = "reproducible"  # Reproducible build
    COMMUNITY = "community"    # Community verified
    UNVERIFIED = "unverified"  # Runs sandboxed only


class SecurityLevel(Enum):
    """Security levels for execution"""
    STRICT = "strict"      # Maximum restrictions
    RELAXED = "relaxed"    # Moderate restrictions
    TRUSTED = "trusted"    # Minimal restrictions


class RiskCategory(Enum):
    """Categories of security risks"""
    NETWORK = "network"
    FILESYSTEM = "filesystem"
    PRIVILEGE = "privilege"
    CRYPTOGRAPHY = "cryptography"
    EXECUTION = "execution"


@dataclass
class TrustScore:
    """Comprehensive trust score for an application"""
    overall: float  # 0.0 to 1.0
    components: Dict[str, float]  # Individual component scores
    last_updated: str
    risk_factors: List[Dict[str, Any]]
    verification_status: TrustLevel


@dataclass
class SecurityPolicy:
    """Security policy for an application"""
    network_access: bool
    filesystem_access: str  # readonly, user_home, full
    gpu_access: bool
    privilege_elevation: bool
    resource_limits: Dict[str, Any]  # cpu, memory, disk
    execution_environment: str  # native, wasm, container, vm


class TrustEvaluator:
    """Evaluates trustworthiness of applications"""
    
    def __init__(self):
        self.trust_weights = {
            'publisher_verification': 0.25,
            'reproducibility': 0.25,
            'malware_scan': 0.20,
            'community_feedback': 0.15,
            'security_hardening': 0.10,
            'update_frequency': 0.05
        }
    
    def evaluate_trust(self, manifest: AppManifest, 
                      reproducibility_level: ReproducibilityLevel,
                      malware_result: MalwareDetectionResult,
                      community_score: float = 0.5) -> TrustScore:
        """
        Evaluate the trustworthiness of an application.
        
        Args:
            manifest: App manifest
            reproducibility_level: Reproducibility level
            malware_result: Malware detection result
            community_score: Community feedback score (0.0 to 1.0)
            
        Returns:
            TrustScore with overall score and components
        """
        components = {}
        
        # Publisher verification score
        pub_verified = self._evaluate_publisher_verification(manifest)
        components['publisher_verification'] = pub_verified
        
        # Reproducibility score
        repro_score = self._evaluate_reproducibility(reproducibility_level)
        components['reproducibility'] = repro_score
        
        # Malware scan score
        malware_score = self._evaluate_malware_result(malware_result)
        components['malware_scan'] = malware_score
        
        # Community feedback score
        components['community_feedback'] = community_score
        
        # Security hardening score
        sec_hardening = self._evaluate_security_hardening(manifest)
        components['security_hardening'] = sec_hardening
        
        # Update frequency score (placeholder)
        components['update_frequency'] = 0.05  # Default low score
        
        # Calculate overall trust score
        overall = sum(
            self.trust_weights[key] * score 
            for key, score in components.items()
        )
        
        # Determine verification status
        verification_status = self._determine_verification_status(
            pub_verified, repro_score, malware_score
        )
        
        # Identify risk factors
        risk_factors = self._identify_risk_factors(manifest, malware_result)
        
        return TrustScore(
            overall=max(0.0, min(1.0, overall)),
            components=components,
            last_updated=datetime.utcnow().isoformat() + "Z",
            risk_factors=risk_factors,
            verification_status=verification_status
        )
    
    def _evaluate_publisher_verification(self, manifest: AppManifest) -> float:
        """Evaluate publisher verification"""
        if manifest.publisher.verified_domains:
            return 1.0  # Fully verified
        else:
            return 0.2  # Unverified publisher
    
    def _evaluate_reproducibility(self, level: ReproducibilityLevel) -> float:
        """Evaluate reproducibility level"""
        scores = {
            ReproducibilityLevel.R0: 0.0,
            ReproducibilityLevel.R1: 0.3,
            ReproducibilityLevel.R2: 0.7,
            ReproducibilityLevel.R3: 1.0
        }
        return scores.get(level, 0.0)
    
    def _evaluate_malware_result(self, result: MalwareDetectionResult) -> float:
        """Evaluate malware detection result"""
        scores = {
            MalwareDetectionResult.SAFE: 1.0,
            MalwareDetectionResult.UNKNOWN: 0.5,
            MalwareDetectionResult.SUSPICIOUS: 0.2,
            MalwareDetectionResult.MALICIOUS: 0.0
        }
        return scores.get(result, 0.5)
    
    def _evaluate_security_hardening(self, manifest: AppManifest) -> float:
        """Evaluate security hardening in manifest"""
        score = 0.5  # Base score
        
        # Check security settings
        if manifest.security.sandbox == "strict":
            score += 0.2
        elif manifest.security.sandbox == "relaxed":
            score += 0.1
        
        if manifest.security.network == "none":
            score += 0.1
        elif manifest.security.network == "outbound":
            score -= 0.1
        
        if manifest.security.filesystem == "readonly":
            score += 0.15
        elif manifest.security.filesystem == "user_home":
            score += 0.05
        
        if not manifest.security.allow_gpu:
            score += 0.05
        
        return max(0.0, min(1.0, score))
    
    def _determine_verification_status(self, pub_verified: float, 
                                     repro_score: float, malware_score: float) -> TrustLevel:
        """Determine verification status based on scores"""
        if pub_verified >= 0.9 and repro_score >= 0.7 and malware_score >= 0.9:
            return TrustLevel.VERIFIED
        elif repro_score >= 0.5 and malware_score >= 0.7:
            return TrustLevel.REPRODUCIBLE
        elif malware_score >= 0.5:
            return TrustLevel.COMMUNITY
        else:
            return TrustLevel.UNVERIFIED
    
    def _identify_risk_factors(self, manifest: AppManifest, 
                              malware_result: MalwareDetectionResult) -> List[Dict[str, Any]]:
        """Identify potential risk factors"""
        risk_factors = []
        
        # Network risk
        if manifest.security.network != "none":
            risk_factors.append({
                "category": RiskCategory.NETWORK.value,
                "severity": "medium" if malware_result == MalwareDetectionResult.SAFE else "high",
                "description": "Application has network access"
            })
        
        # Filesystem risk
        if manifest.security.filesystem != "readonly":
            risk_factors.append({
                "category": RiskCategory.FILESYSTEM.value,
                "severity": "low" if manifest.security.filesystem == "user_home" else "high",
                "description": f"Application has {manifest.security.filesystem} filesystem access"
            })
        
        # GPU risk
        if manifest.security.allow_gpu:
            risk_factors.append({
                "category": RiskCategory.PRIVILEGE.value,
                "severity": "medium",
                "description": "Application has GPU access"
            })
        
        # Malware risk
        if malware_result in [MalwareDetectionResult.SUSPICIOUS, MalwareDetectionResult.MALICIOUS]:
            risk_factors.append({
                "category": RiskCategory.EXECUTION.value,
                "severity": "critical" if malware_result == MalwareDetectionResult.MALICIOUS else "high",
                "description": f"Malware scan returned {malware_result.value}"
            })
        
        return risk_factors


class SecurityOrchestrator:
    """Orchestrates security policies and enforcement"""
    
    def __init__(self):
        self.policy_templates = {
            TrustLevel.VERIFIED: SecurityPolicy(
                network_access=True,
                filesystem_access="user_home",
                gpu_access=True,
                privilege_elevation=False,
                resource_limits={"cpu": 1.0, "memory_mb": 2048},
                execution_environment="native"
            ),
            TrustLevel.REPRODUCIBLE: SecurityPolicy(
                network_access=True,
                filesystem_access="user_home",
                gpu_access=False,
                privilege_elevation=False,
                resource_limits={"cpu": 0.5, "memory_mb": 1024},
                execution_environment="native"
            ),
            TrustLevel.COMMUNITY: SecurityPolicy(
                network_access=False,
                filesystem_access="readonly",
                gpu_access=False,
                privilege_elevation=False,
                resource_limits={"cpu": 0.25, "memory_mb": 512},
                execution_environment="wasm"
            ),
            TrustLevel.UNVERIFIED: SecurityPolicy(
                network_access=False,
                filesystem_access="readonly",
                gpu_access=False,
                privilege_elevation=False,
                resource_limits={"cpu": 0.1, "memory_mb": 256},
                execution_environment="wasm"
            )
        }
        self.active_policies: Dict[str, SecurityPolicy] = {}
        self.lock = threading.Lock()
    
    def assign_security_policy(self, app_id: str, trust_level: TrustLevel) -> SecurityPolicy:
        """Assign a security policy based on trust level"""
        with self.lock:
            template = self.policy_templates.get(trust_level)
            if not template:
                # Default to unverified policy if trust level not found
                template = self.policy_templates[TrustLevel.UNVERIFIED]
            
            # Create a copy of the policy for this app
            policy = SecurityPolicy(
                network_access=template.network_access,
                filesystem_access=template.filesystem_access,
                gpu_access=template.gpu_access,
                privilege_elevation=template.privilege_elevation,
                resource_limits=template.resource_limits.copy(),
                execution_environment=template.execution_environment
            )
            
            self.active_policies[app_id] = policy
            return policy
    
    def enforce_policy(self, app_id: str, operation: str, params: Dict) -> Tuple[bool, str]:
        """Enforce security policy for an operation"""
        with self.lock:
            policy = self.active_policies.get(app_id)
            if not policy:
                return False, f"No policy found for app {app_id}"
            
            # Check specific operations
            if operation == "network_access":
                if not policy.network_access:
                    return False, "Network access denied by security policy"
                return True, "Network access allowed"
            
            elif operation == "filesystem_access":
                access_type = params.get("access_type", "read")
                if policy.filesystem_access == "readonly" and access_type == "write":
                    return False, "Write access denied by security policy"
                elif policy.filesystem_access == "readonly":
                    return True, "Read access allowed"
                elif policy.filesystem_access == "user_home":
                    return True, "User home access allowed"
                else:
                    return False, "Filesystem access denied"
            
            elif operation == "gpu_access":
                if not policy.gpu_access:
                    return False, "GPU access denied by security policy"
                return True, "GPU access allowed"
            
            elif operation == "resource_request":
                requested_cpu = params.get("cpu", 0)
                requested_memory = params.get("memory_mb", 0)
                
                if requested_cpu > policy.resource_limits.get("cpu", 0):
                    return False, f"CPU request {requested_cpu} exceeds limit {policy.resource_limits.get('cpu', 0)}"
                
                if requested_memory > policy.resource_limits.get("memory_mb", 0):
                    return False, f"Memory request {requested_memory}MB exceeds limit {policy.resource_limits.get('memory_mb', 0)}"
                
                return True, "Resource request allowed"
            
            else:
                return False, f"Unknown operation: {operation}"
    
    def get_policy(self, app_id: str) -> Optional[SecurityPolicy]:
        """Get security policy for an app"""
        with self.lock:
            return self.active_policies.get(app_id)

    def update_policy(self, app_id: str, new_policy: SecurityPolicy):
        """Update security policy for an app"""
        with self.lock:
            self.active_policies[app_id] = new_policy


class TrustRegistry:
    """Registry for storing and managing trust information"""
    
    def __init__(self):
        self.trust_scores: Dict[str, TrustScore] = {}
        self.audits: List[Dict[str, Any]] = []
        self.revocations: List[Dict[str, Any]] = []
        self.lock = threading.Lock()
    
    def store_trust_score(self, app_id: str, trust_score: TrustScore):
        """Store trust score for an application"""
        with self.lock:
            self.trust_scores[app_id] = trust_score
    
    def get_trust_score(self, app_id: str) -> Optional[TrustScore]:
        """Get trust score for an application"""
        with self.lock:
            return self.trust_scores.get(app_id)
    
    def audit_trust(self, app_id: str, auditor: str, findings: List[str]) -> str:
        """Record a trust audit"""
        with self.lock:
            audit_id = f"audit_{int(time.time())}_{hashlib.md5((app_id + auditor).encode()).hexdigest()[:8]}"
            
            audit_record = {
                "audit_id": audit_id,
                "app_id": app_id,
                "auditor": auditor,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "findings": findings,
                "trust_before": self.trust_scores.get(app_id).overall if self.trust_scores.get(app_id) else 0.0
            }
            
            self.audits.append(audit_record)
            return audit_id
    
    def revoke_trust(self, app_id: str, reason: str, revoker: str) -> str:
        """Revoke trust for an application"""
        with self.lock:
            # Update trust score to 0
            if app_id in self.trust_scores:
                old_score = self.trust_scores[app_id].overall
                self.trust_scores[app_id] = TrustScore(
                    overall=0.0,
                    components={},
                    last_updated=datetime.utcnow().isoformat() + "Z",
                    risk_factors=[{"category": "trust", "severity": "critical", "description": "Trust revoked"}],
                    verification_status=TrustLevel.UNVERIFIED
                )
            
            revocation_id = f"revoke_{int(time.time())}_{hashlib.md5((app_id + reason).encode()).hexdigest()[:8]}"
            
            revocation_record = {
                "revocation_id": revocation_id,
                "app_id": app_id,
                "reason": reason,
                "revoker": revoker,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "trust_before": old_score if 'old_score' in locals() else 0.0
            }
            
            self.revocations.append(revocation_record)
            return revocation_id
    
    def get_audit_history(self, app_id: str) -> List[Dict[str, Any]]:
        """Get audit history for an application"""
        with self.lock:
            return [audit for audit in self.audits if audit["app_id"] == app_id]
    
    def get_revocation_history(self, app_id: str) -> List[Dict[str, Any]]:
        """Get revocation history for an application"""
        with self.lock:
            return [revocation for revocation in self.revocations if revocation["app_id"] == app_id]


class SecurityManager:
    """Main security and trust management system"""
    
    def __init__(self):
        self.evaluator = TrustEvaluator()
        self.orchestrator = SecurityOrchestrator()
        self.registry = TrustRegistry()
    
    def assess_application(self, manifest: AppManifest,
                          reproducibility_level: ReproducibilityLevel,
                          malware_result: MalwareDetectionResult,
                          community_score: float = 0.5) -> Dict[str, Any]:
        """
        Assess an application's security and trustworthiness.
        
        Args:
            manifest: App manifest
            reproducibility_level: Reproducibility level
            malware_result: Malware detection result
            community_score: Community feedback score
            
        Returns:
            Dictionary with assessment results
        """
        # Evaluate trust
        trust_score = self.evaluator.evaluate_trust(
            manifest, reproducibility_level, malware_result, community_score
        )
        
        # Store trust score
        self.registry.store_trust_score(manifest.metadata["app_id"], trust_score)
        
        # Assign security policy based on trust level
        security_policy = self.orchestrator.assign_security_policy(
            manifest.metadata["app_id"], trust_score.verification_status
        )
        
        return {
            "app_id": manifest.metadata["app_id"],
            "trust_score": trust_score.overall,
            "trust_level": trust_score.verification_status.value,
            "security_policy": {
                "network_access": security_policy.network_access,
                "filesystem_access": security_policy.filesystem_access,
                "gpu_access": security_policy.gpu_access,
                "execution_environment": security_policy.execution_environment,
                "resource_limits": security_policy.resource_limits
            },
            "risk_factors": trust_score.risk_factors,
            "components": trust_score.components,
            "assessment_timestamp": trust_score.last_updated
        }
    
    def enforce_security_policy(self, app_id: str, operation: str, params: Dict) -> Dict[str, Any]:
        """Enforce security policy for an operation"""
        success, message = self.orchestrator.enforce_policy(app_id, operation, params)
        
        return {
            "success": success,
            "message": message,
            "operation": operation,
            "app_id": app_id
        }
    
    def update_trust_score(self, app_id: str, new_score: float, reason: str):
        """Update trust score for an application"""
        current_score = self.registry.get_trust_score(app_id)
        if current_score:
            # Create updated trust score
            updated_score = TrustScore(
                overall=new_score,
                components=current_score.components,
                last_updated=datetime.utcnow().isoformat() + "Z",
                risk_factors=current_score.risk_factors,
                verification_status=current_score.verification_status
            )
            self.registry.store_trust_score(app_id, updated_score)
    
    def audit_application(self, app_id: str, auditor: str, findings: List[str]):
        """Audit an application's trust"""
        return self.registry.audit_trust(app_id, auditor, findings)
    
    def revoke_application_trust(self, app_id: str, reason: str, revoker: str):
        """Revoke trust for an application"""
        return self.registry.revoke_trust(app_id, reason, revoker)
    
    def get_security_report(self, app_id: str) -> Dict[str, Any]:
        """Generate a security report for an application"""
        trust_score = self.registry.get_trust_score(app_id)
        security_policy = self.orchestrator.get_policy(app_id)
        audits = self.registry.get_audit_history(app_id)
        revocations = self.registry.get_revocation_history(app_id)

        return {
            "app_id": app_id,
            "trust_score": trust_score.overall if trust_score else 0.0,
            "trust_level": trust_score.verification_status.value if trust_score else "unknown",
            "security_policy": {
                "network_access": security_policy.network_access if security_policy else False,
                "filesystem_access": security_policy.filesystem_access if security_policy else "unknown",
                "gpu_access": security_policy.gpu_access if security_policy else False,
                "execution_environment": security_policy.execution_environment if security_policy else "unknown",
                "resource_limits": security_policy.resource_limits if security_policy else {}
            } if security_policy else {},
            "risk_factors": trust_score.risk_factors if trust_score else [],
            "audit_history": audits,
            "revocation_history": revocations,
            "report_generated_at": datetime.utcnow().isoformat() + "Z"
        }


# Example usage and test
if __name__ == "__main__":
    from ...types.manifest_schema import (
        AppManifest, Publisher, Source, Versions, Build, Run,
        Security, Trust, Resources, RuntimeType, NetworkPolicy, FilesystemPolicy
    )
    from .reproducible_builds import ReproducibilityLevel
    from ...sandbox.dry_run import MalwareDetectionResult
    
    # Create a security manager
    security_manager = SecurityManager()
    
    # Create a test manifest
    test_manifest = AppManifest(
        api_version="appstore.dev/v1",
        kind="Application",
        metadata={
            "app_id": "test.secure-app",
            "name": "Secure Test App",
            "description": "A test application for security assessment"
        },
        publisher=Publisher(
            name="Secure Publisher",
            verified_domains=["secure-pub.com"]
        ),
        source=Source(
            type="github_repo",
            repo="secure-pub/secure-app"
        ),
        versions=Versions(strategy="semver"),
        build=Build(
            strategy="docker",
            commands=["echo 'Building securely'"]
        ),
        run=Run(
            type="cli",
            entrypoint="app",
            args=[]
        ),
        security=Security(
            sandbox="strict",
            network="none",
            filesystem="readonly",
            allow_gpu=False
        ),
        trust=Trust(verification="R2"),
        resources=Resources(cpu_limit=0.5, memory_limit_mb=512)
    )
    
    # Assess the application
    assessment = security_manager.assess_application(
        test_manifest,
        ReproducibilityLevel.R2,
        MalwareDetectionResult.SAFE,
        community_score=0.8
    )
    
    print("Application Assessment:")
    print(f"  App ID: {assessment['app_id']}")
    print(f"  Trust Score: {assessment['trust_score']:.2f}")
    print(f"  Trust Level: {assessment['trust_level']}")
    print(f"  Network Access: {assessment['security_policy']['network_access']}")
    print(f"  Filesystem Access: {assessment['security_policy']['filesystem_access']}")
    print(f"  Risk Factors: {len(assessment['risk_factors'])}")
    
    # Try to enforce a security policy
    policy_check = security_manager.enforce_security_policy(
        "test.secure-app", "network_access", {}
    )
    print(f"\nPolicy Enforcement Result: {policy_check}")
    
    # Get a security report
    report = security_manager.get_security_report("test.secure-app")
    print(f"\nSecurity Report:")
    print(f"  Trust Score: {report['trust_score']:.2f}")
    print(f"  Trust Level: {report['trust_level']}")
    print(f"  Audit History: {len(report['audit_history'])} audits")
    print(f"  Revocation History: {len(report['revocation_history'])} revocations")
    
    # Audit the application
    audit_id = security_manager.audit_application(
        "test.secure-app", "security-auditor", ["Code review completed", "No vulnerabilities found"]
    )
    print(f"\nAudit recorded with ID: {audit_id}")
    
    # Update trust score
    security_manager.update_trust_score("test.secure-app", 0.95, "Excellent security practices")
    updated_report = security_manager.get_security_report("test.secure-app")
    print(f"Updated trust score: {updated_report['trust_score']:.2f}")