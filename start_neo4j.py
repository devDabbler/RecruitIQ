#!/usr/bin/env python3
"""
Simple script to help start Neo4j database for RecruitIQ.
This script checks if Neo4j is running and provides guidance on how to start it.
"""

import subprocess
import sys
import os
import time
import requests
from typing import Optional

def check_neo4j_status() -> bool:
    """Check if Neo4j is running by trying to connect to it."""
    try:
        # Try to connect to Neo4j browser interface
        response = requests.get("http://localhost:7474", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def start_neo4j() -> bool:
    """Attempt to start Neo4j using common methods."""
    print("Attempting to start Neo4j...")
    
    # Try different ways to start Neo4j
    commands = [
        ["neo4j", "start"],
        ["sudo", "neo4j", "start"],
        ["systemctl", "start", "neo4j"],
        ["sudo", "systemctl", "start", "neo4j"],
        ["brew", "services", "start", "neo4j"],  # macOS with Homebrew
    ]
    
    for cmd in commands:
        try:
            print(f"Trying: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                print(f"Successfully started Neo4j with: {' '.join(cmd)}")
                return True
            else:
                print(f"Command failed: {result.stderr}")
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError) as e:
            print(f"Command failed: {e}")
            continue
    
    return False

def wait_for_neo4j(timeout: int = 60) -> bool:
    """Wait for Neo4j to become available."""
    print(f"Waiting for Neo4j to become available (timeout: {timeout}s)...")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        if check_neo4j_status():
            print("Neo4j is now available!")
            return True
        time.sleep(2)
        print(".", end="", flush=True)
    
    print("\nTimeout waiting for Neo4j to start.")
    return False

def main():
    print("RecruitIQ Neo4j Database Helper")
    print("=" * 40)
    
    # Check if Neo4j is already running
    if check_neo4j_status():
        print("✅ Neo4j is already running!")
        print("You can access the Neo4j browser at: http://localhost:7474")
        return
    
    print("❌ Neo4j is not running.")
    print()
    
    # Try to start Neo4j
    if start_neo4j():
        # Wait for it to become available
        if wait_for_neo4j():
            print("✅ Neo4j started successfully!")
            print("You can access the Neo4j browser at: http://localhost:7474")
            return
        else:
            print("❌ Neo4j failed to start within the timeout period.")
    else:
        print("❌ Could not start Neo4j automatically.")
    
    print()
    print("Manual Neo4j Setup Instructions:")
    print("1. Download Neo4j Desktop from: https://neo4j.com/download/")
    print("2. Install and start Neo4j Desktop")
    print("3. Create a new project and database")
    print("4. Set the following environment variables:")
    print("   - NEO4J_URI=bolt://localhost:7687")
    print("   - NEO4J_USER=neo4j")
    print("   - NEO4J_PASSWORD=your_password")
    print()
    print("Alternative: Use Docker to run Neo4j:")
    print("docker run -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest")
    print()
    print("After starting Neo4j, restart your RecruitIQ application.")

if __name__ == "__main__":
    main() 