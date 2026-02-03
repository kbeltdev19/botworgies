"""
Testing Criteria and Evaluation Matrix for ATS Automation

This document defines the criteria for evaluating the ATS automation system
"""

TEST_CRITERIA = {
    "version": "1.0.0",
    "test_date": "2026-02-03",
    "candidate": {
        "name": "Kent Le",
        "location": "Auburn, AL",
        "target_roles": ["Customer Success Manager", "Account Manager", "Sales Representative"],
        "salary_range": "$75,000 - $95,000",
        "experience_years": 3,
        "remote_preference": ["remote", "hybrid", "on-site"]
    },
    
    "test_parameters": {
        "total_jobs": 500,
        "concurrent_sessions": 5,
        "target_location": "Auburn, AL / Atlanta, GA / Remote",
        "platforms": ["Workday", "Taleo", "iCIMS", "SuccessFactors", "ADP", "Dice", "AngelList"],
        "resume_file": "Test Resumes/Kent_Le_Resume.pdf"
    },
    
    "evaluation_criteria": {
        "success_rate": {
            "excellent": {"min": 85, "description": "Exceptional performance"},
            "good": {"min": 70, "max": 84, "description": "Good performance"},
            "acceptable": {"min": 50, "max": 69, "description": "Acceptable but needs improvement"},
            "poor": {"max": 49, "description": "Unacceptable, major fixes needed"}
        },
        
        "performance_metrics": {
            "avg_time_per_application": {
                "target": "< 45 seconds",
                "acceptable": "< 90 seconds",
                "poor": "> 90 seconds"
            },
            "concurrent_sessions_stability": {
                "target": "100% - no crashes with 5 concurrent",
                "acceptable": "> 90% - occasional issues",
                "poor": "< 90% - frequent crashes"
            },
            "field_detection_accuracy": {
                "target": "> 90% confidence on required fields",
                "acceptable": "> 75% confidence",
                "poor": "< 75% confidence"
            }
        },
        
        "platform_specific": {
            "Workday": {
                "expected_success_rate": 75,
                "expected_avg_time": 60,
                "key_challenges": ["Multi-step wizard", "Account creation", "React hydration"]
            },
            "Taleo": {
                "expected_success_rate": 70,
                "expected_avg_time": 50,
                "key_challenges": ["iframes", "Older UI", "Account creation"]
            },
            "iCIMS": {
                "expected_success_rate": 80,
                "expected_avg_time": 40,
                "key_challenges": ["iframe detection", "Guest apply flow"]
            },
            "SuccessFactors": {
                "expected_success_rate": 65,
                "expected_avg_time": 70,
                "key_challenges": ["Complex multi-step", "SAP integration"]
            },
            "ADP": {
                "expected_success_rate": 85,
                "expected_avg_time": 35,
                "key_challenges": ["Simpler forms, but can have redirects"]
            },
            "Dice": {
                "expected_success_rate": 90,
                "expected_avg_time": 30,
                "key_challenges": ["Easy Apply vs External redirect"]
            },
            "AngelList": {
                "expected_success_rate": 80,
                "expected_avg_time": 35,
                "key_challenges": ["Greenhouse/Lever embeds"]
            }
        },
        
        "error_categories": {
            "acceptable": {
                "external_redirect": "Expected for non-Easy Apply jobs",
                "low_confidence": "Acceptable if < 10% of attempts",
                "rate_limited": "Acceptable if < 5% of attempts"
            },
            "unacceptable": {
                "captcha_blocked": "Should be < 5% with BrowserBase",
                "timeout": "Should be < 10%",
                "element_not_found": "Should be < 15%",
                "navigation_error": "Should be < 5%"
            }
        }
    },
    
    "scoring_weights": {
        "overall_success_rate": 40,
        "platform_coverage": 20,
        "avg_response_time": 15,
        "error_rate": 15,
        "field_accuracy": 10
    },
    
    "pass_fail_criteria": {
        "must_pass": [
            "Overall success rate >= 50%",
            "No platform has 0% success rate",
            "System doesn't crash during 500-job test",
            "Average time per application < 90 seconds"
        ],
        "should_pass": [
            "Overall success rate >= 70%",
            "At least 3 platforms have > 75% success",
            "CAPTCHA/anti-bot blocks < 10%",
            "Average time per application < 60 seconds"
        ],
        "nice_to_have": [
            "Overall success rate >= 85%",
            "All platforms have > 60% success",
            "CAPTCHA/anti-bot blocks < 5%",
            "Average time per application < 45 seconds"
        ]
    },
    
    "reporting_requirements": {
        "must_include": [
            "Total jobs attempted",
            "Overall success rate",
            "Per-platform breakdown",
            "Error categorization",
            "Average time per application",
            "Recommendations for improvement"
        ],
        "optional": [
            "Screenshots of failures",
            "Detailed logs per application",
            "Field-level accuracy metrics"
        ]
    }
}


def evaluate_test_results(report_data: dict) -> dict:
    """
    Evaluate test results against criteria
    
    Returns:
        dict with scores, pass/fail status, and recommendations
    """
    results = {
        "overall_score": 0,
        "passed": [],
        "failed": [],
        "recommendations": [],
        "grade": "F"
    }
    
    success_rate = report_data.get("overall_success_rate", 0)
    
    # Grade based on success rate
    if success_rate >= 85:
        results["grade"] = "A"
        results["passed"].append(f"Excellent success rate: {success_rate:.1f}%")
    elif success_rate >= 70:
        results["grade"] = "B"
        results["passed"].append(f"Good success rate: {success_rate:.1f}%")
    elif success_rate >= 50:
        results["grade"] = "C"
        results["passed"].append(f"Acceptable success rate: {success_rate:.1f}%")
        results["recommendations"].append("Success rate needs improvement")
    else:
        results["grade"] = "F"
        results["failed"].append(f"Poor success rate: {success_rate:.1f}%")
        results["recommendations"].append("Critical: Success rate below acceptable threshold")
    
    # Check platform coverage
    platforms = report_data.get("platform_breakdown", {})
    zero_success_platforms = [
        p for p, s in platforms.items() 
        if s.get("successful", 0) == 0 and s.get("attempts", 0) > 5
    ]
    
    if zero_success_platforms:
        results["failed"].append(f"Platforms with 0% success: {', '.join(zero_success_platforms)}")
        results["recommendations"].append(f"Fix handlers for: {', '.join(zero_success_platforms)}")
    else:
        results["passed"].append("All platforms have some success")
    
    # Check timing
    avg_time = report_data.get("avg_time_per_application_seconds", 0)
    if avg_time < 45:
        results["passed"].append(f"Excellent avg time: {avg_time:.1f}s")
    elif avg_time < 90:
        results["passed"].append(f"Acceptable avg time: {avg_time:.1f}s")
    else:
        results["failed"].append(f"Slow avg time: {avg_time:.1f}s")
        results["recommendations"].append("Optimize selectors and reduce delays")
    
    # Calculate overall score
    score = min(100, success_rate)  # Base on success rate
    if results["grade"] == "A":
        score = min(100, score + 10)
    elif results["grade"] == "F":
        score = max(0, score - 20)
    
    results["overall_score"] = score
    
    return results


if __name__ == "__main__":
    import json
    print("ATS Automation Testing Criteria")
    print("=" * 60)
    print(json.dumps(TEST_CRITERIA, indent=2))
