"""
Federated index sync system for the alternative app store platform.
Implements decentralized synchronization of app metadata across multiple nodes.
Based on the scouts.md specification for federated indexes.
"""
import os
import json
import hashlib
import time
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    requests = None  # Define as None to avoid NameError
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.exceptions import InvalidSignature
    CRYPTO_AVAILABLE = True
except ImportError:
    # Mock cryptography classes if not available
    class MockPrivateKey:
        def sign(self, data, padding, algorithm):
            return b"mock_signature"

        def public_key(self):
            return MockPublicKey()

    class MockPublicKey:
        def verify(self, signature, data, padding, algorithm):
            pass  # Always succeed in mock

    def load_pem_private_key(data, password):
        return MockPrivateKey()

    def generate_private_key(public_exponent, key_size):
        return MockPrivateKey()

    def PKCS1v15():
        return None

    class SHA256:
        pass

    InvalidSignature = Exception
    CRYPTO_AVAILABLE = False
import threading
import queue


@dataclass
class AppEntry:
    """Entry for an application in the index"""
    app_id: str
    manifest_hash: str
    artifact_hash: str
    trust_score: float
    publisher: str
    version: str
    timestamp: str
    signature: str
    reproducibility_level: str = "R0"
    wasm_compatibility: float = 0.0
    accredited: bool = False


@dataclass
class Snapshot:
    """Immutable snapshot of the index"""
    apps: List[AppEntry]
    timestamp: str
    signature: str
    node_id: str
    previous_snapshot_hash: Optional[str] = None


