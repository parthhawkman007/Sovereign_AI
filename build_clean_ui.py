"""BUG-13 Fix: Re-saved without BOM (was UTF-8 with BOM causing SyntaxError U+FEFF)"""
import os
import shutil

def build_ui(source_dir="static_src", dest_dir="static"):
    """Build/copy UI files from source to static serving directory."""
    if not os.path.exists(source_dir):
        print(f"[build_clean_ui] Source dir '{source_dir}' not found. Nothing to build.")
        return
    os.makedirs(dest_dir, exist_ok=True)
    for item in os.listdir(source_dir):
        src = os.path.join(source_dir, item)
        dst = os.path.join(dest_dir, item)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
            print(f"[build_clean_ui] Copied: {item}")
    print(f"[build_clean_ui] Build complete -> {dest_dir}/")

if __name__ == "__main__":
    build_ui()
