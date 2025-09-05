# backend/services/rag_service.py
from typing import Dict, List, Optional, Any, Tuple
import json
import asyncio
import logging
from enum import Enum
import re
# LocalReranker merged from reranker_service.py
from rerankers import Reranker

class LocalReranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        self.reranker = Reranker(model_name)

    def rerank(self, query: str, docs: list[str]) -> list[int]:
        """
        Returns a list of indices representing the reranked order of docs.
        """
        scores = self.reranker.compute_score(query, docs)
        # Sort indices by descending score
        return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

    def rerank_with_scores(self, query: str, docs: list[str]) -> list[tuple[int, float]]:
        scores = self.reranker.compute_score(query, docs)
        return sorted(enumerate(scores), key=lambda x: x[1], reverse=True)


# Import our custom Neo4jVector implementation
from backend.utils.neo4j_vector_custom import CustomNeo4jVector
import sys
if sys.platform != "win32":
    from langchain.retrievers import ContextualCompressionRetriever
    from langchain.retrievers.document_compressors import LLMChainExtractor
else:
    ContextualCompressionRetriever = None
    LLMChainExtractor = None
from langchain_core.documents import Document
from pydantic import BaseModel, Field

from backend.services.llm_service import LLMService
from backend.services.graph_service import GraphService
from backend.utils.config import Settings


logger = logging.getLogger(__name__)


class QueryType(str, Enum):
    CANDIDATE_SEARCH = "candidate_search"
    JOB_SEARCH = "job_search"
    MARKET_INTELLIGENCE = "market_intelligence"
    KNOWLEDGE_QUERY = "knowledge_query"
    CONVERSATIONAL = "conversational"


class RAGResult(BaseModel):
    query: str
    query_type: QueryType
    context: List[Dict[str, Any]]
    sources: List[str] = Field(default_factory=list)
    
    model_config = {"arbitrary_types_allowed": True}


