"""Cross-language numerical regression for the self-contained web calculator."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from dataclasses import asdict

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('mt_web_reference', ROOT / 'skills/mt-distillation/scripts/mt_distillation.py')
mt = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mt
spec.loader.exec_module(mt)


class WebModelTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is needed for browser-model regression')
    def test_javascript_matches_python(self):
        example = json.loads((ROOT / 'skills/mt-distillation/references/example_7_15.json').read_text(encoding='utf-8'))
        cases = [example, asdict(mt.Inputs())]
        cases += [asdict(mt.Inputs(q=q, R=6)) for q in (-0.2, 0, 0.5, 1, 1.05)]
        cases += [dict(example, R=2.081), dict(example, F=250), dict(example, R=0.1), dict(example, alpha=1), dict(example, xW=0.5)]
        payload = []
        for inputs in cases:
            try:
                payload.append({'inputs': inputs, 'result': mt.solve(mt.Inputs(**inputs))})
            except ValueError:
                payload.append({'inputs': inputs, 'error': True})
        result = subprocess.run([shutil.which('node'), str(ROOT / 'tests/check_web.cjs')], input=json.dumps(payload), capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        print(result.stdout.strip())


if __name__ == '__main__':
    unittest.main()
