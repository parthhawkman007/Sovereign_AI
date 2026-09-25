import os
import json
from langchain_community.vectorstores import FAISS  # TODO: migrate when langchain-faiss publishes stable API
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document
from model_router import router

class LongTermMemory:
    def __init__(self, persist_dir=os.path.join("workspace", "vector_databases", "local_faiss_memory")):
        self.persist_dir = persist_dir
        self.prefs_file = os.path.join(persist_dir, "preferences.json")
        self.embeddings = OllamaEmbeddings(model=router.get_embedding_model())
        self.preferences = self._load_prefs()
        self._init_vectorstore()

    def _load_prefs(self):
        if os.path.exists(self.prefs_file):
            with open(self.prefs_file, "r") as f:
                return json.load(f)
        return {}

    def _save_prefs(self):
        os.makedirs(self.persist_dir, exist_ok=True)
        with open(self.prefs_file, "w") as f:
            json.dump(self.preferences, f)

    def _init_vectorstore(self):
        if os.path.exists(os.path.join(self.persist_dir, "index.faiss")):
            self.vectorstore = FAISS.load_local(self.persist_dir, self.embeddings, allow_dangerous_deserialization=True)
        else:
            dummy = Document(page_content="Memory initialized.", metadata={"source": "system"})
            self.vectorstore = FAISS.from_documents([dummy], self.embeddings)
            self.vectorstore.save_local(self.persist_dir)

    def set_preference(self, key, value):
        self.preferences[key] = value
        self._save_prefs()

    def add_memory(self, text, metadata=None):
        import time
        if metadata is None:
            metadata = {"source": "conversation"}
        # Add timestamp to all new memories
        if "timestamp" not in metadata:
            metadata["timestamp"] = time.time()
            
        doc = Document(page_content=text, metadata=metadata)
        self.vectorstore.add_documents([doc])
        self.vectorstore.save_local(self.persist_dir)

    def update_context(self, context):
        self.add_memory(context, metadata={"source": "project_context"})

    def get_all_memories(self):
        raw_logs = []
        if hasattr(self.vectorstore, 'docstore'):
            for doc_id, doc in self.vectorstore.docstore._dict.items():
                if doc.metadata.get("source") == "conversation_log":
                    ts = doc.metadata.get("timestamp", 0)
                    raw_logs.append((doc_id, doc.page_content, ts))
        return raw_logs

    def clear_raw_memories(self, doc_ids):
        if not doc_ids: return
        self.vectorstore.delete(doc_ids)
        self.vectorstore.save_local(self.persist_dir)

    def consolidate_memories(self):
        from langchain_ollama import ChatOllama
        import time
        
        raw_logs = self.get_all_memories()
        if not raw_logs:
            print("[Memory] No raw logs to consolidate.")
            return

        current_time = time.time()
        doc_ids = []
        valid_logs_text = []
        expired_ids = []
        
        # 7-day TTL for raw logs
        TTL_SECONDS = 7 * 24 * 3600 

        for doc_id, text, ts in raw_logs:
            if current_time - ts > TTL_SECONDS:
                expired_ids.append(doc_id)
            else:
                doc_ids.append(doc_id)
                valid_logs_text.append(text)
                
        if expired_ids:
            print(f"[Memory] Expiring {len(expired_ids)} raw logs older than 7 days.")
            self.clear_raw_memories(expired_ids)

        if not valid_logs_text:
            return

        logs_text = "\n\n---\n\n".join(valid_logs_text)
        print(f"[Memory] Consolidating {len(valid_logs_text)} active raw interactions...")
        
        system_prompt = """You are a Memory Consolidation Engine. 
Review the following interaction logs between a user and an AI.
Your task is to identify any MISTAKES the AI made that the user CORRECTED.
Extract these into a concise set of "Golden Rules" or updated facts so the AI never repeats the mistake.
Ignore normal successful interactions. Only output the extracted rules.
Output format:
Rule 1: ...
Rule 2: ...
If there are no corrections or mistakes, output EXACTLY the word: NONE"""

        llm = ChatOllama(model=router.get_reasoning_model(), temperature=0.1)
        response = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Logs:\n{logs_text}"}
        ])
        
        rules = response.content.strip()
        
        # Clear the old conflicting raw logs
        self.clear_raw_memories(doc_ids)
        
        if rules != "NONE" and len(rules) > 5:
            print(f"[Memory] Learned Golden Rules:\n{rules}")
            self.add_memory(f"Golden Rules to Follow:\n{rules}", metadata={"source": "golden_rule"})

    def search_memory(self, query, k=3):
        results = self.vectorstore.similarity_search(query, k=k*2)
        golden = [doc.page_content for doc in results if doc.metadata.get("source") == "golden_rule"]
        others = [doc.page_content for doc in results if doc.metadata.get("source") not in ["system", "golden_rule"]]
        return (golden + others)[:k]

    def get_context_string(self, query=None):
        prefs = ", ".join([f"{k}: {v}" for k, v in self.preferences.items()])
        ctx_str = f"User Preferences: {prefs}\n"
        if query:
            memories = self.search_memory(query, k=3)
            if memories:
                ctx_str += "Relevant Past Memories:\n- " + "\n- ".join(memories)
        return ctx_str
