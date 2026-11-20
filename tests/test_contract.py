"""Tests of the contract (aigen/contract.py) and of the repository rules: one rule, one case. They need neither torch
nor a GPU and generate no image (AGENTS.md, "Testing").

    python3 tests/test_contract.py
"""
import ast
import glob
import os
import re
import sys
import tomllib
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from aigen import contract, generate, model, stages  # noqa: E402

EXAMPLE = os.path.join(ROOT, "examples", "request.json")


class Request(unittest.TestCase):
    def refuses(self, info, *fragments):
        with self.assertRaises(contract.RequestError) as c:
            contract.normalize(info)
        for f in fragments:
            self.assertIn(f, str(c.exception))
        return str(c.exception)

    def test_the_example_passes(self):
        r = contract.normalize(contract.read_request(EXAMPLE))
        self.assertEqual(r["request_version"], 1)

    def test_the_defaults(self):
        r = contract.normalize({"prompt": "1girl"})
        self.assertEqual((r["width"], r["height"], r["steps"], r["cfg"], r["sampler"], r["seed"]),
                         (1024, 1024, 25, 7.0, "euler_a", -1))
        self.assertTrue(r["quality"])
        self.assertEqual((r["style"], r["block_explicit"]), ("anime", True))
        self.assertEqual((r["loras"], r["hires"], r["face_fix"], r["sheet"], r["count"]), ([], None, None, None, 1))

    def test_does_not_change_the_given_dictionary(self):
        info = {"prompt": "1girl", "hires": True}
        contract.normalize(info)
        self.assertEqual(info, {"prompt": "1girl", "hires": True})

    def test_normalizing_twice_gives_the_same(self):
        r = contract.normalize({"prompt": "1girl", "hires": {"scale": 2}, "face_fix": True,
                                "loras": [{"name": "x", "weight": 0.5}]})
        self.assertEqual(contract.normalize(r), r)

    def test_no_version_is_version_1(self):
        contract.normalize({"prompt": "x"})
        contract.normalize({"prompt": "x", "request_version": 1.0})

    def test_unknown_version_is_refused(self):
        for v in (2, 0, "1", True, None):
            self.refuses({"prompt": "x", "request_version": v}, "request_version")

    def test_no_prompt_and_no_sheet_is_refused(self):
        self.refuses({}, "has nothing to generate")
        self.refuses({"prompt": "   "}, "has nothing to generate")
        contract.normalize({"sheet": "aiko"})

    def test_unknown_field_is_refused(self):
        self.refuses({"prompt": "x", "step": 20}, "unknown field 'step'")
        self.refuses({"prompt": "x", "hires": {"factor": 2}}, "'hires'", "'factor'")

    def test_values_out_of_range(self):
        bad = {"width": [255, 1000 + 1, 2056, 1024.0, "1024", True], "height": [0, -8],
               "steps": [0, 151, 2.5], "cfg": [0.5, 31, float("nan"), "7"], "sampler": ["Euler a", ""],
               "seed": [-2, 2 ** 32, 1.0], "count": [0, 65], "quality": [1, "yes"],
               "sheet": ["", "  ", 3], "prompt": [None, 1], "negative": [None],
               "style": ["manga", "", "none"], "block_explicit": [1, None, "true"]}
        for field, values in bad.items():
            for v in values:
                self.refuses({"prompt": "x", field: v}, "'%s'" % field)

    def test_values_at_the_limit_pass(self):
        contract.normalize({"prompt": "x", "width": 256, "height": 2048, "steps": 150, "cfg": 30, "seed": 0,
                            "count": 64})
        contract.normalize({"prompt": "x", "seed": 2 ** 32 - 1, "cfg": 1})
        self.assertIsNone(contract.normalize({"prompt": "x", "style": None})["style"])

    def test_hires_and_face_fix_off_on_and_with_fields(self):
        for off in (None, False):
            self.assertIsNone(contract.normalize({"prompt": "x", "hires": off})["hires"])
        h = contract.normalize({"prompt": "x", "hires": True})["hires"]
        self.assertEqual(h, {"scale": 1.5, "strength": 0.4, "steps": 15, "upscaler": "model"})
        f = contract.normalize({"prompt": "x", "face_fix": {"strength": 0.3}})["face_fix"]
        self.assertEqual((f["strength"], f["max_faces"]), (0.3, 4))
        self.refuses({"prompt": "x", "hires": {"scale": 1}}, "'scale'")
        self.refuses({"prompt": "x", "hires": {"upscaler": "esrgan"}}, "'upscaler'")
        self.refuses({"prompt": "x", "face_fix": {"strength": 0}}, "'strength'")
        self.refuses({"prompt": "x", "hires": "yes"}, "is not a JSON object")

    def test_hires_beyond_the_maximum_is_refused(self):
        self.refuses({"prompt": "x", "width": 2048, "hires": {"scale": 2.5}}, "the maximum is 4096")
        contract.normalize({"prompt": "x", "width": 2048, "hires": {"scale": 2}})

    def test_loras(self):
        r = contract.normalize({"prompt": "x", "loras": [{"name": " style "}, {"name": "b", "weight": -1}]})
        self.assertEqual(r["loras"], [{"name": "style", "weight": 1.0}, {"name": "b", "weight": -1.0}])
        self.refuses({"prompt": "x", "loras": [{"weight": 1}]}, "LoRA 1", "required field 'name'")
        self.refuses({"prompt": "x", "loras": [{"name": "a", "weight": 5}]}, "'weight'")
        self.refuses({"prompt": "x", "loras": "a:1"}, "'loras'")

    def test_hires_side_is_a_multiple_of_8(self):
        self.assertEqual(contract.hires_side(1024, 1.5), 1536)
        self.assertEqual(contract.hires_side(832, 1.3) % 8, 0)


