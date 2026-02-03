"""
A/B Testing Framework for Application Speeds
Tests different application speeds to optimize success rates
"""

import json
import random
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
import statistics


class SpeedVariant(Enum):
    """Application speed variants for testing."""
    SLOW = "slow"          # 15-20 apps/min - conservative
    MODERATE = "moderate"  # 20-30 apps/min - balanced
    FAST = "fast"          # 30-40 apps/min - aggressive
    VERY_FAST = "very_fast"  # 40-60 apps/min - risky


@dataclass
class SpeedConfig:
    """Configuration for a speed variant."""
    variant: SpeedVariant
    target_apps_per_minute: int
    delay_between_apps_ms: int
    typing_speed_wpm: int
    page_load_timeout_ms: int
    form_fill_timeout_ms: int
    
    # Human behavior simulation
    mouse_movement_delay_ms: int
    scroll_delay_ms: int
    click_delay_ms: int
    
    # Rate limiting
    burst_size: int
    burst_cooldown_seconds: int


# Predefined speed configurations
SPEED_VARIANTS = {
    SpeedVariant.SLOW: SpeedConfig(
        variant=SpeedVariant.SLOW,
        target_apps_per_minute=18,
        delay_between_apps_ms=3333,  # ~18 apps/min
        typing_speed_wpm=40,
        page_load_timeout_ms=30000,
        form_fill_timeout_ms=60000,
        mouse_movement_delay_ms=500,
        scroll_delay_ms=800,
        click_delay_ms=300,
        burst_size=3,
        burst_cooldown_seconds=30
    ),
    SpeedVariant.MODERATE: SpeedConfig(
        variant=SpeedVariant.MODERATE,
        target_apps_per_minute=25,
        delay_between_apps_ms=2400,  # ~25 apps/min
        typing_speed_wpm=50,
        page_load_timeout_ms=25000,
        form_fill_timeout_ms=45000,
        mouse_movement_delay_ms=350,
        scroll_delay_ms=600,
        click_delay_ms=200,
        burst_size=5,
        burst_cooldown_seconds=20
    ),
    SpeedVariant.FAST: SpeedConfig(
        variant=SpeedVariant.FAST,
        target_apps_per_minute=35,
        delay_between_apps_ms=1714,  # ~35 apps/min
        typing_speed_wpm=65,
        page_load_timeout_ms=20000,
        form_fill_timeout_ms=35000,
        mouse_movement_delay_ms=200,
        scroll_delay_ms=400,
        click_delay_ms=150,
        burst_size=8,
        burst_cooldown_seconds=15
    ),
    SpeedVariant.VERY_FAST: SpeedConfig(
        variant=SpeedVariant.VERY_FAST,
        target_apps_per_minute=50,
        delay_between_apps_ms=1200,  # ~50 apps/min
        typing_speed_wpm=80,
        page_load_timeout_ms=15000,
        form_fill_timeout_ms=25000,
        mouse_movement_delay_ms=100,
        scroll_delay_ms=250,
        click_delay_ms=100,
        burst_size=10,
        burst_cooldown_seconds=10
    )
}


@dataclass
class ExperimentResult:
    """Results from a single experiment run."""
    variant: SpeedVariant
    timestamp: datetime
    sample_size: int
    
    # Performance metrics
    success_count: int
    failure_count: int
    rate_limited_count: int
    blocked_count: int
    
    # Speed metrics
    actual_apps_per_minute: float
    avg_completion_time_seconds: float
    min_completion_time_seconds: float
    max_completion_time_seconds: float
    
    # Error breakdown
    captcha_errors: int
    form_errors: int
    timeout_errors: int
    network_errors: int
    
    # Quality metrics
    form_completion_rate: float
    resume_upload_success_rate: float
    cover_letter_generation_rate: float
    
    # Cost (if using CAPTCHA solving)
    captcha_cost_usd: float = 0.0
    
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.sample_size == 0:
            return 0.0
        return (self.success_count / self.sample_size) * 100
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        result = asdict(self)
        result['variant'] = self.variant.value
        result['timestamp'] = self.timestamp.isoformat()
        result['success_rate'] = self.success_rate()
        return result