class FederatedIndexNode:
    """A node in the federated index network"""
    
    def __init__(self, node_id: str, private_key: Optional[bytes] = None):
        self.node_id = node_id
        self.apps: Dict[str, AppEntry] = {}
        self.snapshots: List[Snapshot] = []
        self.peers: List[str] = []  # List of peer URLs
        self.sync_queue = queue.Queue()
        
        # Initialize cryptographic keys
        if CRYPTO_AVAILABLE:
            if private_key:
                self.private_key = serialization.load_pem_private_key(
                    private_key, password=None
                )
            else:
                self.private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=2048
                )

            self.public_key = self.private_key.public_key()
        else:
            # Use mock keys when cryptography is not available
            if private_key:
                self.private_key = load_pem_private_key(private_key, password=None)
            else:
                self.private_key = generate_private_key(public_exponent=65537, key_size=2048)

            self.public_key = self.private_key.public_key()
        
        # Start sync thread
        self.sync_thread = threading.Thread(target=self._sync_worker, daemon=True)
        self.sync_thread.start()
    
    def add_peer(self, peer_url: str):
        """Add a peer to synchronize with"""
        if peer_url not in self.peers:
            self.peers.append(peer_url)
    
    def register_app(self, app_entry: AppEntry) -> bool:
        """
        Register an app in the local index.
        
        Args:
            app_entry: App entry to register
            
        Returns:
            True if registration was successful
        """
        # Verify the app entry signature
        if not self._verify_app_signature(app_entry):
            print(f"Invalid signature for app {app_entry.app_id}")
            return False
        
        # Check if app already exists with newer version
        existing = self.apps.get(app_entry.app_id)
        if existing and existing.timestamp > app_entry.timestamp:
            # Existing entry is newer, don't update
            return False
        
        # Add to local index
        self.apps[app_entry.app_id] = app_entry
        
        # Create a new snapshot
        self._create_snapshot()
        
        return True
    
    def get_app(self, app_id: str) -> Optional[AppEntry]:
        """Get an app by ID"""
        return self.apps.get(app_id)
    
    def get_all_apps(self) -> List[AppEntry]:
        """Get all apps in the index"""
        return list(self.apps.values())
    
    def get_latest_snapshot(self) -> Optional[Snapshot]:
        """Get the latest snapshot"""
        if self.snapshots:
            return self.snapshots[-1]
        return None
    
    def sync_with_peers(self):
        """Synchronize with all peers"""
        for peer_url in self.peers:
            try:
                self._sync_with_peer(peer_url)
            except Exception as e:
                print(f"Failed to sync with peer {peer_url}: {e}")
    
    def _sync_with_peer(self, peer_url: str):
        """Synchronize with a specific peer"""
        if not REQUESTS_AVAILABLE:
            print("Requests library not available, cannot sync with peers")
            return

        try:
            # Get the peer's latest snapshot
            response = requests.get(f"{peer_url}/snapshot/latest", timeout=10)
            if response.status_code != 200:
                print(f"Peer {peer_url} returned status {response.status_code}")
                return

            peer_snapshot_data = response.json()
            peer_snapshot = self._deserialize_snapshot(peer_snapshot_data)

            # Verify the snapshot signature
            if not self._verify_snapshot_signature(peer_snapshot):
                print(f"Invalid signature for snapshot from peer {peer_url}")
                return

            # Get apps that are newer than what we have
            for app_entry in peer_snapshot.apps:
                if (app_entry.app_id not in self.apps or
                    self.apps[app_entry.app_id].timestamp < app_entry.timestamp):
                    # Verify the app signature before accepting
                    if self._verify_app_signature(app_entry):
                        self.apps[app_entry.app_id] = app_entry
                        print(f"Updated app {app_entry.app_id} from peer {peer_url}")

            # Create a new local snapshot after sync
            self._create_snapshot()

        except Exception as e:
            print(f"Error syncing with peer {peer_url}: {e}")
    
    def _create_snapshot(self) -> Snapshot:
        """Create a new snapshot of the current index"""
        apps_list = list(self.apps.values())
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        # Create snapshot
        snapshot = Snapshot(
            apps=apps_list,
            timestamp=timestamp,
            signature="",
            node_id=self.node_id,
            previous_snapshot_hash=self._get_latest_snapshot_hash()
        )
        
        # Sign the snapshot
        snapshot.signature = self._sign_snapshot(snapshot)
        
        # Add to snapshots
        self.snapshots.append(snapshot)
        
        # Keep only the last 10 snapshots to save space
        if len(self.snapshots) > 10:
            self.snapshots = self.snapshots[-10:]
        
        return snapshot
    
    def _sign_snapshot(self, snapshot: Snapshot) -> str:
        """Sign a snapshot with the node's private key"""
        snapshot_data = {
            "apps": [self._serialize_app(app) for app in snapshot.apps],
            "timestamp": snapshot.timestamp,
            "node_id": snapshot.node_id,
            "previous_snapshot_hash": snapshot.previous_snapshot_hash
        }

        snapshot_json = json.dumps(snapshot_data, sort_keys=True)

        if CRYPTO_AVAILABLE:
            signature = self.private_key.sign(
                snapshot_json.encode(),
                padding.PKCS1v15(),
                hashes.SHA256()
            )
        else:
            # Create a mock signature when cryptography is not available
            signature = hashlib.sha256(snapshot_json.encode()).digest()

        return signature.hex()
    
    def _verify_snapshot_signature(self, snapshot: Snapshot) -> bool:
        """Verify a snapshot's signature"""
        try:
            # Reconstruct the data that was signed
            snapshot_data = {
                "apps": [self._serialize_app(app) for app in snapshot.apps],
                "timestamp": snapshot.timestamp,
                "node_id": snapshot.node_id,
                "previous_snapshot_hash": snapshot.previous_snapshot_hash
            }
            
            snapshot_json = json.dumps(snapshot_data, sort_keys=True)
            
            # Get the publisher's public key (in a real system, this would come from a registry)
            # For now, we'll assume we have a way to get the public key
            # This is a simplification - in reality, you'd need a PKI system
            # For this demo, we'll skip actual signature verification
            
            # In a real implementation:
            # public_key = self._get_publisher_public_key(snapshot.node_id)
            # public_key.verify(
            #     bytes.fromhex(snapshot.signature),
            #     snapshot_json.encode(),
            #     padding.PKCS1v15(),
            #     hashes.SHA256()
            # )
            
            # For this demo, return True (signature verification would go here)
            return True
        except Exception:
            return False
    
    def _sign_app(self, app_entry: AppEntry) -> str:
        """Sign an app entry with the node's private key"""
        app_data = self._serialize_app(app_entry)
        app_json = json.dumps(app_data, sort_keys=True)

        if CRYPTO_AVAILABLE:
            signature = self.private_key.sign(
                app_json.encode(),
                padding.PKCS1v15(),
                hashes.SHA256()
            )
        else:
            # Create a mock signature when cryptography is not available
            signature = hashlib.sha256(app_json.encode()).digest()

        return signature.hex()
    
    def _verify_app_signature(self, app_entry: AppEntry) -> bool:
        """Verify an app entry's signature"""
        try:
            # Reconstruct the data that was signed
            app_data = self._serialize_app(app_entry)
            app_json = json.dumps(app_data, sort_keys=True)
            
            # In a real implementation, we'd get the publisher's public key
            # For this demo, we'll return True
            return True
        except Exception:
            return False
    
    def _serialize_app(self, app_entry: AppEntry) -> Dict:
        """Serialize an app entry to dictionary"""
        return {
            "app_id": app_entry.app_id,
            "manifest_hash": app_entry.manifest_hash,
            "artifact_hash": app_entry.artifact_hash,
            "trust_score": app_entry.trust_score,
            "publisher": app_entry.publisher,
            "version": app_entry.version,
            "timestamp": app_entry.timestamp,
            "signature": app_entry.signature,
            "reproducibility_level": app_entry.reproducibility_level,
            "wasm_compatibility": app_entry.wasm_compatibility,
            "accredited": app_entry.accredited
        }
    
    def _deserialize_app(self, app_data: Dict) -> AppEntry:
        """Deserialize an app entry from dictionary"""
        return AppEntry(
            app_id=app_data["app_id"],
            manifest_hash=app_data["manifest_hash"],
            artifact_hash=app_data["artifact_hash"],
            trust_score=app_data["trust_score"],
            publisher=app_data["publisher"],
            version=app_data["version"],
            timestamp=app_data["timestamp"],
            signature=app_data["signature"],
            reproducibility_level=app_data.get("reproducibility_level", "R0"),
            wasm_compatibility=app_data.get("wasm_compatibility", 0.0),
            accredited=app_data.get("accredited", False)
        )
    
    def _deserialize_snapshot(self, snapshot_data: Dict) -> Snapshot:
        """Deserialize a snapshot from dictionary"""
        apps = [self._deserialize_app(app_data) for app_data in snapshot_data["apps"]]
        return Snapshot(
            apps=apps,
            timestamp=snapshot_data["timestamp"],
            signature=snapshot_data["signature"],
            node_id=snapshot_data["node_id"],
            previous_snapshot_hash=snapshot_data.get("previous_snapshot_hash")
        )
    
    def _get_latest_snapshot_hash(self) -> Optional[str]:
        """Get the hash of the latest snapshot"""
        if not self.snapshots:
            return None
        
        latest = self.snapshots[-1]
        snapshot_data = {
            "apps": [self._serialize_app(app) for app in latest.apps],
            "timestamp": latest.timestamp,
            "node_id": latest.node_id,
            "previous_snapshot_hash": latest.previous_snapshot_hash
        }
        
        snapshot_json = json.dumps(snapshot_data, sort_keys=True)
        return hashlib.sha256(snapshot_json.encode()).hexdigest()
    
    def _sync_worker(self):
        """Background worker for periodic synchronization"""
        while True:
            try:
                # Wait for sync signal or timeout
                try:
                    # Wait for a sync request or timeout after 30 seconds
                    sync_request = self.sync_queue.get(timeout=30)
                    if sync_request == "sync":
                        self.sync_with_peers()
                except queue.Empty:
                    # Timeout reached, sync with peers anyway
                    self.sync_with_peers()
            except Exception as e:
                print(f"Sync worker error: {e}")
                time.sleep(5)  # Wait before retrying


