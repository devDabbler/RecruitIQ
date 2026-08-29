from __future__ import annotations
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.services.resume_service import ResumeService
import logging
import tempfile
import os
import re
import json
import asyncio
from fastapi import UploadFile
import difflib

from backend.services.agent_framework.base_agent import BaseAgent
from backend.services.agent_framework.agent_registry import register
from backend.services.agent_framework.exceptions import ParsingError
# Remove the direct import of ResumeService to break circular dependency
# from backend.services.resume_service import ResumeService
from backend.services.storage_service import StorageService
from backend.services.llm_service import LLMService
from backend.services.web_search_service import WebSearchService
from backend.services.job_service import JobService
from backend.utils.resume_parsing.models.resume_schema import ResumeData

logger = logging.getLogger(__name__)

# "ai" as a bare substring matches Retail, Maintenance, Trainer, Paid Media and
# plenty of other titles that have nothing to do with machine learning, and any
# of them used to collect the AI scoring bonus below. Match it as a word, or as
# part of a genuinely AI-flavoured compound like "AI/ML".
_AI_ROLE_PATTERN = re.compile(
    r"\b(ai|a\.i\.|artificial intelligence|ml|machine learning|deep learning|nlp|llm|genai)\b",
    re.IGNORECASE,
)


def _is_ai_role(job_title: Optional[str]) -> bool:
    """Whether a role title is AI/ML flavoured, for role-specific score weighting."""
    if not job_title:
        return False
    return bool(_AI_ROLE_PATTERN.search(job_title))


def _job_skills_from(job_data: Optional[Dict[str, Any]]) -> Optional[List[str]]:
    """Pull a job's own required skills out of a job payload.

    The `jobs.skills` column stores a comma-separated string while the API
    serialises it as a list, and this is reached from both directions, so accept
    either. Returns None rather than [] when there is nothing usable: an empty
    list would be indistinguishable from "this role requires no skills" and
    would score every resume at zero overlap.
    """
    if not isinstance(job_data, dict):
        return None

    raw = job_data.get("skills")
    if isinstance(raw, str):
        skills = [s.strip() for s in raw.split(",") if s.strip()]
    elif isinstance(raw, (list, tuple, set)):
        skills = [str(s).strip() for s in raw if str(s).strip()]
    else:
        return None

    return skills or None


