"""Tests of the pure modules: the prompt, the sheets, the LoRAs, the metadata, the configuration, the stage sequences
and the math of the face fix and of the web interface. They need neither torch nor a GPU and generate no image.

    python3 tests/test_pure.py
"""
import datetime
import json
import os
import sys
import tempfile
import tomllib
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from aigen import (config, contract, face, generate, hires, loras, metadata, model, output, prompts,  # noqa: E402
                   sheets, stages, web)

EXAMPLE_SHEET = os.path.join(ROOT, "examples", "characters", "example.toml")


def request(**fields):
    return contract.normalize(dict({"prompt": "1girl"}, **fields))


class Tags(unittest.TestCase):
    def test_splits_at_the_outer_commas(self):
        self.assertEqual(prompts.split_tags("a, (b, c:1.2), [d,e], f"), ["a", "(b, c:1.2)", "[d,e]", "f"])
        self.assertEqual(prompts.split_tags(r"artist \(style\), x"), [r"artist \(style\)", "x"])
        self.assertEqual(prompts.split_tags(" , ,"), [])

    def test_joins_without_repeats(self):
        self.assertEqual(prompts.join_tags("a, B", "b,  c", "A , d"), "a, B, c, d")
        self.assertEqual(prompts.join_tags("", None, "x"), "x")

    def test_build_in_the_order_quality_style_rating_sheet_scene(self):
        sheet = {"tags": "1girl, silver hair", "negative": "bad hands", "loras": []}
        pos, neg = prompts.build(request(prompt="smile, 1girl", negative="blurry"), sheet)
        anime, anime_neg = prompts.STYLES["anime"]
        safe, safe_neg = prompts.SAFE_TAGS
        self.assertEqual(pos, ", ".join((prompts.QUALITY_TAGS, anime, safe, "1girl, silver hair, smile")))
        self.assertEqual(neg, ", ".join((prompts.QUALITY_TAGS_NEGATIVE, anime_neg, safe_neg, "bad hands, blurry")))

    def test_the_default_is_anime_without_explicit(self):
        pos, neg = prompts.build(request())
        for tag in ("source_anime", "rating_safe"):
            self.assertIn(tag, prompts.split_tags(pos))
        for tag in ("source_furry", "3d", "rating_explicit", "rating_questionable"):
            self.assertIn(tag, prompts.split_tags(neg))

    def test_everything_off(self):
        pos, neg = prompts.build(request(quality=False, style=None, block_explicit=False))
        self.assertEqual((pos, neg), ("1girl", ""))

    def test_the_contract_styles_have_tags(self):
        self.assertEqual(set(prompts.STYLES), set(contract.STYLES))

    def test_loras_of_the_sheet_and_of_the_request(self):
        r = prompts.merge_loras([{"name": "a", "weight": 1.0}, {"name": "b", "weight": 0.5}],
                                [{"name": "b", "weight": 0.8}, {"name": "c", "weight": 1.0}])
        self.assertEqual(r, [{"name": "a", "weight": 1.0}, {"name": "b", "weight": 0.8}, {"name": "c", "weight": 1.0}])


class Weights(unittest.TestCase):
    def assertWeights(self, text, expected):
        found = [(t, round(w, 4)) for t, w in prompts.weights(text)]
        self.assertEqual(found, [(t, round(w, 4)) for t, w in expected])

    def test_no_weight(self):
        self.assertWeights("a, b", [("a, b", 1.0)])

    def test_number_parentheses_and_brackets(self):
        self.assertWeights("a, (b:1.3), c", [("a, ", 1.0), ("b", 1.3), (", c", 1.0)])
        self.assertWeights("(b)", [("b", 1.1)])
        self.assertWeights("((b))", [("b", 1.21)])
        self.assertWeights("[b]", [("b", 1 / 1.1)])
        self.assertWeights("(a, (b:2):0.5)", [("a, ", 0.5), ("b", 1.0)])

    def test_escaped_parenthesis_is_text(self):
        self.assertWeights(r"artist \(style\)", [("artist (style)", 1.0)])

    def test_open_without_closing_is_1_1(self):
        self.assertWeights("(b", [("b", 1.1)])

    def test_to_compel(self):
        self.assertEqual(prompts.to_compel("a, (b:1.3), c"), "a, (b)1.3, c")
        self.assertEqual(prompts.to_compel("(red eyes, smile:1.2)"), "(red eyes, smile)1.2")
        self.assertEqual(prompts.to_compel(r"artist \(style\)"), r"artist \(style\)")
        self.assertEqual(prompts.to_compel("score_9, 1girl"), "score_9, 1girl")
        self.assertEqual(prompts.to_compel(""), "")


