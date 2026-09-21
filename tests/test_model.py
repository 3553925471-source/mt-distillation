"""Regression and physical invariants; run with unittest from repository root."""
import importlib.util
import io
from contextlib import redirect_stdout, redirect_stderr
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills' / 'mt-distillation' / 'scripts' / 'mt_distillation.py'
EXAMPLE = ROOT / 'skills' / 'mt-distillation' / 'references' / 'example_7_15.json'
spec = importlib.util.spec_from_file_location('mt_distillation', SCRIPT)
mt = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mt
spec.loader.exec_module(mt)


class ModelTests(unittest.TestCase):
    def test_english_windows_console_does_not_abort_calculation(self):
        stdout = io.TextIOWrapper(io.BytesIO(), encoding='cp1252')
        stderr = io.TextIOWrapper(io.BytesIO(), encoding='cp1252')
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / 'result'
            with redirect_stdout(stdout), redirect_stderr(stderr), patch.object(mt, 'save_origin', side_effect=ImportError('Origin unavailable')):
                self.assertEqual(mt.calculate_and_save(mt.Inputs(), folder, True), 3)
            result = json.loads((folder / 'results.json').read_text(encoding='utf-8'))
            self.assertEqual(result['summary']['N_trays_integer'], 10)
            self.assertIn('塔内理论板数', (folder / '计算结果.txt').read_text(encoding='utf-8'))
            self.assertTrue((folder / 'origin_error.txt').is_file())

    def test_textbook_and_balances(self):
        p = mt.Inputs(**json.loads(EXAMPLE.read_text(encoding='utf-8')))
        r = mt.solve(p)
        s, o = r['summary'], r['operating']
        self.assertAlmostEqual(s['N_trays_fractional'], 13.2758, places=4)
        self.assertEqual(s['N_trays_integer'], 14)
        self.assertEqual(s['feed_stage_from_top'], 8)
        self.assertAlmostEqual(o['D'] / p.F, 0.34)
        self.assertAlmostEqual(o['D'] * p.xD + o['W'] * p.xW, p.F * p.zF)
        self.assertAlmostEqual(o['mr'] * o['xI'] + o['br'], o['ms'] * o['xI'] + o['bs'])
        self.assertAlmostEqual(p.q * o['xe'] - (p.q - 1) * o['ye'], p.zF)
        for row in r['stages']:
            self.assertAlmostEqual(mt.y_eq(row['x'], p.alpha), row['y'])
        self.assertEqual(math.ceil(s['N_trays_fractional']), s['N_trays_integer'])

    def test_feed_states_and_flow_scale(self):
        for q in (-0.2, 0, 0.5, 1, 1.05):
            with self.subTest(q=q):
                p = mt.Inputs(q=q, R=6)
                r = mt.solve(p)
                o = r['operating']
                self.assertAlmostEqual(q * o['xI'] - (q - 1) * o['yI'], p.zF)
                scaled = mt.solve(mt.Inputs(q=q, R=6, F=300))
                self.assertAlmostEqual(r['summary']['N_trays_fractional'], scaled['summary']['N_trays_fractional'])

    def test_invalid_and_infeasible_inputs(self):
        for args in ({'alpha': 1}, {'zF': float('nan')}, {'R': 0.1}, {'xW': 0.6}, {'F': -1}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                mt.solve(mt.Inputs(**args))

    def test_origin_failure_preserves_base_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / 'origin-failed'
            with patch.object(mt, 'save_origin', side_effect=ImportError('Origin unavailable')):
                self.assertEqual(mt.calculate_and_save(mt.Inputs(), folder, True), 3)
            for name in ('results.json', 'MT.png', 'MT.svg', 'origin_error.txt'):
                self.assertTrue((folder / name).is_file(), name)
            self.assertFalse((folder / 'MT_origin.opju').exists())

    def test_cli_portable_and_no_overwrite(self):
        with tempfile.TemporaryDirectory(prefix='MT 中文 path ') as directory:
            folder = Path(directory) / '结果 with spaces'
            args = [sys.executable, str(SCRIPT), '--cli', '--config', str(EXAMPLE), '--out', str(folder)]
            env = dict(os.environ, MT_OUTPUT_DIR=directory, PYTHONIOENCODING='utf-8')
            result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', env=env, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
            content = (folder / 'results.json').read_bytes()
            self.assertGreater((folder / 'MT.png').stat().st_size, 10000)
            repeat = subprocess.run(args, capture_output=True, env=env, timeout=90)
            self.assertNotEqual(repeat.returncode, 0)
            self.assertEqual(content, (folder / 'results.json').read_bytes())

    def test_cli_requires_explicit_input(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--cli'], capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 2)

    def test_base_calculation_does_not_import_origin(self):
        import builtins
        original = builtins.__import__

        def without_origin(name, *args, **kwargs):
            if name in ('originpro', 'OriginExt'):
                raise AssertionError('Ordinary calculation must not import Origin')
            return original(name, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory, patch('builtins.__import__', side_effect=without_origin):
            self.assertEqual(mt.calculate_and_save(mt.Inputs(), Path(directory) / 'ordinary', False), 0)


if __name__ == '__main__':
    unittest.main()
