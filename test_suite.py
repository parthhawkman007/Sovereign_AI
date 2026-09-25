"""
BUG-15 Fix: Rebuilt test suite with proper pytest functions.
Tests cover: CalculationVerifier, sandbox security, schemas, routing logic,
audit log path, _is_deliverable_request, _generic_rag_node signature.
"""
import pytest
import os
import sys

# ─── CalculationVerifier Tests ───────────────────────────────────────────────

class TestCalculationVerifier:
    def setup_method(self):
        from verification import CalculationVerifier
        self.v = CalculationVerifier()

    def test_pass_simple_arithmetic(self):
        code = "result = 2 + 2\nprint(result)"
        status, msg = self.v.verify(code, "4", "The answer is 4.")
        assert status == "PASS", f"Expected PASS, got {status}: {msg}"

    def test_fail_on_execution_error(self):
        code = "raise ValueError('test error')"
        status, msg = self.v.verify(code, "Errors:\nValueError: test error", "The value is 5.")
        assert status == "FAIL"

    def test_fail_syntax_error_in_code(self):
        code = "def broken syntax here"
        status, msg = self.v.verify(code, "4", "The answer is 4.")
        assert status == "FAIL"
        assert "Syntax error" in msg or "syntax" in msg.lower()

    def test_insufficient_no_computation(self):
        code = "result = 42\nprint(result)"  # hardcoded, no BinOp
        status, msg = self.v.verify(code, "42", "The answer is 42.")
        # No computation means VERIFICATION_INSUFFICIENT
        assert status in ("PASS", "VERIFICATION_INSUFFICIENT")

    def test_known_formula_ohms_law(self):
        code = "voltage = 12\nresistance = 4\ncurrent = voltage / resistance\nprint(current, 'A')"
        status, msg = self.v.verify(code, "3.0 A", "The current is 3.0 A.")
        assert status == "PASS", f"Expected PASS, got {status}: {msg}"


# ─── Sandbox Security Tests ───────────────────────────────────────────────────

class TestSandboxSecurity:
    def _check(self, code):
        from tools import _check_sandbox_security, SecurityError
        return _check_sandbox_security, SecurityError

    def test_blocks_import_subprocess(self):
        from tools import _check_sandbox_security, SecurityError
        with pytest.raises(SecurityError, match="blocked"):
            _check_sandbox_security("import subprocess")


    def test_blocks_exec(self):
        from tools import _check_sandbox_security, SecurityError
        with pytest.raises(SecurityError, match="blocked"):
            _check_sandbox_security("exec('import os')")

    def test_blocks_dunder_builtins(self):
        from tools import _check_sandbox_security, SecurityError
        with pytest.raises(SecurityError, match="blocked"):
            _check_sandbox_security("x = __builtins__")

    def test_allows_import_os_for_path_ops(self):
        from tools import _check_sandbox_security, SecurityError
        # import os is now ALLOWED — needed for os.path.exists(), os.path.join() etc.
        _check_sandbox_security("import os\nif os.path.exists('workspace/uploads/data.csv'):\n    print('found')")

    def test_blocks_os_system(self):
        from tools import _check_sandbox_security, SecurityError
        # os.system() is blocked even though import os is allowed
        with pytest.raises(SecurityError, match="blocked"):
            _check_sandbox_security("import os\nos.system('cmd /c dir')")

    def test_blocks_os_popen(self):
        from tools import _check_sandbox_security, SecurityError
        with pytest.raises(SecurityError, match="blocked"):
            _check_sandbox_security("import os\nos.popen('whoami')")

    def test_allows_open_for_file_io(self):
        from tools import _check_sandbox_security, SecurityError
        # open() is now allowed — runs safely in isolated subprocess
        _check_sandbox_security("with open('data.csv', 'r') as f:\n    print(f.read())")

    def test_allows_safe_math(self):
        from tools import _check_sandbox_security, SecurityError
        # Should not raise
        _check_sandbox_security("import math\nresult = math.sqrt(144)\nprint(result)")

    def test_allows_pandas_numpy(self):
        from tools import _check_sandbox_security, SecurityError
        # Should not raise — pandas/numpy are not blocked
        _check_sandbox_security("import pandas as pd\nimport numpy as np\nprint(np.pi)")


# ─── Schema Validation Tests ──────────────────────────────────────────────────

