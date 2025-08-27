from neo4j import GraphDatabase
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_database():
    try:
        # Connect to Neo4j
        driver = GraphDatabase.driver(
            "bolt://localhost:7687",
            auth=("neo4j", "cadjhosea2024$$")
        )
        
        # Create database
        with driver.session(database="system") as session:
            # Create database
            logger.info("Creating neograph database...")
            session.run("CREATE DATABASE neograph")
            logger.info("Database created successfully")
            
            # Wait for database to be ready
            logger.info("Waiting for database to be ready...")
            time.sleep(10)  # Give it some time to initialize
            
            # Verify database exists
            result = session.run("SHOW DATABASES")
            databases = [record["name"] for record in result]
            if "neograph" in databases:
                logger.info("neograph database verified")
            else:
                logger.error("Failed to create neograph database")
                return
        
        # Create indexes and constraints
        with driver.session(database="neograph") as session:
            logger.info("Creating indexes and constraints...")
            
            # Create vector indexes
            session.run("CREATE INDEX candidate_embeddings IF NOT EXISTS FOR (c:Candidate) ON (c.embedding)")
            session.run("CREATE INDEX job_embeddings IF NOT EXISTS FOR (j:Job) ON (j.description_embedding)")
            session.run("CREATE INDEX market_intel_embeddings IF NOT EXISTS FOR (m:MarketIntelligence) ON (m.embedding)")
            session.run("CREATE INDEX knowledge_embeddings IF NOT EXISTS FOR (k:KnowledgeNode) ON (k.embedding)")
            
            # Create constraints
            session.run("CREATE CONSTRAINT candidate_id IF NOT EXISTS FOR (c:Candidate) REQUIRE c.id IS UNIQUE")
            session.run("CREATE CONSTRAINT job_id IF NOT EXISTS FOR (j:Job) REQUIRE j.id IS UNIQUE")
            session.run("CREATE CONSTRAINT skill_name IF NOT EXISTS FOR (s:Skill) REQUIRE s.name IS UNIQUE")
            
            logger.info("Indexes and constraints created successfully")
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
    finally:
        if 'driver' in locals():
            driver.close()

if __name__ == "__main__":
    create_database() 