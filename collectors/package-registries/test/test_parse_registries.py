#!/usr/bin/env python3
"""Tests for the package-registries parser."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PARSER = os.path.join(os.path.dirname(HERE), "parse_registries.py")


def run(files, ecosystems=""):
    """Write `files` into a temp repo, run the parser, return parsed output."""
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for name, content in files.items():
            full = os.path.join(tmp, name)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(content)
            paths.append(name)
        env = dict(os.environ, ECOSYSTEMS=ecosystems)
        proc = subprocess.run(
            [sys.executable, PARSER],
            input="\n".join(paths),
            capture_output=True,
            text=True,
            cwd=tmp,
            env=env,
        )
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout) if proc.stdout.strip() else None


def hosts(result, ecosystem=None):
    entries = result["registries"]
    if ecosystem:
        entries = [e for e in entries if e["ecosystem"] == ecosystem]
    return sorted({e["host"] for e in entries})


class TestNpm(unittest.TestCase):
    def test_explicit_registry(self):
        r = run({".npmrc": "registry=https://dl.cloudsmith.io/basic/acme/npm/\n",
                 "package.json": "{}"})
        self.assertEqual(hosts(r, "npm"), ["dl.cloudsmith.io"])
        self.assertFalse(r["summary"]["has_public"])
        self.assertFalse(r["registries"][0]["is_default"])

    def test_scoped_registry(self):
        r = run({".npmrc": "@acme:registry=https://dl.cloudsmith.io/basic/acme/npm/\n"
                           "registry=https://registry.npmjs.org/\n",
                 "package.json": "{}"})
        self.assertEqual(hosts(r, "npm"), ["dl.cloudsmith.io", "registry.npmjs.org"])
        scoped = [e for e in r["registries"] if e.get("name") == "@acme"]
        self.assertEqual(len(scoped), 1)

    def test_auth_token_never_emitted(self):
        r = run({".npmrc": "//dl.cloudsmith.io/basic/acme/npm/:_authToken=SUPERSECRET\n"
                           "registry=https://dl.cloudsmith.io/basic/acme/npm/\n",
                 "package.json": "{}"})
        self.assertNotIn("SUPERSECRET", json.dumps(r))
        self.assertEqual(hosts(r, "npm"), ["dl.cloudsmith.io"])

    def test_credentials_in_url_are_stripped(self):
        r = run({".npmrc": "registry=https://user:hunter2@nexus.acme.com/repo/\n",
                 "package.json": "{}"})
        self.assertNotIn("hunter2", json.dumps(r))
        self.assertEqual(hosts(r, "npm"), ["nexus.acme.com"])


class TestImplicitDefaults(unittest.TestCase):
    """The load-bearing behaviour: no config still means a real registry."""

    def test_package_json_without_npmrc_reports_public_default(self):
        r = run({"package.json": '{"name":"svc"}'})
        self.assertEqual(hosts(r, "npm"), ["registry.npmjs.org"])
        entry = r["registries"][0]
        self.assertTrue(entry["is_default"])
        self.assertTrue(entry["is_public"])
        self.assertEqual(entry["path"], "package.json")
        self.assertTrue(r["summary"]["has_public"])

    def test_pom_without_repositories_reports_maven_central(self):
        r = run({"pom.xml": "<project><modelVersion>4.0.0</modelVersion></project>"})
        self.assertEqual(hosts(r, "maven"), ["repo.maven.apache.org"])
        self.assertTrue(r["registries"][0]["is_default"])

    def test_csproj_without_nuget_config_reports_nuget_org(self):
        r = run({"App.csproj": "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>"})
        self.assertEqual(hosts(r, "nuget"), ["api.nuget.org"])
        self.assertTrue(r["registries"][0]["is_default"])

    def test_explicit_registry_suppresses_the_default(self):
        r = run({"package.json": "{}",
                 ".npmrc": "registry=https://dl.cloudsmith.io/basic/acme/npm/\n"})
        self.assertEqual(hosts(r, "npm"), ["dl.cloudsmith.io"])
        self.assertFalse(any(e["is_default"] for e in r["registries"]))

    def test_extra_index_alone_does_not_suppress_the_default(self):
        # An extra index does not replace the primary — PyPI is still in play.
        r = run({"requirements.txt": "--extra-index-url https://dl.cloudsmith.io/x/py/simple\nflask\n"})
        self.assertEqual(hosts(r, "pip"), ["dl.cloudsmith.io", "pypi.org"])
        self.assertTrue(r["summary"]["has_public"])


class TestPip(unittest.TestCase):
    def test_requirements_index_url(self):
        r = run({"requirements.txt": "--index-url https://dl.cloudsmith.io/x/py/simple\nflask==2.0\n"})
        self.assertEqual(hosts(r, "pip"), ["dl.cloudsmith.io"])

    def test_requirements_short_flag(self):
        r = run({"requirements.txt": "-i https://dl.cloudsmith.io/x/py/simple\n"})
        self.assertEqual(hosts(r, "pip"), ["dl.cloudsmith.io"])

    def test_pip_conf(self):
        r = run({"pip.conf": "[global]\nindex-url = https://dl.cloudsmith.io/x/py/simple\n",
                 "requirements.txt": "flask\n"})
        self.assertEqual(hosts(r, "pip"), ["dl.cloudsmith.io"])

    def test_pip_conf_underscore_alias(self):
        r = run({"pip.conf": "[global]\nextra_index_url = https://extra.acme.com/simple\n"
                             "index_url = https://dl.cloudsmith.io/x/py/simple\n"})
        self.assertEqual(hosts(r, "pip"), ["dl.cloudsmith.io", "extra.acme.com"])

    def test_pyproject_poetry_source(self):
        r = run({"pyproject.toml": '[[tool.poetry.source]]\nname = "acme"\n'
                                   'url = "https://dl.cloudsmith.io/x/py/simple"\n'})
        self.assertEqual(hosts(r, "pip"), ["dl.cloudsmith.io"])
        self.assertEqual(r["registries"][0].get("name"), "acme")

    def test_pyproject_uv_index(self):
        r = run({"pyproject.toml": '[[tool.uv.index]]\nname = "acme"\n'
                                   'url = "https://dl.cloudsmith.io/x/py/simple"\ndefault = true\n'})
        self.assertEqual(hosts(r, "pip"), ["dl.cloudsmith.io"])


class TestOddPyproject(unittest.TestCase):
    """A pyproject.toml is valid TOML of arbitrary shape.

    `[tool]` with `poetry = "1.9.0"` is legal and just declares no sources.
    Traversing it with plain .get() chains raised AttributeError, which escaped
    the backstop and killed the whole collector — every ecosystem at once, over
    one odd file. Worst on a monorepo walking many pyproject files.
    """

    SHAPES = {
        "scalar tool.poetry": '[tool]\npoetry = "1.9.0"\n',
        "scalar top-level tool": 'tool = "x"\n',
        "source is not a list": '[tool.poetry]\nsource = "notalist"\n',
        "uv index is a number": "[tool.uv]\nindex = 42\n",
        "poetry is a list": "[[tool.poetry]]\nname = 'x'\n",
    }

    def test_odd_shapes_do_not_break_collection(self):
        for label, content in self.SHAPES.items():
            with self.subTest(shape=label):
                r = run({"pyproject.toml": content, "package.json": "{}"})
                # npm must not become collateral damage
                self.assertEqual(r["ecosystems"], ["npm", "pip"])
                # pip declared no source, so its public default applies
                pip = [e for e in r["registries"] if e["ecosystem"] == "pip"]
                self.assertEqual([e["host"] for e in pip], ["pypi.org"])
                self.assertTrue(pip[0]["is_default"])
                # valid TOML that declares no sources is not an error
                self.assertEqual(r.get("errors", []), [])

    def test_real_sources_still_parsed(self):
        """The hardening must not stop valid tables from being read."""
        r = run({"pyproject.toml": '[[tool.poetry.source]]\nname = "acme"\n'
                                   'url = "https://dl.cloudsmith.io/x/py/simple"\n'})
        self.assertEqual(hosts(r, "pip"), ["dl.cloudsmith.io"])


class TestBackstop(unittest.TestCase):
    """An unanticipated parser failure must be recorded, never fatal."""

    def _module(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("parse_registries", PARSER)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_unexpected_exception_is_recorded_not_raised(self):
        mod = self._module()
        original = mod.parse_pyproject

        def boom(*_args, **_kwargs):
            raise AttributeError("'str' object has no attribute 'get'")

        mod.parse_pyproject = boom
        try:
            reg = mod.Registries(mod.ALL_ECOSYSTEMS)
            errors = []
            with tempfile.TemporaryDirectory() as tmp:
                p = os.path.join(tmp, "pyproject.toml")
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write("[tool.poetry]\n")
                mod.handle(reg, p, "pyproject", errors)
            self.assertEqual(len(errors), 1)
            self.assertIn("AttributeError", errors[0]["error"])
            # ecosystem still detected, so the default is still reported
            self.assertIn("pip", reg.detected)
        finally:
            mod.parse_pyproject = original


class TestMaven(unittest.TestCase):
    POM = """<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <repositories>
    <repository><id>acme</id><url>https://dl.cloudsmith.io/basic/acme/mvn/</url></repository>
  </repositories>
  <pluginRepositories>
    <pluginRepository><id>plugins</id><url>https://plugins.acme.com/m2</url></pluginRepository>
  </pluginRepositories>
  <distributionManagement>
    <repository><id>releases</id><url>https://dl.cloudsmith.io/basic/acme/releases/</url></repository>
  </distributionManagement>
