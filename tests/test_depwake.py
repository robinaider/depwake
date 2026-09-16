"""Depwake unit tests (stdlib unittest). Registry is stubbed — no network."""

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from depwake.apply import apply_plan  # noqa: E402
from depwake.manifests import discover  # noqa: E402
from depwake.plan import build  # noqa: E402
from depwake.registry import Latest  # noqa: E402
from depwake.semver import classify, parse  # noqa: E402

STUB = {
    ("npm", "left-pad"): "1.3.1",      # patch ahead of lock 1.3.0
    ("npm", "express"): "5.0.0",       # major ahead of lock 4.17.0
    ("npm", "chalk"): "4.1.2",         # same
    ("pypi", "requests"): "2.32.0",    # minor ahead of pin 2.28.0
    ("pypi", "six"): "1.16.0",         # same
}


def stub_fetch(eco: str, name: str) -> Latest:
    base = name.split("[")[0]
    if (eco, base) in STUB:
        return Latest(STUB[(eco, base)], f"https://example.test/{base}")
    return Latest(None, "", "not in stub")


PKG = {
    "dependencies": {"express": "^4.17.0", "left-pad": "~1.3.0"},
    "devDependencies": {"chalk": "^4.1.0"},
}
LOCK = {
    "lockfileVersion": 3,
    "packages": {
        "": {},
        "node_modules/express": {"version": "4.17.0"},
        "node_modules/left-pad": {"version": "1.3.0"},
        "node_modules/chalk": {"version": "4.1.2"},
    },
}
REQS = "requests==2.28.0\nsix==1.16.0\n"


def make_proj(d: Path) -> Path:
    (d / "package.json").write_text(json.dumps(PKG))
    (d / "package-lock.json").write_text(json.dumps(LOCK))
    (d / "requirements.txt").write_text(REQS)
    return d


