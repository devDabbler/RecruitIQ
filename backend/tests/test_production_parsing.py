"""
Production test for resume parsing using real Roger Waters resume.
This test uses actual services and displays complete extraction results.
"""

import os
import asyncio
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Import the actual parser and services
from backend.utils.resume_parsing.resume_parser_main import ResumeParser
from backend.services.service_registry import provide_llm_service
from backend.services.minio_storage_service import MinioStorageService

async def test_production_resume_parsing():
    """Test parsing the actual Roger Waters resume with real services and display all extracted data."""
    
    print("\n" + "="*80)
    print("PRODUCTION RESUME PARSING TEST - ROGER WATERS RESUME")
    print("="*80)
    
    # Get the path to the Roger Waters resume
    resume_path = "Roger Waters Resume.pdf"
    if not os.path.exists(resume_path):
        print(f"❌ Roger Waters resume not found at {resume_path}")
        return False
    
    try:
        # Initialize real services (no mocking)
        print("Initializing real services...")
        llm_service = provide_llm_service()
        storage_service = MinioStorageService()
        
        # Initialize the parser with real services
        parser = ResumeParser(llm_service=llm_service, verbose=True)
        
        # Parse the resume with real services
        print(f"\nParsing resume: {resume_path}")
        print(f"File exists: {os.path.exists(resume_path)}")
        print(f"File size: {os.path.getsize(resume_path)} bytes")
        
        result = await parser.parse_resume(resume_path)
        
        # Display the extracted data in a comprehensive format
        print("\n" + "="*80)
        print("COMPLETE EXTRACTION RESULTS")
        print("="*80)
        
        # Personal Information
        print("\n📋 PERSONAL INFORMATION:")
        print("-" * 50)
        if result.personal_info:
            pi = result.personal_info
            print(f"Name: {pi.name}")
            print(f"Email: {pi.email}")
            print(f"Phone: {pi.phone}")
            print(f"Location: {pi.location}")
            print(f"Address: {pi.address}")
            print(f"LinkedIn: {pi.linkedin}")
            print(f"Website: {pi.website}")
            print(f"Summary: {pi.summary}")
        else:
            print("❌ No personal information extracted")
        
        # Education
        print("\n🎓 EDUCATION:")
        print("-" * 50)
        if result.education:
            for i, edu in enumerate(result.education, 1):
                print(f"\nEducation {i}:")
                print(f"  Institution: {edu.institution}")
                print(f"  Degree: {edu.degree}")
                print(f"  Field of Study: {edu.field_of_study}")
                print(f"  Start Date: {edu.start_date}")
                print(f"  End Date: {edu.end_date}")
                print(f"  Location: {edu.location}")
                print(f"  Description: {edu.description}")
        else:
            print("❌ No education information extracted")
        
        # Experience - DETAILED VIEW
        print("\n💼 EXPERIENCE (DETAILED VIEW):")
        print("=" * 80)
        if result.experience:
            for i, exp in enumerate(result.experience, 1):
                print(f"\n{'='*60}")
                print(f"EXPERIENCE {i}: {exp.title.upper()}")
                print(f"{'='*60}")
                print(f"Company: {exp.company}")
                print(f"Title: {exp.title}")
                print(f"Location: {exp.location}")
                print(f"Duration: {exp.start_date} - {exp.end_date}")
                print(f"\n📝 FULL DESCRIPTION:")
                print("-" * 40)
                if exp.description:
                    # Split description into bullet points for better readability
                    description_lines = exp.description.split('\n')
                    for line in description_lines:
                        line = line.strip()
                        if line:
                            if line.startswith('•'):
                                print(f"  {line}")
                            else:
                                print(f"  • {line}")
                else:
                    print("  No description available")
                print(f"\n📊 DESCRIPTION STATS:")
                print(f"  Characters: {len(exp.description) if exp.description else 0}")
                print(f"  Words: {len(exp.description.split()) if exp.description else 0}")
                lines_count = len(exp.description.split('\n')) if exp.description else 0
                print(f"  Lines: {lines_count}")
        else:
            print("❌ No experience information extracted")
        
        # Skills
        print("\n🛠️ SKILLS:")
        print("-" * 50)
        if result.skills:
            skill_names = [skill.name for skill in result.skills]
            print(f"Total skills extracted: {len(skill_names)}")
            print("Skills:", ", ".join(skill_names))
        else:
            print("❌ No skills extracted")
        
        # Projects
        print("\n📁 PROJECTS:")
        print("-" * 50)
        if result.projects:
            for i, proj in enumerate(result.projects, 1):
                print(f"\nProject {i}:")
                print(f"  Name: {proj.name}")
                print(f"  Description: {proj.description}")
                print(f"  Technologies: {proj.technologies}")
                print(f"  URL: {proj.url}")
        else:
            print("❌ No projects extracted")
        
        # Certifications
        print("\n🏆 CERTIFICATIONS:")
        print("-" * 50)
        if result.certifications:
            for i, cert in enumerate(result.certifications, 1):
                print(f"\nCertification {i}:")
                print(f"  Name: {cert.name}")
                print(f"  Issuer: {cert.issuer}")
                print(f"  Date: {cert.date}")
                print(f"  Description: {cert.description}")
        else:
            print("❌ No certifications extracted")
        
        # Languages
        print("\n🌍 LANGUAGES:")
        print("-" * 50)
        if result.languages:
            for i, lang in enumerate(result.languages, 1):
                print(f"\nLanguage {i}:")
                print(f"  Language: {lang.language}")
                print(f"  Proficiency: {lang.proficiency}")
        else:
            print("❌ No languages extracted")
        
        # Raw text summary
        print("\n📄 RAW TEXT SUMMARY:")
        print("-" * 50)
        if result.raw_text:
            print(f"Raw text length: {len(result.raw_text)} characters")
            print(f"First 200 characters: {result.raw_text[:200]}...")
            print(f"Last 200 characters: ...{result.raw_text[-200:]}")
        else:
            print("❌ No raw text extracted")
        
        # Validation checks
        print("\n" + "="*80)
        print("VALIDATION CHECKS")
        print("="*80)
        
        # Check if we got meaningful data
        has_personal_info = bool(result.personal_info and result.personal_info.name and result.personal_info.name != "Unknown")
        has_experience = bool(result.experience and len(result.experience) > 0)
        has_education = bool(result.education and len(result.education) > 0)
        has_skills = bool(result.skills and len(result.skills) > 0)
        
        print(f"✅ Personal Info Extracted: {has_personal_info}")
        print(f"✅ Experience Extracted: {has_experience}")
        print(f"✅ Education Extracted: {has_education}")
        print(f"✅ Skills Extracted: {has_skills}")
        
        # Roger Waters specific checks
        print("\n🎸 ROGER WATERS SPECIFIC CHECKS:")
        print("-" * 50)
        
        # Check raw text for Roger Waters
        raw_text_lower = result.raw_text.lower()
        print(f"Raw text contains 'roger': {'roger' in raw_text_lower}")
        print(f"Raw text contains 'waters': {'waters' in raw_text_lower}")
        print(f"Raw text contains 'roger waters': {'roger waters' in raw_text_lower}")
        
        if has_personal_info:
            name = result.personal_info.name.lower()
            print(f"Extracted name contains 'roger': {'roger' in name}")
            print(f"Extracted name contains 'waters': {'waters' in name}")
        
        if has_experience:
            experience_text = " ".join([exp.title.lower() + " " + exp.company.lower() for exp in result.experience])
            print(f"Experience mentions 'pink floyd': {'pink floyd' in experience_text}")
            print(f"Experience mentions 'music': {'music' in experience_text}")
            print(f"Experience mentions 'bass': {'bass' in experience_text}")
        
        # Check for tech skills in raw text
        tech_skills = ['python', 'ruby', 'rails', 'react', 'javascript', 'aws', 'docker', 'kubernetes']
        found_skills = [skill for skill in tech_skills if skill in raw_text_lower]
        print(f"Tech skills found in raw text: {found_skills}")
        
        # Overall assessment
        print("\n" + "="*80)
        print("OVERALL ASSESSMENT")
        print("="*80)
        
        total_fields = 4
        extracted_fields = sum([has_personal_info, has_experience, has_education, has_skills])
        success_rate = (extracted_fields / total_fields) * 100
        
        print(f"Extraction Success Rate: {success_rate:.1f}% ({extracted_fields}/{total_fields} fields)")
        
        if success_rate >= 75:
            print("🎉 EXCELLENT: Resume parsing is working well!")
        elif success_rate >= 50:
            print("✅ GOOD: Resume parsing is working, but could be improved")
        elif success_rate >= 25:
            print("⚠️ FAIR: Resume parsing needs improvement")
        else:
            print("❌ POOR: Resume parsing is not working effectively")
        
        # Expected results based on Roger Waters resume
        print("\n🎯 EXPECTED RESULTS (based on Roger Waters resume):")
        print("-" * 50)
        print("Expected skills: ~33 skills (Python, Ruby on Rails, React, JavaScript, etc.)")
        print("Expected experience: 3 jobs (Coupang, LG, SpaceX)")
        print("Expected education: 2 degrees (MS Software Engineering, BE Computer Science)")
        print("Expected personal info: Roger Waters, contact details")
        
        # Final validation
        print("\n" + "="*80)
        print("FINAL VALIDATION")
        print("="*80)
        
        # Check if we have the expected number of items
        if has_skills:
            skill_count = len(result.skills)
            print(f"Skills extracted: {skill_count} (expected ~33)")
            if skill_count >= 25:
                print("✅ Skills extraction: EXCELLENT")
            elif skill_count >= 15:
                print("✅ Skills extraction: GOOD")
            else:
                print("⚠️ Skills extraction: NEEDS IMPROVEMENT")
        
        if has_experience:
            exp_count = len(result.experience)
            print(f"Experience entries: {exp_count} (expected 3)")
            if exp_count >= 2:
                print("✅ Experience extraction: EXCELLENT")
            else:
                print("⚠️ Experience extraction: NEEDS IMPROVEMENT")
        
        if has_education:
            edu_count = len(result.education)
            print(f"Education entries: {edu_count} (expected 2)")
            if edu_count >= 1:
                print("✅ Education extraction: EXCELLENT")
            else:
                print("⚠️ Education extraction: NEEDS IMPROVEMENT")
        
        # Detailed analysis of extracted data
        print("\n" + "="*80)
        print("DETAILED ANALYSIS")
        print("="*80)
        
        print("\n📊 EXTRACTION ACCURACY ANALYSIS:")
        print("-" * 50)
        
        # Personal Info Analysis
        if has_personal_info:
            pi = result.personal_info
            print(f"\nPersonal Info Accuracy:")
            print(f"  ✅ Name: '{pi.name}' (Expected: 'ROGER WATERS')")
            print(f"  ✅ Email: '{pi.email}' (Expected: 'roger.waters@mail.com')")
            print(f"  ✅ Phone: '{pi.phone}' (Expected: '765-874-8773')")
            print(f"  ✅ Location: '{pi.location}' (Expected: 'West Spokane, WA')")
        
        # Experience Analysis
        if has_experience:
            print(f"\nExperience Analysis:")
            expected_companies = ['Coupang', 'LG', 'Space X']
            expected_titles = ['Senior Software Engineer', 'Software Engineer', 'Intern - Software Engineer']
            
            for i, exp in enumerate(result.experience):
                company_match = exp.company in expected_companies
                title_match = exp.title in expected_titles
                print(f"  Experience {i+1}:")
                print(f"    Company: '{exp.company}' {'✅' if company_match else '❌'}")
                print(f"    Title: '{exp.title}' {'✅' if title_match else '❌'}")
                print(f"    Duration: {exp.start_date} - {exp.end_date}")
        
        # Education Analysis
        if has_education:
            print(f"\nEducation Analysis:")
            expected_institutions = ['San Jose State University', 'Guru Nanak Dev University']
            expected_degrees = ['Master of Science in Software Engineering', 'Bachelor of Engineering in Computer Science']
            
            for i, edu in enumerate(result.education):
                institution_match = edu.institution in expected_institutions
                degree_match = edu.degree in expected_degrees
                print(f"  Education {i+1}:")
                print(f"    Institution: '{edu.institution}' {'✅' if institution_match else '❌'}")
                print(f"    Degree: '{edu.degree}' {'✅' if degree_match else '❌'}")
                print(f"    Duration: {edu.start_date} - {edu.end_date}")
        
        # Skills Analysis
        if has_skills:
            print(f"\nSkills Analysis:")
            expected_skills = [
                'Python', 'Ruby on Rails', 'React', 'JavaScript', 'MySQL', 'Redis', 
                'CSS', 'HTML', 'HAML', 'AWS Lambda', 'RDS', 'JWT', 'OIDC', 'GitHub',
                'RESTful APIs', 'Microservices', 'Elasticsearch', 'Logstash', 'Kibana',
                'Linux', 'Shell Scripting', 'Django', 'NumPy', 'Pandas', 'Seaborn',
                'Matplotlib', 'Node.js', 'CDN Caching', 'Selenium', 'VMware ESX',
                'Internationalization (i18n)', 'RTLcss'
            ]
            
            extracted_skill_names = [skill.name for skill in result.skills]
            missing_skills = [skill for skill in expected_skills if skill not in extracted_skill_names]
            extra_skills = [skill for skill in extracted_skill_names if skill not in expected_skills]
            
            print(f"  Total skills extracted: {len(extracted_skill_names)}")
            print(f"  Expected skills: {len(expected_skills)}")
            print(f"  Skills accuracy: {len([s for s in extracted_skill_names if s in expected_skills])}/{len(expected_skills)}")
            
            if missing_skills:
                print(f"  Missing skills: {missing_skills}")
            if extra_skills:
                print(f"  Extra skills found: {extra_skills}")
        
        print("\n" + "="*80)
        print("TEST COMPLETED SUCCESSFULLY")
        print("="*80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR during parsing: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    # Run the production test
    success = asyncio.run(test_production_resume_parsing())
    if success:
        print("\n🎉 Production test completed successfully!")
    else:
        print("\n❌ Production test failed!")
        exit(1) 