class Sheets(unittest.TestCase):
    def test_the_example_passes(self):
        s = sheets.read_sheet(EXAMPLE_SHEET)
        self.assertEqual(s["sheet_version"], 1)
        self.assertTrue(s["tags"])

    def test_write_and_read_give_the_same(self):
        sheet = {"name": "Ana \"A\" Ü", "tags": "1girl, \\(x\\)\nline", "negative": "", "notes": "ç",
                 "loras": [{"name": "style/v1", "weight": 0.75}]}
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "ana.toml")
            sheets.write_sheet(sheet, path)
            self.assertEqual(sheets.read_sheet(path), sheets.check_sheet(sheet))
            with self.assertRaises(contract.RequestError):
                sheets.write_sheet(sheet, path)
            sheets.write_sheet(dict(sheet, notes="other"), path, overwrite=True)
            self.assertEqual(sheets.read_sheet(path)["notes"], "other")
            self.assertEqual(sheets.list_sheets(folder), ["ana"])

    def test_refusals(self):
        for bad, fragment in (({}, "'name'"), ({"name": "a", "hair": "x"}, "'hair'"),
                              ({"name": "a", "sheet_version": 2}, "sheet_version"),
                              ({"name": "a", "tags": 3}, "'tags'"),
                              ({"name": "a", "loras": [{"name": "x", "weight": 9}]}, "'weight'")):
            with self.assertRaises(contract.RequestError) as c:
                sheets.check_sheet(bad)
            self.assertIn(fragment, str(c.exception))

    def test_invalid_toml(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "bad.toml")
            with open(path, "w", encoding="utf-8") as f:
                f.write("name = \n")
            with self.assertRaises(contract.RequestError) as c:
                sheets.read_sheet(path)
            self.assertIn("is not valid TOML", str(c.exception))

    def test_resolve_and_file_name(self):
        self.assertEqual(sheets.resolve("aiko", "/p"), os.path.join("/p", "aiko.toml"))
        self.assertTrue(sheets.resolve("x/aiko.toml", "/p").endswith(os.path.join("x", "aiko.toml")))
        self.assertEqual(sheets.file_name("Aikô Hoshino!"), "aiko_hoshino")
        with self.assertRaises(contract.RequestError):
            sheets.file_name("!!!")


class Loras(unittest.TestCase):
    def test_parse_list(self):
        self.assertEqual(loras.parse_list("a:0.5\nb, c:-1"),
                         [{"name": "a", "weight": 0.5}, {"name": "b", "weight": 1.0}, {"name": "c", "weight": -1.0}])
        self.assertEqual(loras.parse_list(""), [])
        for bad in ("a:much", "a:9", ":1"):
            with self.assertRaises(contract.RequestError):
                loras.parse_list(bad)

    def test_find_file_and_list(self):
        with tempfile.TemporaryDirectory() as folder:
            os.makedirs(os.path.join(folder, "styles"))
            for n in ("a.safetensors", os.path.join("styles", "b.safetensors"), "c.txt"):
                open(os.path.join(folder, n), "w").close()
            self.assertEqual(loras.list_loras(folder), ["a", "styles/b"])
            self.assertEqual(loras.find_file(folder, "a"), os.path.join(folder, "a.safetensors"))
            self.assertEqual(loras.find_file(folder, "a.safetensors"), os.path.join(folder, "a.safetensors"))
            self.assertIsNone(loras.find_file(folder, "c.txt"))
            self.assertIsNone(loras.find_file(folder, "no"))
        self.assertEqual(loras.list_loras("/does/not/exist"), [])

    def test_adapter_name(self):
        self.assertEqual(loras.adapter_name("styles/b.v2"), "lora_styles_b_v2")


class Metadata(unittest.TestCase):
    def test_parameters_text(self):
        r = request(seed=42, hires=True)
        text = metadata.parameters_text(r, "score_9, 1girl", "score_4", "pony", [{"name": "x", "weight": 0.8}])
        lines = text.split("\n")
        self.assertEqual(lines[0], "score_9, 1girl <lora:x:0.8>")
        self.assertEqual(lines[1], "Negative prompt: score_4")
        for fragment in ("Steps: 25", "Sampler: Euler a", "CFG scale: 7", "Seed: 42", "Size: 1024x1024",
                         "Model: pony", "Hires upscale: 1.5", "Denoising strength: 0.4"):
            self.assertIn(fragment, lines[2])

    def test_the_request_comes_back_from_the_chunk(self):
        r = request(seed=7, face_fix=True, loras=[{"name": "x", "weight": 0.5}])
        chunk = metadata.aigen_chunk(r, "pos", "neg", r["loras"])
        self.assertEqual(metadata.request_from_png({"aigen": chunk, "parameters": "..."}), r)

    def test_png_from_elsewhere_is_refused(self):
        for texts in ({}, {"aigen": "{"}, {"aigen": json.dumps({"format_version": 9, "request": {}})}):
            with self.assertRaises(contract.RequestError):
                metadata.request_from_png(texts)


