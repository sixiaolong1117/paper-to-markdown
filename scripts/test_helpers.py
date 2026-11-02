"""Run with python scripts/test_helpers.py; fixtures are isolated in temporary directories."""
import json
from pathlib import Path
import tempfile
import unittest
from check_markdown import check
from prepare_images import prepare


class HelpersTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def note(self, text):
        p = self.root / 'paper.md'
        p.write_text(text)
        return p

    def test_valid_labels_footnotes_table_and_image(self):
        (self.root / 'images').mkdir()
        (self.root / 'images' / 'figure.png').write_bytes(b'fixture')
        p = self.note('**摘要**：结果 **40.10 dB**、**0.979**。[^r]\n\n'
                      '$$\nx=1\n\\tag{A.1}\n$$\n\n'
                      '![图1](images/figure.png)\n\n'
                      '| 方法 | PSNR↑ |\n| --- | --- |\n| UBS | 40.10 |\n\n'
                      '[^r]: Author. Title. 2025.\n')
        result = check(p, 1, 1, ['A.1'])
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['warnings'], [])

    def test_detects_failed_conversion(self):
        p = self.note('**摘要：**正文 $x\n\n'
                      '![图中的 [0,1) 区间](images/missing.png)\n\n'
                      '$$\nx=1\n\\tag{1}\n$$\n\n$$\nx=2\n\\tag{1}\n$$\n\n'
                      '| 方法 | 数值 |\n| --- | --- |\n| UBS | 1 | 2 |\n\n'
                      '引用[^missing]。\n')
        result = check(p)
        self.assertGreaterEqual(len(result['errors']), 7)

    def test_fences_code_and_inline_math_do_not_corrupt_bold_pairs(self):
        p = self.note('```markdown\n**摘要：** $x ![bad]\n```\n\n'
                      '`**摘要：**`，公式 $x^{**}$。 **40.10 dB** PSNR、**0.979** SSIM。\n')
        self.assertEqual(check(p)['errors'], [])

    def test_equation_block_ids_are_opt_in(self):
        p = self.note('$$\nx=1\n\\tag{1}\n$$\n\n^eq-1\n')
        self.assertEqual(len(check(p)['warnings']), 1)
        self.assertEqual(check(p, allow_block_ids=True)['warnings'], [])

    def test_copy_preserves_bytes_and_survives_moving_folder(self):
        source = self.root / 'original figure.png'
        source.write_bytes(b'fixture content')
        dest = self.root / 'paper' / 'images'
        result = prepare([source], dest)
        self.assertEqual((dest / source.name).read_bytes(), source.read_bytes())
        self.assertIn('images/original%20figure.png', result[0]['markdown'])
        moved = self.root / 'moved'
        dest.parent.rename(moved)
        note = moved / 'paper.md'
        note.write_text(result[0]['markdown'])
        self.assertEqual(check(note, 1)['errors'], [])

    def test_no_overwrite_and_no_ambiguous_names(self):
        source = self.root / 'figure.png'
        source.write_bytes(b'original')
        dest = self.root / 'images'
        prepare([source], dest)
        (dest / source.name).write_bytes(b'user changed')
        with self.assertRaises(ValueError):
            prepare([source], dest)
        self.assertEqual((dest / source.name).read_bytes(), b'user changed')
        other = self.root / 'other'
        other.mkdir()
        (other / source.name).write_bytes(b'other')
        with self.assertRaises(ValueError):
            prepare([source, other / source.name], self.root / 'new')
        self.assertFalse((self.root / 'new').exists())

    def test_images_next_to_markdown(self):
        source = self.root / 'figure.png'
        source.write_bytes(b'fixture')
        dest = self.root / 'paper'
        result = prepare([source], dest, dest)
        self.assertEqual(result[0]['markdown'], '![图注](figure.png)')


if __name__ == '__main__':
    unittest.main()
