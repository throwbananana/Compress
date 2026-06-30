import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import tempfile

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from core.config import PythonConfig, CSharpConfig, NodeConfig, JavaConfig
from core.builders import Builder
from core.utils import resolve_python_entry

class TestBuilders(unittest.TestCase):
    
    def test_build_python_pyinstaller(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            entry_file = os.path.join(temp_dir, "main.py")
            with open(entry_file, "w", encoding="utf-8") as handle:
                handle.write("print('ok')\n")

            config = PythonConfig(entry=entry_file, backend="pyinstaller")
            cmd, _ = Builder.build_python(config)

            self.assertIn("PyInstaller", cmd[2])
            self.assertIn("--onefile", cmd)

    def test_resolve_python_entry_prefers_package_main(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            package_dir = os.path.join(temp_dir, "sample_app")
            os.makedirs(package_dir)
            with open(os.path.join(package_dir, "__main__.py"), "w", encoding="utf-8") as handle:
                handle.write("print('ok')\n")
            with open(os.path.join(package_dir, "helper.py"), "w", encoding="utf-8") as handle:
                handle.write("print('helper')\n")

            self.assertEqual(
                resolve_python_entry(package_dir),
                os.path.join(package_dir, "__main__.py"),
            )

    def test_build_python_resolves_directory_entry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            package_dir = os.path.join(temp_dir, "sample_app")
            os.makedirs(package_dir)
            entry_file = os.path.join(package_dir, "__main__.py")
            with open(entry_file, "w", encoding="utf-8") as handle:
                handle.write("print('ok')\n")

            config = PythonConfig(entry=package_dir, backend="pyinstaller")
            cmd, cwd = Builder.build_python(config)

            self.assertIn(entry_file, cmd)
            self.assertEqual(cwd, package_dir)
        
    @patch('os.path.exists', return_value=True)
    @patch('shutil.which', return_value='/usr/bin/dotnet')
    def test_build_csharp(self, mock_which, mock_exists):
        config = CSharpConfig(project_path="App.csproj", rid="linux-x64")
        cmd, _ = Builder.build_csharp(config)
        self.assertEqual(cmd[0], "dotnet")
        self.assertIn("linux-x64", cmd)
        self.assertIn("--self-contained=true", cmd)

    @patch('os.path.exists', return_value=True)
    @patch('shutil.which', return_value='/usr/bin/npx')
    def test_build_node(self, mock_which, mock_exists):
        config = NodeConfig(entry="app.js")
        cmd, _ = Builder.build_node(config)
        self.assertIn("pkg", cmd)
        self.assertIn("app.js", cmd)

    @patch('os.path.exists', return_value=True)
    @patch('shutil.which', return_value='/usr/bin/jpackage')
    def test_build_java(self, mock_which, mock_exists):
        config = JavaConfig(input_path=".", main_jar="app.jar", output_type="msi")
        cmd, _ = Builder.build_java(config)
        self.assertEqual(cmd[0], "jpackage")
        self.assertIn("--type=msi", cmd)
        self.assertIn("app.jar", cmd)

if __name__ == '__main__':
    unittest.main()