class Config(unittest.TestCase):
    def test_defaults_local_and_variable(self):
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root, "config.ini"), "w", encoding="utf-8") as f:
                f.write("[models]\ncheckpoint =\n[web]\nport = 7860\n")
            c = config.read(root, {})
            self.assertEqual(c.checkpoint, "")
            self.assertEqual(c.loras_folder, os.path.join(root, "models", "loras"))
            with open(os.path.join(root, "config.local.ini"), "w", encoding="utf-8") as f:
                f.write("[models]\ncheckpoint = models/pony.safetensors\n")
            self.assertEqual(config.read(root, {}).checkpoint, os.path.join(root, "models", "pony.safetensors"))
            c = config.read(root, {"AIGEN_CHECKPOINT": "/other/x.safetensors", "AIGEN_PORT": "8000"})
            self.assertEqual((c.checkpoint, c.port), ("/other/x.safetensors", 8000))
            with self.assertRaises(contract.RequestError):
                config.read(root, {"AIGEN_PORT": "port"})

    def test_the_repository_config_ini_has_no_machine_path(self):
        c = config.read(ROOT, {})
        self.assertTrue(c.sheets_folder.startswith(ROOT))
        if not os.path.isfile(os.path.join(ROOT, "config.local.ini")):
            self.assertEqual(c.checkpoint, "")


@stages.declare(writes=("sheet", "report"))
def _request(t):
    pass


@stages.declare(reads=("sheet",), writes=("positive",))
def _prompt(t):
    pass


def _no_declaration(t):
    pass


class Sequence(unittest.TestCase):
    def test_the_right_sequence_passes(self):
        stages.check((_request, _prompt))

    def test_reading_before_the_writer_is_refused(self):
        with self.assertRaises(stages.SequenceError) as c:
            stages.check((_prompt, _request))
        self.assertIn("'test_pure._prompt' reads 'sheet'", str(c.exception))

    def test_the_stage_without_a_declaration_is_refused(self):
        with self.assertRaises(stages.SequenceError) as c:
            stages.check((_request, _no_declaration))
        self.assertIn("does not declare", str(c.exception))

    def test_the_sequences_of_each_mode(self):
        names = lambda r: [stages.name(f) for f in generate.sequence(r)]  # noqa: E731
        base = ["generate.check_request", "prompts.stage", "model.stage", "loras.stage", "generation.stage"]
        self.assertEqual(names(request()), base + ["output.stage"])
        self.assertEqual(names(request(hires=True)), base + ["hires.stage", "output.stage"])
        self.assertEqual(names(request(face_fix=True, hires=True)),
                         base + ["hires.stage", "face.stage", "output.stage"])

    def test_removing_the_request_check_is_refused(self):
        with self.assertRaises(stages.SequenceError):
            stages.check(generate.sequence(request())[1:])


class Face(unittest.TestCase):
    def test_largest(self):
        boxes = [(0, 0, 10, 10), (5, 5, 30, 30), (50, 0, 20, 20), (0, 50, 20, 20)]
        self.assertEqual(face.largest(boxes, 3), [(5, 5, 30, 30), (50, 0, 20, 20), (0, 50, 20, 20)])

    def test_expanded_box_stays_inside_the_image(self):
        self.assertEqual(face.expanded_box((100, 100, 50, 50), 0.5, 1024, 1024), (75, 75, 100, 100))
        self.assertEqual(face.expanded_box((0, 0, 50, 50), 0.5, 1024, 1024), (0, 0, 100, 100))
        self.assertEqual(face.expanded_box((1000, 1000, 24, 24), 1, 1024, 1024), (952, 952, 72, 72))
        self.assertEqual(face.expanded_box((0, 0, 600, 600), 1, 1024, 768), (0, 0, 768, 768))

    def test_box_in_crop(self):
        self.assertEqual(face.box_in_crop((100, 100, 50, 50), (75, 75, 100, 100), 1000),
                         (250, 250, 500, 500))


class Vae(unittest.TestCase):
    def test_the_pony_sizes_do_not_use_tiling(self):
        for width, height in ((1024, 1024), (832, 1216), (1216, 832), (896, 1152), (768, 1344), (1344, 768)):
            self.assertFalse(model.uses_tiling(width, height), (width, height))

    def test_the_large_ones_do(self):
        for width, height in ((1536, 1536), (2048, 2048), (1248, 1824)):
            self.assertTrue(model.uses_tiling(width, height), (width, height))

    def test_prepare_vae_turns_on_and_off(self):
        calls = []

        class Vae:
            def enable_tiling(self):
                calls.append("on")

            def disable_tiling(self):
                calls.append("off")

        class Pipe:
            vae = Vae()
        model.prepare_vae(Pipe(), 2048, 2048)
        model.prepare_vae(Pipe(), 1024, 1024)
        self.assertEqual(calls, ["on", "off"])


