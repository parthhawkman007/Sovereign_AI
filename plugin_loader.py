import os
import importlib.util
import inspect
from typing import List, Callable

def load_plugins(plugins_dir="plugins") -> List[Callable]:
    tools = []
    if not os.path.exists(plugins_dir):
        os.makedirs(plugins_dir)
        return tools

    for filename in os.listdir(plugins_dir):
        if filename.endswith(".py") and filename != "__init__.py":
            filepath = os.path.join(plugins_dir, filename)
            module_name = filename[:-3]
            
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find any functions decorated with @tool or ending with _tool
            for name, obj in inspect.getmembers(module, inspect.isfunction):
                if hasattr(obj, "is_tool") or name.endswith("_tool"):
                    tools.append(obj)
                    print(f"Loaded plugin tool: {name}")
    return tools
