import time
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from rag import LocalKnowledgeBase

class DomainHandler(FileSystemEventHandler):
    def __init__(self, domain, kb):
        self.domain = domain
        self.kb = kb

    def on_created(self, event):
        if not event.is_directory:
            print(f"[{self.domain.upper()}] New file detected: {event.src_path}. Re-ingesting...")
            self.kb.ingest_documents(f"data_{self.domain}")

    def on_modified(self, event):
        if not event.is_directory:
            print(f"[{self.domain.upper()}] File modified: {event.src_path}. Re-ingesting...")
            self.kb.ingest_documents(f"data_{self.domain}")

def start_watcher():
    domains = ["engineering", "commercial", "compliance"]
    observer = Observer()
    
    for domain in domains:
        path = f"data_{domain}"
        if not os.path.exists(path):
            os.makedirs(path)
        
        kb = LocalKnowledgeBase(domain=domain)
        event_handler = DomainHandler(domain, kb)
        observer.schedule(event_handler, path, recursive=False)
        print(f"Started background watcher on {path}/")
        
    observer.start()
    return observer

if __name__ == "__main__":
    obs = start_watcher()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        obs.stop()
    obs.join()
