import os
import importlib.util
import inspect
from typing import List, Callable

def load_plugins(plugins_dir: str = "plugins") -> List[Callable]:
    """
    Loads tools from all .py files in the plugins directory.
    Discovery priority:
      1. PLUGIN_TOOLS list defined in the module (recommended manifest pattern)
      2. Functions decorated with LangChain @tool (detected via .name attribute)
      3. Functions with names ending in '_tool' (legacy)
    """
    tools: List[Callable] = []
    if not os.path.exists(plugins_dir):
        os.makedirs(plugins_dir)
        return tools

    for filename in sorted(os.listdir(plugins_dir)):
        if not filename.endswith(".py") or filename.startswith("_"):
            continue

        filepath = os.path.join(plugins_dir, filename)
        module_name = f"plugin_{filename[:-3]}"

        try:
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as e:
            print(f"[plugin_loader] Failed to load {filename}: {e}")
            continue

        plugin_name = getattr(module, "PLUGIN_NAME", filename[:-3])
        plugin_ver  = getattr(module, "PLUGIN_VERSION", "?")

        # Strategy 1: explicit PLUGIN_TOOLS manifest
        if hasattr(module, "PLUGIN_TOOLS"):
            for tool_fn in module.PLUGIN_TOOLS:
                tools.append(tool_fn)
                tool_label = getattr(tool_fn, 'name', None) or getattr(tool_fn, '__name__', str(tool_fn))
                print(f"[plugin] [OK] Loaded '{tool_label}' from {plugin_name} v{plugin_ver}")
            continue  # don't double-load via fallback strategies

        # Strategy 2: LangChain @tool decorated functions (have a .name attribute)
        loaded = False
        for attr_name, obj in inspect.getmembers(module):
            if callable(obj) and hasattr(obj, "name") and hasattr(obj, "invoke"):
                tools.append(obj)
                print(f"[plugin] [OK] Loaded @tool '{obj.name}' from {plugin_name} v{plugin_ver}")
                loaded = True

        # Strategy 3: legacy _tool suffix
        if not loaded:
            for attr_name, obj in inspect.getmembers(module, inspect.isfunction):
                if attr_name.endswith("_tool"):
                    tools.append(obj)
                    print(f"[plugin] [OK] Loaded '{attr_name}' from {plugin_name} v{plugin_ver}")

    if not tools:
        print("[plugin_loader] No plugin tools found.")
    return tools

