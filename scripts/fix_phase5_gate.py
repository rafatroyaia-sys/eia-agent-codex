"""Script para convertir test_phase5_gate.py de pytest a unittest."""
import re
from pathlib import Path

src = Path("tests/test_phase5_gate.py")
content = src.read_text(encoding="utf-8")

# 1. Replace 'import pytest' with 'import tempfile\nimport unittest'
content = content.replace("import pytest\n", "import tempfile\nimport unittest\n", 1)

# 2. Add (unittest.TestCase) to all classes
classes = [
    "TestPhase5GateIssue", "TestPhase5GateResult", "TestEvaluatePhase5GateStructure",
    "TestEvaluatePhase5GateFactorLevel", "TestEvaluatePhase5GateGapLevel",
    "TestPhase5GateDecision", "TestRealisticOfflineInventory", "TestBuildPhase5GateMarkdown",
    "TestWritePhase5GateOutputs", "TestEvaluateFromJson", "TestCLI",
]
for cls in classes:
    content = content.replace(f"class {cls}:", f"class {cls}(unittest.TestCase):")

# 3. Replace pytest.raises
content = content.replace(
    'with pytest.raises(ValueError, match="severity inválido"):',
    'with self.assertRaisesRegex(ValueError, "severity"):',
)
content = content.replace(
    "with pytest.raises(FileNotFoundError):",
    "with self.assertRaises(FileNotFoundError):",
)
content = content.replace(
    'with pytest.raises(ValueError, match="JSON inválido"):',
    'with self.assertRaisesRegex(ValueError, "JSON"):',
)
content = content.replace(
    'with pytest.raises(ValueError, match="factors"):',
    'with self.assertRaisesRegex(ValueError, "factors"):',
)

# 4. Add setUp/tearDown to classes that use tmp_path
# Classes: TestWritePhase5GateOutputs, TestEvaluateFromJson, TestCLI

SETUP_TEARDOWN = """\n    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()
"""

for cls in ("TestWritePhase5GateOutputs", "TestEvaluateFromJson", "TestCLI"):
    marker = f"class {cls}(unittest.TestCase):"
    content = content.replace(marker, marker + SETUP_TEARDOWN, 1)

# 5. Replace method signatures: def test_xxx(self, tmp_path): -> def test_xxx(self):
content = re.sub(r"def (test_\w+)\(self, tmp_path\):", r"def \1(self):", content)

print("pytest.raises remaining:", content.count("pytest.raises"))
print("(unittest.TestCase):", content.count("(unittest.TestCase)"))
print("import tempfile:", "import tempfile" in content)
print("tmp_path param remaining:", bool(re.search(r"def test_\w+\(self, tmp_path\)", content)))
print("self.tmp_path:", content.count("self.tmp_path"))

src.write_text(content, encoding="utf-8")
print("Done. File written.")