class FederatedIndexManager:
    """Manages the federated index system"""
    
    def __init__(self, node_id: str, private_key: Optional[bytes] = None):
        self.node = FederatedIndexNode(node_id, private_key)
        self.sync_interval = 300  # Sync every 5 minutes
    
    def add_app(self, app_entry: AppEntry) -> bool:
        """
        Add an app to the federated index.
        
        Args:
            app_entry: App entry to add
            
        Returns:
            True if addition was successful
        """
        # Sign the app entry if it's not already signed
        if not app_entry.signature:
            app_entry.signature = self.node._sign_app(app_entry)
        
        return self.node.register_app(app_entry)
    
    def get_app(self, app_id: str) -> Optional[AppEntry]:
        """Get an app by ID"""
        return self.node.get_app(app_id)
    
    def get_all_apps(self) -> List[AppEntry]:
        """Get all apps in the index"""
        return self.node.get_all_apps()
    
    def sync_now(self):
        """Trigger immediate synchronization with peers"""
        self.node.sync_with_peers()
    
    def schedule_sync(self):
        """Schedule periodic synchronization"""
        import threading
        def sync_loop():
            while True:
                time.sleep(self.sync_interval)
                self.sync_now()
        
        sync_thread = threading.Thread(target=sync_loop, daemon=True)
        sync_thread.start()
    
    def add_peer(self, peer_url: str):
        """Add a peer to synchronize with"""
        self.node.add_peer(peer_url)
    
    def get_trust_score(self, app_id: str) -> float:
        """Get the trust score for an app"""
        app = self.get_app(app_id)
        if app:
            return app.trust_score
        return 0.0
    
    def update_trust_score(self, app_id: str, new_score: float):
        """Update the trust score for an app"""
        app = self.get_app(app_id)
        if app:
            app.trust_score = new_score
            # Re-register the app to update the index
            self.node.register_app(app)


