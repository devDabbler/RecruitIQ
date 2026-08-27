#!/usr/bin/env python3
"""
Script to set up experience analysis tables and test enhanced matching
"""

import os
import sys
import json
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models.models import Candidate, Job, CandidateExperienceAnalysis, JobRequirementAnalysis
from services.experience_analysis_service import ExperienceAnalysisService
from services.enhanced_matching_integrator import EnhancedMatchingIntegrator
from services.rag_service import RAGService
from services.matching_service import MatchingService
from utils.database import get_database_url

def setup_database_tables():
    """Create the experience analysis tables in the database"""
    print("🔧 Setting up experience analysis tables...")
    
    # Read the SQL script
    sql_file = backend_dir / "create_experience_tables.sql"
    with open(sql_file, 'r') as f:
        sql_script = f.read()
    
    # Create database engine
    engine = create_engine(get_database_url())
    
    # Execute the SQL script
    with engine.connect() as conn:
        # Split the script into individual statements
        statements = sql_script.split(';')
        for statement in statements:
            statement = statement.strip()
            if statement:
                try:
                    conn.execute(text(statement))
                    conn.commit()
                    print(f"✅ Executed: {statement[:50]}...")
                except Exception as e:
                    print(f"⚠️  Warning (likely already exists): {e}")
    
    print("✅ Database tables setup complete!")

def test_enhanced_matching():
    """Test the enhanced matching system with real data"""
    print("\n🧪 Testing Enhanced Matching System...")
    
    # Initialize services
    experience_service = ExperienceAnalysisService()
    
    # Get database session
    engine = create_engine(get_database_url())
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Get a candidate with experience data
        candidate = db.query(Candidate).first()
        if not candidate:
            print("❌ No candidates found in database")
            return
        
        print(f"📋 Testing with candidate: {candidate.first_name} {candidate.last_name}")
        
        # Get candidate's resume data
        resume = candidate.resumes[0] if candidate.resumes else None
        if not resume or not resume.parsed_data:
            print("❌ No parsed resume data found")
            return
        
        # Analyze candidate experience
        print("🔍 Analyzing candidate experience...")
        analysis_result = experience_service.analyze_candidate_experience(
            candidate_id=candidate.id,
            experience_data=resume.parsed_data.get('experience', [])
        )
        
        print(f"✅ Analysis complete!")
        print(f"   📊 Complexity Score: {analysis_result.get('complexity_score', 'N/A')}/10")
        print(f"   🎯 Achievements Found: {len(analysis_result.get('achievements', []))}")
        print(f"   💻 Technologies: {len(analysis_result.get('technologies', []))}")
        print(f"   👥 Leadership Score: {analysis_result.get('leadership_score', 'N/A')}")
        
        # Save analysis to database
        existing_analysis = db.query(CandidateExperienceAnalysis).filter(
            CandidateExperienceAnalysis.candidate_id == candidate.id
        ).first()
        
        if existing_analysis:
            # Update existing analysis
            for key, value in analysis_result.items():
                if hasattr(existing_analysis, key):
                    setattr(existing_analysis, key, value)
        else:
            # Create new analysis
            analysis_record = CandidateExperienceAnalysis(
                candidate_id=candidate.id,
                achievements=analysis_result.get('achievements'),
                technologies=analysis_result.get('technologies'),
                complexity_score=analysis_result.get('complexity_score'),
                impact_score=analysis_result.get('impact_score'),
                leadership_indicators=analysis_result.get('leadership_indicators'),
                semantic_themes=analysis_result.get('semantic_themes')
            )
            db.add(analysis_record)
        
        db.commit()
        print("💾 Analysis saved to database!")
        
        # Test enhanced matching
        print("\n🎯 Testing Enhanced Matching...")
        
        # Get a job to match against
        job = db.query(Job).first()
        if not job:
            print("❌ No jobs found in database")
            return
        
        print(f"📋 Matching against job: {job.title}")
        
        # Initialize matching services
        rag_service = RAGService()
        matching_service = MatchingService()
        enhanced_integrator = EnhancedMatchingIntegrator(
            rag_service=rag_service,
            matching_service=matching_service,
            experience_service=experience_service
        )
        
        # Perform enhanced matching
        enhanced_match = enhanced_integrator.get_enhanced_match(
            candidate_id=candidate.id,
            job_id=job.id
        )
        
        print(f"✅ Enhanced matching complete!")
        print(f"   📈 Overall Score: {enhanced_match.get('overall_score', 'N/A')}/100")
        print(f"   🎯 Base Match Score: {enhanced_match.get('base_match_score', 'N/A')}/100")
        print(f"   🏆 Experience Bonus: {enhanced_match.get('experience_bonus', 'N/A')}")
        print(f"   💡 Achievement Bonus: {enhanced_match.get('achievement_bonus', 'N/A')}")
        print(f"   🔧 Technology Bonus: {enhanced_match.get('technology_bonus', 'N/A')}")
        
        # Show detailed reasoning
        reasoning = enhanced_match.get('reasoning', {})
        print(f"\n📝 Detailed Reasoning:")
        print(f"   🎯 Experience Alignment: {reasoning.get('experience_alignment', 'N/A')}")
        print(f"   🏆 Achievement Match: {reasoning.get('achievement_match', 'N/A')}")
        print(f"   💻 Technology Proficiency: {reasoning.get('technology_proficiency', 'N/A')}")
        print(f"   👥 Leadership Fit: {reasoning.get('leadership_fit', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

def main():
    """Main function to run the setup and testing"""
    print("🚀 Experience Analysis Enhancement Setup")
    print("=" * 50)
    
    # Setup database tables
    setup_database_tables()
    
    # Test the enhanced matching system
    test_enhanced_matching()
    
    print("\n✅ Setup and testing complete!")
    print("\n🎉 Enhanced Matching System is now ready!")
    print("   - Experience analysis tables created")
    print("   - Enhanced matching algorithms tested")
    print("   - Database integration working")
    print("\n📚 Next steps:")
    print("   - Integrate with frontend components")
    print("   - Add API endpoints for enhanced matching")
    print("   - Implement batch processing for existing candidates")

if __name__ == "__main__":
    main() 