class RAGService:
    def __init__(
        self,
        llm_service: LLMService,
        graph_service: GraphService,
        settings: Settings,
    ):
        self.llm_service = llm_service
        self.graph_service = graph_service
        self.settings = settings
        
        # Initialize vector stores for different retrieval needs
        self.vector_stores = self._initialize_vector_stores()
        
        # Initialize retrievers with document compressors
        self.retrievers = self._initialize_retrievers()
        
        # Initialize the embedding adapter for vector similarity calculations
        self.embedding_adapter = self.llm_service.get_embedding_model()
        
    def search_candidates(self, query: str, limit: int = 10, db=None):
        """
        Search for candidates matching the query string.
        Args:
            query: The search query string
            limit: Maximum number of results to return
            db: Optional database session
        Returns:
            List of candidate dictionaries with match information and explanations
        """
        try:
            from backend.models.models import Candidate, Resume, CandidateSkill
            from sqlalchemy import or_, desc
            import re
            
            if db is None:
                logger.error("Database session is required for search_candidates.")
                return []
            
            # Perform a comprehensive search on candidate name, skills, and resume content
            candidates = db.query(Candidate).filter(
                or_(
                    Candidate.first_name.ilike(f"%{query}%"),
                    Candidate.last_name.ilike(f"%{query}%"),
                    Candidate.skills.any(CandidateSkill.skill_name.ilike(f"%{query}%"))
                )
            ).limit(limit).all()
            
            results = []
            for candidate in candidates:
                # Get candidate skills
                skills = [skill.skill_name for skill in candidate.skills]
                
                # Get candidate's resume for content analysis
                resume = db.query(Resume).filter(Resume.candidate_id == candidate.id).order_by(desc(Resume.created_at)).first()
                
                # Generate match explanation
                match_explanation = self._generate_match_explanation(candidate, resume, query, skills)
                
                # Calculate match score based on various factors
                match_score = self._calculate_match_score(candidate, resume, query, skills)
                
                results.append({
                    "id": candidate.id,
                    "name": f"{candidate.first_name or ''} {candidate.last_name or ''}".strip(),
                    "summary": getattr(candidate, 'summary', '') or '',
                    "skills": skills,
                    "resumes": [r.id for r in (resume and [resume] or [])],
                    "match_score": match_score,
                    "match_explanation": match_explanation,
                    "source": "candidate_search"
                })
            
            if not results:
                # Fallback: return recent candidates with basic explanations
                recent_candidates = db.query(Candidate).order_by(desc(Candidate.id)).limit(limit).all()
                for candidate in recent_candidates:
                    skills = [skill.skill_name for skill in candidate.skills]
                    resume = db.query(Resume).filter(Resume.candidate_id == candidate.id).order_by(desc(Resume.created_at)).first()
                    
                    match_explanation = f"Recent candidate in database with {len(skills)} skills"
                    if skills:
                        match_explanation += f" including {', '.join(skills[:3])}"
                    
                    results.append({
                        "id": candidate.id,
                        "name": f"{candidate.first_name or ''} {candidate.last_name or ''}".strip(),
                        "summary": getattr(candidate, 'summary', '') or '',
                        "skills": skills,
                        "resumes": [r.id for r in (resume and [resume] or [])],
                        "match_score": 50,
                        "match_explanation": match_explanation,
                        "source": "recent_candidates"
                    })
            
            # Sort by match score (highest first)
            results.sort(key=lambda x: x['match_score'], reverse=True)
            return results
            
        except Exception as e:
            logger.error(f"Error searching candidates: {str(e)}")
            return []
    
    def _generate_match_explanation(self, candidate, resume, query, skills):
        """
        Generate a human-readable explanation of why a candidate matches the query.
        
        Args:
            candidate: Candidate object
            resume: Resume object (can be None)
            query: Search query string
            skills: List of candidate skills
            
        Returns:
            str: Explanation of the match
        """
        explanations = []
        query_lower = query.lower()
        
        # Check name match
        full_name = f"{candidate.first_name or ''} {candidate.last_name or ''}".strip()
        if query_lower in full_name.lower():
            explanations.append("Name matches search query")
        
        # Check skills match
        matching_skills = [skill for skill in skills if query_lower in skill.lower()]
        if matching_skills:
            explanations.append(f"Has relevant skills: {', '.join(matching_skills[:3])}")
        
        # Check resume content match
        if resume and resume.parsed_content:
            content_lower = resume.parsed_content.lower()
            if query_lower in content_lower:
                # Extract context around the match
                pos = content_lower.find(query_lower)
                if pos != -1:
                    start = max(0, pos - 100)
                    end = min(len(resume.parsed_content), pos + len(query) + 100)
                    snippet = resume.parsed_content[start:end]
                    snippet = re.sub(r'\s+', ' ', snippet).strip()
                    if len(snippet) > 150:
                        snippet = snippet[:147] + "..."
                    explanations.append(f"Resume mentions: \"{snippet}\"")
        
        # Check current position/company
        if candidate.current_position and query_lower in candidate.current_position.lower():
            explanations.append(f"Current position: {candidate.current_position}")
        
        if candidate.current_company and query_lower in candidate.current_company.lower():
            explanations.append(f"Current company: {candidate.current_company}")
        
        # If no specific matches found, provide general context
        if not explanations:
            if skills:
                explanations.append(f"Professional with {len(skills)} skills including {', '.join(skills[:3])}")
            else:
                explanations.append("Candidate in database")
        
        return " • ".join(explanations)
    
    def _calculate_match_score(self, candidate, resume, query, skills):
        """
        Calculate a match score for the candidate based on various factors.
        
        Args:
            candidate: Candidate object
            resume: Resume object (can be None)
            query: Search query string
            skills: List of candidate skills
            
        Returns:
            float: Match score (0-100)
        """
        score = 0
        query_lower = query.lower()
        
        # Name match (high weight)
        full_name = f"{candidate.first_name or ''} {candidate.last_name or ''}".strip()
        if query_lower in full_name.lower():
            score += 30
        
        # Skills match (high weight)
        matching_skills = [skill for skill in skills if query_lower in skill.lower()]
        if matching_skills:
            score += 25 + (len(matching_skills) * 5)  # Base + bonus for multiple matches
        
        # Resume content match (medium weight)
        if resume and resume.parsed_content:
            content_lower = resume.parsed_content.lower()
            if query_lower in content_lower:
                score += 20
        
        # Current position match (medium weight)
        if candidate.current_position and query_lower in candidate.current_position.lower():
            score += 15
        
        # Current company match (low weight)
        if candidate.current_company and query_lower in candidate.current_company.lower():
            score += 10
        
        # General skills presence (low weight)
        if skills:
            score += min(10, len(skills) * 2)  # Cap at 10 points
        
        return min(100, score)  # Cap at 100

    def _initialize_vector_stores(self) -> Dict[QueryType, CustomNeo4jVector]:
        """Initialize Neo4j vector stores for different content types."""
        vector_stores = {}
        
        # Candidate vector store
        vector_stores[QueryType.CANDIDATE_SEARCH] = CustomNeo4jVector.from_existing_graph(
            embedding=self.llm_service.get_embedding_model(),
            url=self.settings.neo4j_uri,
            username=self.settings.neo4j_user,
            password=self.settings.neo4j_password,
            index_name="candidate_embeddings",
            node_label="Candidate",
            text_node_properties=["full_text", "skills", "experience"],
            embedding_node_property="embedding",
        )
        
        # Job vector store
        vector_stores[QueryType.JOB_SEARCH] = CustomNeo4jVector.from_existing_graph(
            embedding=self.llm_service.get_embedding_model(),
            url=self.settings.neo4j_uri,
            username=self.settings.neo4j_user,
            password=self.settings.neo4j_password,
            index_name="job_embeddings",
            node_label="Job",
            text_node_properties=[
                "title", "job_overview", "required_qualifications", "skills"
            ],
            embedding_node_property="description_embedding",
        )
        
        # Market intelligence vector store
        vector_stores[QueryType.MARKET_INTELLIGENCE] = CustomNeo4jVector.from_existing_graph(
            embedding=self.llm_service.get_embedding_model(),
            url=self.settings.neo4j_uri,
            username=self.settings.neo4j_user,
            password=self.settings.neo4j_password,
            index_name="market_intel_embeddings",
            node_label="MarketIntelligence",
            text_node_properties=["content", "source", "category"],
            embedding_node_property="embedding",
        )
        
        # Knowledge base vector store
        vector_stores[QueryType.KNOWLEDGE_QUERY] = CustomNeo4jVector.from_existing_graph(
            embedding=self.llm_service.get_embedding_model(),
            url=self.settings.neo4j_uri,
            username=self.settings.neo4j_user,
            password=self.settings.neo4j_password,
            index_name="knowledge_embeddings",
            node_label="KnowledgeNode",
            text_node_properties=["content", "source", "category"],
            embedding_node_property="embedding",
        )
        
        return vector_stores
    
    def _initialize_retrievers(self) -> Dict[QueryType, Any]:
        """Initialize retrievers with document compressors for more relevant results."""
        import sys
        import platform
        
        retrievers = {}
        
        # Enhanced Windows detection and proper warning handling
        is_windows = sys.platform == "win32" or platform.system().lower() == "windows"
        compression_available = ContextualCompressionRetriever is not None and LLMChainExtractor is not None
        
        if is_windows or not compression_available:
            if is_windows:
                logger.info("Windows platform detected - using basic retrievers without compression to avoid compatibility issues")
            else:
                logger.warning("ContextualCompressionRetriever/LLMChainExtractor not available - using basic retrievers")
            
            # Use basic retrievers without compression on Windows or when compression is unavailable
            for query_type, vector_store in self.vector_stores.items():
                try:
                    retrievers[query_type] = vector_store.as_retriever(
                        search_type="similarity",
                        search_kwargs={"k": 5},
                    )
                    logger.debug(f"Initialized basic retriever for {query_type.value}")
                except Exception as e:
                    logger.error(f"Failed to initialize basic retriever for {query_type.value}: {e}")
            
            return retrievers
        
        # For non-Windows platforms with compression available
        try:
            # Create LLM-based document compressor
            llm = self.llm_service.get_llm("cohere")
            compressor = LLMChainExtractor.from_llm(llm)
            
            # Create retrievers for each vector store
            for query_type, vector_store in self.vector_stores.items():
                try:
                    base_retriever = vector_store.as_retriever(
                        search_type="similarity",
                        search_kwargs={"k": 5},
                    )
                    # Apply context compression
                    retrievers[query_type] = ContextualCompressionRetriever(
                        base_compressor=compressor,
                        base_retriever=base_retriever,
                    )
                    logger.debug(f"Initialized compressed retriever for {query_type.value}")
                except Exception as e:
                    logger.error(f"Failed to initialize compressed retriever for {query_type.value}: {e}")
                    # Fallback to basic retriever
                    try:
                        retrievers[query_type] = vector_store.as_retriever(
                            search_type="similarity",
                            search_kwargs={"k": 5},
                        )
                        logger.info(f"Fallback to basic retriever for {query_type.value}")
                    except Exception as fallback_e:
                        logger.error(f"Failed to initialize fallback retriever for {query_type.value}: {fallback_e}")
                        
        except Exception as e:
            logger.error(f"Failed to initialize document compressor: {e}")
            # Fallback to basic retrievers
            for query_type, vector_store in self.vector_stores.items():
                try:
                    retrievers[query_type] = vector_store.as_retriever(
                        search_type="similarity",
                        search_kwargs={"k": 5},
                    )
                    logger.info(f"Fallback to basic retriever for {query_type.value}")
                except Exception as fallback_e:
                    logger.error(f"Failed to initialize fallback retriever for {query_type.value}: {fallback_e}")
        
        logger.info(f"Initialized {len(retrievers)} retrievers successfully")
        return retrievers
    
    async def process_query(self, query: str, history: Optional[List[Dict]] = None) -> RAGResult:
        """Process a user query through the RAG pipeline."""
        # Understand the query type
        query_type = await self._classify_query_intent(query, history)
        
        # Expand the query for better retrieval
        expanded_query = await self._expand_query(query, query_type)
        
        # Retrieve relevant documents
        documents = await self._retrieve_documents(expanded_query, query_type)
        
        # Post-process and rerank the documents
        ranked_documents = await self._rerank_documents(documents, query, query_type)
        
        # Assemble context from the documents
        context, sources = self._assemble_context(ranked_documents, query_type)
        
        return RAGResult(
            query=query,
            query_type=query_type,
            context=context,
            sources=sources,
        )
    
    async def _classify_query_intent(
        self, query: str, history: Optional[List[Dict]] = None
    ) -> QueryType:
        """Classify the user's query intent to determine retrieval strategy."""
        prompt = f"""
        Analyze the following query and determine its primary intent category.
        Query: "{query}"
        
        Context: The query is related to a recruiting platform. 
        
        Select the most appropriate category:
        1. CANDIDATE_SEARCH: Looking for candidates with specific skills or attributes
        2. JOB_SEARCH: Searching for job listings or job-related information
        3. MARKET_INTELLIGENCE: Seeking market data like salary info, hiring trends, etc.
        4. KNOWLEDGE_QUERY: General knowledge question about recruiting practices
        5. CONVERSATIONAL: General conversation, clarification, or follow-up
        
        Return only the category name like "CANDIDATE_SEARCH".
        """
        
        # Add conversation history context if available
        if history:
            recent_history = history[-5:]  # Use last 5 messages
            history_text = "\n".join([
                f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
                for msg in recent_history
            ])
            prompt += f"\n\nConversation history:\n{history_text}"
        
        # Use Meta Llama for classification when available
        model_override = None
        try:
            from backend.utils.config import Settings
            settings = Settings()
            if getattr(settings, 'openrouter_enabled', False):
                model_override = getattr(settings, 'openrouter_default_model', None)
        except Exception:
            pass
        
        intent = await self.llm_service.generate_text_async(
            prompt=prompt, 
            model=model_override,
            max_tokens=10,
        )
        
        # Clean up and validate the response
        intent = intent.strip().upper()
        try:
            return QueryType(intent.lower())
        except ValueError:
            logger.warning(
                f"Invalid intent classification: {intent}. "
                f"Defaulting to knowledge query."
            )
            return QueryType.KNOWLEDGE_QUERY
    
    async def _expand_query(self, query: str, query_type: QueryType) -> str:
        """Expand the query to improve retrieval effectiveness."""
        prompt = f"""
        Original Query: "{query}"
        Query Type: {query_type.value}
        
        Please expand this query to improve search results by adding relevant terms,
        synonyms, or related concepts based on the query type. The expanded query 
        should capture the semantic meaning of the original while enriching it with
        recruiting-specific terminology.
        
        Return only the expanded query text.
        """
        
        # Use Meta Llama for query expansion when available
        expanded_query = await self.llm_service.generate_text_async(
            prompt=prompt, 
            model=model_override,
            max_tokens=100,
        )
        
        return expanded_query.strip()
    
    async def _retrieve_documents(
        self, query: str, query_type: QueryType
    ) -> List[Document]:
        """Retrieve relevant documents based on the query and query type."""
        if query_type == QueryType.CONVERSATIONAL:
            # For conversational queries, try multiple retrievers
            all_docs = []
            retriever_types = [
                QueryType.KNOWLEDGE_QUERY, 
                QueryType.CANDIDATE_SEARCH, 
                QueryType.JOB_SEARCH
            ]
            for retriever_type in retriever_types:
                if retriever_type in self.retrievers:
                    docs = await asyncio.to_thread(
                        self.retrievers[retriever_type].get_relevant_documents, query
                    )
                    all_docs.extend(docs)
            
            # Limit to most relevant
            return all_docs[:5]
        else:
            # Use the appropriate retriever for the query type
            if query_type in self.retrievers:
                return await asyncio.to_thread(
                    self.retrievers[query_type].get_relevant_documents, query
                )
            else:
                logger.warning(f"No retriever found for query type: {query_type}")
                return []
    
    async def _rerank_documents(
        self, documents: List[Document], query: str, query_type: QueryType, use_groq_llama: bool = False
    ) -> List[Document]:
        """
        Rerank documents using AnswerDotAI/rerankers (local reranker).
        Optionally, use Groq Llama3-70B reranking if use_groq_llama=True.
        """
        if not documents:
            logger.warning("No documents to rerank - returning empty list")
            return []
        if len(documents) == 1:
            logger.info("Only one document to rerank - returning as is")
            return documents

        # Use rerankers for up to 10 documents
        if len(documents) <= 10:
            doc_texts = [doc.page_content for doc in documents]
            try:
                logger.info("Attempting AnswerDotAI local reranking...")
                local_reranker = LocalReranker(model_name="BAAI/bge-reranker-base")
                ranked_indices = local_reranker.rerank(query, doc_texts)
                if not ranked_indices or len(ranked_indices) != len(documents):
                    logger.warning(f"Local reranker returned unexpected indices: {ranked_indices}")
                    if not use_groq_llama:
                        return documents
                reranked_docs = [documents[i] for i in ranked_indices]
                logger.info(f"Successfully reranked {len(documents)} documents using AnswerDotAI/rerankers.")
                return reranked_docs
            except Exception as e:
                logger.warning(f"Local reranker failed: {e}")
                # Fallback to Groq reranking if enabled
                # (do not return here, allow Groq fallback below)

        # Fallback: Groq Llama reranking using model/api from .env
        import os
        groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        groq_enabled = os.getenv("GROQ_ENABLED", "false").lower() == "true"
        if use_groq_llama or groq_enabled:
            try:
                logger.info(f"Attempting Groq Llama reranking with model: {groq_model}")
                prompt = (
                    f"Query: {query}\n"
                    f"Documents: {json.dumps([doc.page_content for doc in documents])}\n"
                    f"Rate relevance of each document to the query on a scale of 0-10 as a JSON list."
                )
                # Use Meta Llama for reranking when available
                rerank_model = model_override if 'model_override' in locals() else groq_model
                score_text = await self.llm_service.generate_text_async(
                    prompt=prompt,
                    model=rerank_model,
                    max_tokens=100,
                )
                scores = json.loads(score_text.strip())
                if len(scores) != len(documents):
                    logger.warning(
                        f"Groq Llama rerank: Score count mismatch: got {len(scores)}, expected {len(documents)}"
                    )
                    return documents
                doc_score_pairs = list(zip(documents, scores))
                doc_score_pairs.sort(key=lambda x: x[1], reverse=True)
                logger.info(f"Successfully reranked {len(documents)} documents using Groq Llama ({groq_model}).")
                return [doc for doc, _ in doc_score_pairs]
            except Exception as e:
                logger.warning(f"Groq Llama reranker failed: {e}")
                return documents

        # For larger sets, use original order (or implement batch reranking if needed)
        logger.info("More than 10 documents, skipping reranking and returning original order.")
        return documents


    
    def _assemble_context(
        self, documents: List[Document], query_type: QueryType
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        """Assemble context from retrieved documents for LLM consumption."""
        context = []
        sources = []
        
        for doc in documents:
            metadata = doc.metadata or {}
            source = metadata.get("source", "Unknown")
            
            context.append({
                "content": doc.page_content,
                "metadata": metadata
            })
            
            if source not in sources:
                sources.append(source)
        
        return context, sources
        
    async def search_jobs(self, query: str, limit: int = 10, db=None) -> List[Dict[str, Any]]:
        """
        Search for jobs matching the query string.
        Args:
            query: The search query string
            limit: Maximum number of results to return
            db: Optional database session
        Returns:
            List of job dictionaries with match information
        """
        logger.info(f"Searching for jobs with query: {query}")
        
        query_type = await self._classify_query_intent(query)
        if query_type != QueryType.JOB_SEARCH and "job" not in query.lower():
            logger.info(
                f"Query classified as {query_type}, not a job search. "
                f"Returning empty results."
            )
            return []
        
        try:
            jobs = []
            try:
                # Vector search via graph service
                vector_results = await self.graph_service.search_jobs(query, limit=limit)
                if vector_results:
                    for job in vector_results:
                        jobs.append({
                            **job,
                            "match_type": "semantic",
                            "match_score": job.get("score", 0) * 100 # To %age
                        })
            except Exception as e:
                logger.error(f"Error in vector search for jobs: {str(e)}")
            
            # Fallback to SQL if needed
            if not jobs and db:
                from sqlalchemy import or_, text
                from backend.models.models import Job
                
                sql_query = db.query(Job).filter(
                    or_(
                        Job.title.ilike(f"%{query}%"),
                        Job.description.ilike(f"%{query}%"),
                        Job.requirements.ilike(f"%{query}%"),
                        Job.department.ilike(f"%{query}%")
                    )
                ).order_by(text("created_at DESC")).limit(limit)
                
                sql_results = sql_query.all()
                
                for job in sql_results:
                    if not any(j.get("id") == job.id for j in jobs):
                        skills = []
                        if isinstance(job.skills, str) and job.skills:
                            skills = job.skills.split(",")
                        
                        jobs.append({
                            "id": job.id,
                            "title": job.title,
                            "department": job.department,
                            "description": job.description,
                            "requirements": job.requirements,
                            "responsibilities": job.responsibilities,
                            "location": job.location,
                            "location_type": job.location_type,
                            "job_type": job.job_type,
                            "experience_level": job.experience_level,
                            "skills": skills,
                            "status": job.status,
                            "created_at": (job.created_at.isoformat() 
                                        if job.created_at else None),
                            "match_type": "keyword",
                            "match_score": 50.0 # Default keyword score
                        })
            
            # Fallback to recent jobs if still no results
            if not jobs and db:
                from backend.models.models import Job
                from sqlalchemy import text
                
                recent_jobs = db.query(Job).order_by(
                    text("created_at DESC")
                ).limit(5).all()
                
                for job in recent_jobs:
                    skills = []
                    if isinstance(job.skills, str) and job.skills:
                        skills = job.skills.split(",")
                    
                    jobs.append({
                        "id": job.id,
                        "title": job.title,
                        "department": job.department,
                        "description": job.description,
                        "requirements": job.requirements,
                        "responsibilities": job.responsibilities,
                        "location": job.location,
                        "location_type": job.location_type,
                        "job_type": job.job_type,
                        "experience_level": job.experience_level,
                        "skills": skills,
                        "status": job.status,
                        "created_at": (job.created_at.isoformat() 
                                    if job.created_at else None),
                        "match_type": "recent",
                        "match_score": 0.0 # No match
                    })
            
            # Sort by score
            jobs = sorted(jobs, key=lambda j: j.get("match_score", 0), reverse=True)
            return jobs[:limit]
        except Exception as e:
            logger.error(f"Error searching for jobs: {str(e)}")
            return []

    def _extract_experience_level(self, text: str) -> Tuple[str, int]:
        """
        Extract experience level from text and return a normalized value.
        
        Args:
            text: Text to extract experience level from (job title, description, etc.)
            
        Returns:
            Tuple of (experience_level, years) where experience_level is one of:
            'entry', 'junior', 'mid', 'senior', 'lead', 'principal', 'executive'
        """
        text = text.lower()
        
        # First, look for explicit years of experience mentioned
        year_patterns = [
            r'(\d+)\+?\s*years?\s*(of\s*)?experience',
            r'experience\s*(of|:)?\s*(\d+)\+?\s*years?',
            r'(\d+)\+?\s*yrs?\s*(of\s*)?experience',
            r'experience\s*(of|:)?\s*(\d+)\+?\s*yrs?',
            r'(\d+)\+?\s*y\.?o\.?e\.?',  # Abbreviation: y.o.e. (years of experience)
        ]
        
        years = 0
        for pattern in year_patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                for group in groups:
                    if group and group.isdigit():
                        years = int(group)
                        break
                if years > 0:
                    break
                    
        # Map specific experience levels mentioned in the text
        level_keywords = {
            'entry': ['entry', 'entry level', 'entry-level', 'junior', 'intern', 'internship', 'graduate', 'trainee', 'apprentice', 'beginner'],
            'junior': ['junior', 'jr', 'jr.', 'associate', 'early career'],
            'mid': ['mid', 'mid level', 'mid-level', 'intermediate', 'regular', 'experienced'],
            'senior': ['senior', 'sr', 'sr.', 'experienced', 'expert', 'advanced'],
            'lead': ['lead', 'team lead', 'technical lead', 'manager', 'head of', 'director'],
            'principal': ['principal', 'staff', 'distinguished', 'architect'],
            'executive': ['chief', 'cto', 'cio', 'vp', 'vice president', 'executive']
        }
        
        # Find the highest level mentioned
        found_level = 'mid'  # Default to mid-level if nothing is found
        level_hierarchy = ['entry', 'junior', 'mid', 'senior', 'lead', 'principal', 'executive']
        
        for level, keywords in level_keywords.items():
            if any(keyword in text for keyword in keywords):
                idx = level_hierarchy.index(level)
                current_idx = level_hierarchy.index(found_level)
                if idx > current_idx:
                    found_level = level
        
        # If we found years but no specific level, infer level from years
        if years > 0 and found_level == 'mid':
            if years < 2:
                found_level = 'entry'
            elif years < 5:
                found_level = 'mid'
            elif years < 8:
                found_level = 'senior'
            elif years < 12:
                found_level = 'lead'
            else:
                found_level = 'principal'
                
        # Map level to approximate years if we didn't find explicit years
        if years == 0:
            level_to_years = {
                'entry': 1,
                'junior': 2,
                'mid': 4,
                'senior': 7,
                'lead': 10,
                'principal': 12,
                'executive': 15
            }
            years = level_to_years.get(found_level, 4)
            
        return found_level, years

    def _calculate_experience_match_score(self, job_level: str, job_years: int, candidate_level: str, candidate_years: int) -> float:
        """
        Calculate an experience match score between job requirements and candidate experience.
        
        Args:
            job_level: Job experience level (entry, junior, mid, senior, etc.)
            job_years: Job required years of experience
            candidate_level: Candidate experience level
            candidate_years: Candidate years of experience
            
        Returns:
            Match score between 0-100
        """
        # Define level hierarchy for comparison
        level_hierarchy = ['entry', 'junior', 'mid', 'senior', 'lead', 'principal', 'executive']
        
        # Get indices for levels
        try:
            job_idx = level_hierarchy.index(job_level)
            candidate_idx = level_hierarchy.index(candidate_level)
        except ValueError:
            # Default to mid if level not found
            job_idx = level_hierarchy.index('mid')
            candidate_idx = level_hierarchy.index('mid')
            
        # Calculate level match component (0-100)
        level_diff = candidate_idx - job_idx
        
        if level_diff < -2:  # Significantly underqualified
            level_match = 20
        elif level_diff == -2:  # Somewhat underqualified
            level_match = 40
        elif level_diff == -1:  # Slightly underqualified
            level_match = 70
        elif level_diff == 0:  # Perfect level match
            level_match = 100
        elif level_diff == 1:  # Slightly overqualified
            level_match = 90
        elif level_diff == 2:  # Somewhat overqualified
            level_match = 80
        else:  # Significantly overqualified
            level_match = 60
            
        # Calculate years match component (0-100)
        years_diff = candidate_years - job_years
        
        if years_diff < -3:  # Significantly less experience
            years_match = 30
        elif years_diff < -1:  # Somewhat less experience
            years_match = 60
        elif years_diff <= 1:  # Almost exact experience match
            years_match = 100
        elif years_diff <= 3:  # Slightly more experience
            years_match = 90
        elif years_diff <= 5:  # Somewhat more experience
            years_match = 80
        else:  # Significantly more experience
            years_match = 70
            
        # Blend level and years match scores (level is more important)
        final_score = (level_match * 0.7) + (years_match * 0.3)
        
        # Add context to score
        if job_level in ['entry', 'junior'] and candidate_level in ['senior', 'lead', 'principal']:
            # Significant overqualification penalty for entry roles
            final_score -= 20
            
        if job_level in ['principal', 'executive'] and candidate_level in ['entry', 'junior']:
            # Significant underqualification penalty for senior roles
            final_score -= 25
            
        return max(min(final_score, 100), 0)  # Ensure score is between 0-100
            
    async def search_candidates_for_jobs(
        self, job_ids: List[int], min_score: float = 30.0, limit: int = 10, db=None
    ) -> List[Dict[str, Any]]:
        """
        Find candidates matching jobs using a hybrid pipeline.
        Pipeline: Neo4j Graph -> Vector -> SQL -> LLM Rerank -> Market Intel + Experience Match + Skill Semantic Match
        Args:
            job_ids: List of job IDs to match against
            min_score: Minimum score threshold
            limit: Max candidates per job
            db: Optional database session
        Returns:
            List of dictionaries: {job_id, job_title, candidates: [...]} 
        """
        if not job_ids or not db:
            return []
            
        results = []
        
        try:
            from backend.models.models import Job, Candidate, Resume, Skill
            from sqlalchemy import desc
            import asyncio
            import re
            import json
            import logging
            import random
            import numpy as np
            from sklearn.metrics.pairwise import cosine_similarity
            
            logger = logging.getLogger(__name__)
            
            # Define the parse_llm_json_response function here
            def parse_llm_json_response(text):
                """
                Attempts to parse JSON from LLM text responses, handling common formatting issues.
                Args:
                    text: The text to parse
                Returns:
                    Parsed JSON object or empty dict if parsing fails
                """
                if not text:
                    return []
                    
                # First, clean up the text by removing markdown code blocks
                cleaned_text = text.strip()
                # Try to find a JSON block within markdown code blocks
                json_match = re.search(r'```(?:json)?\s*(\[.*?\]|\{.*?\})```', cleaned_text, re.DOTALL)
                if json_match:
                    logger.info("Found JSON within markdown code blocks")
                    json_str = json_match.group(1)
                else:
                    # Look for array or object pattern directly
                    array_match = re.search(r'(\[.*?\])', cleaned_text, re.DOTALL)
                    object_match = re.search(r'(\{.*?\})', cleaned_text, re.DOTALL)
                    if array_match:
                        logger.info("Found JSON array pattern")
                        json_str = array_match.group(1)
                    elif object_match:
                        logger.info("Found JSON object pattern")
                        json_str = object_match.group(1)
                    else:
                        # Just use the whole text if we couldn't extract a clear JSON pattern
                        logger.info("No clear JSON pattern found, using entire text")
                        json_str = cleaned_text
                # Try to parse the JSON
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON: {e}")
                    # Try to fix common issues and retry parsing
                    # 1. Replace single quotes with double quotes
                    json_str = json_str.replace("'", '"')
                    # 2. Try to fix unescaped quotes in strings
                    json_str = re.sub(r'(?<!")(w+)(?!")', r'"\1"', json_str)
                    # 3. Try to fix trailing commas
                    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        logger.error("Failed to parse JSON even after attempting fixes")
                        # Last resort: if it looks like an array of objects, try to extract each object individually
                        if json_str.startswith('[') and json_str.endswith(']'):
                            results = []
                            # Find all patterns that look like objects
                            object_patterns = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', json_str)
                            for obj_str in object_patterns:
                                try:
                                    obj = json.loads(obj_str)
                                    results.append(obj)
                                except:
                                    pass
                            if results:
                                logger.info(f"Successfully extracted {len(results)} objects from array")
                                return results
                        # Return empty dict or list as fallback
                        return [] if json_str.strip().startswith('[') else {}
            
            for job_id in job_ids:
                job = db.query(Job).filter(Job.id == job_id).first()
                if not job:
                    continue
                    
                job_result = {
                    "job_id": job.id,
                    "job_title": job.title,
                    "candidates": []
                }
                
                # Extract job details
                job_skills = []
                if isinstance(job.skills, str) and job.skills:
                    job_skills = job.skills.split(",")
                job_description = job.job_overview or ""
                job_requirements = job.required_qualifications or ""
                
                logger.info(f"Starting hybrid matching for job_id: {job_id}")
                
                # Analyze job role with more robust patterns
                job_role = job.title.lower() if job.title else ""
                job_description = (job.job_overview or "").lower()
                job_requirements = (job.required_qualifications or "").lower()
                
                # Use both title and description/requirements for better role classification
                job_is_product_role = any(term in job_role for term in ["product", "pm", "product manager"]) or \
                                    any(term in job_description for term in ["product management", "product owner", "product roadmap"])
                                    
                job_is_dev_role = any(term in job_role for term in ["developer", "engineer", "programmer", "coder", "software"]) or \
                                any(term in job_description for term in ["software development", "programming", "coding", "development", "backend", "frontend"])
                                
                job_is_design_role = any(term in job_role for term in ["designer", "ux", "ui", "design"]) or \
                                    any(term in job_description for term in ["user experience", "user interface", "ux/ui", "graphic design"])
                                    
                job_is_ai_role = any(term in job_role for term in ["ai", "ml", "machine learning", "data scientist", "nlp"]) or \
                                any(term in job_description for term in ["artificial intelligence", "machine learning", "deep learning", "neural network", "data science"])
                
                # If no specific role is detected, try to infer from skills or description
                if not any([job_is_product_role, job_is_dev_role, job_is_design_role, job_is_ai_role]):
                    # Check job skills for additional clues
                    if job_skills:
                        job_is_dev_role = any(s.lower() in ["python", "java", "javascript", "react", "node", "c#", "ruby", ".net", "php", "golang"] for s in job_skills)
                        job_is_design_role = any(s.lower() in ["figma", "sketch", "adobe", "ui", "ux", "photoshop", "illustrator"] for s in job_skills)
                        job_is_ai_role = any(s.lower() in ["tensorflow", "pytorch", "machine learning", "nlp", "data science", "keras", "scikit-learn"] for s in job_skills)
                        job_is_product_role = any(s.lower() in ["product management", "agile", "scrum", "product owner", "jira", "roadmap"] for s in job_skills)
                    
                    # Default to dev role if still unclassified (most common)
                    if not any([job_is_product_role, job_is_dev_role, job_is_design_role, job_is_ai_role]):
                        job_is_dev_role = True
                
                logger.info(
                    f"Job role classification: Product={job_is_product_role}, Dev={job_is_dev_role}, "
                    f"Design={job_is_design_role}, AI={job_is_ai_role}"
                )
                
                # ===== STEP 1: Neo4j Graph Matching =====
                graph_candidates = []
                try:
                    logger.info(f"1. Graph Matching: Neo4j for job_id: {job_id}")
                    # Get more candidates initially
                    graph_matches = await self.graph_service.get_candidates_matching_job(
                        job_id, limit=limit*2  
                    )
                    
                    if graph_matches:
                        logger.info(f"Found {len(graph_matches)} potential candidates via Neo4j graph matching.")
                        
                        successful_lookups = 0
                        failed_lookups = 0
                        
                        for i, match in enumerate(graph_matches):
                            candidate_id = None
                            candidate_id_str = None
                            try:
                                # Robust ID extraction - Log the original match data
                                logger.debug(f"Processing Neo4j match {i+1}/{len(graph_matches)}: {match}")
                                
                                if "candidate_id" in match and match["candidate_id"] is not None:
                                    candidate_id = match["candidate_id"]
                                    logger.debug(f"Extracted candidate_id: {candidate_id} (type: {type(candidate_id).__name__}) from key 'candidate_id'")
                                elif "id" in match and match["id"] is not None:
                                    candidate_id = match["id"]
                                    logger.debug(f"Extracted candidate_id: {candidate_id} (type: {type(candidate_id).__name__}) from key 'id'")
                                
                                if candidate_id is None:
                                    logger.warning("No valid 'candidate_id' or 'id' key found in Neo4j match object. Skipping match.")
                                    failed_lookups += 1
                                    continue
                                
                                # Convert to string for DB lookup - Log before and after
                                candidate_id_str = str(candidate_id)
                                logger.info(f"Attempting DB lookup for candidate_id: '{candidate_id_str}' (converted from type: {type(candidate_id).__name__})")

                                # Get candidate from primary database (PostgreSQL)
                                # Log the query filter being applied
                                logger.debug(f"Executing DB query: Candidate.id == '{candidate_id_str}'")
                                candidate = db.query(Candidate).filter(
                                    Candidate.id == candidate_id_str
                                ).first()

                                if not candidate:
                                    logger.warning(
                                        f"Candidate ID '{candidate_id_str}' NOT FOUND in PostgreSQL database. "
                                        f"Possible data sync issue or ID mismatch (e.g., int vs str). Skipping match."
                                    )
                                    failed_lookups += 1
                                    continue 
                                
                                # If found, log success
                                successful_lookups += 1
                                logger.debug(f"Successfully found candidate ID '{candidate_id_str}' in DB.")

                                # Process valid candidate
                                resume = candidate.resumes[0] if candidate.resumes else None
                                cand_pos = candidate.current_position or ""
                                cand_skills = [skill.skill_name for skill in candidate.skills]
                                name = f"{candidate.first_name or ''} {candidate.last_name or ''}".strip() or "Unknown Candidate"
                                email = candidate.email or ""
                                
                                # Calculate role match score dynamically
                                role_match_score = self._calculate_role_similarity_score(
                                    job.title, cand_pos
                                )
                                
                                # Calculate initial score from graph with more differentiation
                                base_score = match.get("score", 0.65) * 100
                                
                                # Add random variation (±5%) to break ties
                                variation = random.uniform(-5, 5)
                                
                                # Blend scores with weights depending on confidence
                                match_score = (base_score * 0.4) + (role_match_score * 0.6) + variation
                                match_score = max(match_score, 35.0)  # Minimum score
                                
                                # Generate explanation details
                                ai_keywords = ["ai", "ml", "nlp", "data scientist"]
                                ai_skills = [
                                    s.name for s in candidate.skills 
                                    if any(kw in s.name.lower() for kw in ai_keywords)
                                ]
                                
                                is_senior = any(t in pos_lower for t in ["senior", "lead"])
                                is_junior = any(t in pos_lower for t in ["junior", "entry"])
                                
                                # Build explanation string
                                role_detail = ""
                                if role_match_score > 70: role_detail = f"Excellent role alignment: {cand_pos} aligns well."
                                elif role_match_score > 50: role_detail = f"Good role alignment: {cand_pos} has related skills."
                                else: role_detail = f"Limited role alignment: {cand_pos} might require transition."
                                
                                skills_detail = ""
                                if ai_skills: skills_detail = f" Has {len(ai_skills)} AI skills: {', '.join(ai_skills[:3])}{'...' if len(ai_skills) > 3 else ''}."
                                elif cand_skills: skills_detail = f" Has {len(cand_skills)} technical skills."
                                
                                exp_detail = ""
                                if is_senior and "senior" in pos_lower: exp_detail = " Experience level matches senior role requirements."
                                elif is_junior and "junior" in pos_lower: exp_detail = " Note: Candidate may be overqualified for this junior position."
                                
                                # Combine details
                                match_explanation = role_detail + skills_detail + exp_detail
                                
                                # Store candidate info with source
                                graph_candidates.append({
                                    "id": candidate.id,
                                    "name": name,
                                    "email": email,
                                    "resume_id": resume.id if resume else None,
                                    "skills": cand_skills,
                                    "position": cand_pos,
                                    "match_score": match_score,
                                    "match_explanation": match_explanation,
                                    "source": "graph"
                                })
                            except Exception as e:
                                failed_lookups += 1
                                logger.error(f"Error processing Neo4j match for ID '{candidate_id_str}' if available: {str(e)}", exc_info=True)
                                
                        logger.info(f"Neo4j candidate lookup summary: {successful_lookups} successful, {failed_lookups} failed.")
                        
                except Exception as e:
                    logger.warning(f"Graph matching step failed entirely: {str(e)}. Will rely on other methods.", exc_info=True)
                
                # ===== STEP 2: Vector Embedding Matching =====
                # Use vector embeddings for semantic similarity matching
                vector_candidates = []
                try:
                    logger.info(f"2. Vector Matching: Using embeddings for semantic similarity")
                    
                    # Get all candidates that have resumes
                    candidates_with_resumes = db.query(Candidate).join(Resume).all()
                    
                    if candidates_with_resumes and self.retrievers.get("resume"):
                        # Create a job query from title and requirements
                        job_query = f"Job Title: {job.title}\nRequirements: {job_requirements}"
                        
                        # Use the resume retriever with compression to find semantically similar resumes
                        retriever = self.retrievers["resume"]
                        
                        # Get resume texts for all candidates
                        resume_texts = []
                        resume_candidates = []
                        
                        for candidate in candidates_with_resumes:
                            resume = db.query(Resume).filter(
                                Resume.candidate_id == candidate.id
                            ).order_by(desc(Resume.created_at)).first()
                            
                            if resume and resume.parsed_content:
                                resume_texts.append(resume.parsed_content)
                                resume_candidates.append(candidate)
                        
                        # If we have resume texts, use the embedding model to find similarities
                        if resume_texts and resume_candidates:
                            try:
                                # Get embeddings for job query and resumes
                                job_embedding = self.embedding_adapter.embed_query(job_query)
                                resume_embeddings = self.embedding_adapter.embed_documents(resume_texts)
                                
                                # Validate embeddings before processing
                                if not job_embedding or not resume_embeddings:
                                    logger.warning("Empty embedding results - skipping vector matching")
                                    raise ValueError("Invalid embedding results")
                                
                                if len(resume_embeddings) != len(resume_texts):
                                    logger.warning(
                                        f"Embedding count mismatch: got {len(resume_embeddings)}, "
                                        f"expected {len(resume_texts)}"
                                    )
                                    raise ValueError("Embedding count mismatch")
                                
                                # Convert to numpy arrays
                                job_embedding_np = np.array(job_embedding).reshape(1, -1)
                                resume_embeddings_np = np.array(resume_embeddings)
                                
                                # Calculate similarities
                                similarities = cosine_similarity(job_embedding_np, resume_embeddings_np)[0]
                                
                                # Check for NaN values in similarities
                                if np.isnan(similarities).any():
                                    logger.warning("NaN values found in similarity scores - skipping vector matching")
                                    raise ValueError("Invalid similarity scores")
                                    
                            except ImportError as e:
                                logger.error(f"Missing required library: {str(e)}")
                                continue  # Skip vector matching
                            except ValueError as e:
                                logger.error(f"Vector matching value error: {str(e)}")
                                continue  # Skip vector matching
                            except Exception as e:
                                logger.error(f"Error in vector matching: {str(e)}", exc_info=True)
                                continue  # Skip vector matching
                            
                            # Create candidate entries with similarity scores
                            for i, similarity in enumerate(similarities):
                                candidate = resume_candidates[i]
                                
                                # Get candidate skills
                                candidate_skills = [skill.skill_name for skill in candidate.skills]
                                
                                # Get candidate position/role information
                                candidate_position = candidate.current_position.lower() if candidate.current_position else ""
                                
                                # Determine candidate role type
                                is_product_manager = any(term in candidate_position for term in ["product", "pm", "product manager", "product owner"])
                                is_developer = any(term in candidate_position for term in ["developer", "engineer", "software", "programming", "coder"])
                                is_designer = any(term in candidate_position for term in ["designer", "ux", "ui", "design"])
                                
                                # Calculate role match score
                                role_match_score = 0
                                if job_is_product_role and is_product_manager:
                                    role_match_score = 100
                                elif job_is_dev_role and is_developer:
                                    role_match_score = 100
                                elif job_is_design_role and is_designer:
                                    role_match_score = 100
                                else:
                                    # Assign partial points for related roles (especially for AI and software engineering crossover)
                                    if job_is_ai_role and is_developer:
                                        role_match_score = 70  # Software engineers can transition to AI roles
                                    elif job_is_dev_role and any(term in candidate_position for term in ["ai", "machine learning", "data scientist"]):
                                        role_match_score = 70  # AI specialists can code too
                                    else:
                                        # Significant penalty for role mismatch
                                        role_match_score = 20
                                
                                # Calculate initial match score from embedding similarity
                                similarity_score = similarity * 100  # Convert to percentage
                                
                                # Boost similarity scores that are good but might fall below threshold
                                if similarity_score > 65:
                                    similarity_score = min(similarity_score * 1.15, 100)  # Boost by 15% but cap at 100
                                
                                # Blend scores with more weight on role matching
                                match_score = (similarity_score * 0.4) + (role_match_score * 0.6)
                                
                                # Ensure reasonable minimum score for semantic matches
                                match_score = max(match_score, 35.0)
                                
                                # Generate explanation
                                if role_match_score > 50:
                                    match_explanation = f"Strong role match: {candidate_position} for {job.title}. Semantic similarity: {similarity_score:.1f}%"
                                else:
                                    match_explanation = f"Weak role match: {candidate_position} for {job.title}. Semantic similarity: {similarity_score:.1f}%"
                                
                                # Only include if score is reasonable - use more permissive threshold for initial filtering
                                if match_score >= min_score * 0.6:  # More permissive initial threshold for vector matches
                                    resume = db.query(Resume).filter(
                                        Resume.candidate_id == candidate.id
                                    ).order_by(desc(Resume.created_at)).first()
                                    
                                    vector_candidates.append({
                                        "id": candidate.id,
                                        "name": f"{candidate.first_name} {candidate.last_name}".strip(),
                                        "email": candidate.email,
                                        "resume_id": resume.id if resume else None,
                                        "skills": candidate_skills,
                                        "position": candidate_position,
                                        "match_score": match_score,
                                        "match_explanation": match_explanation,
                                        "source": "vector"
                                    })
                except Exception as e:
                    logger.warning(f"Vector matching failed: {str(e)}. Will rely on other methods.")
                
                # ===== STEP 3: SQL Skill Overlap Matching =====
                # Use direct SQL queries for hard skill matching
                sql_candidates = []
                try:
                    logger.info(f"3. SQL Matching: Using direct skill overlap from database")
                    
                    if job_skills:
                        # Find candidates with matching skills
                        from backend.models.models import CandidateSkill
                        candidates_with_skills = db.query(Candidate).filter(
                            Candidate.skills.any(CandidateSkill.skill_name.in_(job_skills))
                        ).all()
                        
                        for candidate in candidates_with_skills:
                            # Get candidate skills
                            candidate_skills = [s.skill_name for s in candidate.skills] if candidate.skills else []
                            
                            # Count matching skills
                            matching_skill_count = sum(1 for skill in candidate_skills if skill in job_skills)
                            
                            if matching_skill_count > 0:
                                # Calculate match score based on skill overlap
                                match_score = min(80, 30 + (matching_skill_count * 10))
                                explanation = f"Matches {matching_skill_count} required skill(s): {', '.join([s for s in candidate_skills if s in job_skills])}"
                                
                                # Construct name from first_name and last_name
                                candidate_name = f"{candidate.first_name or ''} {candidate.last_name or ''}".strip()
                                if not candidate_name:
                                    candidate_name = "Unknown Candidate"

                                candidate_match_data = {
                                    "id": candidate.id,
                                    "name": candidate_name, # Use constructed name
                                    "match_score": round(match_score, 1),
                                    "match_explanation": explanation,
                                    "source": "Database (Skill Match)",
                                    "skills": candidate_skills,
                                    "position": candidate.current_position if hasattr(candidate, 'current_position') else "",
                                    "location": candidate.location if hasattr(candidate, 'location') else "",
                                    "experience": candidate.years_experience if hasattr(candidate, 'years_experience') else 0
                                }
                                
                                # Add education data if available
                                if hasattr(candidate, 'education') and candidate.education:
                                    candidate_match_data["education"] = candidate.education
                                
                                sql_candidates.append(candidate_match_data)
                except Exception as e:
                    logger.warning(f"SQL skill matching failed: {str(e)}. Will rely on other methods.")
                    
                # Combine and deduplicate candidates from all sources
                all_candidates = []
                seen_ids = set()
                
                # Combine results from all sources, preferring graph matches when duplicates exist
                for candidate_list in [graph_candidates, vector_candidates, sql_candidates]:
                    for candidate in candidate_list:
                        if candidate["id"] not in seen_ids and candidate["match_score"] >= min_score:
                            all_candidates.append(candidate)
                            seen_ids.add(candidate["id"])
                
                # Sort candidates by match score (descending)
                all_candidates.sort(key=lambda x: x["match_score"], reverse=True)
                
                # Apply the limit per job
                job_result["candidates"] = all_candidates[:limit]
                
                # Add to results
                results.append(job_result)
                
        except Exception as e:
            logger.error(f"Error in search_candidates_for_jobs: {str(e)}", exc_info=True)
            
        return results