class File(unittest.TestCase):
    def test_that_does_not_exist(self):
        with self.assertRaises(contract.RequestError) as c:
            contract.read_request(os.path.join(ROOT, "examples", "does_not_exist.json"))
        self.assertIn("request not found", str(c.exception))


class Codes(unittest.TestCase):
    def test_codes_and_versions(self):
        self.assertEqual((contract.OK, contract.GENERATION_FAILED, contract.BAD_REQUEST), (0, 1, 2))
        self.assertEqual((contract.REQUEST_VERSION, contract.SHEET_VERSION, contract.FORMAT_VERSION), (1, 1, 1))

    def test_wrong_option_exits_with_2_and_error(self):
        with self.assertRaises(SystemExit) as c:
            generate.parse_args(["--steps", "many", "x.png"])
        self.assertEqual(c.exception.code, contract.BAD_REQUEST)

    def test_the_contract_samplers_are_the_model_ones(self):
        self.assertEqual(set(contract.SAMPLERS), set(model.SCHEDULERS))


def _modules():
    mods = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "aigen", "*.py"))):
        with open(f, encoding="utf-8") as source:
            mods[os.path.basename(f)[:-3]] = ast.parse(source.read())
    return mods


class Structure(unittest.TestCase):
    """The code rules of aigen/: short functions, no import cycle and no heavy library imported at the top of a
    module (AGENTS.md, "Rules")."""

    HEAVY = {"torch", "diffusers", "transformers", "accelerate", "safetensors", "compel", "PIL", "numpy", "cv2",
             "spandrel", "gradio"}

    @classmethod
    def setUpClass(cls):
        cls.mods = _modules()

    def test_no_function_over_80_lines(self):
        long = ["%s.%s (%d lines)" % (m, n.name, n.end_lineno - n.lineno + 1)
                for m, t in self.mods.items() for n in ast.walk(t)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.end_lineno - n.lineno + 1 > 80]
        self.assertEqual(long, [])

    def test_no_module_imports_another_in_a_cycle(self):
        graph = {m: set() for m in self.mods}
        for m, t in self.mods.items():
            for n in ast.walk(t):
                if isinstance(n, ast.ImportFrom) and n.module == "aigen":
                    graph[m] |= {a.name for a in n.names if a.name in self.mods}
                elif isinstance(n, ast.ImportFrom) and (n.module or "").startswith("aigen."):
                    graph[m].add(n.module.split(".", 1)[1])

        def cycle(m, path):
            for d in sorted(graph[m]):
                if d in path:
                    return path[path.index(d):] + [d]
                c = cycle(d, path + [d])
                if c:
                    return c
            return None
        for m in self.mods:
            self.assertIsNone(cycle(m, [m]), "import cycle")

    def test_no_heavy_library_at_the_top(self):
        found = []
        for m, t in self.mods.items():
            top = [n for n in t.body if isinstance(n, (ast.Import, ast.ImportFrom, ast.If, ast.Try))]
            for node in top:
                for n in ast.walk(node):
                    if isinstance(n, ast.Import):
                        names = [a.name for a in n.names]
                    elif isinstance(n, ast.ImportFrom):
                        names = [n.module or ""]
                    else:
                        continue
                    found += ["%s: %s" % (m, x) for x in names if x.split(".")[0] in self.HEAVY]
        self.assertEqual(found, [])

    def test_every_stage_of_the_sequence_declares(self):
        for hires in (None, True):
            for face_fix in (None, True):
                r = contract.normalize({"prompt": "x", "hires": hires, "face_fix": face_fix})
                stages.check(generate.sequence(r))