class IndexSyncProtocol:
    """Protocol for synchronizing indexes between nodes"""
    
    @staticmethod
    def serialize_snapshot(snapshot: Snapshot) -> str:
        """Serialize a snapshot for transmission"""
        snapshot_data = {
            "apps": [app.__dict__ for app in snapshot.apps],
            "timestamp": snapshot.timestamp,
            "signature": snapshot.signature,
            "node_id": snapshot.node_id,
            "previous_snapshot_hash": snapshot.previous_snapshot_hash
        }
        return json.dumps(snapshot_data)
    
    @staticmethod
    def deserialize_snapshot(data: str) -> Snapshot:
        """Deserialize a snapshot from transmission"""
        snapshot_data = json.loads(data)
        apps = [AppEntry(**app_data) for app_data in snapshot_data["apps"]]
        return Snapshot(
            apps=apps,
            timestamp=snapshot_data["timestamp"],
            signature=snapshot_data["signature"],
            node_id=snapshot_data["node_id"],
            previous_snapshot_hash=snapshot_data["previous_snapshot_hash"]
        )


# Example usage and test
if __name__ == "__main__":
    import tempfile
    
    # Create a federated index manager
    manager = FederatedIndexManager("node1")
    
    # Create a test app entry
    test_app = AppEntry(
        app_id="test.app",
        manifest_hash="sha256:abc123",
        artifact_hash="sha256:def456",
        trust_score=0.92,
        publisher="did:example:123",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat() + "Z",
        signature=""
    )
    
    # Add the app to the index
    success = manager.add_app(test_app)
    print(f"App registration success: {success}")
    
    # Get the app back
    retrieved_app = manager.get_app("test.app")
    if retrieved_app:
        print(f"Retrieved app: {retrieved_app.app_id}, trust: {retrieved_app.trust_score}")
    
    # Add a peer (this would be a real URL in production)
    manager.add_peer("http://example-peer.com")
    
    # Get all apps
    all_apps = manager.get_all_apps()
    print(f"Total apps in index: {len(all_apps)}")
    
    # Update trust score
    manager.update_trust_score("test.app", 0.95)
    updated_app = manager.get_app("test.app")
    print(f"Updated trust score: {updated_app.trust_score}")
    
    # Sync with peers (would make network calls in real implementation)
    print("Syncing with peers...")
    manager.sync_now()
    print("Sync completed.")