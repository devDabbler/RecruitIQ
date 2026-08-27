#!/usr/bin/env python3
"""
Test script to verify startup optimizations.
This script tests the optimized backend startup process.
"""

import time
import logging
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir.parent))

def test_startup_optimization():
    """Test the startup optimization."""
    print("🧪 Testing startup optimization...")
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    start_time = time.time()
    
    try:
        # Test import optimization
        print("📦 Testing import optimization...")
        from backend.utils.startup_optimizer import optimize_imports, startup_timer
        optimize_imports()
        
        # Test agent framework initialization
        print("🤖 Testing agent framework initialization...")
        from backend.services.agent_framework import initialize_agents, list_agents
        initialize_agents()
        agents = list_agents()
        print(f"✅ Loaded {len(agents)} agents: {list(agents.keys())}")
        
        # Test service registry
        print("🔧 Testing service registry...")
        from backend.services.service_registry import provide_llm_service
        llm_service = provide_llm_service()
        print("✅ LLM service initialized successfully")
        
        # Test database connection (if available)
        print("🗄️  Testing database connection...")
        try:
            from backend.utils.database import verify_postgres_connection
            verify_postgres_connection()
            print("✅ Database connection successful")
        except Exception as e:
            print(f"⚠️  Database connection failed (expected if not configured): {e}")
        
        total_time = time.time() - start_time
        print(f"\n🎉 Startup optimization test completed in {total_time:.2f} seconds")
        
        if total_time < 5:
            print("✅ Excellent startup performance!")
        elif total_time < 10:
            print("✅ Good startup performance")
        else:
            print("⚠️  Startup performance could be improved")
        
        return True
        
    except Exception as e:
        print(f"❌ Startup optimization test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_startup_optimization()
    sys.exit(0 if success else 1) 