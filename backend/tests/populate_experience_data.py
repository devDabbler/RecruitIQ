#!/usr/bin/env python3
"""
Script to populate candidate_experience table from parsed resume data
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
from utils.database import SQLALCHEMY_DATABASE_URL

def populate_experience_data():
    """Populate candidate_experience table from parsed resume data for all candidates"""
    print("🔧 Populating experience data from parsed resumes...")
    
    # Create database engine
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Get all candidates first
        candidates = db.execute(
            text("""
            SELECT DISTINCT c.id, c.first_name, c.last_name
            FROM candidates c
            JOIN resumes r ON c.id = r.candidate_id
            ORDER BY c.id
            """)
        ).fetchall()
        
        if not candidates:
            print("❌ No candidates found")
            return
        
        print(f"📋 Found {len(candidates)} candidates")
        
        # Now get parsed data for each candidate
        candidates_with_data = []
        for candidate in candidates:
            resume_data = db.execute(
                text("""
                SELECT parsed_data
                FROM resumes 
                WHERE candidate_id = :candidate_id 
                ORDER BY created_at DESC 
                LIMIT 1
                """),
                {"candidate_id": candidate.id}
            ).fetchone()
            
            if resume_data and resume_data.parsed_data:
                candidates_with_data.append({
                    'id': candidate.id,
                    'first_name': candidate.first_name,
                    'last_name': candidate.last_name,
                    'parsed_data': resume_data.parsed_data
                })
        
        candidates = candidates_with_data
        
        if not candidates:
            print("❌ No candidates with parsed resume data found")
            return
        
        print(f"📋 Found {len(candidates)} candidates with parsed resume data")
        
        success_count = 0
        for candidate in candidates:
            candidate_id = candidate['id']
            candidate_name = f"{candidate['first_name']} {candidate['last_name']}"
            
            print(f"🔍 Processing {candidate_name}...")
            
            # Check if experience data already exists
            existing_experience = db.execute(
                text("SELECT COUNT(*) FROM candidate_experience WHERE candidate_id = :candidate_id"),
                {"candidate_id": candidate_id}
            ).fetchone()[0]
            
            if existing_experience > 0:
                print(f"   ⏭️  Experience data already exists for {candidate_name}")
                continue
            
            # Parse the JSON data
            parsed_data = candidate['parsed_data']
            if parsed_data is None or parsed_data == 'null':
                print(f"   ⚠️  No parsed data for {candidate_name}")
                continue
                
            if isinstance(parsed_data, str):
                try:
                    parsed_data = json.loads(parsed_data)
                except json.JSONDecodeError:
                    print(f"   ❌ Invalid JSON data for {candidate_name}")
                    continue
            
            # Extract experience data
            experience_list = parsed_data.get('experience', [])
            if not experience_list:
                print(f"   ⚠️  No experience data found in resume for {candidate_name}")
                continue
            
            # Insert experience records
            for exp in experience_list:
                company = exp.get('company', '')
                title = exp.get('title', '')
                location = exp.get('location', '')
                description = exp.get('description', '')
                
                # Handle dates
                start_date = exp.get('start_date')
                end_date = exp.get('end_date')
                
                # Convert date strings to proper format
                if start_date and start_date != 'Present':
                    try:
                        from datetime import datetime
                        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                    except:
                        start_date = None
                
                # Handle end_date - set to None if 'Present'
                if end_date == 'Present':
                    end_date = None
                elif end_date:
                    try:
                        from datetime import datetime
                        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                    except:
                        end_date = None
                
                # Determine if this is current position
                current = end_date is None
                
                # Insert the experience record
                db.execute(
                    text("""
                    INSERT INTO candidate_experience 
                    (candidate_id, company, position, location, start_date, end_date, current, description)
                    VALUES (:candidate_id, :company, :position, :location, :start_date, :end_date, :current, :description)
                    """),
                    {
                        "candidate_id": candidate_id,
                        "company": company,
                        "position": title,
                        "location": location,
                        "start_date": start_date,
                        "end_date": end_date,
                        "current": current,
                        "description": description
                    }
                )
            
            db.commit()
            success_count += 1
            print(f"   ✅ Successfully populated {len(experience_list)} experience records for {candidate_name}")
        
        print(f"\n🎉 Experience data population complete!")
        print(f"   ✅ Successfully processed {success_count} candidates")
        print(f"   📊 Total candidates: {len(candidates)}")
        
    except Exception as e:
        print(f"❌ Error populating experience data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    populate_experience_data() 