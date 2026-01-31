"""
Monetization and reputation system for the alternative app store platform.
Implements economic incentives and reputation scoring for publishers and users.
Based on the scouts.md specification for monetized/reputation-gated submission.
"""
import time
import hashlib
import json
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading


class ReputationType(Enum):
    """Types of reputation scores"""
    PUBLISHER = "publisher"
    USER = "user"
    APP = "app"


class SubmissionTier(Enum):
    """Submission tiers based on reputation/credentials"""
    ACCREDITED = "accredited"      # High trust, automatic approval
    VERIFIED = "verified"          # Medium trust, faster review
    COMMUNITY = "community"        # Low trust, requires review
    UNVERIFIED = "unverified"      # No trust, requires payment/deposit


@dataclass
class ReputationRecord:
    """Record of reputation for an entity"""
    entity_id: str
    reputation_type: ReputationType
    score: float  # 0.0 to 1.0
    history: List[Dict]  # History of reputation changes
    last_updated: str
    metadata: Dict[str, Any]


@dataclass
class SubmissionRecord:
    """Record of a submission attempt"""
    submission_id: str
    app_id: str
    publisher_id: str
    tier: SubmissionTier
    fee_paid: float
    timestamp: str
    status: str  # pending, approved, rejected, quarantined
    review_notes: List[str]
    metadata: Dict[str, Any]


@dataclass
class TransactionRecord:
    """Record of a financial transaction"""
    transaction_id: str
    from_entity: str
    to_entity: str
    amount: float
    transaction_type: str  # fee, reward, stake, refund
    timestamp: str
    status: str  # pending, completed, failed, refunded
    metadata: Dict[str, Any]


class ReputationCalculator:
    """Calculates reputation scores based on various factors"""
    
    def __init__(self):
        # Weight factors for different reputation signals
        self.weights = {
            'past_success_rate': 0.3,
            'community_reviews': 0.2,
            'reproducibility': 0.2,
            'security_score': 0.15,
            'update_frequency': 0.1,
            'malware_free_history': 0.05
        }
    
    def calculate_publisher_reputation(self, publisher_data: Dict) -> float:
        """
        Calculate publisher reputation based on various factors.
        
        Args:
            publisher_data: Dictionary containing publisher information
            
        Returns:
            Reputation score (0.0 to 1.0)
        """
        score = 0.0
        
        # Past success rate (0-1)
        past_success = publisher_data.get('past_success_rate', 0.0)
        score += self.weights['past_success_rate'] * past_success
        
        # Community reviews average (0-1)
        avg_review = publisher_data.get('avg_community_review', 0.0)
        score += self.weights['community_reviews'] * avg_review
        
        # Reproducibility score (0-1)
        repro_score = publisher_data.get('reproducibility_score', 0.0)
        score += self.weights['reproducibility'] * repro_score
        
        # Security score (0-1)
        sec_score = publisher_data.get('security_score', 0.0)
        score += self.weights['security_score'] * sec_score
        
        # Update frequency bonus (0-1)
        update_freq = publisher_data.get('update_frequency_score', 0.0)
        score += self.weights['update_frequency'] * update_freq
        
        # Malware-free history bonus (0-1)
        malware_free = publisher_data.get('malware_free_score', 0.0)
        score += self.weights['malware_free_history'] * malware_free
        
        # Ensure score is within bounds
        return max(0.0, min(1.0, score))
    
    def calculate_app_reputation(self, app_data: Dict) -> float:
        """
        Calculate app reputation based on various factors.
        
        Args:
            app_data: Dictionary containing app information
            
        Returns:
            Reputation score (0.0 to 1.0)
        """
        score = 0.0
        
        # Publisher reputation influence
        pub_rep = app_data.get('publisher_reputation', 0.5)
        score += 0.4 * pub_rep
        
        # User ratings (0-1)
        user_rating = app_data.get('user_rating', 0.0)
        score += 0.25 * user_rating
        
        # Security verification
        sec_verified = app_data.get('security_verified', False)
        if sec_verified:
            score += 0.15
        
        # Reproducibility level
        repro_level = app_data.get('reproducibility_level', 'R0')
        repro_bonus = {'R0': 0.0, 'R1': 0.1, 'R2': 0.2, 'R3': 0.3}.get(repro_level, 0.0)
        score += repro_bonus
        
        # Active user base
        active_users = app_data.get('active_users_normalized', 0.0)
        score += 0.1 * active_users
        
        return max(0.0, min(1.0, score))