class ABTestManager:
    """
    Manages A/B tests for application speeds.
    
    Usage:
        ab_test = ABTestManager()
        
        # Assign variant
        variant = ab_test.assign_variant("user_123")
        config = ab_test.get_config(variant)
        
        # Record results
        ab_test.record_result(variant, success=True)
        
        # Get winner
        winner = ab_test.get_winning_variant()
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path) if storage_path else Path("data/ab_tests.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Active experiments
        self.experiments: Dict[str, List[ExperimentResult]] = {}
        
        # User assignments
        self.user_assignments: Dict[str, SpeedVariant] = {}
        
        # Running totals
        self.running_totals: Dict[SpeedVariant, Dict[str, int]] = {
            variant: {"success": 0, "failure": 0, "total": 0}
            for variant in SpeedVariant
        }
        
        self._load_data()
    
    def _load_data(self):
        """Load previous experiment data."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    # Could load historical data here
            except Exception as e:
                print(f"Error loading AB test data: {e}")
    
    def _save_data(self):
        """Save experiment data."""
        data = {
            "last_updated": datetime.now().isoformat(),
            "running_totals": {
                k.value: v for k, v in self.running_totals.items()
            },
            "user_assignments_count": len(self.user_assignments)
        }
        
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def assign_variant(self, user_id: str) -> SpeedVariant:
        """
        Assign a speed variant to a user.
        Uses balanced random assignment.
        """
        if user_id in self.user_assignments:
            return self.user_assignments[user_id]
        
        # Find variant with fewest assignments for balance
        variant_counts = {variant: 0 for variant in SpeedVariant}
        for assigned in self.user_assignments.values():
            variant_counts[assigned] += 1
        
        # Pick least used variant
        min_count = min(variant_counts.values())
        least_used = [v for v, c in variant_counts.items() if c == min_count]
        
        assigned = random.choice(least_used)
        self.user_assignments[user_id] = assigned
        
        return assigned
    
    def get_config(self, variant: SpeedVariant) -> SpeedConfig:
        """Get configuration for a variant."""
        return SPEED_VARIANTS[variant]
    
    def record_result(
        self,
        variant: SpeedVariant,
        success: bool,
        error_type: Optional[str] = None
    ):
        """Record the result of an application."""
        self.running_totals[variant]["total"] += 1
        
        if success:
            self.running_totals[variant]["success"] += 1
        else:
            self.running_totals[variant]["failure"] += 1
        
        # Save periodically
        if sum(t["total"] for t in self.running_totals.values()) % 100 == 0:
            self._save_data()
    
    def record_experiment_result(self, result: ExperimentResult):
        """Record a complete experiment result."""
        experiment_id = datetime.now().strftime("%Y%m%d_%H%M")
        
        if experiment_id not in self.experiments:
            self.experiments[experiment_id] = []
        
        self.experiments[experiment_id].append(result)
        self._save_data()
    
    def get_winning_variant(self, min_samples: int = 100) -> Optional[SpeedVariant]:
        """
        Determine the winning variant based on success rates.
        
        Returns None if not enough data.
        """
        # Calculate success rates
        rates = {}
        for variant, totals in self.running_totals.items():
            if totals["total"] >= min_samples:
                rates[variant] = totals["success"] / totals["total"]
        
        if not rates:
            return None
        
        # Return variant with highest success rate
        return max(rates, key=rates.get)
    
    def get_variant_stats(self) -> Dict[str, Any]:
        """Get statistics for all variants."""
        stats = {}
        
        for variant, totals in self.running_totals.items():
            total = totals["total"]
            success = totals["success"]
            
            stats[variant.value] = {
                "total_attempts": total,
                "successes": success,
                "failures": totals["failure"],
                "success_rate": (success / total * 100) if total > 0 else 0,
                "config": {
                    "target_apps_per_minute": SPEED_VARIANTS[variant].target_apps_per_minute,
                    "delay_between_apps_ms": SPEED_VARIANTS[variant].delay_between_apps_ms
                }
            }
        
        # Add winner
        winner = self.get_winning_variant(min_samples=50)
        stats["current_winner"] = winner.value if winner else "insufficient_data"
        
        return stats
    
    def get_recommendation(self) -> Dict[str, Any]:
        """Get recommendation for optimal speed."""
        stats = self.get_variant_stats()
        winner = self.get_winning_variant()
        
        if not winner:
            return {
                "recommendation": "MODERATE",
                "reason": "Insufficient data - using safe default",
                "confidence": 0,
                "target_apps_per_minute": 25
            }
        
        winner_stats = self.running_totals[winner]
        success_rate = winner_stats["success"] / winner_stats["total"] * 100
        
        config = SPEED_VARIANTS[winner]
        
        return {
            "recommendation": winner.value,
            "reason": f"Highest success rate at {success_rate:.1f}%",
            "confidence": min(100, winner_stats["total"] / 10),  # Confidence grows with samples
            "target_apps_per_minute": config.target_apps_per_minute,
            "sample_size": winner_stats["total"],
            "all_variants": stats
        }
    
    def run_experiment(
        self,
        variant: SpeedVariant,
        sample_size: int,
        simulate: bool = True
    ) -> ExperimentResult:
        """
        Run an experiment with a specific variant.
        
        In production, this would actually run applications.
        """
        print(f"\n🧪 Running experiment: {variant.value}")
        print(f"   Sample size: {sample_size}")
        
        if simulate:
            # Simulate results based on expected performance
            # Slower = higher success rate but fewer apps
            base_success_rate = {
                SpeedVariant.SLOW: 0.92,
                SpeedVariant.MODERATE: 0.85,
                SpeedVariant.FAST: 0.75,
                SpeedVariant.VERY_FAST: 0.60
            }
            
            success_rate = base_success_rate.get(variant, 0.80)
            
            successes = int(sample_size * success_rate)
            failures = sample_size - successes
            
            # Error breakdown
            captcha_errors = int(failures * 0.4)
            form_errors = int(failures * 0.3)
            timeout_errors = int(failures * 0.2)
            network_errors = failures - captcha_errors - form_errors - timeout_errors
            
            result = ExperimentResult(
                variant=variant,
                timestamp=datetime.now(),
                sample_size=sample_size,
                success_count=successes,
                failure_count=failures,
                rate_limited_count=int(sample_size * 0.05),
                blocked_count=int(sample_size * 0.02),
                actual_apps_per_minute=SPEED_VARIANTS[variant].target_apps_per_minute * (0.9 + random.random() * 0.2),
                avg_completion_time_seconds=45 + random.random() * 30,
                min_completion_time_seconds=20,
                max_completion_time_seconds=120,
                captcha_errors=captcha_errors,
                form_errors=form_errors,
                timeout_errors=timeout_errors,
                network_errors=network_errors,
                form_completion_rate=0.95,
                resume_upload_success_rate=0.98,
                cover_letter_generation_rate=0.90
            )
            
            print(f"   ✅ Success rate: {result.success_rate():.1f}%")
            print(f"   📊 Apps/min: {result.actual_apps_per_minute:.1f}")
            
            self.record_experiment_result(result)
            return result
        
        else:
            # Real experiment would be implemented here
            raise NotImplementedError("Real experiments not yet implemented")
    
    def find_optimal_speed(self, sample_size_per_variant: int = 100) -> Dict[str, Any]:
        """
        Run experiments on all variants to find optimal speed.
        """
        print("\n" + "="*60)
        print("🔬 A/B TEST: Finding Optimal Application Speed")
        print("="*60)
        
        results = []
        for variant in SpeedVariant:
            result = self.run_experiment(variant, sample_size_per_variant, simulate=True)
            results.append(result)
        
        # Analyze results
        print("\n📊 RESULTS:")
        print("-"*60)
        
        best_variant = None
        best_score = 0
        
        for result in sorted(results, key=lambda r: r.success_rate(), reverse=True):
            variant = result.variant.value
            success_rate = result.success_rate()
            apps_per_min = result.actual_apps_per_minute
            
            # Score = success_rate * apps_per_min (weighted combination)
            score = success_rate * apps_per_min
            
            print(f"  {variant:12} | Success: {success_rate:5.1f}% | "
                  f"Speed: {apps_per_min:5.1f}/min | Score: {score:7.1f}")
            
            if score > best_score:
                best_score = score
                best_variant = result.variant
        
        recommendation = {
            "optimal_variant": best_variant.value if best_variant else "moderate",
            "target_apps_per_minute": SPEED_VARIANTS[best_variant].target_apps_per_minute if best_variant else 25,
            "expected_success_rate": next((r.success_rate() for r in results if r.variant == best_variant), 85),
            "all_results": [r.to_dict() for r in results]
        }
        
        print("\n✅ RECOMMENDATION:")
        print(f"   Use {recommendation['optimal_variant'].upper()} speed")
        print(f"   Target: {recommendation['target_apps_per_minute']} apps/minute")
        print(f"   Expected success rate: {recommendation['expected_success_rate']:.1f}%")
        
        return recommendation


# Global instance for use throughout the application
_ab_test_manager: Optional[ABTestManager] = None


def get_ab_test_manager() -> ABTestManager:
    """Get or create global AB test manager."""
    global _ab_test_manager
    if _ab_test_manager is None:
        _ab_test_manager = ABTestManager()
    return _ab_test_manager


if __name__ == "__main__":
    # Test A/B testing framework
    ab = ABTestManager()
    
    # Find optimal speed
    result = ab.find_optimal_speed(sample_size_per_variant=50)
    
    print(f"\nStats: {json.dumps(ab.get_variant_stats(), indent=2)}")
