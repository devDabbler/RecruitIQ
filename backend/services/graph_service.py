import os
import json
import logging
from typing import Dict, List, Optional, Union, Any
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
import numpy as np

from backend.utils.config import Settings

logger = logging.getLogger(__name__)

class GraphService:
    """Service for interacting with Neo4j graph database.
    
    This service handles storing and retrieving embeddings for resumes and jobs,
    as well as performing semantic matching between candidates and job postings.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize the Neo4j graph service.
        
        Args:
            settings: Application settings. If not provided, will be loaded from environment.
        """
        if settings is None:
            settings = Settings()
            
        self.uri = settings.neo4j_uri
        self.user = settings.neo4j_user
        self.password = settings.neo4j_password
        self.database = os.getenv("NEO4J_DATABASE", "neo4j")
        
        try:
            # Configure the driver with proper connection settings
            self.driver = GraphDatabase.driver(
                self.uri, 
                auth=(self.user, self.password),
                # Add connection configuration to improve reliability
                max_connection_lifetime=300,  # 5 minutes
                max_connection_pool_size=50,
                connection_acquisition_timeout=60
            )
            
            # First, check database availability using the system database
            try:
                with self.driver.session(database="system") as session:
                    # Check if the database exists and is available
                    result = session.run("SHOW DATABASES")
                    databases = {record["name"]: record["currentStatus"] for record in result}
                    
                    if self.database in databases:
                        status = databases[self.database]
                        logger.info(f"Database '{self.database}' exists with status: {status}")
                        
                        # If database is offline, try to start it
                        if status.lower() != "online":
                            logger.info(f"Database '{self.database}' is not online. Attempting to start it.")
                            session.run(f"START DATABASE {self.database}")
                            logger.info(f"Started database '{self.database}'")
                    else:
                        logger.warning(f"Database '{self.database}' not found in Neo4j instance")
                        # We won't create it automatically as it should already exist
            except Exception as system_error:
                logger.warning(f"Could not check database status: {str(system_error)}")
            
            # Now try to connect to the specified database
            try:
                with self.driver.session(database=self.database) as session:
                    result = session.run("RETURN 1 as test")
                    result.single()
                    
                    # Ensure indexes exist
                    self._ensure_schema(session)
                    
                    logger.info(f"Successfully connected to Neo4j at {self.uri} using database '{self.database}'")
                    
                    # Check if GDS is available
                    has_gds = self.check_gds_availability()
                    logger.info(f"Neo4j Graph Data Science library available: {has_gds}")
                    
            except Exception as e:
                logger.error(f"Error verifying Neo4j database '{self.database}': {e}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {str(e)}")
            # Initialize driver as None but don't raise exception to allow app to start
            self.driver = None
            
            # Provide helpful guidance for common connection issues
            if "Couldn't connect to" in str(e) or "Connection refused" in str(e):
                logger.warning("""
Neo4j database connection failed. This is likely because:
1. Neo4j is not running - start it with: neo4j start
2. Neo4j is running on a different port - check your NEO4J_URI setting
3. Neo4j credentials are incorrect - check NEO4J_USER and NEO4J_PASSWORD

The application will continue to run, but candidate search and matching features may not work properly.
                """)
            elif "Authentication failed" in str(e):
                logger.warning("""
Neo4j authentication failed. Please check:
1. NEO4J_USER and NEO4J_PASSWORD environment variables
2. Neo4j user credentials in the database
                """)

    def _ensure_schema(self, session):
        """Ensure all necessary constraints and indexes are created in the database."""
        logger.info("Ensuring database schema (constraints and indexes)...")
        
        # Constraints for uniqueness and faster lookups
        session.run("CREATE CONSTRAINT candidate_id IF NOT EXISTS FOR (c:Candidate) REQUIRE c.id IS UNIQUE")
        session.run("CREATE CONSTRAINT resume_id IF NOT EXISTS FOR (r:Resume) REQUIRE r.id IS UNIQUE")
        session.run("CREATE CONSTRAINT job_id IF NOT EXISTS FOR (j:Job) REQUIRE j.id IS UNIQUE")
        session.run("CREATE CONSTRAINT skill_name IF NOT EXISTS FOR (s:Skill) REQUIRE s.name IS UNIQUE")
        
        # Vector index for job description embeddings
        try:
            # Check if the index already exists
            result = session.run("SHOW INDEXES YIELD name WHERE name = 'job_description_embedding'")
            if result.peek() is None:
                logger.info("Vector index 'job_description_embedding' not found. Creating it now...")
                session.run("""
                CREATE VECTOR INDEX job_description_embedding IF NOT EXISTS
                FOR (j:Job)
                ON (j.description_embedding)
                OPTIONS { indexConfig: {
                    `vector.dimensions`: 384,
                    `vector.similarity_function`: 'cosine'
                }}
                """)
                logger.info("Successfully created vector index 'job_description_embedding'.")
            else:
                logger.info("Vector index 'job_description_embedding' already exists.")
        except Exception as e:
            # Handle cases where vector indexes might not be supported (e.g., older Neo4j versions)
            if "Unknown command" in str(e) or "invalid syntax" in str(e):
                logger.warning("Could not create vector index. This might be because your Neo4j version doesn't support it. Matching will rely on other methods.")
            else:
                logger.error(f"Failed to create or verify vector index: {e}")
        
        logger.info("Schema setup complete.")
    
    def close(self):
        """Close the Neo4j driver connection."""
        if self.driver is not None:
            self.driver.close()
            
    def get_job_by_id(self, job_id: int) -> Dict[str, Any]:
        """Retrieve a job and its skills from Neo4j by ID.
        
        Args:
            job_id: The database ID of the job
            
        Returns:
            Dictionary containing job information with skills list
        """
        if self.driver is None:
            logger.warning("Neo4j driver not initialized. Cannot retrieve job.")
            return {}
        
        try:
            with self.driver.session(database=self.database) as session:
                # Query job node and related skills
                result = session.run(
                    """
                    MATCH (j:Job {id: $job_id})
                    OPTIONAL MATCH (j)-[:HAS_SKILL]->(s:Skill)
                    RETURN j as job, collect(s.name) as skills
                    """,
                    job_id=job_id
                )
                
                record = result.single()
                if not record:
                    logger.warning(f"Job with ID {job_id} not found in Neo4j")
                    return {}
                    
                # Convert Neo4j node to dictionary
                job_data = dict(record["job"])
                skills = record["skills"]
                
                # Remove None values from skills list
                skills = [skill for skill in skills if skill is not None]
                
                # Add skills to job data
                job_data["skills"] = skills
                
                return job_data
                
        except Exception as e:
            logger.error(f"Error retrieving job from Neo4j: {str(e)}")
            return {}
    
    def store_candidate_with_resume(self, candidate_id: int, candidate_data: Dict, 
                                  resume_id: int, resume_data: Dict, 
                                  embeddings: Dict[str, List[float]]):
        """Store a candidate and their resume in Neo4j with embeddings.
        
        Args:
            candidate_id: The database ID of the candidate
            candidate_data: Dictionary containing candidate information
            resume_id: The database ID of the resume
            resume_data: Dictionary containing resume information
            embeddings: Dictionary of embeddings for different resume components
        """
        if self.driver is None:
            logger.warning("Neo4j driver not initialized. Skipping graph storage.")
            return
        
        try:
            with self.driver.session(database=self.database) as session:
                # Create or update the candidate node
                session.run(
                    """
                    MERGE (c:Candidate {id: $candidate_id})
                    SET c.name = $name,
                        c.email = $email,
                        c.phone = $phone,
                        c.location = $location,
                        c.created_at = CASE
                            WHEN c.created_at IS NULL THEN datetime()
                            ELSE c.created_at
                        END,
                        c.updated_at = datetime()
                    """,
                    candidate_id=candidate_id,
                    name=f"{candidate_data.get('first_name', '')} {candidate_data.get('last_name', '')}".strip(),
                    email=candidate_data.get('email', ''),
                    phone=candidate_data.get('phone', ''),
                    location=candidate_data.get('location', '')
                )
                
                # Create or update the resume node with embeddings
                session.run(
                    """
                    MERGE (r:Resume {id: $resume_id})
                    SET r.file_name = $file_name,
                        r.content_type = $content_type,
                        r.profile_embedding = $profile_embedding,
                        r.skills_embedding = $skills_embedding,
                        r.parser_version = $parser_version,
                        r.validation_status = $validation_status,
                        r.validation_score = $validation_score,
                        r.created_at = CASE
                            WHEN r.created_at IS NULL THEN datetime()
                            ELSE r.created_at
                        END,
                        r.updated_at = datetime()
                    """,
                    resume_id=resume_id,
                    file_name=resume_data.get('file_name', ''),
                    content_type=resume_data.get('content_type', ''),
                    profile_embedding=embeddings.get('profile', []),
                    skills_embedding=embeddings.get('skills', [])
                )
                
                # Create relationship between candidate and resume
                session.run(
                    """
                    MATCH (c:Candidate {id: $candidate_id})
                    MATCH (r:Resume {id: $resume_id})
                    MERGE (c)-[:HAS_RESUME]->(r)
                    """,
                    candidate_id=candidate_id,
                    resume_id=resume_id
                )
                
                # Create skill nodes and relationships
                if 'skills' in resume_data and resume_data['skills']:
                    for skill in resume_data['skills']:
                        skill_name = skill['name'] if isinstance(skill, dict) else skill
                session.run(
                    """
                    MERGE (s:Skill {name: $skill_name})
                    SET s.created_at = CASE
                        WHEN s.created_at IS NULL THEN datetime()
                        ELSE s.created_at
                    END,
                    s.updated_at = datetime()
                    WITH s
                    MATCH (r:Resume {id: $resume_id})
                    MERGE (r)-[:HAS_SKILL]->(s)
                            """,
                            skill_name=skill_name,
                            resume_id=resume_id
                        )
                
                logger.info(f"Successfully stored candidate {candidate_id} and resume {resume_id} in Neo4j")
                
        except Exception as e:
            logger.error(f"Error storing candidate and resume in Neo4j: {str(e)}")
    
    def store_job(self, job_id: int, job_data: Dict, embeddings: Dict[str, List[float]]):
        """Store a job posting in Neo4j with embeddings.
        
        Args:
            job_id: The database ID of the job
            job_data: Dictionary containing job information
            embeddings: Dictionary of embeddings for different job components
        """
        if self.driver is None:
            logger.warning("Neo4j driver not initialized. Skipping graph storage.")
            return
        
        try:
            with self.driver.session(database=self.database) as session:
                # Create or update the job node with embeddings
                session.run(
                    """
                    MERGE (j:Job {id: $job_id})
                    SET j.title = $title,
                        j.department = $department,
                        j.job_overview = $job_overview,
                        j.required_qualifications = $required_qualifications,
                        j.location = $location,
                        j.job_type = $job_type,
                        j.experience_level = $experience_level,
                        j.status = $status,
                        j.description_embedding = $description_embedding,
                        j.requirements_embedding = $requirements_embedding,
                        j.skills_embedding = $skills_embedding,
                        j.updated_at = datetime()
                    """,
                    job_id=job_id,
                    title=job_data.get('title', ''),
                    department=job_data.get('department', ''),
                    job_overview=job_data.get('job_overview', ''),
                    required_qualifications=job_data.get('required_qualifications', ''),
                    location=job_data.get('location', ''),
                    job_type=job_data.get('job_type', ''),
                    experience_level=job_data.get('experience_level', ''),
                    status=job_data.get('status', ''),
                    description_embedding=embeddings.get('description', []),
                    requirements_embedding=embeddings.get('requirements', []),
                    skills_embedding=embeddings.get('skills', [])
                )
                
                # Create skill nodes and relationships
                if 'skills' in job_data and job_data['skills']:
                    skills = job_data['skills']
                    if isinstance(skills, list):
                        for skill in skills:
                            skill_name = skill['name'] if isinstance(skill, dict) else skill
                            session.run(
                                """
                                MERGE (s:Skill {name: $skill_name})
                                WITH s
                                MATCH (j:Job {id: $job_id})
                                MERGE (j)-[:REQUIRES]->(s)
                                """,
                                skill_name=skill_name,
                                job_id=job_id
                            )
                
                logger.info(f"Successfully stored job {job_id} in Neo4j")
                
        except Exception as e:
            logger.error(f"Error storing job in Neo4j: {str(e)}")
    
    def find_matching_candidates(self, job_id: int, limit: int = 10) -> List[Dict]:
        """Find candidates that match a job posting using skills and relationships.
        
        Args:
            job_id: The database ID of the job
            limit: Maximum number of candidates to return
            
        Returns:
            List of matching candidates with similarity scores
        """
        if self.driver is None:
            logger.warning("Neo4j driver not initialized. Cannot find matching candidates.")
            return []
        
        try:
            with self.driver.session(database=self.database) as session:
                # Use skill-based matching instead of vector matching
                # This is more reliable and doesn't require vector indexes
                candidates = []
                
                # First try to get job skills
                job_result = session.run(
                    """
                    MATCH (j:Job {id: $job_id})-[:REQUIRES]->(s:Skill)
                    RETURN j.title as job_title, collect(s.name) as required_skills
                    """,
                    job_id=job_id
                )
                
                job_record = job_result.single()
                if job_record:
                    job_title = job_record.get("job_title", "")
                    required_skills = job_record.get("required_skills", [])
                    logger.info(f"Job {job_id} ('{job_title}') requires skills: {required_skills}")
                    
                    # Find candidates with matching skills
                    if required_skills:
                        logger.info(f"Searching for candidates matching required skills: {required_skills}")
                        skill_result = session.run(
                            """
                            MATCH (c:Candidate)-[:HAS_RESUME]->(r)-[:HAS_SKILL]->(s:Skill)
                            WHERE s.name IN $skills
                            WITH c, r, collect(DISTINCT s.name) as matching_skills, count(DISTINCT s) as skill_matches, $total_skills as total_required
                            RETURN 
                                c.id as candidate_id, 
                                c.name as candidate_name, 
                                c.email as candidate_email,
                                r.id as resume_id, 
                                toFloat(skill_matches) / total_required as match_score,
                                matching_skills
                            ORDER BY match_score DESC
                            LIMIT $limit
                            """,
                            skills=required_skills,
                            total_skills=len(required_skills),
                            limit=limit
                        )
                        
                        for record in skill_result:
                            match_score = record.get("match_score", 0) * 100  # Convert to percentage
                            matching_skills = record.get("matching_skills", [])
                            logger.info(f"Candidate {record.get('candidate_id')} matched skills: {matching_skills}, score: {match_score}")
                            
                            # Only include candidates with meaningful match scores
                            if match_score >= 30:
                                candidates.append({
                                    "id": record.get("candidate_id"),
                                    "name": record.get("candidate_name"),
                                    "email": record.get("candidate_email"),
                                    "resume_id": record.get("resume_id"),
                                    "match_score": match_score,
                                    "match_explanation": f"Matched {len(matching_skills)} of {len(required_skills)} required skills for {job_title}"
                                })
                    else:
                        logger.info(f"No required skills found for job {job_id}.")
                else:
                    logger.info(f"No job record found in Neo4j for job_id={job_id}.")
                
                # If we didn't find matches with skills, try to get all candidates as a fallback
                if not candidates:
                    logger.info(f"No strong skill matches found for job {job_id}. Returning fallback candidates.")
                    all_result = session.run(
                        """
                        MATCH (c:Candidate)
                        OPTIONAL MATCH (c)-[:HAS_RESUME]->(r)
                        WITH c, r
                        RETURN 
                            c.id as candidate_id, 
                            c.name as candidate_name, 
                            c.email as candidate_email,
                            r.id as resume_id
                        LIMIT $limit
                        """,
                        limit=limit
                    )
                    
                    for record in all_result:
                        logger.info(f"Fallback candidate: {record.get('candidate_id')} ({record.get('candidate_name')})")
                        candidates.append({
                            "id": record.get("candidate_id"),
                            "name": record.get("candidate_name"),
                            "email": record.get("candidate_email"),
                            "resume_id": record.get("resume_id"),
                            "match_score": 30.0,  # Minimum score
                            "match_explanation": "Basic candidate match"
                        })
                
                logger.info(f"Returning {len(candidates)} candidates for job {job_id}")
                return candidates
                
        except Exception as e:
            logger.error(f"Error finding matching candidates in Neo4j: {str(e)}")
            return []
    
    async def get_candidates_matching_job(self, job_id: int, limit: int = 10) -> List[Dict]:
        """Find candidates that match a job posting using vector similarity and skill relationships.
        
        This is an async wrapper around find_matching_candidates for use in async contexts.
        It explicitly handles the case where REQUIRES relationships don't exist yet.
        
        Args:
            job_id: The database ID of the job
            limit: Maximum number of candidates to return
            
        Returns:
            List of matching candidates with similarity scores
        """
        if self.driver is None:
            logger.warning("Neo4j driver not initialized. Cannot find matching candidates.")
            return []
        
        try:
            # First try to get basic job information to validate it exists
            with self.driver.session(database=self.database) as session:
                job_result = session.run(
                    """
                    MATCH (j:Job {id: $job_id})
                    RETURN j.title as job_title
                    """,
                    job_id=job_id
                )
                
                job_record = job_result.single()
                if not job_record:
                    logger.warning(f"Job with ID {job_id} not found in Neo4j")
                    return []

                # Now check if REQUIRES relationships exist
                relationship_result = session.run(
                    """
                    MATCH (j:Job {id: $job_id})-[:REQUIRES]->(s:Skill)
                    RETURN count(s) as skill_count
                    """,
                    job_id=job_id
                )
                
                relationship_record = relationship_result.single()
                skill_count = relationship_record.get("skill_count", 0) if relationship_record else 0
                
                if skill_count == 0:
                    # No REQUIRES relationships exist for this job
                    # This is the specific case we want to detect and handle
                    logger.warning(f"No REQUIRES relationships found for job {job_id}. This is expected if job-skill relationships haven't been established yet.")
                    
                    # Instead of raising an error, get basic candidate information
                    all_result = session.run(
                        """
                        MATCH (c:Candidate)
                        OPTIONAL MATCH (c)-[:HAS_RESUME]->(r)
                        RETURN 
                            c.id as candidate_id, 
                            c.name as candidate_name, 
                            c.email as candidate_email,
                            r.id as resume_id
                        LIMIT $limit
                        """,
                        limit=limit
                    )
                    
                    candidates = []
                    for record in all_result:
                        candidates.append({
                            "candidate_id": record.get("candidate_id"),
                            "name": record.get("candidate_name"),
                            "email": record.get("candidate_email"),
                            "resume_id": record.get("resume_id"),
                            "score": 0.35  # Default score (35%) - slightly higher than threshold to avoid precision issues
                        })
                    
                    return candidates
                else:
                    # REQUIRES relationships exist, proceed with normal matching
                    # Use asyncio.to_thread to run the synchronous method in a separate thread
                    import asyncio
                    candidates = await asyncio.to_thread(self.find_matching_candidates, job_id, limit)
                    
                    # Format for consistency with the RAG service expectations
                    return [{
                        "candidate_id": c.get("id"),
                        "name": c.get("name"),
                        "email": c.get("email"),
                        "resume_id": c.get("resume_id"),
                        "score": c.get("match_score") / 100 if c.get("match_score") else 0.35  # Using 35% to avoid precision issues
                    } for c in candidates]
            
        except Exception as e:
            if "REQUIRES" in str(e):
                # This explicitly handles the case where the 'REQUIRES' relationship doesn't exist
                logger.warning(f"REQUIRES relationship issue in Neo4j for job {job_id}: {str(e)}")
                raise Exception(f"Missing REQUIRES relationships for job {job_id}. Neo4j error: {str(e)}")
            else:
                logger.error(f"Error in get_candidates_matching_job: {str(e)}")
                raise
    
    def _ensure_schema(self, session):
        """Ensure that all required indexes and constraints exist."""
        try:
            # First get all existing indexes
            result = session.run("SHOW INDEXES")
            existing_indexes = [record.get('name') for record in result]
            
            # Create timestamp indexes if they don't exist
            if 'idx_candidate_created_at' not in existing_indexes:
                session.run("CREATE INDEX idx_candidate_created_at FOR (c:Candidate) ON (c.created_at)")
                logger.info("Created index for Candidate created_at")
                
            if 'idx_resume_created_at' not in existing_indexes:
                session.run("CREATE INDEX idx_resume_created_at FOR (r:Resume) ON (r.created_at)")
                logger.info("Created index for Resume created_at")
                
            if 'idx_skill_created_at' not in existing_indexes:
                session.run("CREATE INDEX idx_skill_created_at FOR (s:Skill) ON (s.created_at)")
                logger.info("Created index for Skill created_at")
            
            # Create vector indexes only if they don't exist
            try:
                if 'resume_profile_embedding' not in existing_indexes:
                    session.run(
                        """
                        CALL db.index.vector.createNodeIndex(
                            'resume_profile_embedding',
                            'Resume',
                            'profile_embedding',
                            384,
                            'cosine'
                        )
                        """
                    )
                    logger.info("Created vector index for resume profile embeddings")
            except Exception as e:
                if "AlreadyIndexedException" not in str(e):
                    logger.warning(f"Error creating resume profile embedding index: {str(e)}")
            
            try:
                if 'job_description_embedding' not in existing_indexes:
                    session.run(
                        """
                        CALL db.index.vector.createNodeIndex(
                            'job_description_embedding',
                            'Job',
                            'description_embedding',
                            384,
                            'cosine'
                        )
                        """
                    )
                    logger.info("Created vector index for job description embeddings")
            except Exception as e:
                if "AlreadyIndexedException" not in str(e):
                    logger.warning(f"Error creating job description embedding index: {str(e)}")
                
            try:
                if 'job_requirements_embedding' not in existing_indexes:
                    session.run(
                        """
                        CALL db.index.vector.createNodeIndex(
                            'job_requirements_embedding',
                            'Job',
                            'requirements_embedding',
                            384,
                            'cosine'
                        )
                        """
                    )
                    logger.info("Created vector index for job requirements embeddings")
            except Exception as e:
                if "AlreadyIndexedException" not in str(e):
                    logger.warning(f"Error creating job requirements embedding index: {str(e)}")
                
            try:
                if 'job_skills_embedding' not in existing_indexes:
                    session.run(
                        """
                        CALL db.index.vector.createNodeIndex(
                            'job_skills_embedding',
                            'Job',
                            'skills_embedding',
                            384,
                            'cosine'
                        )
                        """
                    )
                    logger.info("Created vector index for job skills embeddings")
            except Exception as e:
                if "AlreadyIndexedException" not in str(e):
                    logger.warning(f"Error creating job skills embedding index: {str(e)}")
                
        except Exception as e:
            logger.warning(f"Error ensuring vector indexes: {str(e)}")
            
    async def get_candidates_matching_job(self, job_id: int, limit: int = 10) -> List[Dict]:
        """Find candidates that match a specific job based on profile similarity.
        
        This is an alias for find_matching_candidates for backward compatibility.
        
        Args:
            job_id: The database ID of the job
            limit: Maximum number of candidates to return
            
        Returns:
            List of matching candidates with similarity scores
        """
        return self.find_matching_candidates(job_id, limit)



    def find_similar_jobs(self, title_embedding, limit=10):
        """Find jobs similar to a given title embedding.

        Args:
            title_embedding: The embedding vector for the target job title.
            limit: The maximum number of similar jobs to return.

        Returns:
            A list of job dictionaries, each including a list of skills.
        """
        if self.driver is None:
            logger.warning("Neo4j driver not initialized. Cannot find similar jobs.")
            return []

        try:
            with self.driver.session(database=self.database) as session:
                # Check how many jobs we have in the database first
                try:
                    job_count = session.run("MATCH (j:Job) RETURN count(j) as count").single()["count"]
                    logger.info(f"Total job count in Neo4j: {job_count}")
                    
                    # Check how many have embeddings
                    jobs_with_embeddings = session.run(
                        "MATCH (j:Job) WHERE j.description_embedding IS NOT NULL RETURN count(j) as count"
                    ).single()["count"]
                    logger.info(f"Jobs with description embeddings: {jobs_with_embeddings}")
                except Exception as count_err:
                    logger.error(f"Error checking job counts: {count_err}")
                
                # Verify that the vector index exists
                index_exists = False
                try:
                    index_result = session.run("SHOW INDEXES WHERE name = 'job_description_embedding'")
                    indexes = list(index_result)
                    index_exists = len(indexes) > 0
                    if index_exists:
                        logger.info(f"Vector index exists: {indexes}")
                    else:
                        logger.error("Vector index 'job_description_embedding' does not exist!")
                except Exception as idx_err:
                    logger.error(f"Error checking vector index existence: {idx_err}")
                    index_exists = False
                
                # Use REQUIRES relationship instead of HAS_SKILL for consistency with the rest of the code
                # This matches the relationship type used in the store_job method
                logger.info("Executing vector search query for similar jobs...")
                try:
                    # First try to get jobs regardless of vector search to see what's available
                    sample_jobs = session.run(
                        """
                        MATCH (j:Job) 
                        WHERE j.status = 'open' OR j.status = 'active'
                        RETURN j.id, j.title, j.status 
                        LIMIT 5
                        """
                    )
                    sample_jobs_list = list(sample_jobs)
                    logger.info(f"Sample jobs in database: {sample_jobs_list}")
                    
                    # If vector index does not exist, skip vector query and use fallback immediately
                    if not index_exists:
                        logger.info("Skipping vector query because index is missing. Using fallback query.")
                        fallback_result = session.run(
                            """
                            MATCH (j:Job)
                            WHERE j.status = 'open' OR j.status = 'active'
                            OPTIONAL MATCH (j)-[:REQUIRES]->(s:Skill)
                            RETURN j.id AS id, j.title AS title, j.department AS department,
                                   collect(DISTINCT s.name) AS skills, 0.5 AS similarity_score
                            LIMIT $limit
                            """,
                            limit=limit
                        )
                        jobs = [dict(record) for record in fallback_result]
                        logger.info(f"Fallback (no index) found {len(jobs)} jobs")
                        for job in jobs:
                            if 'skills' in job:
                                job['skills'] = [skill for skill in job['skills'] if skill is not None]
                        return jobs

                    # Now try the vector search since index exists
                    result = session.run(
                        """
                        CALL db.index.vector.queryNodes('job_description_embedding', $limit, $embedding) YIELD node AS j, score
                        WHERE j.status = 'open' OR j.status = 'active'  
                        OPTIONAL MATCH (j)-[:REQUIRES]->(s:Skill)
                        RETURN j.id AS id, j.title AS title, j.department AS department, 
                               collect(DISTINCT s.name) AS skills, score AS similarity_score
                        LIMIT $limit
                        """,
                        limit=limit,
                        embedding=title_embedding
                    )
                    
                    jobs = [dict(record) for record in result]
                    logger.info(f"Found {len(jobs)} jobs similar to the provided title embedding.")
                    
                    # Filter out any None values from skills
                    for job in jobs:
                        if 'skills' in job:
                            job['skills'] = [skill for skill in job['skills'] if skill is not None]
                    
                    return jobs
                except Exception as query_err:
                    if "job_description_embedding" in str(query_err):
                        # This is likely an index not found error
                        logger.error(f"Vector index error: {query_err}")
                        # Try with a basic query as fallback
                        logger.info("Attempting fallback query without vector search...")
                        fallback_result = session.run(
                            """
                            MATCH (j:Job)
                            WHERE j.status = 'open' OR j.status = 'active'
                            OPTIONAL MATCH (j)-[:REQUIRES]->(s:Skill)
                            RETURN j.id AS id, j.title AS title, j.department AS department,
                                   collect(DISTINCT s.name) AS skills, 0.5 AS similarity_score
                            LIMIT $limit
                            """,
                            limit=limit
                        )
                        jobs = [dict(record) for record in fallback_result]
                        logger.info(f"Fallback query found {len(jobs)} active jobs")
                        return jobs
                    else:
                        # Re-raise the error for the outer exception handler
                        raise
        except Exception as e:
            logger.error(f"Error finding similar jobs in Neo4j: {e}")
            return []
    
    def check_gds_availability(self):
        """Check if the Neo4j Graph Data Science library is available.
        
        Returns:
            bool: True if GDS is available, False otherwise
        """
        if self.driver is None:
            logger.warning("Neo4j driver not initialized. Cannot check GDS availability.")
            return False
            
        try:
            with self.driver.session(database=self.database) as session:
                try:
                    result = session.run("CALL gds.list() YIELD name RETURN count(*) as count")
                    count = result.single()["count"]
                    return count >= 0  # If we can execute this, GDS is available
                except Exception as e:
                    logger.warning(f"GDS library not available: {e}")
                    return False
        except Exception as e:
            logger.error(f"Error checking GDS availability: {e}")
            return False
    
    def vector_search_jobs(self, query_embedding, limit=5):
        """Search for jobs based on vector similarity using GDS when available.
        
        Args:
            query_embedding: The embedding vector to search with
            limit: Maximum number of results to return
            
        Returns:
            List of similar jobs with scores
        """
        if self.driver is None:
            logger.warning("Neo4j driver not initialized. Cannot perform vector search.")
            return []
        
        embedding_dim = len(query_embedding) if query_embedding else 0
        if embedding_dim == 0:
            logger.error("Empty query embedding provided")
            return []
        
        try:
            with self.driver.session(database=self.database) as session:
                # Check if we have any jobs to search
                count_check = session.run("MATCH (j:Job) WHERE j.description_embedding IS NOT NULL RETURN count(j) as count")
                job_count = count_check.single()["count"]
                
                if job_count == 0:
                    logger.warning("No jobs with embeddings found in database")
                    return []
                
                # Detect Neo4j vector index dimensions
                target_dimension = 384  # Default fallback dimension
                try:
                    logger.info("Checking vector index dimensions")
                    result = session.run("CALL db.index.vector.list()")
                    vector_indexes_details = list(result)
                    
                    for details in vector_indexes_details:
                        index_name = details.get('name', '')
                        dimension = details.get('dimension', 0)
                        if index_name.startswith('job_') and 'embedding' in index_name.lower():
                            logger.info(f"Found job index {index_name} with dimension {dimension}")
                            target_dimension = dimension
                            break
                    logger.info(f"Using target dimension of {target_dimension} for vector search")
                except Exception as e:
                    logger.warning(f"Error determining vector index dimensions, using default {target_dimension}: {e}")
                
                # Adjust dimensions of the query embedding to match Neo4j indexes
                if embedding_dim != target_dimension:
                    logger.warning(f"Embedding dimension mismatch: Neo4j expects {target_dimension}, got {embedding_dim}")
                    if embedding_dim < target_dimension:
                        logger.info(f"Zero-padding embedding from {embedding_dim} to {target_dimension} dimensions")
                        query_embedding = query_embedding + [0.0] * (target_dimension - embedding_dim)
                    else:
                        logger.info(f"Truncating embedding from {embedding_dim} to {target_dimension} dimensions")
                        query_embedding = query_embedding[:target_dimension]
                
                # Check if Neo4j Graph Data Science library is available
                has_gds = self.check_gds_availability()
                
                # Try to find available job vector indexes
                job_vector_indexes = []
                try:
                    result = session.run("SHOW INDEXES")
                    available_indexes = [record.get('name') for record in result]
                    job_vector_indexes = [idx for idx in available_indexes if idx.startswith('job_') and 'embedding' in idx.lower()]
                    logger.info(f"Available job vector indexes: {job_vector_indexes}")
                except Exception as e:
                    logger.error(f"Error getting available indexes: {e}")
                
                # Try GDS cosine similarity if available
                try:
                    if has_gds:
                        logger.info("Using GDS cosine similarity for vector search")
                        result = session.run(
                            """
                            MATCH (j:Job)
                            WHERE j.description_embedding IS NOT NULL
                            WITH j, gds.similarity.cosine(j.description_embedding, $embedding) AS score
                            ORDER BY score DESC
                            LIMIT $limit
                            RETURN j.id AS id, j.title AS title, score,
                                   j.job_overview AS description, j.department AS company,
                                   j.location AS location
                            """,
                            embedding=query_embedding,
                            limit=limit
                        )
                        return self._process_vector_search_results(result)
                except Exception as e:
                    logger.error(f"Error during GDS vector search: {e}")
                
                # Try vector index search with each available job index
                for index_name in job_vector_indexes:
                    try:
                        logger.info(f"Using standard vector index search with {index_name}")
                        result = session.run(
                            """
                            CALL db.index.vector.queryNodes($index_name, $limit, $embedding)
                            YIELD node, score
                            RETURN node.id AS id, node.title AS title, score,
                                   node.job_overview AS description, node.department AS company,
                                   node.location AS location
                            """,
                            index_name=index_name,
                            limit=limit,
                            embedding=query_embedding
                        )
                        return self._process_vector_search_results(result)
                    except Exception as e:
                        logger.error(f"Error during vector index search with {index_name}: {e}")
                
                # Try with hardcoded index as last resort
                try:
                    logger.info("Falling back to job_description_embedding index")
                    result = session.run(
                        """
                        CALL db.index.vector.queryNodes($index_name, $limit, $embedding)
                        YIELD node, score
                        RETURN node.id AS id, node.title AS title, score,
                               node.job_overview AS description, node.department AS company,
                               node.location AS location
                        """,
                        index_name="job_description_embedding",
                        limit=limit,
                        embedding=query_embedding
                    )
                    return self._process_vector_search_results(result)
                except Exception as e:
                    logger.error(f"Error during fallback vector index search: {e}")
                
                # Fall back to simple job retrieval if all vector searches failed
                logger.warning("All vector search methods failed. Falling back to simple job retrieval.")
                result = session.run(
                    """
                    MATCH (j:Job)
                    RETURN j.id AS id, j.title AS title, 0.0 AS score,
                           j.job_overview AS description, j.department AS company,
                           j.location AS location
                    LIMIT $limit
                    """,
                    limit=limit
                )
                return self._process_vector_search_results(result)
                    
        except Exception as e:
            logger.error(f"Error during vector search: {e}")
            return []
    
    def _process_vector_search_results(self, result):
        """Process Neo4j vector search results and handle NaN scores."""
        import numpy as np
        
        if result is None:
            return []
            
        try:
            # Process results and handle potential NaN scores
            jobs = []
            for record in result:
                # Replace NaN scores with 0.0 to avoid downstream errors
                score = record["score"]
                if score is None or np.isnan(score):
                    score = 0.0
                    
                jobs.append({
                    "id": record["id"],
                    "title": record["title"],
                    "score": score,
                    "description": record.get("description", ""),
                    "company": record.get("company", ""),
                    "location": record.get("location", "")
                })
                
            return jobs
        except Exception as e:
            logger.error(f"Error processing vector search results: {e}")
            return []


# Singleton instance
_graph_service_instance = None

def get_graph_service():
    """Return a singleton instance of GraphService"""
    global _graph_service_instance
    if _graph_service_instance is None:
        from backend.utils.config import get_settings
        settings = get_settings()
        _graph_service_instance = GraphService(settings)
    return _graph_service_instance
