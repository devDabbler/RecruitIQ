#!/usr/bin/env python3
"""
Sean B. Collins Resume - Parser Comparison Test
Tests both enhanced and unified parsers against Sean's specific resume to validate improvements.
"""

import os
import sys
import asyncio
import logging
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Import both parsers
from utils.enhanced_resume_parser import EnhancedResumeParser
from services.enhanced_parse_service import EnhancedParseService
from utils.unified_resume_parser import UnifiedResumeParser
from utils.resume_parser import ResumeParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SeanResumeComparison:
    """Comprehensive comparison of parsers using Sean B. Collins' resume"""
    
    def __init__(self, resume_path: str):
        """
        Initialize the comparison test
        
        Args:
            resume_path: Path to Sean's resume PDF
        """
        self.resume_path = Path(resume_path)
        if not self.resume_path.exists():
            raise FileNotFoundError(f"Resume file not found: {resume_path}")
        
        # Initialize parsers
        self.enhanced_parser = EnhancedResumeParser()
        self.enhanced_service = EnhancedParseService()
        self.unified_parser = UnifiedResumeParser()
        self.original_parser = ResumeParser()
        
        # Store results
        self.results = {}
        self.comparison_report = {}
        
    async def run_comprehensive_comparison(self):
        """Run comprehensive comparison between all parsers"""
        logger.info(f"Starting comprehensive comparison using {self.resume_path.name}")
        
        # Test 1: Enhanced Parser (Core)
        await self.test_enhanced_parser_core()
        
        # Test 2: Enhanced Parser (Service with LLM)
        await self.test_enhanced_parser_service()
        
        # Test 3: Unified Parser
        await self.test_unified_parser()
        
        # Test 4: Original Parser
        await self.test_original_parser()
        
        # Test 5: Performance Comparison
        await self.test_performance_comparison()
        
        # Generate comprehensive report
        self.generate_comparison_report()
        
        return self.comparison_report

    async def test_enhanced_parser_core(self):
        """Test the core enhanced parser"""
        logger.info("Testing Enhanced Parser (Core)...")
        
        try:
            start_time = time.time()
            result = await asyncio.to_thread(
                self.enhanced_parser.parse_resume, 
                str(self.resume_path)
            )
            end_time = time.time()
            
            self.results['enhanced_core'] = {
                'success': True,
                'parsing_time': round(end_time - start_time, 3),
                'result': result,
                'personal_info': {
                    'name': result.personal_info.name if result.personal_info else None,
                    'email': result.personal_info.email if result.personal_info else None,
                    'phone': result.personal_info.phone if result.personal_info else None,
                    'location': result.personal_info.location if result.personal_info else None,
                    'linkedin': result.personal_info.linkedin if result.personal_info else None,
                    'github': result.personal_info.github if result.personal_info else None,
                },
                'summary': result.summary,
                'experience_count': len(result.experience) if result.experience else 0,
                'skills_count': len(result.skills) if result.skills else 0,
                'education_count': len(result.education) if result.education else 0,
                'experience_details': [
                    {
                        'title': exp.title,
                        'company': exp.company,
                        'location': exp.location,
                        'description_length': len(exp.description) if exp.description else 0,
                        'achievements_count': len(exp.achievements) if hasattr(exp, 'achievements') and exp.achievements else 0,
                        'technologies_count': len(exp.technologies) if hasattr(exp, 'technologies') and exp.technologies else 0
                    }
                    for exp in (result.experience or [])
                ],
                'skills_by_category': {}
            }
            
            # Organize skills by category
            if result.skills:
                skills_by_cat = {}
                for skill in result.skills:
                    category = skill.category or "Other"
                    if category not in skills_by_cat:
                        skills_by_cat[category] = []
                    skills_by_cat[category].append(skill.name)
                self.results['enhanced_core']['skills_by_category'] = skills_by_cat
            
        except Exception as e:
            logger.error(f"Enhanced parser core failed: {e}")
            self.results['enhanced_core'] = {
                'success': False,
                'error': str(e)
            }

    async def test_enhanced_parser_service(self):
        """Test the enhanced parser service with LLM integration"""
        logger.info("Testing Enhanced Parser Service (with LLM)...")
        
        try:
            start_time = time.time()
            result = await self.enhanced_service.parse_resume_from_file(str(self.resume_path))
            end_time = time.time()
            
            # Get parsing statistics
            stats = self.enhanced_service.get_parsing_stats(result)
            
            self.results['enhanced_service'] = {
                'success': True,
                'parsing_time': round(end_time - start_time, 3),
                'extraction_confidence': stats['extraction_confidence'],
                'personal_info_completeness': stats['personal_info_completeness'],
                'result': result,
                'personal_info': {
                    'name': result.personal_info.name if result.personal_info else None,
                    'email': result.personal_info.email if result.personal_info else None,
                    'phone': result.personal_info.phone if result.personal_info else None,
                    'location': result.personal_info.location if result.personal_info else None,
                    'linkedin': result.personal_info.linkedin if result.personal_info else None,
                    'github': result.personal_info.github if result.personal_info else None,
                },
                'summary': result.summary,
                'experience_count': len(result.experience) if result.experience else 0,
                'skills_count': len(result.skills) if result.skills else 0,
                'education_count': len(result.education) if result.education else 0,
                'stats': stats
            }
            
        except Exception as e:
            logger.error(f"Enhanced parser service failed: {e}")
            self.results['enhanced_service'] = {
                'success': False,
                'error': str(e)
            }

    async def test_unified_parser(self):
        """Test the unified parser"""
        logger.info("Testing Unified Parser...")
        
        try:
            # Create a mock upload file for the unified parser
            from fastapi import UploadFile
            from io import BytesIO
            
            # Read the file content
            with open(self.resume_path, 'rb') as f:
                file_content = f.read()
            
            # Create mock UploadFile
            file_obj = BytesIO(file_content)
            upload_file = UploadFile(
                filename=self.resume_path.name,
                file=file_obj,
                content_type="application/pdf"
            )
            
            start_time = time.time()
            file_id, result = await self.unified_parser.parse_resume(upload_file)
            end_time = time.time()
            
            self.results['unified'] = {
                'success': True,
                'parsing_time': round(end_time - start_time, 3),
                'file_id': file_id,
                'result': result,
                'personal_info': {
                    'name': result.personal_info.name if result.personal_info else None,
                    'email': result.personal_info.email if result.personal_info else None,
                    'phone': result.personal_info.phone if result.personal_info else None,
                    'location': result.personal_info.location if result.personal_info else None,
                    'linkedin': result.personal_info.linkedin if result.personal_info else None,
                    'github': result.personal_info.github if result.personal_info else None,
                },
                'summary': result.summary,
                'experience_count': len(result.experience) if result.experience else 0,
                'skills_count': len(result.skills) if result.skills else 0,
                'education_count': len(result.education) if result.education else 0,
                'experience_details': [
                    {
                        'title': exp.title if hasattr(exp, 'title') else '',
                        'company': exp.company if hasattr(exp, 'company') else '',
                        'location': exp.location if hasattr(exp, 'location') else '',
                        'description_length': len(exp.description) if hasattr(exp, 'description') and exp.description else 0
                    }
                    for exp in (result.experience or [])
                ]
            }
            
        except Exception as e:
            logger.error(f"Unified parser failed: {e}")
            self.results['unified'] = {
                'success': False,
                'error': str(e)
            }

    async def test_original_parser(self):
        """Test the original parser for baseline comparison"""
        logger.info("Testing Original Parser...")
        
        try:
            start_time = time.time()
            result = await asyncio.to_thread(
                self.original_parser.parse, 
                str(self.resume_path)
            )
            end_time = time.time()
            
            self.results['original'] = {
                'success': True,
                'parsing_time': round(end_time - start_time, 3),
                'result': result,
                'personal_info': {
                    'name': result.personal_info.name if result.personal_info else None,
                    'email': result.personal_info.email if result.personal_info else None,
                    'phone': result.personal_info.phone if result.personal_info else None,
                    'location': result.personal_info.location if result.personal_info else None,
                    'linkedin': result.personal_info.linkedin if result.personal_info else None,
                },
                'summary': result.summary,
                'experience_count': len(result.experience) if result.experience else 0,
                'skills_count': len(result.skills) if result.skills else 0,
                'education_count': len(result.education) if result.education else 0
            }
            
        except Exception as e:
            logger.error(f"Original parser failed: {e}")
            self.results['original'] = {
                'success': False,
                'error': str(e)
            }

    async def test_performance_comparison(self):
        """Compare performance across all parsers"""
        logger.info("Running performance comparison...")
        
        performance_results = {}
        
        # Run each parser multiple times for average performance
        for parser_name in ['enhanced_core', 'enhanced_service', 'unified', 'original']:
            if parser_name in self.results and self.results[parser_name]['success']:
                times = []
                for i in range(3):  # Run 3 times
                    try:
                        if parser_name == 'enhanced_core':
                            start = time.time()
                            await asyncio.to_thread(self.enhanced_parser.parse_resume, str(self.resume_path))
                            times.append(time.time() - start)
                        elif parser_name == 'enhanced_service':
                            start = time.time()
                            await self.enhanced_service.parse_resume_from_file(str(self.resume_path))
                            times.append(time.time() - start)
                        # Skip unified and original for multiple runs to avoid complications
                    except Exception as e:
                        logger.warning(f"Performance test failed for {parser_name}: {e}")
                
                if times:
                    performance_results[parser_name] = {
                        'avg_time': round(sum(times) / len(times), 3),
                        'min_time': round(min(times), 3),
                        'max_time': round(max(times), 3)
                    }
        
        self.results['performance'] = performance_results

    def generate_comparison_report(self):
        """Generate comprehensive comparison report"""
        logger.info("Generating comparison report...")
        
        # Initialize report structure
        self.comparison_report = {
            'test_summary': {
                'resume_file': self.resume_path.name,
                'timestamp': datetime.now().isoformat(),
                'parsers_tested': list(self.results.keys())
            },
            'extraction_comparison': {},
            'performance_comparison': {},
            'detailed_analysis': {},
            'recommendations': []
        }
        
        # Compare extraction results
        successful_results = {
            name: data for name, data in self.results.items() 
            if data.get('success', False) and name != 'performance'
        }
        
        if successful_results:
            # Personal info comparison
            personal_info_comparison = {}
            for parser_name, data in successful_results.items():
                personal_info = data.get('personal_info', {})
                personal_info_comparison[parser_name] = {
                    'name_extracted': bool(personal_info.get('name')),
                    'email_extracted': bool(personal_info.get('email')),
                    'phone_extracted': bool(personal_info.get('phone')),
                    'location_extracted': bool(personal_info.get('location')),
                    'linkedin_extracted': bool(personal_info.get('linkedin')),
                    'github_extracted': bool(personal_info.get('github')),
                    'completeness_score': self._calculate_personal_info_score(personal_info)
                }
            
            # Experience comparison
            experience_comparison = {}
            for parser_name, data in successful_results.items():
                experience_comparison[parser_name] = {
                    'experience_count': data.get('experience_count', 0),
                    'has_detailed_descriptions': any(
                        exp.get('description_length', 0) > 100 
                        for exp in data.get('experience_details', [])
                    ) if 'experience_details' in data else False,
                    'has_achievements': any(
                        exp.get('achievements_count', 0) > 0 
                        for exp in data.get('experience_details', [])
                    ) if 'experience_details' in data else False,
                    'has_technologies': any(
                        exp.get('technologies_count', 0) > 0 
                        for exp in data.get('experience_details', [])
                    ) if 'experience_details' in data else False
                }
            
            # Skills comparison
            skills_comparison = {}
            for parser_name, data in successful_results.items():
                skills_by_cat = data.get('skills_by_category', {})
                skills_comparison[parser_name] = {
                    'total_skills': data.get('skills_count', 0),
                    'categories_found': len(skills_by_cat),
                    'categories': list(skills_by_cat.keys()) if skills_by_cat else [],
                    'has_categorization': len(skills_by_cat) > 1
                }
            
            # Summary comparison
            summary_comparison = {}
            for parser_name, data in successful_results.items():
                summary = data.get('summary', '')
                summary_comparison[parser_name] = {
                    'has_summary': bool(summary and len(summary.strip()) > 50),
                    'summary_length': len(summary.strip()) if summary else 0
                }
            
            self.comparison_report['extraction_comparison'] = {
                'personal_info': personal_info_comparison,
                'experience': experience_comparison,
                'skills': skills_comparison,
                'summary': summary_comparison
            }
        
        # Performance comparison
        if 'performance' in self.results:
            self.comparison_report['performance_comparison'] = self.results['performance']
        
        # Add parsing times from initial runs
        parsing_times = {}
        for parser_name, data in successful_results.items():
            if 'parsing_time' in data:
                parsing_times[parser_name] = data['parsing_time']
        self.comparison_report['parsing_times'] = parsing_times
        
        # Detailed analysis and recommendations
        self._generate_detailed_analysis()
        
        # Save report to file
        report_filename = f"sean_resume_comparison_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(self.comparison_report, f, indent=2, default=str)
        
        # Print summary
        self._print_comparison_summary()
        
        logger.info(f"Detailed comparison report saved to: {report_filename}")

    def _calculate_personal_info_score(self, personal_info: Dict) -> float:
        """Calculate completeness score for personal info"""
        fields = ['name', 'email', 'phone', 'location', 'linkedin']
        present_fields = sum(1 for field in fields if personal_info.get(field))
        return round(present_fields / len(fields), 2)

    def _generate_detailed_analysis(self):
        """Generate detailed analysis and recommendations"""
        analysis = {
            'strengths_by_parser': {},
            'weaknesses_by_parser': {},
            'overall_winner': None,
            'specific_improvements': []
        }
        
        # Analyze each parser's strengths and weaknesses
        extraction_comp = self.comparison_report.get('extraction_comparison', {})
        
        for parser_name in ['enhanced_core', 'enhanced_service', 'unified', 'original']:
            if parser_name in self.results and self.results[parser_name].get('success'):
                strengths = []
                weaknesses = []
                
                # Personal info analysis
                personal_info = extraction_comp.get('personal_info', {}).get(parser_name, {})
                if personal_info.get('completeness_score', 0) >= 0.8:
                    strengths.append("Excellent personal info extraction")
                elif personal_info.get('completeness_score', 0) < 0.5:
                    weaknesses.append("Poor personal info extraction")
                
                # Experience analysis
                experience = extraction_comp.get('experience', {}).get(parser_name, {})
                if experience.get('has_detailed_descriptions'):
                    strengths.append("Detailed job descriptions")
                else:
                    weaknesses.append("Lacks detailed job descriptions")
                
                if experience.get('has_achievements'):
                    strengths.append("Extracts achievements")
                else:
                    weaknesses.append("Misses achievements")
                
                # Skills analysis
                skills = extraction_comp.get('skills', {}).get(parser_name, {})
                if skills.get('has_categorization'):
                    strengths.append("Categorizes skills effectively")
                else:
                    weaknesses.append("Poor skills categorization")
                
                # Summary analysis
                summary = extraction_comp.get('summary', {}).get(parser_name, {})
                if summary.get('has_summary'):
                    strengths.append("Extracts professional summary")
                else:
                    weaknesses.append("Misses professional summary")
                
                analysis['strengths_by_parser'][parser_name] = strengths
                analysis['weaknesses_by_parser'][parser_name] = weaknesses
        
        # Determine overall winner
        parser_scores = {}
        for parser_name in analysis['strengths_by_parser']:
            score = len(analysis['strengths_by_parser'][parser_name]) - len(analysis['weaknesses_by_parser'][parser_name])
            parser_scores[parser_name] = score
        
        if parser_scores:
            analysis['overall_winner'] = max(parser_scores.items(), key=lambda x: x[1])
        
        # Generate specific improvements
        improvements = []
        if 'enhanced_core' in parser_scores and 'unified' in parser_scores:
            if parser_scores['enhanced_core'] > parser_scores['unified']:
                improvements.append("Enhanced parser shows significant improvements over unified parser")
            
        self.comparison_report['detailed_analysis'] = analysis
        
        # Generate recommendations
        recommendations = []
        if analysis.get('overall_winner'):
            winner_name, score = analysis['overall_winner']
            recommendations.append(f"Recommended parser: {winner_name} (score: {score})")
        
        if any('enhanced' in parser for parser in parser_scores):
            enhanced_score = max(score for parser, score in parser_scores.items() if 'enhanced' in parser)
            unified_score = parser_scores.get('unified', 0)
            if enhanced_score > unified_score:
                recommendations.append("Enhanced parser outperforms unified parser - recommend migration")
        
        self.comparison_report['recommendations'] = recommendations

    def _print_comparison_summary(self):
        """Print a formatted summary of the comparison"""
        print("\n" + "="*80)
        print("SEAN B. COLLINS RESUME - PARSER COMPARISON REPORT")
        print("="*80)
        
        # Test results summary
        print(f"\nTEST FILE: {self.resume_path.name}")
        print(f"TIMESTAMP: {self.comparison_report['test_summary']['timestamp']}")
        
        successful_parsers = [
            name for name, data in self.results.items() 
            if data.get('success', False) and name != 'performance'
        ]
        failed_parsers = [
            name for name, data in self.results.items() 
            if not data.get('success', False) and name != 'performance'
        ]
        
        print(f"\nSUCCESSFUL PARSERS: {len(successful_parsers)}")
        for parser in successful_parsers:
            print(f"  ✅ {parser}")
        
        if failed_parsers:
            print(f"\nFAILED PARSERS: {len(failed_parsers)}")
            for parser in failed_parsers:
                print(f"  ❌ {parser}: {self.results[parser].get('error', 'Unknown error')}")
        
        # Extraction comparison
        if 'extraction_comparison' in self.comparison_report:
            print(f"\n{'EXTRACTION COMPARISON':^80}")
            print("-" * 80)
            
            # Personal info
            print(f"{'Parser':<20} {'Name':<8} {'Email':<8} {'Phone':<8} {'Location':<8} {'LinkedIn':<8} {'Score':<8}")
            print("-" * 80)
            
            personal_info_comp = self.comparison_report['extraction_comparison'].get('personal_info', {})
            for parser_name, data in personal_info_comp.items():
                name_check = "✅" if data.get('name_extracted') else "❌"
                email_check = "✅" if data.get('email_extracted') else "❌"
                phone_check = "✅" if data.get('phone_extracted') else "❌"
                location_check = "✅" if data.get('location_extracted') else "❌"
                linkedin_check = "✅" if data.get('linkedin_extracted') else "❌"
                score = data.get('completeness_score', 0)
                
                print(f"{parser_name:<20} {name_check:<8} {email_check:<8} {phone_check:<8} {location_check:<8} {linkedin_check:<8} {score:<8}")
            
            # Experience and skills summary
            print(f"\n{'CONTENT EXTRACTION SUMMARY':^80}")
            print("-" * 80)
            print(f"{'Parser':<20} {'Experience':<12} {'Skills':<10} {'Summary':<10} {'Categories':<12}")
            print("-" * 80)
            
            exp_comp = self.comparison_report['extraction_comparison'].get('experience', {})
            skills_comp = self.comparison_report['extraction_comparison'].get('skills', {})
            summary_comp = self.comparison_report['extraction_comparison'].get('summary', {})
            
            for parser_name in successful_parsers:
                exp_count = exp_comp.get(parser_name, {}).get('experience_count', 0)
                skills_count = skills_comp.get(parser_name, {}).get('total_skills', 0)
                has_summary = "✅" if summary_comp.get(parser_name, {}).get('has_summary') else "❌"
                categories = skills_comp.get(parser_name, {}).get('categories_found', 0)
                
                print(f"{parser_name:<20} {exp_count:<12} {skills_count:<10} {has_summary:<10} {categories:<12}")
        
        # Performance summary
        if 'parsing_times' in self.comparison_report:
            print(f"\n{'PERFORMANCE COMPARISON':^80}")
            print("-" * 80)
            print(f"{'Parser':<20} {'Time (seconds)':<15}")
            print("-" * 80)
            
            for parser_name, time_taken in self.comparison_report['parsing_times'].items():
                print(f"{parser_name:<20} {time_taken:<15}")
        
        # Recommendations
        if self.comparison_report.get('recommendations'):
            print(f"\n{'RECOMMENDATIONS':^80}")
            print("-" * 80)
            for i, recommendation in enumerate(self.comparison_report['recommendations'], 1):
                print(f"{i}. {recommendation}")
        
        print("\n" + "="*80)


async def main():
    """Main function to run the comparison test"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Compare parsers using Sean B. Collins resume')
    parser.add_argument(
        '--resume-path', 
        default='Sean B. Collins Resume - Recruiting Leader.pdf',
        help='Path to Sean\'s resume file'
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize comparison test
        comparison = SeanResumeComparison(args.resume_path)
        
        # Run comprehensive comparison
        report = await comparison.run_comprehensive_comparison()
        
        print(f"\nComparison completed successfully!")
        print(f"Report saved to disk with detailed JSON output.")
        
        return report
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please ensure Sean's resume file is in the current directory or provide the correct path.")
        return None
    except Exception as e:
        print(f"Error during comparison: {e}")
        logger.exception("Exception details:")
        return None


if __name__ == "__main__":
    asyncio.run(main()) 