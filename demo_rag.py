from rag import LocalKnowledgeBase

if __name__ == "__main__":
    print("=== Demo 3: Local RAG with nomic-embed-text ===")
    
    kb = LocalKnowledgeBase()
    
    print("\n1. Ingesting internal SOPs...")
    kb.ingest_documents("sops_data")
    
    print("\n2. Querying Knowledge Base...")
    query = "What is the maximum allowable stress for carbon steel piping in Sector 4?"
    print(f"Query: '{query}'")
    
    result = kb.search(query)
    
    print("\n--- Retrieval Results ---")
    print(result)