@register(
    name="ResumeProcessingAgent",
    description="Handles all resume processing tasks, from initial parsing to enhancement and quality analysis."
)
class ResumeProcessingAgent(BaseAgent):
    """
    An agent dedicated to processing resumes. It orchestrates services
    for parsing, storing, and analyzing resume content.
    """

    def __init__(self, resume_service: 'ResumeService', storage_service: StorageService, llm_service: LLMService, web_search_service: WebSearchService, job_service: JobService):
        self.resume_service = resume_service
        self.storage_service = storage_service
        self.llm_service = llm_service
        self.web_search_service = web_search_service
        self.job_service = job_service

    async def _process_single_file(
        self,
        file: UploadFile,
        target_job_title: Optional[str],
        job_skills: Optional[List[str]] = None,
        job_requirements: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Processes a single resume file, including parsing, enrichment, analysis, and saving to database.

        `job_skills` and `job_requirements`, when given, come from a real
        requisition and make the fit analysis specific to that opening rather
        than to the market average for its title.
        """
        logger.info(f"Processing single file: {file.filename}")

        try:
            # Import database dependency
            from backend.utils.database import get_db
            from sqlalchemy.orm import Session
            
            # Get database session for saving
            db_generator = get_db()
            db_session: Session = next(db_generator)
            
            try:
                # Use the resume service's parse_resume_upload_no_save method which parses but does NOT save to database
                result = await self.resume_service.parse_resume_upload_no_save(file, strategy='comprehensive')
                
                # Extract the parsed data and identifiers
                resume_id = result.get("resume_id")  # Will be None for no-save operations
                file_id = result.get("file_id")      # Will be None for no-save operations
                parsed_data = result.get("parsed_data")
                
                logger.info(f"Resume parsed for analysis (not saved to database). resume_id: {resume_id}, file_id: {file_id}")

                # If parsed_data is missing or empty, return an error
                if not parsed_data or (isinstance(parsed_data, dict) and not parsed_data):
                    logger.error(f"Parsed data is empty for file: {file.filename}")
                    return {
                        "status": "error",
                        "filename": file.filename,
                        "message": "Resume parsing completed but no data could be extracted. Please check the resume format or try another file."
                    }

                # Continue with agent enhancements
                parsed_data = await self._validate_and_clean_data(parsed_data)

                # Run independent analyses concurrently to reduce total latency
                enrich_task = asyncio.create_task(self._enrich_with_linkedin_profile(parsed_data))
                quality_task = asyncio.create_task(self._assess_resume_quality(parsed_data))
                suggestions_task = asyncio.create_task(self._generate_skill_suggestions(parsed_data))

                market_alignment_task = None
                market_alignment = None
                job_fit_score = 0
                hiring_recommendation = {
                    "score": 0,
                    "recommendation": "Could not analyze job fit",
                    "details": "No job title provided for comparison",
                    "decision": "undetermined"
                }
                
                if target_job_title:
                    market_alignment_task = asyncio.create_task(
                        self._analyze_market_alignment(
                            parsed_data, target_job_title, job_skills, job_requirements
                        )
                    )

                # Await concurrent tasks
                try:
                    enriched_data, quality_assessment, skill_suggestions = await asyncio.gather(
                        enrich_task, quality_task, suggestions_task
                    )
                    # Use enriched data going forward
                    parsed_data = enriched_data if enriched_data else parsed_data
                except Exception as e:
                    logger.error(f"Error in parallel analyses: {e}")
                    # Fallbacks if any task failed
                    if not 'quality_assessment' in locals() or quality_assessment is None:
                        quality_assessment = {"clarity_score": 5, "impact_score": 5, "skills_relevance_score": 5}
                    if not 'skill_suggestions' in locals() or skill_suggestions is None:
                        skill_suggestions = {"technical_skills": [], "soft_skills": [], "certifications": [], "recommendations": ""}

                if market_alignment_task:
                    try:
                        market_alignment = await market_alignment_task
                    except Exception as e:
                        logger.error(f"Market alignment task failed: {e}")
                        market_alignment = None
                
                if target_job_title:
                    # Calculate job fit score with normalized Jaccard-based skills overlap
                    if market_alignment and 'matching_skills' in market_alignment and 'market_skills' in market_alignment:
                        matching_count = len(market_alignment['matching_skills'])
                        total_market_skills = len(market_alignment['market_skills'])
                        # Fallback-safe union estimate for Jaccard-style scoring
                        candidate_skills_norm = set()
                        if parsed_data.get('skills'):
                            for sk in parsed_data.get('skills', []):
                                if isinstance(sk, dict) and sk.get('name'):
                                    candidate_skills_norm.add(re.sub(r"[\./,+_]+", " ", sk['name'].strip().lower()))
                        union_count = len(set(market_alignment['market_skills']).union(candidate_skills_norm)) or max(total_market_skills, 1)
                        overlap_ratio = matching_count / max(union_count, 1)
                        skills_score = min(10.0, round(overlap_ratio * 10.0, 2))
                        logger.info(
                            f"[JobFit] target='{target_job_title}' match={matching_count} market={total_market_skills} union={union_count} "
                            f"overlap_ratio={overlap_ratio:.4f} skills_score={skills_score} quality=(clarity={quality_assessment.get('clarity_score', 5)}, "
                            f"impact={quality_assessment.get('impact_score', 5)}, relevance={quality_assessment.get('skills_relevance_score', 5)})"
                        )

                        # Factor in quality assessment
                        clarity = quality_assessment.get('clarity_score', 5)
                        impact = quality_assessment.get('impact_score', 5)
                        skills_relevance = quality_assessment.get('skills_relevance_score', 5)

                        # Enhanced weighted score calculation with role-specific adjustments
                        base_score = (skills_score * 0.6) + (clarity * 0.1) + (impact * 0.2) + (skills_relevance * 0.1)
                        
                        # Apply role-specific adjustments
                        if _is_ai_role(target_job_title):
                            # For AI roles, check for core AI/ML skills and adjust score
                            core_ai_skills = {'ai', 'ml', 'python', 'tensorflow', 'pytorch', 'pandas', 'numpy', 'git', 'aws', 'azure', 'gcp'}
                            candidate_skills_set = set()
                            if parsed_data.get('skills'):
                                for sk in parsed_data.get('skills', []):
                                    if isinstance(sk, dict) and sk.get('name'):
                                        candidate_skills_set.add(re.sub(r"[\./,+_]+", " ", sk['name'].strip().lower()))
                            
                            core_matches = len(candidate_skills_set.intersection(core_ai_skills))
                            if core_matches >= 5:  # Strong AI foundation
                                base_score += 1.0
                            elif core_matches >= 3:  # Moderate AI foundation
                                base_score += 0.5
                            elif core_matches >= 1:  # Basic AI foundation
                                base_score += 0.2
                            
                            # Experience bonus for AI-related work
                            ai_experience_bonus = 0
                            for exp in parsed_data.get('experience', []):
                                if isinstance(exp, dict) and exp.get('description'):
                                    desc = exp['description'].lower()
                                    if any(term in desc for term in ['ai', 'machine learning', 'deep learning', 'neural', 'tensorflow', 'pytorch']):
                                        ai_experience_bonus += 0.3
                                        break
                            base_score += min(ai_experience_bonus, 0.6)
                        
                        job_fit_score = round(min(10.0, max(0.0, base_score)), 1)
                        logger.info(f"[JobFit] final_score={job_fit_score} from skills={skills_score}, clarity={clarity}, impact={impact}, relevance={skills_relevance}")

                        # Enhanced hiring recommendation with more nuanced thresholds
                        if job_fit_score >= 8.0:
                            recommendation = "Strong Candidate"
                            details = "Excellent job fit with strong technical alignment. Proceed with interview."
                            decision = "yes"
                        elif job_fit_score >= 6.5:
                            recommendation = "Good Candidate"
                            details = "Good job fit with solid foundation. Consider for screening call."
                            decision = "yes"
                        elif job_fit_score >= 5.0:
                            recommendation = "Potential Candidate"
                            details = "Moderate job fit. Consider for initial screening if other factors are favorable."
                            decision = "maybe"
                        elif job_fit_score >= 3.5:
                            recommendation = "Weak Candidate"
                            details = "Limited job fit. May require significant upskilling for this role."
                            decision = "no"
                        else:
                            recommendation = "Poor Candidate"
                            details = "Very limited job fit. Not recommended for this role."
                            decision = "no"

                        hiring_recommendation = {
                            "score": job_fit_score,
                            "recommendation": recommendation,
                            "details": details,
                            "decision": decision
                        }

                return {
                    "status": "success",
                    "filename": file.filename,
                    "resume_id": resume_id,  # Include resume_id for frontend
                    "file_id": file_id,      # Include file_id for reference
                    "message": f"Agent processed and analyzed resume '{file.filename}' successfully.",
                    "job_fit_score": job_fit_score,
                    "hiring_recommendation": hiring_recommendation,
                    "quality_assessment": quality_assessment,
                    "market_alignment": market_alignment,
                    "skill_suggestions": skill_suggestions,
                    "data": parsed_data
                }
            finally:
                # Ensure database session is properly closed
                db_session.close()
                
        except Exception as e:
            logger.error(f"Processing for file {file.filename} failed: {e}", exc_info=True)
            return {
                "status": "error",
                "filename": file.filename,
                "message": str(e)
            }

    async def _analyze_market_alignment(
        self,
        parsed_data: Dict[str, Any],
        target_job_title: str,
        job_skills: Optional[List[str]] = None,
        job_requirements: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyzes the resume's skills against a target role.

        Two sources are possible, and which one was used is reported in
        `source` so the UI can say so rather than implying more rigour than
        there is:

        - "job": the caller named a real requisition, and `job_skills` holds
          that job's own required skills. The comparison is against what this
          employer actually asked for.
        - "market": only a free-text title was available, so the baseline comes
          from a pgvector lookup of similar jobs and, failing that, a static
          per-role skill list. That is an estimate about a job *like* this one,
          not about a specific opening.

        `job_requirements` is the requisition's qualifications prose. It informs
        the written commentary only; it does not move the numeric score, because
        turning prose into a comparable skill set would need an extraction step
        whose errors would be invisible inside a number.
        """
        source = "job" if job_skills else "market"
        logger.info(
            f"Analyzing alignment for target job: '{target_job_title}' (source={source})"
        )
        analysis_result = {
            "target_job_title": target_job_title,
            "source": source,
            "market_skills": [],
            "matching_skills": [],
            "missing_skills": [],
            "candidate_skills": [],
            "overlap_ratio": 0.0,
            "commentary": "Analysis could not be performed.",
        }

        try:
            # Helper to normalize skill strings for more robust matching
            def _norm(s: str) -> str:
                s = (s or "").strip().lower()
                # unify common separators and punctuation
                s = re.sub(r"[\./,+_]+", " ", s)
                s = re.sub(r"\s+", " ", s).strip()
                # simple canonicalizations that are broadly applicable (not job specific)
                replacements = {
                    "machine learning": "ml",
                    "deep learning": "dl",
                    "rest apis": "rest api",
                    "rest-api": "rest api",
                    "rest": "rest api",
                    "restful api": "rest api",
                    "restful apis": "rest api",
                    "ci cd": "ci/cd",
                    "springboot": "spring boot",
                    "js": "javascript",
                    "node js": "node.js",
                    "vue js": "vue js",
                    "react js": "react",
                    "typescript": "typescript",
                    "postgresql": "sql",
                    "postgres": "sql",
                    "my sql": "mysql",
                    "mysql": "sql",
                    # Add AI/ML specific normalizations
                    "artificial intelligence": "ai",
                    "machine learning": "ml",
                    "deep learning": "dl",
                    "neural networks": "neural network",
                    "natural language processing": "nlp",
                    "computer vision": "cv",
                    "data science": "data science",
                    "tensorflow": "tensorflow",
                    "pytorch": "pytorch",
                    "scikit-learn": "scikit learn",
                    "scikit learn": "scikit learn",
                    "pandas": "pandas",
                    "numpy": "numpy",
                    "matplotlib": "matplotlib",
                    "seaborn": "seaborn",
                    "jupyter": "jupyter",
                    "git": "git",
                    "github": "git",
                    "gitlab": "git",
                    "docker": "docker",
                    "kubernetes": "kubernetes",
                    "k8s": "kubernetes",
                    "aws": "aws",
                    "amazon web services": "aws",
                    "azure": "azure",
                    "google cloud": "gcp",
                    "gcp": "gcp",
                    "google cloud platform": "gcp",
                }
                return replacements.get(s, s)

            # Collect and normalize candidate skills
            candidate_skills_raw = []
            for skill in parsed_data.get('skills', []) or []:
                if isinstance(skill, dict) and skill.get('name'):
                    candidate_skills_raw.append(skill.get('name', ''))
                elif isinstance(skill, str):
                    candidate_skills_raw.append(skill)
            candidate_skills = {_norm(x) for x in candidate_skills_raw if x}
            
            if job_skills:
                # A real requisition was named. Its own skill list is the
                # baseline, full stop: no similarity search, no static fallback.
                # Substituting a guess here when a real answer exists is exactly
                # the failure this parameter was added to remove.
                market_skills_list = list(job_skills)
                logger.info(
                    f"Scoring against {len(market_skills_list)} skills from the '{target_job_title}' requisition"
                )
            else:
                # Get skills from comparable jobs with enhanced fallback
                market_skills_list = await self.job_service.get_skills_for_comparable_jobs(target_job_title)

                # Enhanced fallback for specialized roles like Gen AI Engineer
                if not market_skills_list or len(market_skills_list) < 5:
                    logger.info(f"Market skills list too small ({len(market_skills_list) if market_skills_list else 0}), using enhanced fallback for '{target_job_title}'")
                    market_skills_list = self._get_enhanced_fallback_skills(target_job_title)

            # Limit to top-N unique skills to avoid denominator inflation when aggregating many jobs
            market_skills_clean = []
            seen = set()
            for sk in market_skills_list:
                n = _norm(sk)
                if n and n not in seen:
                    market_skills_clean.append(n)
                    seen.add(n)
                if len(market_skills_clean) >= 30:
                    break
            market_skills = set(market_skills_clean)
            
            analysis_result["market_skills"] = sorted(list(market_skills))

            # Enhanced candidate skill expansion with better AI/ML detection
            if candidate_skills:
                expanded = set()
                # Split on common delimiters and connective words
                delimiters = r",|/|\\|\||;|\band\b|\bwith\b|\busing\b|\bsuch as\b|\bon\b|\bincluding\b|\bfor\b|\bto\b|\bexperience with\b|\bproficient in\b|\bhands[- ]on with\b"
                for phrase in list(candidate_skills):
                    parts = [p.strip() for p in re.split(delimiters, phrase) if p and p.strip()]
                    for p in parts:
                        # Direct exact match
                        if p in market_skills:
                            expanded.add(p)
                        # Any market skill as a whole word substring within the part
                        for mk in market_skills:
                            if re.search(r"(?<![a-z0-9])" + re.escape(mk) + r"(?![a-z0-9])", p):
                                expanded.add(mk)
                        # N-gram matching (1-4 grams) against market skills
                        tokens = [t for t in re.split(r"\s+", p) if t]
                        for n in range(1, 5):
                            for i in range(0, max(0, len(tokens)-n+1)):
                                gram = " ".join(tokens[i:i+n])
                                if gram in market_skills:
                                    expanded.add(gram)
                        # Fuzzy near-match (to catch small variants)
                        try:
                            close = difflib.get_close_matches(p, market_skills, n=1, cutoff=0.85)  # Lowered threshold for better matching
                            if close:
                                expanded.add(close[0])
                        except Exception:
                            pass
                if expanded:
                    logger.info(f"[JobFit] Expanded {len(candidate_skills)} candidate phrases to {len(expanded)} atomic skills via market vocabulary")
                    candidate_skills = expanded

            # Enhanced text-based skill inference with better AI/ML pattern recognition
            text_sources = []
            try:
                if isinstance(parsed_data.get('raw_text'), str):
                    text_sources.append(parsed_data['raw_text'])
            except Exception:
                pass
            for exp in parsed_data.get('experience', []) or []:
                if isinstance(exp, dict) and isinstance(exp.get('description'), str):
                    text_sources.append(exp['description'])
            # Fallback to the raw file content held by resume_service if available
            try:
                if hasattr(self.resume_service, 'file_content') and isinstance(self.resume_service.file_content, str):
                    text_sources.append(self.resume_service.file_content)
                elif hasattr(self.resume_service, 'last_file_content') and isinstance(self.resume_service.last_file_content, str):
                    text_sources.append(self.resume_service.last_file_content)
            except Exception:
                pass
            haystack = _norm(" ".join(text_sources))
            inferred = set()
            
            # Enhanced pattern matching for AI/ML skills
            for sk in market_skills:
                # Build robust variant patterns dynamically from the market skill text
                # - allow separators (space, hyphen, slash, underscore) between tokens
                # - allow optional plural 's' at the end (e.g., "rest apis")
                # - also check a contiguous no-space variant (e.g., "cicd")
                tokens = [t for t in re.split(r"[/\-\s_]+", sk) if t]
                if tokens:
                    sep = r"(?:[\s\-/_]+)"
                    joined = sep.join(map(re.escape, tokens)) + r"s?"
                    nospace = re.escape("".join(tokens)) + r"s?"
                    pattern_variants = [joined, nospace]
                else:
                    pattern_variants = [re.escape(sk) + r"s?"]

                matched = False
                for pv in pattern_variants:
                    pattern = r"(?<![a-z0-9])" + pv + r"(?![a-z0-9])"
                    if re.search(pattern, haystack):
                        matched = True
                        break
                if matched:
                    inferred.add(sk)
            
            # Additional AI/ML specific pattern matching
            ai_ml_patterns = {
                'ai': r'\b(?:ai|artificial intelligence|machine learning|deep learning|neural networks?)\b',
                'ml': r'\b(?:ml|machine learning|deep learning|neural networks?)\b',
                'python': r'\b(?:python|py)\b',
                'tensorflow': r'\b(?:tensorflow|tf)\b',
                'pytorch': r'\b(?:pytorch|torch)\b',
                'pandas': r'\b(?:pandas|pd)\b',
                'numpy': r'\b(?:numpy|np)\b',
                'git': r'\b(?:git|github|gitlab)\b',
                'docker': r'\b(?:docker|container)\b',
                'kubernetes': r'\b(?:kubernetes|k8s)\b',
                'aws': r'\b(?:aws|amazon web services)\b',
                'azure': r'\b(?:azure|microsoft cloud)\b',
                'gcp': r'\b(?:gcp|google cloud|google cloud platform)\b',
            }
            
            for skill_name, pattern in ai_ml_patterns.items():
                if skill_name in market_skills and re.search(pattern, haystack, re.IGNORECASE):
                    inferred.add(skill_name)
            
            if inferred:
                before = len(candidate_skills)
                candidate_skills = (candidate_skills or set()).union(inferred)
                after = len(candidate_skills)
                logger.info(f"[JobFit] Inferred {len(inferred)} additional skills from resume text; candidate set grew {before}->{after}")

            # Enhanced alias normalization with more AI/ML mappings
            try:
                market_set = set(market_skills)
                augmented = set(candidate_skills)

                for tok in list(candidate_skills):
                    t = tok.lower().strip()
                    # git* -> git
                    if 'git' in market_set and (t == 'github' or t == 'gitlab' or t == 'bitbucket' or 'github' in t or 'gitlab' in t or 'bitbucket' in t):
                        augmented.add('git')
                    # rest api variants -> rest api
                    if any(ms == 'rest api' for ms in market_set):
                        if re.search(r'\brest\s*ful\b', t) or re.search(r'\brest\b.*\bapi', t) or re.search(r'\bapis\b', t):
                            augmented.add('rest api')
                    # ci/cd variants -> ci/cd
                    if 'ci/cd' in market_set:
                        if re.search(r'\bci[\s\-/_]?cd\b', t) or re.search(r'\bcicd\b', t):
                            augmented.add('ci/cd')
                    # postgresql -> postgres
                    if 'postgres' in market_set and (t == 'postgresql' or 'postgresql' in t or t == 'postgres sql'):
                        augmented.add('postgres')
                    # sql family -> sql (generic)
                    if 'sql' in market_set:
                        if re.search(r'\bms\s*sql\s*server\b', t) or re.search(r'\bmssql\b', t) or re.search(r'\bsql\s*server\b', t):
                            augmented.add('sql')
                        if re.search(r'\bmysql\b', t):
                            augmented.add('sql')
                    # kubernetes shorthand -> kubernetes
                    if 'kubernetes' in market_set and (t == 'k8s' or re.search(r'\bk8s\b', t)):
                        augmented.add('kubernetes')
                    # AI/ML specific mappings
                    if 'ai' in market_set and (t == 'artificial intelligence' or 'machine learning' in t or 'deep learning' in t):
                        augmented.add('ai')
                    if 'ml' in market_set and (t == 'machine learning' or 'deep learning' in t):
                        augmented.add('ml')
                    if 'python' in market_set and (t == 'py' or 'python' in t):
                        augmented.add('python')
                    if 'tensorflow' in market_set and (t == 'tf' or 'tensorflow' in t):
                        augmented.add('tensorflow')
                    if 'pytorch' in market_set and (t == 'torch' or 'pytorch' in t):
                        augmented.add('pytorch')

                if len(augmented) > len(candidate_skills):
                    logger.info(f"[JobFit] Alias normalization added {len(augmented) - len(candidate_skills)} tokens via dynamic mapping to market skills")
                    candidate_skills = augmented
            except Exception:
                pass

            analysis_result["candidate_skills"] = sorted(list(candidate_skills))
            analysis_result["matching_skills"] = sorted(list(candidate_skills.intersection(market_skills)))
            analysis_result["missing_skills"] = sorted(list(market_skills.difference(candidate_skills)))
            
            # Enhanced overlap ratio calculation with weighted scoring
            union = market_skills.union(candidate_skills)
            basic_overlap = len(candidate_skills.intersection(market_skills)) / max(len(union), 1)
            
            # Apply role-specific weighting for specialized positions
            if _is_ai_role(target_job_title):
                # For AI roles, give more weight to core AI/ML skills
                core_ai_skills = {'ai', 'ml', 'python', 'tensorflow', 'pytorch', 'pandas', 'numpy', 'git', 'aws', 'azure', 'gcp'}
                core_matches = len(candidate_skills.intersection(market_skills).intersection(core_ai_skills))
                core_weight = min(0.3, core_matches * 0.1)  # Bonus for core skills
                weighted_overlap = basic_overlap + core_weight
                analysis_result["overlap_ratio"] = round(min(1.0, weighted_overlap), 4)
            else:
                analysis_result["overlap_ratio"] = round(basic_overlap, 4)

            # Enhanced LLM commentary with more specific guidance
            if source == "job":
                baseline_line = (
                    f"The resume was compared against an actual open requisition for "
                    f"'{target_job_title}' and the skills that role requires."
                )
                skills_label = "Skills required by this role"
            else:
                baseline_line = (
                    f"The resume was compared against the skills typically demanded "
                    f"in the market for the job title '{target_job_title}'. No specific "
                    f"requisition was provided."
                )
                skills_label = "Common market skills"

            requirements_block = ""
            if job_requirements:
                # Cap the prose: qualifications fields run long and the useful
                # signal is at the top.
                requirements_block = (
                    f"\n            Required qualifications for this role:\n"
                    f"            {job_requirements.strip()[:1200]}\n"
                )

            prompt = f"""
            {baseline_line}

            Candidate's Skills: {', '.join(sorted(list(candidate_skills)))}
            {skills_label}: {', '.join(analysis_result['market_skills'])}

            Matching Skills: {', '.join(analysis_result['matching_skills'])}
            Missing Skills: {', '.join(analysis_result['missing_skills'])}
            {requirements_block}
            Provide a brief, encouraging, and constructive analysis (2-3 sentences) for the candidate.
            Comment on their strengths (matching skills) and areas for potential growth (missing skills).
            For AI/ML roles, emphasize the importance of core skills like Python, ML frameworks, and cloud platforms.
            """
            
            commentary_msg = await self.llm_service.generate_text_async(prompt, max_tokens=150)
            analysis_result["commentary"] = commentary_msg.content if hasattr(commentary_msg, 'content') else str(commentary_msg)

        except Exception as e:
            logger.error(f"Failed to perform market alignment analysis: {e}")
        
        return analysis_result

    def _get_enhanced_fallback_skills(self, job_title: str) -> List[str]:
        """
        Enhanced fallback skill sets for specialized roles when market data is insufficient.
        """
        job_title_lower = job_title.lower()
        
        # Core AI/ML Engineer skills
        if 'gen ai' in job_title_lower or 'ai engineer' in job_title_lower or 'machine learning engineer' in job_title_lower:
            return [
                'python', 'machine learning', 'deep learning', 'neural networks', 'tensorflow', 'pytorch',
                'scikit-learn', 'pandas', 'numpy', 'matplotlib', 'seaborn', 'jupyter', 'git', 'github',
                'docker', 'kubernetes', 'aws', 'azure', 'gcp', 'sql', 'rest api', 'ci/cd', 'agile',
                'data analysis', 'data cleaning', 'data visualization', 'nlp', 'computer vision',
                'mlops', 'model deployment', 'api development', 'cloud computing', 'statistics',
                'linear algebra', 'calculus', 'probability', 'optimization', 'algorithms'
            ]
        
        # Software Engineer skills
        elif 'software engineer' in job_title_lower or 'developer' in job_title_lower:
            return [
                'python', 'java', 'javascript', 'typescript', 'react', 'angular', 'vue', 'node.js',
                'git', 'github', 'docker', 'kubernetes', 'aws', 'azure', 'gcp', 'sql', 'rest api',
                'ci/cd', 'agile', 'microservices', 'api development', 'cloud computing', 'linux',
                'html', 'css', 'bootstrap', 'tailwind', 'express', 'spring', 'django', 'flask',
                'postgresql', 'mysql', 'mongodb', 'redis', 'elasticsearch', 'kafka', 'rabbitmq'
            ]
        
        # Data Scientist skills
        elif 'data scientist' in job_title_lower or 'data analyst' in job_title_lower:
            return [
                'python', 'r', 'sql', 'pandas', 'numpy', 'matplotlib', 'seaborn', 'jupyter',
                'scikit-learn', 'tensorflow', 'pytorch', 'statistics', 'machine learning',
                'data analysis', 'data cleaning', 'data visualization', 'git', 'github',
                'aws', 'azure', 'gcp', 'tableau', 'power bi', 'excel', 'spark', 'hadoop',
                'probability', 'linear algebra', 'calculus', 'optimization', 'ab testing'
            ]
        
        # Default fallback
        else:
            return [
                'python', 'java', 'javascript', 'git', 'sql', 'aws', 'azure', 'gcp', 'docker',
                'kubernetes', 'rest api', 'ci/cd', 'agile', 'cloud computing', 'linux',
                'html', 'css', 'react', 'node.js', 'postgresql', 'mysql', 'mongodb'
            ]

    async def _generate_skill_suggestions(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates skill suggestions based on the candidate's experience and current skills.
        This is an agent mode enhancement that provides additional value.
        """
        logger.info("Generating skill suggestions based on experience...")
        
        suggestions = {
            "technical_skills": [],
            "soft_skills": [],
            "certifications": [],
            "recommendations": ""
        }
        
        try:
            # Extract current skills and experience for context
            current_skills = set()
            for skill in parsed_data.get('skills', []):
                if isinstance(skill, dict) and skill.get('name'):
                    current_skills.add(skill['name'].lower())
            
            # Extract industries and job titles from experience
            industries = set()
            job_titles = set()
            experience_text = ""
            
            for exp in parsed_data.get('experience', []):
                if isinstance(exp, dict):
                    if exp.get('company'):
                        industries.add(exp['company'].lower())
                    if exp.get('title'):
                        job_titles.add(exp['title'].lower())
                    if exp.get('description'):
                        experience_text += exp['description'] + "\n"
            
            # If we have sufficient experience data, use LLM to suggest skills
            if experience_text and len(job_titles) > 0:
                prompt = f"""Based on the candidate's experience and current skills, suggest additional skills and certifications that would enhance their profile:
                
Experience summary: {experience_text[:1000]}  # Limit text size

Current job titles: {', '.join(job_titles)}

Current skills: {', '.join(current_skills)}

Provide:
1. 5-7 technical skills that complement their profile
2. 3-5 soft skills that would enhance marketability
3. 2-3 relevant certifications worth pursuing
4. A brief recommendation paragraph

Format as JSON with keys: technical_skills, soft_skills, certifications, recommendations"""
                
                # Get suggestions from LLM with strict JSON instruction
                try:
                    system_msg = (
                        "You are a career advisor specializing in enhancing professional resumes. "
                        "Return ONLY a valid JSON object with keys: technical_skills (array), soft_skills (array), "
                        "certifications (array), recommendations (string). No code fences, no extra text."
                    )
                    content = await self.llm_service.generate_text(
                        prompt,
                        task_type="general",
                        max_tokens=800,
                        system_message=system_msg,
                    )
                    logger.debug(f"LLM response for skill suggestions: {content}")

                    # Robust JSON extraction (brace counting)
                    text = str(content or "").strip()
                    json_str = None
                    if "{" in text and "}" in text:
                        brace = 0
                        start = -1
                        for i, ch in enumerate(text):
                            if ch == '{':
                                if brace == 0:
                                    start = i
                                brace += 1
                            elif ch == '}':
                                brace -= 1
                                if brace == 0 and start != -1:
                                    json_str = text[start:i+1]
                                    break
                    if json_str is None:
                        # Handle common code-fence responses
                        if "```json" in text:
                            try:
                                json_str = text.split("```json",1)[1].split("```",1)[0].strip()
                            except Exception:
                                json_str = None

                    data = json.loads(json_str) if json_str else {}
                    # Update suggestions with parsed data
                    suggestions["technical_skills"] = data.get("technical_skills", [])
                    suggestions["soft_skills"] = data.get("soft_skills", [])
                    suggestions["certifications"] = data.get("certifications", [])
                    suggestions["recommendations"] = data.get("recommendations", ")")

                    # Ensure types
                    for key in ("technical_skills","soft_skills","certifications"):
                        if not isinstance(suggestions[key], list):
                            suggestions[key] = []
                    if not isinstance(suggestions["recommendations"], str):
                        suggestions["recommendations"] = ""

                    logger.info(
                        f"Generated {len(suggestions['technical_skills'])} technical, "
                        f"{len(suggestions['soft_skills'])} soft, {len(suggestions['certifications'])} certs."
                    )

                except Exception as e:
                    logger.error(f"Error generating/processing LLM skill suggestions, using fallback: {e}")
                    # Provide deterministic fallback suggestions based on job titles and current skills
                    inferred = []
                    for title in job_titles:
                        try:
                            inferred.extend(self._infer_skills_for_role(title))
                        except Exception:
                            pass
                    inferred = [s for s in inferred if s.lower() not in current_skills]
                    suggestions["technical_skills"] = list(dict.fromkeys(inferred))[:7]
                    suggestions["soft_skills"] = ["communication","teamwork","problem-solving","adaptability"]
                    suggestions["certifications"] = ["AWS Certified Cloud Practitioner","Scrum Master"]
                    suggestions["recommendations"] = (
                        "Focus on complementary tools and certifications aligned with your recent roles."
                    )
        except Exception as e:
            logger.error(f"Error in skill suggestion generation: {e}")
        
        return suggestions

    async def _validate_and_clean_data(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Performs basic data validation and cleaning on parsed resume data.
        Also enhances data with missing fields using regex extraction.
        """
        logger.info("Validating and cleaning parsed data...")
        if 'personal_info' in parsed_data and parsed_data['personal_info']:
            email = parsed_data['personal_info'].get('email')
            if email and not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                logger.warning(f"Invalid email format found: {email}. Clearing.")
                parsed_data['personal_info']['email'] = None

            phone = parsed_data['personal_info'].get('phone')
            if phone:
                # Basic cleaning for phone numbers
                cleaned_phone = re.sub(r'[^\d]', '', phone)
                if len(cleaned_phone) < 7:
                    logger.warning(f"Invalid phone number found: {phone}. Clearing.")
                    parsed_data['personal_info']['phone'] = None
                    
        # Extract missing fields from resume content
        parsed_data = await self._extract_missing_fields(parsed_data)
        
        return parsed_data
        
    async def _extract_missing_fields(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract missing fields from resume content using regex or other methods.
        Ensures feature parity between agent mode and basic mode.
        """
        # Get resume content from parsed data if available
        resume_content = parsed_data.get('raw_text', "")
        
        # If no raw_text, try to get from resume service attributes
        if not resume_content:
            if hasattr(self.resume_service, 'file_content'):
                resume_content = self.resume_service.file_content
            elif hasattr(self.resume_service, 'last_file_content'):
                resume_content = self.resume_service.last_file_content
            elif hasattr(self.resume_service, '_current_file_content'):
                resume_content = self.resume_service._current_file_content
            
        if not resume_content:
            logger.warning("No resume content available for missing field extraction")
            return parsed_data
            
        # Extract missing personal_info fields using direct regex patterns
        if 'personal_info' in parsed_data and parsed_data['personal_info']:
            # Address extraction
            address = parsed_data['personal_info'].get('address')
            if not address:
                try:
                    # Address patterns
                    address_patterns = [
                        r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Place|Pl|Way|Terrace|Ter)\b',
                        r'\b[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Place|Pl|Way|Terrace|Ter)\s+\d+\b',
                        r'\b\d+\s+[A-Za-z\s]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Place|Pl|Way|Terrace|Ter)\b'
                    ]
                    
                    for pattern in address_patterns:
                        address_matches = re.findall(pattern, resume_content, re.IGNORECASE)
                        if address_matches and address_matches[0]:
                            logger.info(f"Address found via regex: {address_matches[0]}")
                            parsed_data['personal_info']['address'] = address_matches[0].strip()
                            break
                except Exception as e:
                    logger.warning(f"Failed to extract address with regex: {e}")
                    
            # Extract website if missing
            website = parsed_data['personal_info'].get('website')
            if not website:
                try:
                    # More restrictive website patterns to avoid false positives
                    website_patterns = [
                        # Full URLs with protocol
                        r'\b(?:https?://)[a-zA-Z0-9-]+(?:\.[a-zA-Z]{2,})+(?:/[^\s]*)?\b',
                        # URLs with www prefix
                        r'\bwww\.[a-zA-Z0-9-]+(?:\.[a-zA-Z]{2,})+(?:/[^\s]*)?\b',
                        # Domain names that appear in common website contexts
                        r'\b(?:website|portfolio|site)[:\s]+(?:https?://)?(?:www\.)?([a-zA-Z0-9-]+(?:\.[a-zA-Z]{2,})+)(?:/[^\s]*)?\b',
                        # Standalone domains with clear TLDs that are commonly used for websites
                        r'\b[a-zA-Z0-9-]+\.(?:com|org|net|io|dev|me|co|tech|design|portfolio|works)\b(?:/[^\s]*)?'
                    ]
                    
                    for pattern in website_patterns:
                        website_matches = re.findall(pattern, resume_content, re.IGNORECASE)
                        if website_matches:
                            for match in website_matches:
                                candidate = match.strip() if isinstance(match, str) else match
                                
                                # Enhanced validation to prevent false positives
                                if self._is_valid_website(candidate, parsed_data):
                                    logger.info(f"Website found via regex: {candidate}")
                                    parsed_data['personal_info']['website'] = candidate
                                    break
                            if parsed_data['personal_info'].get('website'):
                                break
                except Exception as e:
                    logger.warning(f"Failed to extract website with regex: {e}")
                    
            # Extract github if missing
            github = parsed_data['personal_info'].get('github')
            if not github:
                try:
                    github_patterns = [
                        r'\b(?:https?://)?(?:www\.)?github\.com/[a-zA-Z0-9-]+\b',
                        r'\bgithub\.com/[a-zA-Z0-9-]+\b',
                        r'\bgithub\.com\s*/\s*[a-zA-Z0-9-]+\b'
                    ]
                    
                    for pattern in github_patterns:
                        github_matches = re.findall(pattern, resume_content, re.IGNORECASE)
                        if github_matches and github_matches[0]:
                            candidate = github_matches[0].strip()
                            # Ensure proper format
                            if not candidate.startswith('http'):
                                candidate = f"https://{candidate}"
                            logger.info(f"GitHub profile found via regex: {candidate}")
                            parsed_data['personal_info']['github'] = candidate
                            break
                except Exception as e:
                    logger.warning(f"Failed to extract GitHub with regex: {e}")
        
        return parsed_data

    async def _enrich_with_linkedin_profile(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Uses web search to find and add a LinkedIn profile URL.
        """
        logger.info("Attempting to enrich with LinkedIn profile...")
        personal_info = parsed_data.get('personal_info', {})
        name = personal_info.get('name')
        if not name:
            logger.warning("Cannot search for LinkedIn profile without a name.")
            return parsed_data

        # Construct a targeted search query
        query = f'"{name}" LinkedIn profile'
        if parsed_data.get('experience'):
            latest_exp = parsed_data['experience'][0]
            company = latest_exp.get('company')
            title = latest_exp.get('title')
            if company:
                query += f' "{company}"'
            if title:
                query += f' "{title}"'
        
        logger.info(f"Performing web search with query: {query}")
        try:
            search_results = await self.web_search_service.search(query)
            
            # Find the first result that is a valid LinkedIn profile URL
            for result in search_results:
                url = result.get('link')
                # Check if it looks like a LinkedIn URL
                if url and ('linkedin.com/in/' in url or 'linkedin.com/pub/' in url):
                    # Basic validation to avoid company pages or job postings
                    if '/jobs/' not in url:
                        logger.info(f"Found likely LinkedIn profile: {url}")
                        # If we found a profile URL, ensure it's formatted properly and add to personal_info
                        parsed_data['personal_info']['linkedin'] = url
                        break # Stop after finding the first likely match
            else:
                logger.info("No definitive LinkedIn profile found in search results.")

        except Exception as e:
            logger.error(f"Failed to perform web search for LinkedIn profile: {e}")
        
        return parsed_data

    async def parse_with_recovery(self, file_path: str) -> ResumeData:
        """
        Parses a resume with a fallback strategy.
        First attempts the comprehensive parsing, and if it fails with a
        ParsingError, it falls back to a section-by-section strategy.
        """
        try:
            logger.info("Attempting parsing with 'fast' strategy...")
            return await self.resume_service.parse_resume_file(file_path, strategy='fast')
        except ParsingError as e:
            logger.warning(f"Comprehensive parsing failed: {e}. Falling back to 'section_by_section' strategy.")
            try:
                return await self.resume_service.parse_resume_file(file_path, strategy='section_by_section')
            except ParsingError as final_e:
                logger.error(f"Fallback parsing strategy also failed: {final_e}")
                raise  # Re-raise the final exception
    
    def _is_valid_website(self, candidate: str, parsed_data: Dict[str, Any]) -> bool:
        """
        Enhanced validation for website candidates to prevent false positives.
        
        Args:
            candidate: The potential website URL/domain to validate
            parsed_data: The parsed resume data for additional context checks
            
        Returns:
            bool: True if the candidate is likely a valid website, False otherwise
        """
        if not candidate or len(candidate.strip()) < 4:
            return False
            
        candidate = candidate.strip().lower()
        
        # Get email information for comparison
        email = parsed_data.get('personal_info', {}).get('email', '')
        email_domain = ""
        if email and '@' in email:
            email_domain = email.split('@')[-1].lower()
        
        # Get name information for comparison
        name = parsed_data.get('personal_info', {}).get('name', '').lower()
        name_parts = name.split() if name else []
        
        # Exclude email domains and providers
        email_providers = {
            'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'icloud.com', 
            'aol.com', 'protonmail.com', 'mail.com', 'zoho.com', 'yandex.com', 
            'gmx.com', 'live.com', 'msn.com', 'comcast.net', 'verizon.net'
        }
        
        # Basic format checks
        if (
            '@' in candidate or  # Exclude email addresses
            candidate.startswith('mailto:') or  # Exclude mailto links
            candidate in email_providers or  # Exclude email providers
            candidate == email_domain or  # Exclude user's email domain
            'linkedin.com' in candidate or  # Exclude LinkedIn (handled separately)
            'github.com' in candidate  # Exclude GitHub (handled separately)
        ):
            return False
        
        # Check if candidate is just a name part without a proper domain
        # This prevents "jacob.smith" type false positives
        if '.' in candidate:
            parts = candidate.split('.')
            # If it's just two parts and both are likely name components
            if len(parts) == 2:
                first_part, second_part = parts[0], parts[1]
                
                # Check if this looks like firstname.lastname pattern
                if (
                    len(first_part) <= 15 and  # Reasonable name length
                    len(second_part) <= 15 and  # Reasonable name length
                    first_part.isalpha() and  # Only letters
                    second_part.isalpha() and  # Only letters
                    (first_part in name_parts or second_part in name_parts)  # Matches name parts
                ):
                    return False
                    
                # Check if second part is not a valid TLD or common website domain
                common_tlds = {
                    'com', 'org', 'net', 'io', 'dev', 'me', 'co', 'tech', 'design', 
                    'portfolio', 'works', 'site', 'app', 'web', 'online', 'xyz'
                }
                if second_part not in common_tlds:
                    return False
        
        # Must have at least one dot to be a valid domain
        if '.' not in candidate:
            return False
            
        # Additional validation: must look like a proper domain
        domain_pattern = r'^(?:https?://)?(?:www\.)?[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$'
        if not re.match(domain_pattern, candidate):
            return False
            
        return True

    async def _assess_resume_quality(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Uses the LLM to perform a structured quality assessment of the parsed resume data.
        Returns a dictionary with scores and feedback.
        """
        logger.info("Performing structured resume quality assessment...")
        
        assessment = {
            "clarity_score": 0,
            "impact_score": 0,
            "skills_relevance_score": 0,
            "overall_feedback": "Quality assessment could not be performed."
        }

        summary_parts = []
        if parsed_data.get('personal_info', {}).get('name'):
            summary_parts.append(f"Name: {parsed_data['personal_info']['name']}")
        
        experience_summary = []
        for exp in parsed_data.get('experience', []):
            experience_summary.append(f"- {exp.get('title')} at {exp.get('company')}: {(exp.get('description') or '')[:100]}...")
        if experience_summary:
            summary_parts.append("Experience:\n" + "\n".join(experience_summary))

        skills_summary = ", ".join([skill.get('name') for skill in parsed_data.get('skills', [])[:15] if skill.get('name')])
        if skills_summary:
            summary_parts.append(f"Skills: {skills_summary}")

        prompt = f"""
        Act as a senior recruiter. Analyze the following resume summary and provide a structured quality assessment.
        Return a JSON object with three scores (clarity_score, impact_score, skills_relevance_score) from 1-10 and a concise overall_feedback string (2 sentences max).

        - clarity_score: How clear and easy to understand is the experience? (1=vague, 10=crystal clear).
        - impact_score: Does the candidate demonstrate quantifiable results and achievements? (1=no impact shown, 10=strong, quantified impact).
        - skills_relevance_score: How relevant and modern are the listed skills? (1=irrelevant/outdated, 10=highly relevant and modern).
        - overall_feedback: A summary of the resume's strengths and areas for improvement.

        Resume Summary:
        ---
        {chr(10).join(summary_parts)}
        ---

        Return ONLY the JSON object.
        """
        
        try:
            response_msg = await self.llm_service.generate_text_async(prompt, max_tokens=250)
            response_text = response_msg.content if hasattr(response_msg, 'content') else str(response_msg)
            
            # Extract JSON from the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                assessment = json.loads(json_match.group(0))
            else:
                logger.warning("Could not parse JSON from quality assessment response.")

        except Exception as e:
            logger.error(f"Failed to assess resume quality: {e}")
        
        return assessment

    async def process_resume(self, file: UploadFile, db=None, save_to_db: bool = False, candidate_id: Optional[str] = None,
                             target_job_title: Optional[str] = None, job_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a single resume file, adapting to the interface expected by the resume router.

        Args:
            file: The uploaded resume file
            db: Database session
            save_to_db: Whether to save the resume to the database
            candidate_id: Optional candidate ID for association
            target_job_title: Optional job title to score market/job fit against
            job_data: Optional full job object. Supplies the title when none is
                given, and when it carries the job's own `skills` the fit is
                scored against that requisition instead of the market average.

        Returns:
            A dictionary with parsing results and metadata
        """
        # Derive a title from job_data when none was provided explicitly
        if (not target_job_title or not str(target_job_title).strip()) and isinstance(job_data, dict):
            for key in ("title", "job_title", "name", "role"):
                value = job_data.get(key)
                if isinstance(value, str) and value.strip():
                    target_job_title = value.strip()
                    logger.info(f"Derived target_job_title from job_data['{key}']: {target_job_title}")
                    break

        job_skills = _job_skills_from(job_data)
        job_requirements = None
        if isinstance(job_data, dict):
            raw = job_data.get("required_qualifications") or job_data.get("requirements")
            if isinstance(raw, str) and raw.strip():
                job_requirements = raw.strip()

        logger.info(
            f"Processing resume: {file.filename}, save_to_db={save_to_db}, candidate_id={candidate_id}, "
            f"target_job_title={target_job_title}, job_skills={len(job_skills) if job_skills else 0}"
        )

        # Process the single file with our internal method
        result = await self._process_single_file(
            file,
            target_job_title=target_job_title,
            job_skills=job_skills,
            job_requirements=job_requirements,
        )
        
        # Format the result to match the expected structure in the router
        # Ensure parsed_data is available in the response
        if "data" in result and "parsed_data" not in result:
            result["parsed_data"] = result["data"]
            
        return result

    async def execute(self, task: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Executes the resume processing task.
        This involves saving the uploaded file temporarily and passing its path
        to the resume parsing service.
        """
        logger.info("ResumeProcessingAgent executing task...")
        files: List[UploadFile] = task.get("files")
        # Support both top-level and nested under 'details' (as provided by router)
        details = task.get("details", {}) if isinstance(task.get("details"), dict) else {}
        target_job_title = task.get("target_job_title") or details.get("target_job_title")  # Extract optional job title
        job_data = task.get("job_data") or details.get("job_data")  # Full job object if provided

        # If target_job_title is missing/blank, try deriving it from job_data dynamically
        if (not target_job_title or not str(target_job_title).strip()) and isinstance(job_data, dict):
            # Prefer standard title field; fallback to name or role-like keys
            for key in ("title", "job_title", "name", "role"):
                value = job_data.get(key)
                if isinstance(value, str) and value.strip():
                    target_job_title = value.strip()
                    logger.info(f"Derived target_job_title from job_data['{key}']: {target_job_title}")
                    break

        if not files:
            logger.warning("Agent received no files in the task list.")
            return {"error": "No files were found in the agent's task list."}
        
        # Create a list of processing tasks to run in parallel
        processing_tasks = [self._process_single_file(file, target_job_title) for file in files]
        
        # Run all processing tasks concurrently
        results = await asyncio.gather(*processing_tasks, return_exceptions=True)
        
        # Process results, separating success from failures
        successful_processes = []
        failed_processes = []
        for res in results:
            if isinstance(res, Exception):
                # This handles exceptions that might have been raised outside the try/except in _process_single_file
                failed_processes.append({"status": "error", "filename": "unknown", "message": str(res)})
            elif res.get("status") == "success":
                successful_processes.append(res)
            else:
                failed_processes.append(res)

        # The frontend expects a simplified response for single-file uploads.
        # We will return the details of the first successful process directly.
        if successful_processes:
            # Return the result of the first successful file processing
            return successful_processes[0]
        elif failed_processes:
            # If all processes failed, return the first failure details
            return failed_processes[0]
        else:
            # Fallback in case no files were processed
            return {"status": "error", "message": "No files were processed by the agent."}