import os
import json
import sys
import importlib.util
from pathlib import Path

class ModelBundle:
    def __init__(self, ok: bool, path: Path|None, meta: dict|None, is_placeholder: bool = False):
        self.ok, self.path, self.meta = ok, path, meta or {}
        self.is_placeholder = is_placeholder

def _test_model_loader(model_path: Path, model_class_name: str) -> bool:
    """Test if model loader works or raises NotImplementedError (placeholder)"""
    try:
        loader_path = model_path / "loader.py"
        if not loader_path.exists():
            return False
        
        # Import the loader module
        spec = importlib.util.spec_from_file_location("model_loader", loader_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Get the model class
        model_class = getattr(module, model_class_name)
        model_instance = model_class()
        
        # Test predict method with dummy data
        if model_class_name == "RolesModel":
            model_instance.predict([])
        else:  # TestRowModel
            model_instance.predict([])
        
        return True  # If we get here, it's a real model
        
    except NotImplementedError:
        return False  # This is a placeholder
    except Exception:
        return False  # Some other error, treat as unavailable

def load_roles_model(dir_env="MODEL_ROLES_DIR") -> ModelBundle:
    # Try local models first, then /models
    default_path = "/models/roles"
    local_path = "/Users/charliehockenberry/source/lab-ai/models/roles"
    p = Path(os.getenv(dir_env, local_path if Path(local_path).exists() else default_path))
    meta_path = p / "metadata.json"
    
    if not p.exists() or not meta_path.exists():
        return ModelBundle(False, None, None, False)
    
    try:
        meta = json.loads(meta_path.read_text())
        is_real_model = _test_model_loader(p, "RolesModel")
        is_placeholder = not is_real_model
        
        return ModelBundle(True, p, meta, is_placeholder)
    except Exception:
        return ModelBundle(False, None, None, False)

def load_testrow_model(dir_env="MODEL_TESTROW_DIR") -> ModelBundle:
    # Try local models first, then /models
    default_path = "/models/testrow"
    local_path = "/Users/charliehockenberry/source/lab-ai/models/testrow"
    p = Path(os.getenv(dir_env, local_path if Path(local_path).exists() else default_path))
    meta_path = p / "metadata.json"
    
    if not p.exists() or not meta_path.exists():
        return ModelBundle(False, None, None, False)
    
    try:
        meta = json.loads(meta_path.read_text())
        is_real_model = _test_model_loader(p, "TestRowModel")
        is_placeholder = not is_real_model
        
        return ModelBundle(True, p, meta, is_placeholder)
    except Exception:
        return ModelBundle(False, None, None, False)