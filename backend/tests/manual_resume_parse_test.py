import os
from pathlib import Path

from backend.services.nebius_ai_service import NebiusAIService
from backend.utils.resume_parsing.resume_parser import ResumeParser
from backend.services.storage_service import StorageService

# print("=== ENTERED manual_resume_parse_test.py top-level ===")  # Commented out to reduce noise

if __name__ == "__main__":
    # print("=== ENTERED __main__ block in manual_resume_parse_test.py ===")  # Commented out to reduce noise
    # Set up config and services
    config = {
        "temperature": 0.1,
        "max_tokens": 2000,
        "timeout": 120.0,
        "api_key": os.environ.get("NEBIUS_API_KEY", "")
    }
    nebius_service = NebiusAIService(config)
    storage_service = StorageService()
    parser = ResumeParser(storage_service, nebius_service)

    test_file = Path(r"C:\Users\seaso\RecruitIQ\Alex_Jones_Resume.pdf")

    if not test_file.exists():
        print(f"Resume file not found at: {test_file}")
        exit(1)

    import asyncio

    async def main():
        try:
            print(f"Parsing resume: {test_file.name}")
            resume_data = await parser.parse(test_file)
            
            # Print a human-friendly summary first
            print("\n" + "="*60)
            print("🎯 RESUME PARSING RESULTS")
            print("="*60)
            
            # If resume_data has a model_dump method (Pydantic), use it for clean output
            if hasattr(resume_data, 'model_dump'):
                final_data = resume_data.model_dump()
            elif hasattr(resume_data, 'dict'):
                final_data = resume_data.dict()
            else:
                final_data = resume_data
            
            # Print summary
            pi = final_data.get('personal_info', {})
            print(f"👤 Name: {pi.get('name', 'N/A')}")
            print(f"📧 Email: {pi.get('email', 'N/A')}")
            print(f"📍 Location: {pi.get('location', 'N/A')}")
            print(f"💼 Experience: {len(final_data.get('experience', []))} entries")
            print(f"🎓 Education: {len(final_data.get('education', []))} entries")
            print(f"🛠️  Skills: {len(final_data.get('skills', []))} skills")
            
            # Show first few skills for quick verification
            skills = final_data.get('skills', [])
            if skills:
                skill_names = [s.get('name', '') for s in skills[:5]]
                print(f"   Sample skills: {', '.join(skill_names)}{'...' if len(skills) > 5 else ''}")
            
            print("\n" + "="*60)
            print("📋 COMPLETE JSON OUTPUT")
            print("="*60)
            import json
            print(json.dumps(final_data, indent=2, ensure_ascii=False))

            # Print debug info only if there were issues
            if hasattr(resume_data, 'debug_info') and resume_data.debug_info.get('error'):
                print("\n" + "="*60)
                print("⚠️  DEBUG INFO (Errors Found)")
                print("="*60)
                print(json.dumps(resume_data.debug_info, indent=2, ensure_ascii=False))
                
        except Exception as e:
            print(f"❌ Exception during parsing: {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(main())