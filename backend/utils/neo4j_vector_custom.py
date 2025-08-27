"""
Custom implementation of Neo4jVector to override the deprecated elementId(n) usage
and replace db.create.setVectorProperty with db.create.setNodeVectorProperty.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from langchain_community.vectorstores.neo4j_vector import Neo4jVector

logger = logging.getLogger(__name__)

class CustomNeo4jVector(Neo4jVector):
    """Custom Neo4j Vector implementation that fixes deprecated Cypher queries."""
    
    @classmethod
    def from_existing_graph(
        cls,
        embedding,
        url: str,
        username: str,
        password: str,
        index_name: str,
        node_label: str,
        text_node_properties: List[str],
        embedding_node_property: str,
        database: str = "neo4j",
        retrieval_query: Optional[str] = None,
        **kwargs: Any,
    ) -> "CustomNeo4jVector":
        """Create a Neo4j vectorstore from an existing graph."""
        # This method just calls the parent class's constructor with the same arguments
        # The actual query modifications happen in the _add_embeddings_to_neo4j method
        instance = super().from_existing_graph(
            embedding=embedding,
            url=url,
            username=username,
            password=password,
            index_name=index_name,
            node_label=node_label,
            text_node_properties=text_node_properties,
            embedding_node_property=embedding_node_property,
            database=database,
            retrieval_query=retrieval_query,
            **kwargs,
        )
        
        # Return a CustomNeo4jVector instance with all the same attributes
        custom_instance = cls.__new__(cls)
        custom_instance.__dict__.update(instance.__dict__)
        return custom_instance
    
    def _add_embeddings_to_neo4j(
        self, vectors: List[Tuple[str, List[float], Dict[str, Any]]]
    ) -> None:
        """Add embeddings to Neo4j.
        
        Override the parent method to use node.id instead of elementId(n) and
        db.create.setNodeVectorProperty instead of db.create.setVectorProperty.
        """
        # Prepare data for batch insertion
        data = []
        for node_id, embedding, _ in vectors:
            # Convert string node_id to int if possible (for proper comparison in Cypher)
            try:
                node_id_value = int(node_id)
            except (ValueError, TypeError):
                node_id_value = node_id
                
            data.append({"id": node_id_value, "embedding": embedding})
        
        # Skip if no data
        if not data:
            return
        
        # Use node.id instead of elementId(n) and db.create.setNodeVectorProperty
        # instead of db.create.setVectorProperty
        query = f"""
        UNWIND $data AS row
        MATCH (n:`{self.node_label}`) 
        WHERE n.id = row.id
        CALL db.create.setNodeVectorProperty(n, '{self.embedding_node_property}', row.embedding)
        RETURN count(n)
        """
        
        with self._driver.session(database=self.database) as session:
            session.run(query, {"data": data})