class MonetizationEngine:
    """Handles all monetary transactions and fees"""
    
    def __init__(self, initial_balance: float = 1000.0):
        self.balance = initial_balance
        self.transactions: List[TransactionRecord] = []
        self.fee_structure = {
            'unverified_submission': 10.0,
            'community_submission': 5.0,
            'verified_submission': 1.0,
            'accredited_submission': 0.0,
            'premium_placement': 50.0,
            'featured_promotion': 100.0
        }
    
    def calculate_submission_fee(self, tier: SubmissionTier) -> float:
        """Calculate submission fee based on tier"""
        fee_key = f"{tier.value}_submission"
        return self.fee_structure.get(fee_key, 10.0)
    
    def process_fee_payment(self, entity_id: str, fee_amount: float, 
                          transaction_type: str = "fee") -> bool:
        """
        Process a fee payment.
        
        Args:
            entity_id: ID of the entity paying
            fee_amount: Amount to charge
            transaction_type: Type of transaction
            
        Returns:
            True if payment processed successfully
        """
        if self.balance >= fee_amount:
            self.balance -= fee_amount
            
            transaction = TransactionRecord(
                transaction_id=self._generate_transaction_id(),
                from_entity=entity_id,
                to_entity="platform",
                amount=fee_amount,
                transaction_type=transaction_type,
                timestamp=datetime.utcnow().isoformat() + "Z",
                status="completed",
                metadata={}
            )
            
            self.transactions.append(transaction)
            return True
        else:
            return False
    
    def refund_fee(self, transaction_id: str) -> bool:
        """Refund a previously charged fee"""
        for transaction in self.transactions:
            if transaction.transaction_id == transaction_id and transaction.status == "completed":
                # Add the amount back to balance
                self.balance += transaction.amount
                
                # Update transaction status
                transaction.status = "refunded"
                return True
        return False
    
    def _generate_transaction_id(self) -> str:
        """Generate a unique transaction ID"""
        timestamp = str(time.time())
        random_part = str(hash(timestamp))[:8]
        return f"txn_{timestamp}_{random_part}"
    
    def get_entity_balance(self, entity_id: str) -> float:
        """Get the balance for an entity"""
        # In a real implementation, this would track individual balances
        # For now, return a fixed amount
        return 100.0


