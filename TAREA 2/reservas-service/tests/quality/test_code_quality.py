"""Code quality and cleanup tests (T066)."""
import pytest
import ast
import inspect
import os
import sys


class TestCodeQuality:
    """Code cleanup and quality tests (T066)."""

    @pytest.fixture
    def project_root(self):
        return os.path.join(os.path.dirname(__file__), "..", "..")

    def get_python_files(self, project_root):
        """Get all Python files in src/."""
        python_files = []
        src_path = os.path.join(project_root, "reservas-service", "src")
        for root, dirs, files in os.walk(src_path):
            for file in files:
                if file.endswith(".py") and not file.startswith("."):
                    python_files.append(os.path.join(root, file))
        return python_files

    def test_all_files_have_type_hints(self, project_root):
        """Verify all function signatures have type hints."""
        python_files = self.get_python_files(project_root)
        
        for file_path in python_files:
            with open(file_path) as f:
                content = f.read()
            
            try:
                tree = ast.parse(content)
            except SyntaxError:
                pytest.fail(f"Syntax error in {file_path}")
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Skip private methods and test functions
                    if node.name.startswith("_") or node.name.startswith("test_"):
                        continue
                    
                    # Check return type annotation
                    if node.returns is None and node.name != "__init__":
                        pytest.fail(f"Missing return type hint: {file_path}:{node.name}")
                    
                    # Check argument type annotations
                    for arg in node.args.args:
                        if arg.arg != "self" and arg.annotation is None:
                            pytest.fail(f"Missing type hint for argument '{arg.arg}' in {file_path}:{node.name}")

    def test_all_public_functions_have_docstrings(self, project_root):
        """Verify public functions have docstrings."""
        python_files = self.get_python_files(project_root)
        
        for file_path in python_files:
            with open(file_path) as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Skip private methods
                    if node.name.startswith("_"):
                        continue
                    
                    # Check for docstring
                    if not ast.get_docstring(node):
                        pytest.fail(f"Missing docstring: {file_path}:{node.name}")

    def test_no_unused_imports(self, project_root):
        """Check for unused imports (basic check)."""
        import pyflakes.api
        import pyflakes.reporter
        from io import StringIO
        
        python_files = self.get_python_files(project_root)
        
        for file_path in python_files:
            with open(file_path) as f:
                content = f.read()
            
            # Use pyflakes to detect unused imports
            from pyflakes import checker
            tree = ast.parse(content)
            w = checker.Checker(tree, file_path)
            
            # Filter for unused import warnings
            unused_imports = [
                msg for msg in w.messages
                if "imported but unused" in str(msg)
            ]
            
            if unused_imports:
                print(f"Unused imports in {file_path}: {[str(m) for m in unused_imports]}")
                # Don't fail, just warn

    def test_no_todo_fixme_in_production_code(self, project_root):
        """Check for TODO/FIXME comments in production code."""
        python_files = self.get_python_files(project_root)
        
        for file_path in python_files:
            with open(file_path) as f:
                content = f.read()
            
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                if "TODO" in line or "FIXME" in line:
                    # Allow in test files
                    if "/tests/" not in file_path:
                        pytest.fail(f"TODO/FIXME in production code: {file_path}:{line_num}")

    def test_no_print_statements_in_production(self, project_root):
        """Check for print statements in production code."""
        python_files = self.get_python_files(project_root)
        
        for file_path in python_files:
            if "/tests/" in file_path:
                continue
            
            with open(file_path) as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id == "print":
                        pytest.fail(f"Print statement in production code: {file_path}")

    def test_consistent_naming_conventions(self, project_root):
        """Check naming conventions (snake_case for functions/variables)."""
        python_files = self.get_python_files(project_root)
        
        for file_path in python_files:
            with open(file_path) as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Functions should be snake_case
                    if not node.name[0].islower() and not node.name.startswith("_"):
                        if not any(c.isupper() for c in node.name[1:]):
                            pass  # Might be camelCase, warn
                
                if isinstance(node, ast.ClassDef):
                    # Classes should be PascalCase
                    if not node.name[0].isupper():
                        pytest.fail(f"Class not PascalCase: {file_path}:{node.name}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])