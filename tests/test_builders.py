import unittest
from unittest.mock import patch
import os
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from core.config import AndroidConfig, PythonConfig, PythonAndroidConfig, CSharpConfig, NodeConfig, JavaConfig
from core.builders import Builder
from core.python_android import find_built_artifacts, suggest_python_android_assets, suggest_python_android_requirements

class TestBuilders(unittest.TestCase):

    @patch('os.path.exists', return_value=True)
    @patch('shutil.which', return_value='/usr/bin/python')
    def test_build_python_pyinstaller(self, mock_which, mock_exists):
        config = PythonConfig(entry="main.py", backend="pyinstaller")
        cmd, _ = Builder.build_python(config)
        self.assertIn("PyInstaller", cmd[2])
        self.assertIn("--onefile", cmd)

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


    @patch('core.python_android.shutil.which', return_value='/bin/sh')
    def test_build_python_android_generates_staging_project(self, mock_which):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / "pyapp"
            source_dir.mkdir()
            (source_dir / "app.py").write_text('__version__ = "1.2.3"\nprint("hello")\n', encoding='utf-8')
            (source_dir / "helper.py").write_text('print("helper")\n', encoding='utf-8')

            config = PythonAndroidConfig(
                entry=str(source_dir / "app.py"),
                app_name="Demo Python App",
                package_domain="com.demo",
                package_name="demo-python-app",
                requirements="kivy,requests",
                orientation="landscape",
                build_mode="debug",
            )
            result = Builder.build_python_android(config)

            stage_dir = Path(result["project_dir"])
            self.assertTrue(stage_dir.exists())
            self.assertEqual(result["cmd"][-1], "debug")
            self.assertTrue(result["buildozer_spec"].endswith("buildozer.spec"))
            self.assertEqual(result["cwd"], str(stage_dir))
            self.assertTrue((stage_dir / "buildozer.spec").exists())
            self.assertTrue((stage_dir / "app" / "app.py").exists())
            self.assertTrue((stage_dir / "app" / "helper.py").exists())
            wrapper = (stage_dir / "app" / "main.py").read_text(encoding='utf-8')
            self.assertIn("runpy.run_path", wrapper)
            self.assertIn("app.py", wrapper)

            spec = (stage_dir / "buildozer.spec").read_text(encoding='utf-8')
            self.assertIn("title = Demo Python App", spec)
            self.assertIn("package.name = demopythonapp", spec)
            self.assertIn("package.domain = com.demo", spec)
            self.assertIn("version = 1.2.3", spec)
            self.assertIn("requirements = python3,kivy,requests", spec)
            self.assertIn("orientation = landscape", spec)
            self.assertIn("android.permissions = INTERNET", spec)
            self.assertIn("source.dir = app", spec)
            self.assertIn("android.api = 35", spec)
            self.assertIn("bin", result["artifact_dir"])
            self.assertIn("Python Android packaging project generated successfully.", result["log_text"])

    @patch('core.python_android.shutil.which', return_value='/bin/sh')
    def test_build_python_android_uses_existing_main(self, mock_which):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / "pyapp"
            source_dir.mkdir()
            (source_dir / "main.py").write_text('print("hello")\n', encoding='utf-8')

            config = PythonAndroidConfig(
                entry=str(source_dir / "main.py"),
                app_name="My App",
                build_mode="release",
            )
            result = Builder.build_python_android(config)

            stage_dir = Path(result["project_dir"])
            staged_main = (stage_dir / "app" / "main.py").read_text(encoding='utf-8')
            self.assertEqual(staged_main, 'print("hello")\n')
            self.assertEqual(result["cmd"][-1], "release")
            self.assertIn("package.domain = org.compass", (stage_dir / "buildozer.spec").read_text(encoding='utf-8'))

    @patch('core.python_android.shutil.which', return_value='/bin/sh')
    def test_build_python_android_supports_permissions_and_manual_assets(self, mock_which):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / "pyapp"
            (source_dir / "assets").mkdir(parents=True)
            (source_dir / "main.py").write_text('print("hello")\n', encoding='utf-8')
            (source_dir / "assets" / "custom-icon.png").write_text('icon', encoding='utf-8')
            (source_dir / "assets" / "custom-splash.png").write_text('splash', encoding='utf-8')

            config = PythonAndroidConfig(
                entry=str(source_dir / "main.py"),
                app_name="My App",
                permissions="INTERNET, CAMERA, RECORD_AUDIO",
                orientation="portrait-reverse",
                min_sdk=26,
                target_sdk=34,
                icon_path="assets/custom-icon.png",
                presplash_path="assets/custom-splash.png",
            )
            result = Builder.build_python_android(config)

            stage_dir = Path(result["project_dir"])
            spec = (stage_dir / "buildozer.spec").read_text(encoding='utf-8')
            readme = (stage_dir / "README.md").read_text(encoding='utf-8')
            self.assertIn("android.permissions = INTERNET,CAMERA,RECORD_AUDIO", spec)
            self.assertIn("orientation = portrait-reverse", spec)
            self.assertIn("android.minapi = 26", spec)
            self.assertIn("android.api = 34", spec)
            self.assertIn("icon.filename = app/assets/custom-icon.png", spec)
            self.assertIn("presplash.filename = app/assets/custom-splash.png", spec)
            self.assertIn("Permissions: `INTERNET,CAMERA,RECORD_AUDIO`", readme)


    @patch('core.python_android.shutil.which')
    @patch('core.python_android.is_windows_mount_path', return_value=True)
    @patch('core.python_android.is_probably_wsl', return_value=True)
    def test_build_python_android_adds_environment_hints(self, mock_wsl, mock_mount, mock_which):
        def which_side_effect(name):
            if name == 'buildozer':
                return '/bin/sh'
            return None

        mock_which.side_effect = which_side_effect

        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / 'mnt' / 'c' / 'demoapp'
            source_dir.mkdir(parents=True)
            (source_dir / 'main.py').write_text('print("hello")\n', encoding='utf-8')

            config = PythonAndroidConfig(entry=str(source_dir / 'main.py'))
            result = Builder.build_python_android(config)

            self.assertIn('Environment Hints:', result['log_text'])
            self.assertIn('under /mnt/...', result['log_text'])
            self.assertIn('adb was not found in PATH', result['log_text'])
            self.assertIn('sdkmanager was not found in PATH', result['log_text'])

    def test_find_built_artifacts_prefers_latest_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            older = artifact_dir / 'app-debug.apk'
            newer = artifact_dir / 'app-release.aab'
            older.write_text('apk', encoding='utf-8')
            newer.write_text('aab', encoding='utf-8')
            os.utime(older, (1, 1))
            os.utime(newer, (2, 2))

            found = find_built_artifacts(str(artifact_dir))

            self.assertEqual(found[0], str(newer))
            self.assertEqual(found[1], str(older))

    def test_suggest_python_android_requirements_reads_project_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / "pyapp"
            source_dir.mkdir()
            (source_dir / "main.py").write_text('print("hello")\n', encoding='utf-8')
            (source_dir / "requirements.txt").write_text('requests>=2\nhttpx==0.27\n', encoding='utf-8')

            suggestion = suggest_python_android_requirements(str(source_dir / "main.py"))

            self.assertEqual(suggestion["requirements"], "python3,requests,httpx")
            self.assertIn("requirements.txt", suggestion["sources"])
            self.assertFalse(suggestion["uses_kivy"])

    def test_suggest_python_android_requirements_defaults_to_kivy_when_detected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / "pyapp"
            source_dir.mkdir()
            (source_dir / "main.py").write_text('from kivy.app import App\n', encoding='utf-8')

            suggestion = suggest_python_android_requirements(str(source_dir / "main.py"))

            self.assertEqual(suggestion["requirements"], "python3,kivy")
            self.assertEqual(suggestion["sources"], [])
            self.assertTrue(suggestion["uses_kivy"])


    def test_suggest_python_android_assets_detects_icon_and_presplash(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / "pyapp"
            (source_dir / "assets").mkdir(parents=True)
            (source_dir / "main.py").write_text('print("hello")\n', encoding='utf-8')
            (source_dir / "assets" / "icon.png").write_text('icon', encoding='utf-8')
            (source_dir / "assets" / "splash.png").write_text('splash', encoding='utf-8')

            suggestion = suggest_python_android_assets(str(source_dir / "main.py"))

            self.assertEqual(suggestion["icon_path"], "assets/icon.png")
            self.assertEqual(suggestion["presplash_path"], "assets/splash.png")


    @patch('core.python_android.shutil.which', return_value='/bin/sh')
    def test_build_python_android_warns_about_metadata_and_requirement_risks(self, mock_which):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / "pyapp"
            source_dir.mkdir()
            (source_dir / "main.py").write_text('print("hello")\n', encoding='utf-8')
            (source_dir / "requirements.txt").write_text('requests>=2\n', encoding='utf-8')
            (source_dir / "native_module.pyx").write_text('print("cython")\n', encoding='utf-8')

            config = PythonAndroidConfig(
                entry=str(source_dir / "main.py"),
                requirements="requests>=2,git+https://example.com/demo.git,cython",
            )
            result = Builder.build_python_android(config)

            self.assertIn("Compatibility Hints:", result["log_text"])
            self.assertIn("Direct URL, wheel, or VCS-style requirement entries were detected", result["log_text"])
            self.assertIn("Version ranges were detected in the Android requirements", result["log_text"])
            self.assertIn("Compiled/native source files were detected", result["log_text"])
            self.assertIn("native build steps were detected", result["log_text"])

    @patch('core.python_android.shutil.which', return_value='/bin/sh')
    def test_build_python_android_warns_when_project_metadata_exists_but_requirements_are_blank(self, mock_which):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / "pyapp"
            source_dir.mkdir()
            (source_dir / "main.py").write_text('print("hello")\n', encoding='utf-8')
            (source_dir / "pyproject.toml").write_text('[build-system]\nrequires = ["setuptools"]\n', encoding='utf-8')

            config = PythonAndroidConfig(
                entry=str(source_dir / "main.py"),
                requirements="",
            )
            result = Builder.build_python_android(config)

            readme = Path(result["project_dir"]) / "README.md"
            readme_text = readme.read_text(encoding='utf-8')
            self.assertIn("Project metadata files were detected (pyproject.toml)", result["log_text"])
            self.assertIn("## Compatibility Hints", readme_text)
            self.assertIn("pyproject.toml", readme_text)
    def test_build_android_generates_project(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / "webapp"
            output_dir = Path(temp_dir) / "android-project"
            (source_dir / "pages").mkdir(parents=True)
            (source_dir / "index.html").write_text(
                "<html><head></head><body><h1>Home</h1></body></html>",
                encoding="utf-8",
            )
            (source_dir / "pages" / "about.html").write_text(
                "<html><head></head><body><h1>About</h1></body></html>",
                encoding="utf-8",
            )

            config = AndroidConfig(
                source_dir=str(source_dir),
                output_dir=str(output_dir),
                app_name="Demo App",
                package_name="com.demo.app",
            )
            result = Builder.build_android(config)

            self.assertEqual(result["project_dir"], str(output_dir.resolve()))
            self.assertIsNone(result["cmd"])
            self.assertTrue((output_dir / "app" / "src" / "main" / "AndroidManifest.xml").exists())
            self.assertTrue((output_dir / "app" / "src" / "main" / "java" / "com" / "demo" / "app" / "MainActivity.java").exists())
            self.assertIn("Android project generated successfully.", result["log_text"])
            self.assertIn("Start Page: index.html", result["log_text"])
            self.assertIn("Android Gradle Plugin: 8.13.0", result["log_text"])

            root_html = (output_dir / "app" / "src" / "main" / "assets" / "app" / "index.html").read_text(encoding="utf-8")
            nested_html = (output_dir / "app" / "src" / "main" / "assets" / "app" / "pages" / "about.html").read_text(encoding="utf-8")
            self.assertIn('href="compass-mobile-adapter.css"', root_html)
            self.assertIn('src="compass-mobile-adapter.js"', root_html)
            self.assertIn('href="../compass-mobile-adapter.css"', nested_html)
            self.assertIn('src="../compass-mobile-adapter.js"', nested_html)

            settings_gradle = (output_dir / "settings.gradle").read_text(encoding="utf-8")
            colors_xml = (output_dir / "app" / "src" / "main" / "res" / "values" / "colors.xml").read_text(encoding="utf-8")
            app_build_gradle = (output_dir / "app" / "build.gradle").read_text(encoding="utf-8")
            readme = (output_dir / "README.md").read_text(encoding="utf-8")
            self.assertIn("COMPASS_USE_ALIYUN_MIRRORS", settings_gradle)
            self.assertIn("google()", settings_gradle)
            self.assertTrue(colors_xml.startswith("<?xml"))
            self.assertIn("com.android.application' version '8.13.0", (output_dir / "build.gradle").read_text(encoding="utf-8"))
            self.assertIn("androidx.webkit:webkit:1.15.0", app_build_gradle)
            self.assertIn("COMPASS_ANDROID_KEYSTORE_FILE", app_build_gradle)
            self.assertIn("keystore.properties.example", readme)
            self.assertTrue((output_dir / "keystore.properties.example").exists())
            self.assertTrue((output_dir / "app" / "src" / "main" / "res" / "xml" / "network_security_config.xml").exists())

    def test_build_android_prefers_dist_output_for_frontend_roots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / "frontend"
            output_dir = Path(temp_dir) / "android-project"
            (source_dir / "src").mkdir(parents=True)
            (source_dir / "dist" / "assets").mkdir(parents=True)
            (source_dir / "package.json").write_text('{"name":"demo"}', encoding="utf-8")
            (source_dir / "src" / "index.html").write_text('<html><body>wrong root</body></html>', encoding="utf-8")
            (source_dir / "dist" / "index.html").write_text('<html><body>correct dist</body></html>', encoding="utf-8")
            (source_dir / "dist" / "assets" / "app.js").write_text('console.log("ok")', encoding="utf-8")

            config = AndroidConfig(
                source_dir=str(source_dir),
                output_dir=str(output_dir),
                app_name="Demo App",
                package_name="com.demo.app",
            )
            result = Builder.build_android(config)

            self.assertIn(f"Web Root: {source_dir / 'dist'}", result["log_text"])
            copied_index = (output_dir / "app" / "src" / "main" / "assets" / "app" / "index.html").read_text(encoding="utf-8")
            self.assertIn("correct dist", copied_index)
            self.assertTrue((output_dir / "app" / "src" / "main" / "assets" / "app" / "assets" / "app.js").exists())
            self.assertFalse((output_dir / "app" / "src" / "main" / "assets" / "app" / "dist").exists())

    def test_build_android_prepares_gradle_apk_command(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / "webapp"
            output_dir = Path(temp_dir) / "android-project"
            sdk_dir = Path(temp_dir) / "AndroidSdk"
            gradle_dir = Path(temp_dir) / "gradle-bin"
            gradle_dir.mkdir()
            sdk_dir.mkdir()
            source_dir.mkdir()
            (source_dir / "index.html").write_text("<html><body>Hello</body></html>", encoding="utf-8")
            gradle_path = gradle_dir / ("gradle.bat" if os.name == "nt" else "gradle")
            gradle_path.write_text("@echo off\n" if os.name == "nt" else "#!/bin/sh\n", encoding="utf-8")

            config = AndroidConfig(
                source_dir=str(source_dir),
                output_dir=str(output_dir),
                build_mode="apk_debug",
                gradle_path=str(gradle_path),
                android_sdk_path=str(sdk_dir),
            )
            result = Builder.build_android(config)

            self.assertEqual(result["cmd"][-1], "assembleDebug")
            self.assertIn("--no-daemon", result["cmd"])
            self.assertTrue(result["artifact_dir"].endswith(os.path.join("app", "build", "outputs", "apk", "debug")))
            self.assertTrue((output_dir / "local.properties").exists())
            self.assertIn("Gradle Task: assembleDebug", result["log_text"])
            self.assertIn("JDK 17+", result["log_text"])

    @patch("core.android_project.shutil.which", return_value=None)
    @patch("core.android_project.Path.home")
    def test_build_android_detects_gradle_from_wrapper_cache(self, mock_home, mock_which):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_dir = temp_path / "webapp"
            output_dir = temp_path / "android-project"
            sdk_dir = temp_path / "AndroidSdk"
            cached_gradle = temp_path / ".gradle" / "wrapper" / "dists" / "gradle-8.14-all" / "hash" / "gradle-8.14" / "bin"

            source_dir.mkdir()
            sdk_dir.mkdir()
            cached_gradle.mkdir(parents=True)
            (source_dir / "index.html").write_text("<html><body>Hello</body></html>", encoding="utf-8")
            (cached_gradle / ("gradle.bat" if os.name == "nt" else "gradle")).write_text("stub", encoding="utf-8")
            mock_home.return_value = temp_path

            config = AndroidConfig(
                source_dir=str(source_dir),
                output_dir=str(output_dir),
                build_mode="apk_debug",
                android_sdk_path=str(sdk_dir),
            )
            result = Builder.build_android(config)

            self.assertIn("assembleDebug", result["cmd"])
            self.assertIn(".gradle", result["cmd"][0])

    def test_build_android_rejects_output_inside_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / "webapp"
            output_dir = source_dir / "android-project"
            source_dir.mkdir()
            (source_dir / "index.html").write_text("<html></html>", encoding="utf-8")

            config = AndroidConfig(source_dir=str(source_dir), output_dir=str(output_dir))

            with self.assertRaises(ValueError):
                Builder.build_android(config)

if __name__ == '__main__':
    unittest.main()