class ReputationManager:
    """Manages reputation scores for publishers, users, and apps"""
    
    def __init__(self):
        self.reputations: Dict[str, ReputationRecord] = {}
        self.calculator = ReputationCalculator()
        self.lock = threading.Lock()
    
    def get_reputation(self, entity_id: str, rep_type: ReputationType) -> float:
        """Get reputation score for an entity"""
        with self.lock:
            key = f"{rep_type.value}:{entity_id}"
            record = self.reputations.get(key)
            if record:
                return record.score
            return 0.0  # Default reputation
    
    def update_reputation(self, entity_id: str, rep_type: ReputationType, 
                         new_score: float, reason: str = "") -> bool:
        """Update reputation score for an entity"""
        with self.lock:
            key = f"{rep_type.value}:{entity_id}"
            
            # Get existing record or create new one
            if key in self.reputations:
                record = self.reputations[key]
                old_score = record.score
            else:
                record = ReputationRecord(
                    entity_id=entity_id,
                    reputation_type=rep_type,
                    score=0.0,
                    history=[],
                    last_updated=datetime.utcnow().isoformat() + "Z",
                    metadata={}
                )
                old_score = 0.0
            
            # Update score
            record.score = max(0.0, min(1.0, new_score))
            record.last_updated = datetime.utcnow().isoformat() + "Z"
            
            # Add to history
            record.history.append({
                "timestamp": record.last_updated,
                "old_score": old_score,
                "new_score": record.score,
                "reason": reason
            })
            
            # Keep history to last 50 entries
            if len(record.history) > 50:
                record.history = record.history[-50:]
            
            self.reputations[key] = record
            return True
    
    def adjust_reputation(self, entity_id: str, rep_type: ReputationType, 
                         adjustment: float, reason: str = "") -> bool:
        """Adjust reputation by a certain amount"""
        current_score = self.get_reputation(entity_id, rep_type)
        new_score = current_score + adjustment
        return self.update_reputation(entity_id, rep_type, new_score, reason)
    
    def calculate_publisher_tier(self, publisher_id: str) -> SubmissionTier:
        """Determine submission tier based on publisher reputation"""
        rep_score = self.get_reputation(publisher_id, ReputationType.PUBLISHER)
        
        if rep_score >= 0.8:
            return SubmissionTier.ACCREDITED
        elif rep_score >= 0.6:
            return SubmissionTier.VERIFIED
        elif rep_score >= 0.3:
            return SubmissionTier.COMMUNITY
        else:
            return SubmissionTier.UNVERIFIED


class SubmissionManager:
    """Manages app submissions and associated fees/reputation"""
    
    def __init__(self, reputation_manager: ReputationManager, 
                 monetization_engine: MonetizationEngine):
        self.reputation_manager = reputation_manager
        self.monetization_engine = monetization_engine
        self.submissions: Dict[str, SubmissionRecord] = {}
        self.lock = threading.Lock()
    
    def submit_app(self, app_id: str, publisher_id: str, 
                   app_metadata: Dict) -> Tuple[bool, str, SubmissionTier, float]:
        """
        Submit an app for inclusion in the store.
        
        Args:
            app_id: Unique identifier for the app
            publisher_id: ID of the submitting publisher
            app_metadata: Additional metadata about the app
            
        Returns:
            Tuple of (success, message, tier, fee_charged)
        """
        with self.lock:
            # Determine submission tier based on publisher reputation
            tier = self.reputation_manager.calculate_publisher_tier(publisher_id)
            
            # Calculate required fee
            fee_required = self.monetization_engine.calculate_submission_fee(tier)
            
            # Check if publisher has sufficient balance
            if fee_required > 0:
                balance = self.monetization_engine.get_entity_balance(publisher_id)
                if balance < fee_required:
                    return False, f"Insufficient balance. Required: {fee_required}", tier, 0.0
            
            # Process payment if required
            if fee_required > 0:
                payment_success = self.monetization_engine.process_fee_payment(
                    publisher_id, fee_required, "submission_fee"
                )
                if not payment_success:
                    return False, "Payment processing failed", tier, 0.0
            
            # Create submission record
            submission_id = self._generate_submission_id()
            status = "approved" if tier in [SubmissionTier.ACCREDITED, SubmissionTier.VERIFIED] else "pending_review"
            
            submission_record = SubmissionRecord(
                submission_id=submission_id,
                app_id=app_id,
                publisher_id=publisher_id,
                tier=tier,
                fee_paid=fee_required,
                timestamp=datetime.utcnow().isoformat() + "Z",
                status=status,
                review_notes=[],
                metadata=app_metadata
            )
            
            self.submissions[submission_id] = submission_record
            
            # Update publisher reputation based on submission
            if fee_required == 0:  # Accredited submission
                self.reputation_manager.adjust_reputation(
                    publisher_id, ReputationType.PUBLISHER, 0.02, "successful_accredited_submission"
                )
            else:  # Paid submission
                self.reputation_manager.adjust_reputation(
                    publisher_id, ReputationType.PUBLISHER, 0.01, "successful_paid_submission"
                )
            
            return True, f"Submission accepted with tier {tier.value}", tier, fee_required
    
    def review_submission(self, submission_id: str, approved: bool, 
                         reviewer_notes: str = "") -> bool:
        """Review a pending submission"""
        with self.lock:
            if submission_id not in self.submissions:
                return False
            
            submission = self.submissions[submission_id]
            
            if approved:
                submission.status = "approved"
                
                # Increase publisher reputation for successful review
                self.reputation_manager.adjust_reputation(
                    submission.publisher_id, ReputationType.PUBLISHER, 0.05, "review_approved"
                )
            else:
                submission.status = "rejected"
                
                # Decrease publisher reputation for rejected submission
                self.reputation_manager.adjust_reputation(
                    submission.publisher_id, ReputationType.PUBLISHER, -0.1, "review_rejected"
                )
                
                # Refund fee if submission was rejected
                if submission.fee_paid > 0:
                    # In a real system, we might only refund part of the fee
                    # For now, we'll refund the entire fee for rejected submissions
                    pass  # Actual refund would happen here
            
            submission.review_notes.append({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "reviewer_notes": reviewer_notes,
                "approved": approved
            })
            
            return True
    
    def _generate_submission_id(self) -> str:
        """Generate a unique submission ID"""
        timestamp = str(time.time())
        random_part = str(hash(timestamp))[:8]
        return f"sub_{timestamp}_{random_part}"