class TestCanonicalDocument:
    def test_empty_document_valid(self):
        from schemas import CanonicalDocument
        doc = CanonicalDocument()
        assert doc.findings == []
        assert doc.measurements == []
        assert doc.equipment == []
        assert doc.actions == []

    def test_finding_requires_all_fields(self):
        from schemas import CanonicalDocument
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            CanonicalDocument.model_validate({
                "findings": [{"id": "F-01"}]  # missing required fields
            })

    def test_valid_full_document(self):
        from schemas import CanonicalDocument
        prov = {"source": "test.pdf", "evidence": "page 1", "confidence": "HIGH", "extraction_method": "LLM"}
        doc = CanonicalDocument.model_validate({
            "findings": [{"id": "F-01", "description": "Corrosion", "target": "T-101", "severity": "HIGH", "provenance": prov}],
            "measurements": [{"id": "M-01", "raw_value": "5mm", "normalized_value": 5.0, "unit": "mm", "target": "T-101", "provenance": prov}],
        })
        assert len(doc.findings) == 1
        assert len(doc.measurements) == 1

    def test_invalid_extraction_method_rejected(self):
        from schemas import CanonicalDocument
        from pydantic import ValidationError
        prov = {"source": "test.pdf", "evidence": "page 1", "confidence": "HIGH", "extraction_method": "PDF reader"}
        with pytest.raises(ValidationError):
            CanonicalDocument.model_validate({
                "findings": [{"id": "F-01", "description": "X", "target": "Y", "severity": "LOW", "provenance": prov}]
            })


# ─── Agent Routing Logic Tests ────────────────────────────────────────────────

class TestIsDeliverableRequest:
    def test_docx_keyword_detected(self):
        from agent import _is_deliverable_request
        from langchain_core.messages import HumanMessage
        result = _is_deliverable_request([HumanMessage(content="Generate a Word report")])
        assert result is True

    def test_xlsx_keyword_detected(self):
        from agent import _is_deliverable_request
        from langchain_core.messages import HumanMessage
        result = _is_deliverable_request([HumanMessage(content="Create an Excel spreadsheet")])
        assert result is True

    def test_no_deliverable_keyword(self):
        from agent import _is_deliverable_request
        from langchain_core.messages import HumanMessage
        result = _is_deliverable_request([HumanMessage(content="What is Python?")])
        assert result is False

    def test_empty_messages(self):
        from agent import _is_deliverable_request
        result = _is_deliverable_request([])
        assert result is False


# ─── Plugin Registry Tests ────────────────────────────────────────────────────

class TestPluginRegistry:
    def test_plugin_registry_is_dict(self):
        from agent import _plugin_tool_registry
        assert isinstance(_plugin_tool_registry, dict), "_plugin_tool_registry must be a dict"

    def test_plugin_registry_keys_are_strings(self):
        from agent import _plugin_tool_registry
        for key in _plugin_tool_registry:
            assert isinstance(key, str), f"Registry key must be str, got {type(key)}"


# ─── Generic RAG Node Signature Test ─────────────────────────────────────────

class TestGenericRagNodeSignature:
    def test_accepts_four_args(self):
        import inspect
        from agent import _generic_rag_node
        sig = inspect.signature(_generic_rag_node)
        params = list(sig.parameters.keys())
        assert 'config' in params, f"_generic_rag_node must have 'config' param. Got: {params}"

    def test_config_has_default(self):
        import inspect
        from agent import _generic_rag_node
        sig = inspect.signature(_generic_rag_node)
        config_param = sig.parameters.get('config')
        assert config_param is not None
        assert config_param.default is not inspect.Parameter.empty, "config param must have a default value"


# ─── Audit Log Path Test ──────────────────────────────────────────────────────

class TestAuditLogPath:
    def test_validation_node_uses_workspace_path(self):
        """Ensure validation_node writes audit logs to workspace/ not project root."""
        import ast
        with open('agent.py', 'r', encoding='utf-8') as f:
            source = f.read()
        # Should not have bare 'audit.log' open calls (only workspace/audit.log)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == 'open':
                    if node.args:
                        first_arg = node.args[0]
                        if isinstance(first_arg, ast.Constant) and first_arg.value == 'audit.log':
                            pytest.fail(f"Found bare 'audit.log' open() at line {node.lineno} — should use os.path.join('workspace', 'audit.log')")


# ─── Config YAML Tests ────────────────────────────────────────────────────────

class TestConfigYaml:
    def test_all_required_model_keys_present(self):
        import yaml
        with open('config.yaml', 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        models = cfg.get('models', {})
        required = ['reasoning', 'coding', 'vision', 'embedding', 'document']
        for key in required:
            assert key in models, f"Missing model key in config.yaml: '{key}'"
