from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, load_index_from_storage
import os

INDEX_DIR = "./vector_index"

def create_index(documents_dir):
    # Try to load the index from storage if it exists
    if os.path.exists(INDEX_DIR):
        try:
            storage_context = StorageContext.from_defaults(persist_dir=INDEX_DIR)
            index = load_index_from_storage(storage_context)
            print("Loaded existing index.")
            return index
        except Exception as e:
            print(f"Failed to load existing index: {e}. Rebuilding index.")
            # If loading fails, proceed to rebuild the index.

    # If index doesn't exist or failed to load, create a new one
    print("Creating new index...")
    try:
        documents = SimpleDirectoryReader(documents_dir).load_data()
    except ValueError:
        print("No documents found in 'docs' directory. Index will be created when documents are uploaded.")
        return None

    if not documents:
        print("No documents found to index.")
        return None
    
    index = VectorStoreIndex.from_documents(documents)
    index.storage_context.persist(persist_dir=INDEX_DIR)
    print("New index created and persisted.")
    return index

def query_index(index, query_text):
    if index is None:
        return "No index found. Please upload documents first."
    query_engine = index.as_query_engine()
    response = query_engine.query(query_text)
    return response