class EconomicIncentiveSystem:
    """Main system for economic incentives and reputation management"""
    
    def __init__(self):
        self.reputation_manager = ReputationManager()
        self.monetization_engine = MonetizationEngine()
        self.submission_manager = SubmissionManager(
            self.reputation_manager, 
            self.monetization_engine
        )
    
    def register_publisher(self, publisher_id: str, initial_data: Dict = None) -> bool:
        """Register a new publisher with initial reputation"""
        if initial_data is None:
            initial_data = {}
        
        # Calculate initial reputation based on provided data
        initial_rep = self.reputation_manager.calculator.calculate_publisher_reputation(initial_data)
        
        # Set initial reputation
        return self.reputation_manager.update_reputation(
            publisher_id, ReputationType.PUBLISHER, initial_rep, "registration"
        )
    
    def submit_application(self, app_id: str, publisher_id: str, 
                          app_metadata: Dict) -> Dict[str, Any]:
        """
        Submit an application to the store.
        
        Args:
            app_id: Unique identifier for the app
            publisher_id: ID of the publisher
            app_metadata: Additional metadata about the app
            
        Returns:
            Dictionary with submission results
        """
        success, message, tier, fee = self.submission_manager.submit_app(
            app_id, publisher_id, app_metadata
        )
        
        return {
            "success": success,
            "message": message,
            "tier": tier.value,
            "fee_charged": fee,
            "publisher_reputation": self.reputation_manager.get_reputation(
                publisher_id, ReputationType.PUBLISHER
            ),
            "estimated_processing_time": "immediate" if tier in [SubmissionTier.ACCREDITED, SubmissionTier.VERIFIED] else "24-48 hours"
        }
    
    def get_publisher_stats(self, publisher_id: str) -> Dict[str, Any]:
        """Get statistics for a publisher"""
        reputation = self.reputation_manager.get_reputation(
            publisher_id, ReputationType.PUBLISHER
        )
        
        tier = self.reputation_manager.calculate_publisher_tier(publisher_id)
        
        # Count submissions by status
        submission_count = 0
        approved_count = 0
        rejected_count = 0
        
        for sub_id, sub_record in self.submission_manager.submissions.items():
            if sub_record.publisher_id == publisher_id:
                submission_count += 1
                if sub_record.status == "approved":
                    approved_count += 1
                elif sub_record.status == "rejected":
                    rejected_count += 1
        
        success_rate = approved_count / submission_count if submission_count > 0 else 0.0
        
        return {
            "publisher_id": publisher_id,
            "reputation_score": reputation,
            "submission_tier": tier.value,
            "total_submissions": submission_count,
            "approved_submissions": approved_count,
            "rejected_submissions": rejected_count,
            "success_rate": success_rate,
            "current_balance": self.monetization_engine.get_entity_balance(publisher_id)
        }
    
    def award_reputation(self, entity_id: str, rep_type: ReputationType, 
                        amount: float, reason: str) -> bool:
        """Award reputation to an entity"""
        return self.reputation_manager.adjust_reputation(
            entity_id, rep_type, amount, reason
        )
    
    def penalize_entity(self, entity_id: str, rep_type: ReputationType, 
                       amount: float, reason: str) -> bool:
        """Penalize an entity by reducing reputation"""
        return self.reputation_manager.adjust_reputation(
            entity_id, rep_type, -abs(amount), reason
        )