class Launchers(unittest.TestCase):
    """The launchers in bin/: all of them find Python through bin/_python.sh (the lookup in one place) and stop with 2
    without it."""

    CALLERS = ("aigen.sh", "aigen_batch.sh", "aigen_web.sh")

    def read(self, name):
        with open(os.path.join(ROOT, "bin", name), encoding="utf-8") as f:
            return f.read()

    def test_the_lookup_in_one_place(self):
        for name in self.CALLERS:
            text = self.read(name)
            self.assertIn('/_python.sh"', text, name)
            self.assertIn('[ -n "$PY" ] || exit 2', text, name)
            self.assertNotIn(".venv", text, name + ": the lookup is the one in bin/_python.sh")

    def test_the_shortcut_finds_python_the_same_way_and_opens_the_browser(self):
        text = self.read("open_web.sh")
        self.assertIn('/_python.sh"', text)
        self.assertIn("-m aigen.web --open", text)
        self.assertIn("open_web.sh", self.read("install_shortcut.sh"))

    def test_each_launcher_calls_its_module(self):
        for name, mod in zip(self.CALLERS, ("generate", "batch", "web")):
            self.assertIn("-m aigen.%s " % mod, self.read(name), name)
            self.assertTrue(os.path.isfile(os.path.join(ROOT, "aigen", mod + ".py")))

    def test_they_are_executable(self):
        for name in self.CALLERS + ("open_web.sh", "install.sh", "install_shortcut.sh", "download_extras.sh"):
            self.assertTrue(os.access(os.path.join(ROOT, "bin", name), os.X_OK), name)


class Docs(unittest.TestCase):
    """What the documents say about the code is checked against the code."""

    def read(self, name):
        with open(os.path.join(ROOT, name), encoding="utf-8") as f:
            return f.read()

    def test_every_dependency_has_its_license_listed(self):
        with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
            deps = tomllib.load(f)["project"]["dependencies"]
        licenses = self.read(os.path.join("docs", "licenses.md")).lower()
        for d in deps:
            name = re.match(r"[A-Za-z0-9_.\-]+", d).group(0).lower()
            self.assertIn("| %s |" % name, licenses, "docs/licenses.md does not list " + name)

    def test_the_stage_table_is_the_one_the_stages_declare(self):
        r = contract.normalize({"prompt": "x", "hires": True, "face_fix": True})
        expected = [(stages.name(f), ", ".join(sorted(f.reads)), ", ".join(sorted(f.writes)))
                    for f in generate.sequence(r)]
        section = self.read("docs/how-it-works.md").split("## The stages in the code", 1)[1].split("\n## ", 1)[0]
        rows = re.findall(r"^\| `([a-z_]+\.[a-z_]+)` \| ([^|]*) \| ([^|]*) \|", section, re.M)
        found = [(n, reads.strip().replace("`", ""), writes.strip().replace("`", "")) for n, reads, writes in rows]
        self.assertEqual(found, expected)

    def test_every_request_field_is_in_the_contract(self):
        text = self.read(os.path.join("docs", "contract.md"))
        for field in list(contract.REQUEST_FIELDS) + ["loras", "hires", "face_fix", "request_version"]:
            self.assertTrue("`%s`" % field in text, "docs/contract.md does not mention the field " + field)
        for fields in (contract.HIRES_FIELDS, contract.FACE_FIELDS):
            for field in fields:
                self.assertTrue("`%s`" % field in text, "docs/contract.md does not mention the field " + field)


