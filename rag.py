import os
import re
import json
import logging
import pickle
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
import openpyxl
import email
from pypdf import PdfReader
from docx import Document as DocxDocument
from model_router import router

logging.basicConfig(filename='audit.log', level=logging.INFO, format='%(asctime)s - %(message)s')

def split_text(text, chunk_size=500, chunk_overlap=50):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - chunk_overlap
    return chunks

class LocalKnowledgeBase:
    def __init__(self, domain="general"):
        self.domain = domain
        self.persist_dir = f"local_faiss_index_{domain}"
        self.embeddings = OllamaEmbeddings(model=router.get_embedding_model())
        self.graph_file = os.path.join(self.persist_dir, "entity_graph.json")
        self.bm25_file = os.path.join(self.persist_dir, "bm25_index.pkl")
        self.corpus_file = os.path.join(self.persist_dir, "corpus.pkl")
        
    def _get_role(self, filename):
        if "_secret" in filename.lower() or "_confidential" in filename.lower():
            return "admin"
        return "engineer"

    def _extract_entities(self, text):
        # Extract engineering tags like PX-992A, V-102
        pattern = r'\b[A-Z]{1,3}-\d{2,4}[A-Z]?\b'
        return list(set(re.findall(pattern, text)))

    def _load_excel(self, file_path):
        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            text_content = []
            for sheet in wb.sheetnames:
                ws = wb[sheet]
                text_content.append(f"Sheet: {sheet}")
                for row in ws.iter_rows(values_only=True):
                    row_str = " | ".join([str(c) for c in row if c is not None])
                    if row_str:
                        text_content.append(row_str)
            return [Document(page_content="\n".join(text_content), metadata={"source": os.path.basename(file_path), "role": self._get_role(file_path)})]
        except Exception as e:
            print(f"Failed to load excel {file_path}: {e}")
            return []

    def _load_eml(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                msg = email.message_from_file(f)
            content = f"Subject: {msg.get('subject', '')}\nFrom: {msg.get('from', '')}\nTo: {msg.get('to', '')}\n\n"
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        content += part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')
            else:
                content += msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='replace')
            return [Document(page_content=content, metadata={"source": os.path.basename(file_path), "role": self._get_role(file_path)})]
        except Exception as e:
            print(f"Failed to load email {file_path}: {e}")
            return []

    def _load_pdf(self, file_path):
        try:
            reader = PdfReader(file_path)
            content = "\n".join([page.extract_text() for page in reader.pages]).strip()
            return [Document(page_content=content, metadata={"source": os.path.basename(file_path), "role": self._get_role(file_path)})]
        except Exception as e:
            print(f"Failed to load pdf {file_path}: {e}")
            return []

    def _load_docx(self, file_path):
        try:
            doc = DocxDocument(file_path)
            content = "\n".join([p.text for p in doc.paragraphs]).strip()
            return [Document(page_content=content, metadata={"source": os.path.basename(file_path), "role": self._get_role(file_path)})]
        except Exception as e:
            print(f"Failed to load docx {file_path}: {e}")
            return []
            
    def _load_txt(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return [Document(page_content=content, metadata={"source": os.path.basename(file_path), "role": self._get_role(file_path)})]
        except Exception as e:
            print(f"Failed to load txt {file_path}: {e}")
            return []

    def ingest_documents(self, data_dir: str):
        print(f"[{self.domain.upper()}] Ingesting documents from {data_dir}...")
        documents = []
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            return

        for filename in os.listdir(data_dir):
            file_path = os.path.join(data_dir, filename)
            ext = file_path.lower().split('.')[-1]
            if ext == 'xlsx': documents.extend(self._load_excel(file_path))
            elif ext == 'eml': documents.extend(self._load_eml(file_path))
            elif ext == 'pdf': documents.extend(self._load_pdf(file_path))
            elif ext == 'docx': documents.extend(self._load_docx(file_path))
            elif ext == 'txt': documents.extend(self._load_txt(file_path))

        if not documents:
            return

        docs = []
        corpus = []
        entity_graph = {}
        
        for doc in documents:
            chunks = split_text(doc.page_content, 500, 50)
            for chunk in chunks:
                docs.append(Document(page_content=chunk, metadata=doc.metadata))
                corpus.append(chunk)
                
                # Graph Extraction
                entities = self._extract_entities(chunk)
                for ent in entities:
                    if ent not in entity_graph:
                        entity_graph[ent] = []
                    if doc.metadata['source'] not in entity_graph[ent]:
                        entity_graph[ent].append(doc.metadata['source'])
        
        if not os.path.exists(self.persist_dir):
            os.makedirs(self.persist_dir)

        # Build BM25
        tokenized_corpus = [doc.split(" ") for doc in corpus]
        bm25 = BM25Okapi(tokenized_corpus)
        with open(self.bm25_file, 'wb') as f:
            pickle.dump(bm25, f)
        with open(self.corpus_file, 'wb') as f:
            pickle.dump(list(zip(corpus, [d.metadata for d in docs])), f)
            
        # Save Graph
        with open(self.graph_file, 'w') as f:
            json.dump(entity_graph, f)

        # Build FAISS
        vectorstore = FAISS.from_documents(docs, self.embeddings)
        vectorstore.save_local(self.persist_dir)
        print(f"[{self.domain.upper()}] Knowledge base saved to {self.persist_dir}")

    def search(self, query: str, user_role: str = "engineer", k: int = 3) -> str:
        if not os.path.exists(self.persist_dir) or not os.path.exists(os.path.join(self.persist_dir, "index.faiss")):
            return f"[{self.domain.upper()}] Knowledge base not initialized."
            
        # FAISS Search with Role Filter
        vectorstore = FAISS.load_local(self.persist_dir, self.embeddings, allow_dangerous_deserialization=True)
        # Assuming engineer can only see engineer, admin can see all
        filter_dict = {} if user_role == 'admin' else {"role": "engineer"}
        
        try:
            faiss_results = vectorstore.similarity_search(query, k=k, filter=filter_dict)
        except Exception:
             faiss_results = vectorstore.similarity_search(query, k=k) # Fallback if filter not supported natively by this FAISS version
             if user_role != 'admin':
                 faiss_results = [doc for doc in faiss_results if doc.metadata.get("role", "engineer") == "engineer"]

        # BM25 Search
        bm25_results = []
        if os.path.exists(self.bm25_file) and os.path.exists(self.corpus_file):
            with open(self.bm25_file, 'rb') as f:
                bm25 = pickle.load(f)
            with open(self.corpus_file, 'rb') as f:
                corpus_data = pickle.load(f)
                
            tokenized_query = query.split(" ")
            doc_scores = bm25.get_scores(tokenized_query)
            top_n = sorted(range(len(doc_scores)), key=lambda i: doc_scores[i], reverse=True)[:k]
            
            for i in top_n:
                content, metadata = corpus_data[i]
                if user_role == 'admin' or metadata.get("role", "engineer") == "engineer":
                    bm25_results.append(Document(page_content=content, metadata=metadata))

        # Combine results (simple deduplication for RRF approximation)
        all_results = faiss_results + bm25_results
        unique_results = {}
        for doc in all_results:
            if doc.page_content not in unique_results:
                unique_results[doc.page_content] = doc

        final_results = list(unique_results.values())[:k]
        
        # Graph Enrichment
        graph_context = ""
        if os.path.exists(self.graph_file):
            with open(self.graph_file, 'r') as f:
                entity_graph = json.load(f)
            query_entities = self._extract_entities(query)
            for ent in query_entities:
                if ent in entity_graph:
                    graph_context += f"\n[Graph] Entity {ent} is referenced in: {', '.join(entity_graph[ent])}"

        if not final_results and not graph_context:
            return f"[{self.domain.upper()}] No relevant information found."
            
        context = "\n\n".join([f"Source: {doc.metadata.get('source', 'Unknown')} (Role: {doc.metadata.get('role', 'unknown')})\nContent: {doc.page_content}" for doc in final_results])
        context += graph_context
        
        logging.info(f"USER:{user_role} | DOMAIN:{self.domain} | QUERY:{query} | RETRIEVED_SOURCES:{[d.metadata.get('source') for d in final_results]}")
        return context

if __name__ == "__main__":
    for domain, folder in [("engineering", "data_engineering"), ("commercial", "data_commercial"), ("compliance", "data_compliance")]:
        kb = LocalKnowledgeBase(domain=domain)
        kb.ingest_documents(folder)
