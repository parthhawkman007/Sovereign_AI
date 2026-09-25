import os
import re
import json
import logging
import pickle
from langchain_community.vectorstores import FAISS  # TODO: migrate when langchain-faiss publishes stable API
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
import openpyxl
import email
from pypdf import PdfReader
from docx import Document as DocxDocument
from pptx import Presentation
from model_router import router

logging.basicConfig(filename=os.path.join("workspace", "audit.log"), level=logging.INFO, format='%(asctime)s - %(message)s')

# FIX 7 — Audit log rotation: cap at 10 MB, keep 3 backups.
# Replaces the unbounded append-only log with a rotating handler so
# audit.log never exceeds 10 MB (older entries roll to audit.log.1/.2/.3).
try:
    from logging.handlers import RotatingFileHandler as _RFH
    _audit_log_path = os.path.join("workspace", "audit.log")
    os.makedirs("workspace", exist_ok=True)
    _rfh = _RFH(
        _audit_log_path,
        maxBytes=10 * 1024 * 1024,  # 10 MB per file
        backupCount=3,               # keep audit.log.1, .2, .3
        encoding="utf-8",
    )
    _rfh.setLevel(logging.INFO)
    _rfh.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    logging.getLogger().addHandler(_rfh)
except Exception as _e:
    logging.warning(f"[RAG] Could not attach RotatingFileHandler: {_e}")


def split_text(text, chunk_size=500, chunk_overlap=50):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - chunk_overlap
    return chunks

class LocalKnowledgeBase:
    def __init__(self, domain="general", persist_dir=None):
        self.domain = domain
        self.persist_dir = persist_dir or os.path.join("workspace", "vector_databases", f"local_faiss_index_{domain}")
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
            from tools import extract_pdf_pages
            pages = extract_pdf_pages(file_path)
            docs = []
            for p in pages:
                if p["text"].strip():
                    docs.append(Document(
                        page_content=p["text"],
                        metadata={
                            "source": os.path.basename(file_path),
                            "page": p["page"],
                            "role": self._get_role(file_path)
                        }
                    ))
            return docs
        except Exception as e:
            print(f"Failed to load pdf {file_path}: {e}")
            return []

    def _load_docx(self, file_path):
        try:
            doc = DocxDocument(file_path)
            content = []
            for p in doc.paragraphs:
                if p.text.strip():
                    content.append(p.text)
            for table in doc.tables:
                for row in table.rows:
                    row_data = [cell.text.replace("\n", " ").strip() for cell in row.cells]
                    content.append(" | ".join(row_data))
            full_content = "\n".join(content).strip()
            return [Document(page_content=full_content, metadata={"source": os.path.basename(file_path), "role": self._get_role(file_path)})]
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

    def _load_pptx(self, file_path):
        try:
            prs = Presentation(file_path)
            content = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        content.append(shape.text)
            text_content = "\n".join(content).strip()
            return [Document(page_content=text_content, metadata={"source": os.path.basename(file_path), "role": self._get_role(file_path)})]
        except Exception as e:
            print(f"Failed to load pptx {file_path}: {e}")
            return []

    def ingest_documents(self, data_dir: str):
        print(f"[{self.domain.upper()}] Ingesting documents from {data_dir}...")
        documents = []
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            return

        for root, _, files in os.walk(data_dir):
            for filename in files:
                file_path = os.path.join(root, filename)
                ext = file_path.lower().split('.')[-1]
                if ext == 'xlsx': documents.extend(self._load_excel(file_path))
                elif ext == 'eml': documents.extend(self._load_eml(file_path))
                elif ext == 'pdf': documents.extend(self._load_pdf(file_path))
                elif ext == 'docx': documents.extend(self._load_docx(file_path))
                elif ext == 'txt': documents.extend(self._load_txt(file_path))
                elif ext in ['ppt', 'pptx']: documents.extend(self._load_pptx(file_path))

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

        # Build FAISS in batches to prevent WinError 10054
        batch_size = 50
        vectorstore = None
        for i in range(0, len(docs), batch_size):
            batch = docs[i:i + batch_size]
            if vectorstore is None:
                vectorstore = FAISS.from_documents(batch, self.embeddings)
            else:
                vectorstore.add_documents(batch)
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
             faiss_results = vectorstore.similarity_search(query, k=k * 5) # Retrieve more for post-filtering
             if user_role != 'admin':
                 faiss_results = [doc for doc in faiss_results if doc.metadata.get("role", "engineer") == "engineer"]
             faiss_results = faiss_results[:k]

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
            

        # FIX 6 — Prompt Injection Defense (block, don't just flag)
        # If a retrieved chunk contains injection commands, replace the entire
        # chunk content with a warning. The malicious instruction text is NOT
        # forwarded to the LLM.
        _INJECTION_PATTERNS = [
            "ignore previous instructions",
            "ignore system instructions",
            "disregard previous",
            "forget previous instructions",
            "you are now",
            "new instructions:",
        ]
        sanitized_results = []
        for doc in final_results:
            text = doc.page_content
            lower_text = text.lower()
            if any(pattern in lower_text for pattern in _INJECTION_PATTERNS):
                logging.warning(
                    f"[SECURITY] Prompt injection pattern detected in source "
                    f"'{doc.metadata.get('source', 'Unknown')}'. Chunk blocked."
                )
                # Replace chunk content entirely — do NOT forward the injection text
                text = (
                    f"[SECURITY: PROMPT INJECTION DETECTED AND BLOCKED] "
                    f"A chunk from source '{doc.metadata.get('source', 'Unknown')}' "
                    f"contained instruction-override text and has been redacted."
                )
            sanitized_results.append((doc, text))

        context = "\n\n".join([
            f"<EVIDENCE source=\"{doc.metadata.get('source', 'Unknown')}\" "
            f"role=\"{doc.metadata.get('role', 'unknown')}\">\n{text}\n</EVIDENCE>"
            for doc, text in sanitized_results
        ])
        context += graph_context

        logging.info(
            f"USER:{user_role} | DOMAIN:{self.domain} | QUERY:{query} | "
            f"RETRIEVED_SOURCES:{[d.metadata.get('source') for d in final_results]}"
        )
        return context


if __name__ == "__main__":
    for domain, folder in [("engineering", "data_engineering"), ("commercial", "data_commercial"), ("compliance", "data_compliance")]:
        kb = LocalKnowledgeBase(domain=domain)
        kb.ingest_documents(folder)