class TestSemver(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(classify(parse("1.2.3"), parse("1.2.9")), "patch")
        self.assertEqual(classify(parse("1.2.3"), parse("1.9.0")), "minor")
        self.assertEqual(classify(parse("1.2.3"), parse("2.0.0")), "major")
        self.assertEqual(classify(parse("1.2.3"), parse("1.2.3")), "same")
        self.assertEqual(classify(parse("0.2.3"), parse("0.9.0")), "major")  # pre-1.0

    def test_parse_rejects_junk(self):
        self.assertIsNone(parse(None))
        self.assertIsNone(parse("latest"))
        self.assertIsNotNone(parse("v1.2.3"))


class TestPlan(unittest.TestCase):
    def test_grouping(self):
        with tempfile.TemporaryDirectory() as d:
            deps, _ = discover(make_proj(Path(d)))
            plan = build(deps, fetcher=stub_fetch, advisory_fetcher=lambda spec: {})
        by_name = {i.dep.name: i for i in plan.items}
        self.assertEqual(by_name["express"].risk, "major")
        self.assertEqual(by_name["left-pad"].risk, "patch")
        self.assertEqual(by_name["chalk"].risk, "same")
        self.assertEqual(by_name["requests"].risk, "minor")
        self.assertEqual(by_name["six"].risk, "same")
        self.assertTrue(all(i.dep.current_source in ("lock", "pin") for i in plan.items))

    def test_unknown_without_lock(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "package.json").write_text(json.dumps({"dependencies": {"x": "*"}}))
            deps, _ = discover(root)
            plan = build(deps, fetcher=stub_fetch, advisory_fetcher=lambda spec: {})
        self.assertEqual(plan.items[0].risk, "unknown")


class TestApply(unittest.TestCase):
    def test_patch_only_by_default(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_proj(Path(d))
            deps, _ = discover(root)
            plan = build(deps, fetcher=stub_fetch, advisory_fetcher=lambda spec: {})
            res = apply_plan(root, plan)
            pkg = json.loads((root / "package.json").read_text())
            self.assertEqual(pkg["dependencies"]["left-pad"], "~1.3.1")  # bumped
            self.assertEqual(pkg["dependencies"]["express"], "^4.17.0")  # major untouched
            reqs = (root / "requirements.txt").read_text()
            self.assertIn("requests==2.28.0", reqs)  # minor untouched by default
            self.assertTrue((root / "package.json.bak").exists())  # backup kept
            self.assertTrue(any("major" in s for s in res.skipped))

    def test_include_minor_and_dry_run(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_proj(Path(d))
            deps, _ = discover(root)
            plan = build(deps, fetcher=stub_fetch, advisory_fetcher=lambda spec: {})
            res = apply_plan(root, plan, include={"patch", "minor"}, dry_run=True)
            self.assertIn("requests==2.28.0", (root / "requirements.txt").read_text())
            self.assertFalse((root / "requirements.txt.bak").exists())  # dry run writes nothing
            self.assertTrue(any("requests" in c for c in res.changed))

    def test_no_manifest_is_usage_error(self):
        from depwake.cli import main
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(main(["plan", d]), 2)


class TestAdvisories(unittest.TestCase):
    def _plan(self):
        from depwake.registry import Advisory
        with tempfile.TemporaryDirectory() as d:
            deps, _ = discover(make_proj(Path(d)))
        def adv_stub(depspec):
            return {("npm", "left-pad"): [Advisory("GHSA-x", "bad pad", "High", 7.5, "1.3.1",
                                                   "https://osv.dev/vulnerability/GHSA-x")]}
        return build(deps, fetcher=stub_fetch, advisory_fetcher=adv_stub)

    def test_advisory_note_and_counts(self):
        plan = self._plan()
        left = next(i for i in plan.items if i.dep.name == "left-pad")
        self.assertIn("🔒 1 advisory", left.note)
        self.assertIn("GHSA-x", left.note)
        self.assertEqual(plan.advisory_count(), 1)
        # security rows sort first inside their risk group
        patches = plan.grouped()["patch"]
        self.assertEqual(patches[0].dep.name, "left-pad")

    def test_offline_degrades(self):
        from depwake.cli import main
        with tempfile.TemporaryDirectory() as d:
            root = make_proj(Path(d))
            self.assertEqual(main(["plan", str(root), "--offline", "--format", "json"]), 0)


class TestCache(unittest.TestCase):
    def test_roundtrip_and_ttl(self):
        from depwake import cache
        key = "depwake-test-key"
        cache.put(key, {"version": "1.2.3"})
        self.assertEqual(cache.get(key), {"version": "1.2.3"})
        self.assertIsNone(cache.get(key, ttl=-1))  # expired
        self.assertIsNone(cache.get("depwake-missing-key"))


class TestManifestEdges(unittest.TestCase):
    def test_requirement_includes_and_markers(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "requirements.txt").write_text(
                "-r extra.txt\n"
                "uvicorn==0.20.0; python_version > '3.8'\n"
                "gunicorn>=20.0 \\\n"
                "  ; sys_platform != 'win32'\n")
            (root / "extra.txt").write_text("httpx==0.23.0\n-r requirements.txt\n")
            deps, _ = discover(root)
        by_name = {x.name: x for x in deps}
        self.assertEqual(by_name["httpx"].current, "0.23.0")  # include followed
        self.assertEqual(by_name["uvicorn"].current, "0.20.0")  # marker stripped
        self.assertEqual(by_name["gunicorn"].current, "20.0.0")  # continuation joined + padded
        self.assertEqual(len(deps), 3)  # include cycle terminates, no dupes

    def test_git_urls_and_aliases_are_unknown_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "package.json").write_text(json.dumps({
                "dependencies": {
                    "myfork": "github:user/myfork#v1.0.0",
                    "real": "npm:actual@1.2.3",
                }}))
            deps, _ = discover(root)
            plan = build(deps, fetcher=stub_fetch, advisory_fetcher=lambda spec: {})
        risks = {i.dep.name: i.risk for i in plan.items}
        self.assertEqual(risks["myfork"], "unknown")
        self.assertEqual(risks["real"], "unknown")

    def test_pyproject_optionals_noted_not_counted(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "pyproject.toml").write_text(
                "[project]\nname = 'x'\ndependencies = ['a==1.0.0']\n"
                "[project.optional-dependencies]\ntest = ['pytest==7.0.0']\n")
            deps, notes = discover(root)
        self.assertEqual([x.name for x in deps], ["a"])
        self.assertTrue(any("optional" in n for n in notes))

    def test_verify_reports_and_strict_gates(self):
        from depwake.cli import main
        with tempfile.TemporaryDirectory() as d:
            root = make_proj(Path(d))
            self.assertEqual(main(["verify", str(root)]), 0)
            (root / "requirements.txt").write_text("mystery\n")
            self.assertEqual(main(["verify", str(root), "--strict"]), 1)


class TestSmoothUX(unittest.TestCase):
    def test_color_never_has_no_escapes(self):
        from depwake.report import format_text
        with tempfile.TemporaryDirectory() as d:
            deps, _ = discover(make_proj(Path(d)))
            plan = build(deps, fetcher=stub_fetch, advisory_fetcher=lambda spec: {})
        plain = format_text(plan, color=False)
        self.assertNotIn("\033[", plain)
        colored = format_text(plan, color=True)
        self.assertIn("\033[", colored)
        # same content modulo escapes
        self.assertEqual(re.sub(r"\033\[[0-9;]*m", "", colored), plain)

    def test_config_ignore_and_fail_on(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_proj(Path(d))
            (root / "depwake.toml").write_text('ignore = ["express"]\nfail_on = "minor"\n')
            deps, notes, ignored, fail_on = __import__(
                "depwake.cli", fromlist=["_resolve_config"])._resolve_config(
                    __import__("argparse").Namespace(root=str(root), fail_on=None))
            self.assertNotIn("express", [x.name for x in deps])
            self.assertEqual(ignored, ["express"])
            self.assertEqual(fail_on, "minor")
            self.assertTrue(any("ignored 1" in n for n in notes))

    def test_output_file_and_json_counts(self):
        import json
        import depwake.cli as cli_mod
        orig = cli_mod.fetch
        cli_mod.fetch = lambda eco, name, timeout=10.0: stub_fetch(eco, name)
        try:
            with tempfile.TemporaryDirectory() as d:
                root = make_proj(Path(d))
                out = Path(d) / "plan.json"
                self.assertEqual(cli_mod.main(["plan", str(root), "--format", "json",
                                               "--no-advisories", "--no-cache",
                                               "-o", str(out), "--quiet"]), 0)
                data = json.loads(out.read_text())
                self.assertIn("counts", data)
                self.assertIn("advisory_count", data)
                self.assertEqual(data["counts"]["major"], 1)
        finally:
            cli_mod.fetch = orig

    def test_min_severity_hides(self):
        from depwake.registry import Advisory
        with tempfile.TemporaryDirectory() as d:
            deps, _ = discover(make_proj(Path(d)))
        advs = [Advisory("LOW-1", "eh", "Low", 2.0, "9.9.9", "u"),
                Advisory("CRIT-1", "bad", "Critical", 9.8, "9.9.9", "u")]
        plan = build(deps, fetcher=stub_fetch,
                     advisory_fetcher=lambda spec: {("npm", "left-pad"): advs},
                     min_severity="High")
        left = next(i for i in plan.items if i.dep.name == "left-pad")
        self.assertEqual([a.id for a in left.advisories], ["CRIT-1"])
        self.assertTrue(any("hidden" in n for n in plan.notes))

    def test_apply_hints(self):
        import io
        from contextlib import redirect_stdout
        import depwake.cli as cli_mod
        orig = cli_mod.fetch
        cli_mod.fetch = lambda eco, name, timeout=10.0: stub_fetch(eco, name)
        try:
            with tempfile.TemporaryDirectory() as d:
                root = make_proj(Path(d))
                buf = io.StringIO()
                with redirect_stdout(buf):
                    cli_mod.main(["apply", str(root), "--no-advisories",
                                  "--no-cache", "--quiet"])
                self.assertIn("next:", buf.getvalue())
        finally:
            cli_mod.fetch = orig


if __name__ == "__main__":
    unittest.main()