</project>"""

    def test_namespaced_pom(self):
        r = run({"pom.xml": self.POM})
        self.assertIn("dl.cloudsmith.io", hosts(r, "maven"))
        kinds = {e["kind"] for e in r["registries"]}
        self.assertEqual(kinds, {"primary", "plugin", "publish"})

    def test_settings_xml_mirror(self):
        settings = """<settings><mirrors>
          <mirror><id>central</id><url>https://dl.cloudsmith.io/basic/acme/mvn/</url>
          <mirrorOf>*</mirrorOf></mirror></mirrors></settings>"""
        r = run({"settings.xml": settings, "pom.xml": "<project/>"})
        mirror = [e for e in r["registries"] if e["kind"] == "mirror"]
        self.assertEqual(len(mirror), 1)
        # A mirror counts as a primary, so Maven Central is not added as default.
        self.assertNotIn("repo.maven.apache.org", hosts(r, "maven"))

    def test_malformed_xml_is_reported_not_fatal(self):
        r = run({"pom.xml": "<project><unclosed>"})
        self.assertIn("errors", r)
        # Ecosystem still detected, so the default is still reported.
        self.assertEqual(hosts(r, "maven"), ["repo.maven.apache.org"])


class TestGradle(unittest.TestCase):
    def test_maven_url_block(self):
        r = run({"build.gradle": 'repositories { maven { url "https://dl.cloudsmith.io/basic/acme/mvn/" } }'})
        self.assertEqual(hosts(r, "gradle"), ["dl.cloudsmith.io"])

    def test_kts_uri_form(self):
        r = run({"build.gradle.kts": 'repositories { maven { url = uri("https://dl.cloudsmith.io/x/mvn/") } }'})
        self.assertEqual(hosts(r, "gradle"), ["dl.cloudsmith.io"])

    def test_maven_central_shorthand_is_public(self):
        r = run({"build.gradle": "repositories { mavenCentral() }"})
        self.assertEqual(hosts(r, "gradle"), ["repo.maven.apache.org"])
        self.assertTrue(r["summary"]["has_public"])

    def test_commented_out_repository_is_ignored(self):
        r = run({"build.gradle": 'repositories {\n'
                                 '  // maven { url "https://evil.example.com/m2" }\n'
                                 '  maven { url "https://dl.cloudsmith.io/x/mvn/" }\n}'})
        self.assertEqual(hosts(r, "gradle"), ["dl.cloudsmith.io"])

    def test_unresolved_variable_is_skipped(self):
        r = run({"build.gradle": 'repositories { maven { url "$artifactoryUrl/repo" } }'})
        self.assertEqual(hosts(r, "gradle"), ["repo.maven.apache.org"])
        self.assertTrue(r["registries"][0]["is_default"])


class TestRubyGems(unittest.TestCase):
    def test_gemfile_source(self):
        r = run({"Gemfile": 'source "https://dl.cloudsmith.io/basic/acme/gems/"\ngem "rails"\n'})
        self.assertEqual(hosts(r, "rubygems"), ["dl.cloudsmith.io"])

    def test_public_rubygems(self):
        r = run({"Gemfile": 'source "https://rubygems.org"\n'})
        self.assertEqual(hosts(r, "rubygems"), ["rubygems.org"])
        self.assertTrue(r["summary"]["has_public"])


class TestNuGet(unittest.TestCase):
    def test_package_sources(self):
        cfg = """<?xml version="1.0"?><configuration><packageSources><clear />
          <add key="acme" value="https://dl.cloudsmith.io/basic/acme/nuget/index.json" />
        </packageSources></configuration>"""
        r = run({"nuget.config": cfg})
        self.assertEqual(hosts(r, "nuget"), ["dl.cloudsmith.io"])

    def test_case_insensitive_filename(self):
        cfg = """<configuration><packageSources>
          <add key="nuget.org" value="https://api.nuget.org/v3/index.json" />
        </packageSources></configuration>"""
        r = run({"NuGet.Config": cfg})
        self.assertEqual(hosts(r, "nuget"), ["api.nuget.org"])
        self.assertTrue(r["summary"]["has_public"])


class TestAggregate(unittest.TestCase):
    def test_polyglot_repo(self):
        r = run({
            "svc-node/package.json": "{}",
            "svc-node/.npmrc": "registry=https://dl.cloudsmith.io/basic/acme/npm/\n",
            "svc-py/requirements.txt": "--index-url https://pypi.org/simple\n",
            "svc-java/pom.xml": "<project/>",
        })
        self.assertEqual(r["ecosystems"], ["maven", "npm", "pip"])
        self.assertEqual(
            r["registries_used"],
            ["dl.cloudsmith.io", "pypi.org", "repo.maven.apache.org"],
        )
        self.assertTrue(r["summary"]["has_public"])

    def test_no_package_manager_writes_nothing(self):
        self.assertIsNone(run({"README.md": "# docs only"}))

    def test_ecosystems_filter(self):
        r = run({"package.json": "{}", "pom.xml": "<project/>"}, ecosystems="npm")
        self.assertEqual(r["ecosystems"], ["npm"])
        self.assertEqual(hosts(r), ["registry.npmjs.org"])

    def test_summary_matches_entries(self):
        r = run({"package.json": "{}",
                 ".npmrc": "registry=https://dl.cloudsmith.io/basic/acme/npm/\n"})
        self.assertEqual(
            r["summary"]["has_public"],
            any(e["is_public"] for e in r["registries"]),
        )
        self.assertEqual(
            r["registries_used"], sorted({e["host"] for e in r["registries"]})
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