class Math(unittest.TestCase):
    def test_hires_steps(self):
        self.assertEqual(hires.total_steps(15, 0.4), 38)
        self.assertEqual(int(hires.total_steps(15, 0.4) * 0.4), 15)
        self.assertEqual(hires.total_steps(20, 1.0), 20)

    def test_output_paths(self):
        self.assertEqual(output.paths("/x/a.png", 1), ["/x/a.png"])
        self.assertEqual(output.paths("/x/a.png", 2), ["/x/a_001.png", "/x/a_002.png"])
        self.assertEqual(output.report_path("/x/a.png"), "/x/a.aigen.json")

    def test_existing_output_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            png = os.path.join(folder, "a.png")
            output.check_outputs([png])
            open(output.report_path(png), "w").close()
            with self.assertRaises(contract.RequestError):
                output.check_outputs([png])
            with self.assertRaises(contract.RequestError):
                output.check_outputs([os.path.join(folder, "b.jpg")])


class CommandLine(unittest.TestCase):
    def test_style_and_explicit_from_the_options(self):
        r = generate.request_from_args(generate.parse_args(["x.png", "--prompt", "1girl"]))
        self.assertEqual((r["style"], r["block_explicit"]), ("anime", True))
        r = generate.request_from_args(generate.parse_args(["x.png", "--prompt", "1girl", "--style", "none",
                                                            "--allow-explicit"]))
        self.assertEqual((r["style"], r["block_explicit"]), (None, False))

    def test_hires_options_turn_on_the_hires(self):
        r = generate.request_from_args(generate.parse_args(["x.png", "--prompt", "1girl", "--hires-scale", "2"]))
        self.assertEqual(r["hires"]["scale"], 2.0)
        self.assertIsNone(r["face_fix"])

    def test_face_fix_options_turn_on_the_face_fix(self):
        r = generate.request_from_args(generate.parse_args(["x.png", "--prompt", "1girl", "--face-fix-max", "2",
                                                            "--no-quality"]))
        self.assertEqual((r["face_fix"]["max_faces"], r["quality"], r["hires"]), (2, False, None))


class Form(unittest.TestCase):
    def test_round_trip(self):
        r = request(sheet="aiko", seed=3, hires={"scale": 2.0}, loras=[{"name": "x", "weight": 0.5}], style=None,
                    block_explicit=False)
        v = web.form_from_request(r)
        self.assertEqual(set(v), set(web.FIELDS))
        self.assertEqual(web.request_from_form(v), r)

    def test_off_and_without_a_sheet(self):
        v = web.form_from_request(request())
        self.assertEqual((v["sheet"], v["hires"], v["face_fix"]), (web.NO_SHEET, False, False))
        self.assertEqual((v["style"], v["block_explicit"]), ("anime", True))
        self.assertEqual(web.request_from_form(v), request())

    def test_the_failure_log_appends(self):
        with tempfile.TemporaryDirectory() as folder:
            now = datetime.datetime(2026, 1, 2, 3, 4, 5)
            path = web.log_failure(folder, {"prompt": "1girl"}, "Traceback ...\nError: x\n", now)
            web.log_failure(folder, {"prompt": "2"}, "Other", now)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            self.assertEqual(os.path.basename(path), web.LOG)
            self.assertEqual(text.count("=== 2026-01-02T03:04:05"), 2)
            self.assertIn('request: {"prompt": "1girl"}', text)
            self.assertIn("Error: x", text)

    def test_new_path_does_not_repeat(self):
        now = datetime.datetime(2026, 1, 2, 3, 4, 5)
        with tempfile.TemporaryDirectory() as folder:
            first = web.new_path(folder, now)
            self.assertEqual(first, os.path.join(folder, "2026-01-02", "030405.png"))
            os.makedirs(os.path.dirname(first))
            open(first, "w").close()
            self.assertEqual(web.new_path(folder, now), os.path.join(folder, "2026-01-02", "030405_2.png"))


class Examples(unittest.TestCase):
    def test_the_pyproject_reads(self):
        with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
            self.assertIn("dependencies", tomllib.load(f)["project"])


if __name__ == "__main__":
    result = unittest.main(argv=["test_pure"], exit=False, verbosity=2).result
    sys.stdout.flush()
    sys.exit(0 if result.wasSuccessful() else 1)
