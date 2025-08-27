"""
Monkey-patch Neo4j Session.run to replace deprecated setVectorProperty with setNodeVectorProperty.
"""
import logging

# Suppress Neo4j deprecation warnings at import
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)

def patch_neo4j_set_vector_property():
    try:
        from neo4j import Session as Neo4jSession
    except ImportError:
        try:
            from neo4j._sync.session import Session as Neo4jSession
        except ImportError:
            logging.getLogger(__name__).warning(
                "Neo4j Session class not found; skipping vector property patch."
            )
            return

    _original_run = Neo4jSession.run

    def patched_run(self, query, *args, **kwargs):
        if "CALL db.create.setVectorProperty" in query:
            query = query.replace(
                "CALL db.create.setVectorProperty",
                "CALL db.create.setNodeVectorProperty",
            )
            
        # Fix the YIELD node issue with setNodeVectorProperty
        if "CALL db.create.setNodeVectorProperty" in query and "YIELD node" in query:
            query = query.replace(
                "YIELD node",
                ""
            )
            # Also fix the RETURN count(*) to use a valid reference
            if "RETURN count(*)" in query:
                query = query.replace(
                    "RETURN count(*)",
                    "RETURN count(n)"
                )
        
        # Fix the elementId(n) issue by replacing it with n.id
        if "elementId(n)" in query:
            query = query.replace(
                "elementId(n)",
                "n.id"
            )
                
        return _original_run(self, query, *args, **kwargs)

    Neo4jSession.run = patched_run

    try:
        from neo4j._async.session import AsyncSession as Neo4jAsyncSession
        _orig_async_run = Neo4jAsyncSession.run

        async def patched_async_run(self, query, *args, **kwargs):
            if "CALL db.create.setVectorProperty" in query:
                query = query.replace(
                    "CALL db.create.setVectorProperty",
                    "CALL db.create.setNodeVectorProperty",
                )
                
            # Fix the YIELD node issue with setNodeVectorProperty
            if "CALL db.create.setNodeVectorProperty" in query and "YIELD node" in query:
                query = query.replace(
                    "YIELD node",
                    ""
                )
                # Also fix the RETURN count(*) to use a valid reference
                if "RETURN count(*)" in query:
                    query = query.replace(
                        "RETURN count(*)",
                        "RETURN count(n)"
                    )
            
            # Fix the elementId(n) issue by replacing it with n.id
            if "elementId(n)" in query:
                query = query.replace(
                    "elementId(n)",
                    "n.id"
                )
                    
            return await _orig_async_run(self, query, *args, **kwargs)

        Neo4jAsyncSession.run = patched_async_run
    except ImportError:
        pass

# Apply the patch immediately on module import
patch_neo4j_set_vector_property()
