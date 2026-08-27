#!/usr/bin/env python3
"""
Debug test for bullet point consolidation issues.
"""

import sys
import os
from backend.utils.resume_parsing.utils.text_utils import consolidate_bullet_points, format_bullets_as_description

def test_consolidation_with_real_data():
    """Test consolidation with the actual problematic data from the production test."""
    
    print("🔍 Debugging Bullet Point Consolidation Issues")
    print("=" * 50)
    
    # Sample data from the production test that showed issues
    problematic_bullets = [
        "Fraud Detection and Business Intelligence Top Performer for 2 Consecutive Years",
        "Collaborate with business stakeholders to translate the risk factors and detection pattern into detection models using SQL and Python, achieving efficiency improvement by 20%",
        "Collaborate with business stakeholders to translate the risk factors and detection pattern into detection models using SQL and Python, achieving efficiency improvement by 20%. Received shout-out for Innovation at Global All-Hands.",
        "Develop machine learning models using K-Means in Python (NumPy, Pandas, sklearn, Matplotlib) for customer risk rating.",
        "Build dashboard to monitor ongoing performance of models and deliver ad-hoc analytics reports for senior leadership.",
        "Mentor senior and junior data scientists."
    ]
    
    print("📝 Original bullets:")
    for i, bullet in enumerate(problematic_bullets, 1):
        print(f"  {i}. {bullet}")
    
    print(f"\n🔧 Consolidating {len(problematic_bullets)} bullets...")
    consolidated = consolidate_bullet_points(problematic_bullets)
    
    print(f"\n✅ Consolidated into {len(consolidated)} bullets:")
    for i, bullet in enumerate(consolidated, 1):
        print(f"  {i}. {bullet}")
    
    print(f"\n📋 Final formatted result:")
    formatted = format_bullets_as_description(consolidated)
    print(formatted)
    
    # Test with the actual fragmented data from production
    print(f"\n" + "="*50)
    print("🔍 Testing with actual fragmented data from production:")
    
    fragmented_data = [
        "Fraud Detection and Business Intelligence Top Performer for 2 Consecutive Years",
        "Collaborate with business stakeholders to translate the risk factors and detectio",
        "Collaborate with business stakeholders to translate the risk factors and detection pattern into detection models using SQL and Python, achieving efficiency improvement by",
        "Collaborate with business stakeholders to translate the risk factors and detection pattern into detection models using SQL and Python, achieving efficiency improvement by 20%. Received shout-out for Innovation at Global All-Hands.",
        "Develop machine learning models using K-Means in Python (NumPy, Pandas, sklearn,",
        "Develop machine learning models using K-Means in Python (NumPy, Pandas, sklearn, Matplotlib) for customer risk rating.",
        "Build dashboard to monitor ongoing performance of models and deliver ad-hoc analy",
        "Build dashboard to monitor ongoing performance of models and deliver ad-hoc analytics reports for senior leadership.",
        "Mentor senior and junior data scientists."
    ]
    
    print("📝 Fragmented bullets:")
    for i, bullet in enumerate(fragmented_data, 1):
        print(f"  {i}. {bullet}")
    
    print(f"\n🔧 Consolidating fragmented bullets...")
    consolidated_fragmented = consolidate_bullet_points(fragmented_data)
    
    print(f"\n✅ Consolidated into {len(consolidated_fragmented)} bullets:")
    for i, bullet in enumerate(consolidated_fragmented, 1):
        print(f"  {i}. {bullet}")
    
    print(f"\n📋 Final formatted result:")
    formatted_fragmented = format_bullets_as_description(consolidated_fragmented)
    print(formatted_fragmented)

if __name__ == "__main__":
    test_consolidation_with_real_data() 