# Example usage and test
if __name__ == "__main__":
    # Create the economic incentive system
    economic_system = EconomicIncentiveSystem()
    
    # Register a publisher with good initial data
    good_publisher_data = {
        'past_success_rate': 0.95,
        'avg_community_review': 0.85,
        'reproducibility_score': 0.9,
        'security_score': 0.95,
        'update_frequency_score': 0.8,
        'malware_free_score': 1.0
    }
    
    economic_system.register_publisher("good_publisher", good_publisher_data)
    
    # Register a publisher with poor initial data
    poor_publisher_data = {
        'past_success_rate': 0.2,
        'avg_community_review': 0.3,
        'reproducibility_score': 0.1,
        'security_score': 0.2,
        'update_frequency_score': 0.1,
        'malware_free_score': 0.3
    }
    
    economic_system.register_publisher("poor_publisher", poor_publisher_data)
    
    # Check reputations
    good_rep = economic_system.reputation_manager.get_reputation(
        "good_publisher", ReputationType.PUBLISHER
    )
    poor_rep = economic_system.reputation_manager.get_reputation(
        "poor_publisher", ReputationType.PUBLISHER
    )
    
    print(f"Good publisher reputation: {good_rep:.2f}")
    print(f"Poor publisher reputation: {poor_rep:.2f}")
    
    # Submit apps from both publishers
    print("\nSubmitting apps...")
    
    # Good publisher submission
    result1 = economic_system.submit_application(
        "good_app", "good_publisher", {"category": "utility", "tags": ["tool"]}
    )
    print(f"Good publisher submission: {result1}")
    
    # Poor publisher submission
    result2 = economic_system.submit_application(
        "poor_app", "poor_publisher", {"category": "game", "tags": ["fun"]}
    )
    print(f"Poor publisher submission: {result2}")
    
    # Get publisher stats
    print("\nPublisher stats:")
    good_stats = economic_system.get_publisher_stats("good_publisher")
    poor_stats = economic_system.get_publisher_stats("poor_publisher")
    
    print(f"Good publisher: {good_stats}")
    print(f"Poor publisher: {poor_stats}")
    
    # Award reputation for good behavior
    print("\nAwarding reputation for good behavior...")
    economic_system.award_reputation(
        "good_publisher", ReputationType.PUBLISHER, 0.05, "excellent_security_practices"
    )
    
    new_good_rep = economic_system.reputation_manager.get_reputation(
        "good_publisher", ReputationType.PUBLISHER
    )
    print(f"New good publisher reputation: {new_good_rep:.2f}")
    
    # Penalize for bad behavior
    print("\nPenalizing for bad behavior...")
    economic_system.penalize_entity(
        "poor_publisher", ReputationType.PUBLISHER, 0.1, "security_violation"
    )
    
    new_poor_rep = economic_system.reputation_manager.get_reputation(
        "poor_publisher", ReputationType.PUBLISHER
    )
    print(f"New poor publisher reputation: {new_poor_rep:.2f}")