class Public(unittest.TestCase):
    """The repository is public (AGENTS.md, "Public repository"): no versioned file is an image, a model weight, a
    generation report or a generation log, and the secret scanner and .gitignore refuse all of them by name."""

    FORBIDDEN = ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.gif", "*.bmp", "*.avif", "*.safetensors", "*.ckpt", "*.pt",
                 "*.pth", "*.onnx", "*.gguf", "*.aigen.json", "aigen-web.log")

    def versioned(self):
        ls = Isolation.git("ls-tree", "-r", "-z", "--name-only", Isolation.REV) if Isolation.REV else \
            Isolation.git("ls-files", "-z")
        if ls is None:
            self.skipTest("no git")
        return [c for c in ls.split("\0") if c]

    def test_no_versioned_file_is_forbidden(self):
        import fnmatch
        found = [c for c in self.versioned()
                 if any(fnmatch.fnmatch(os.path.basename(c).lower(), p) for p in self.FORBIDDEN)]
        self.assertEqual(found, [])

    def test_the_secret_scanner_refuses_by_name(self):
        sys.path.insert(0, os.path.join(ROOT, "bin"))
        try:
            import check_secrets
        finally:
            sys.path.pop(0)
        for p in self.FORBIDDEN:
            example = p.replace("*", "x")
            self.assertTrue(check_secrets.is_forbidden(os.path.join("any", "folder", example)), example)
        self.assertFalse(check_secrets.is_forbidden("examples/request.json"))

    def test_the_gitignore_ignores(self):
        with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8") as f:
            lines = {l.strip() for l in f}
        for p in self.FORBIDDEN:
            self.assertIn(p, lines, ".gitignore does not ignore " + p)


class Isolation(unittest.TestCase):
    """Nothing from a private project of the clone's owner enters the public repository. The terms are in a local list,
    outside git (.aigen-denylist: one term per line, case-insensitive, # comments); without it, the cases are skipped.
    Checks the name and the text of every versioned file and, in the commits no remote has yet, the author, the
    message and every added line. In the pre-push hook the test runs on a copy of the tree: AIGEN_GIT_ROOT is the
    repository (where the list is) and AIGEN_REV, the commit being pushed; without them, this repository and the
    index."""

    LIST = ".aigen-denylist"
    REPO = os.environ.get("AIGEN_GIT_ROOT", ROOT)
    REV = os.environ.get("AIGEN_REV")

    @classmethod
    def git(cls, *args):
        import subprocess
        try:
            r = subprocess.run(["git", "-C", cls.REPO, "-c", "core.quotePath=false"] + list(args),
                               capture_output=True, check=False)
        except OSError:
            return None
        return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None

    def terms(self):
        path = os.path.join(self.REPO, self.LIST)
        if not os.path.isfile(path):
            self.skipTest("no local list " + self.LIST)
        with open(path, encoding="utf-8") as f:
            terms = [t.strip().lower() for t in f if t.strip() and not t.strip().startswith("#")]
        if not terms:
            self.skipTest("the local list %s is empty" % self.LIST)
        return terms

    def versioned(self):
        ls = self.git("ls-tree", "-r", "-z", "--name-only", self.REV) if self.REV else self.git("ls-files", "-z")
        if ls is None:
            self.skipTest("no git")
        return [c for c in ls.split("\0") if c]

    @staticmethod
    def find(terms, text):
        low = text.lower()
        return [t for t in terms if t in low]

    def test_the_list_is_not_versioned(self):
        self.terms()
        self.assertNotIn(self.LIST, self.versioned())

    def test_no_file_mentions_a_term(self):
        terms, found = self.terms(), []
        for c in self.versioned():
            found += ["%s (in the name): %s" % (c, t) for t in self.find(terms, c)]
            f = os.path.join(ROOT, c)
            if not os.path.isfile(f):
                continue
            with open(f, "rb") as source:
                data = source.read()
            if b"\0" in data[:8192]:
                continue  # binary
            for i, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
                found += ["%s:%d: %s" % (c, i, t) for t in self.find(terms, line)]
        self.assertEqual(found, [])

    def test_no_new_commit_mentions_a_term(self):
        terms = self.terms()
        log = self.git("log", "-p", "--unified=0", "--no-color", "--no-ext-diff", "--no-renames",
                       "--format=%x01%h %an <%ae> %cn <%ce>%n%B", self.REV or "HEAD", "--not", "--remotes")
        if log is None:
            self.skipTest("no git or no commits")
        found, commit = [], "?"
        for line in log.splitlines():
            if line.startswith("\x01"):
                commit = line[1:].split()[0]
                line = line[1:]
            elif line.startswith(("-", "@@")):
                continue  # what is removed and the hunk context belong to what already existed
            found += ["commit %s: %s" % (commit, t) for t in self.find(terms, line)]
        self.assertEqual(found, [])


if __name__ == "__main__":
    result = unittest.main(argv=["test_contract"], exit=False, verbosity=2).result
    sys.stdout.flush()
    sys.exit(0 if result.wasSuccessful() else 1)
