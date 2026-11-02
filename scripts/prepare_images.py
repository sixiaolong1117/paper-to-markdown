#!/usr/bin/env python3
"""Copy explicit figure files; preserve single-page PDFs plus PNG previews. Never overwrite different bytes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import quote


def same(a, b):
    return hashlib.sha256(a.read_bytes()).digest() == hashlib.sha256(b.read_bytes()).digest()


def copy_checked(source, target):
    if target.exists():
        if not target.is_file() or not same(source, target):
            raise ValueError(f'目标已存在且内容不同，停止覆盖：{target}')
    else:
        shutil.copy2(source, target)


def prepare(sources, dest, markdown_dir=None):
    sources = [p.resolve(strict=True) for p in sources]
    names = []
    for p in sources:
        if not p.is_file():
            raise ValueError(f'不是文件：{p}')
        if p.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.svg', '.webp', '.gif', '.pdf'):
            raise ValueError(f'此脚本不处理 {p.suffix}；请先渲染为常用图像格式。')
        names.append(p.name)
        if p.suffix.lower() == '.pdf':
            names.append(p.stem + '.preview.png')
    if len(names) != len(set(names)):
        raise ValueError('源文件或预览文件名冲突；请先在临时副本中按图号重命名。')
    env = dict(os.environ, LC_ALL='C')
    for p in sources:
        if p.suffix.lower() == '.pdf':
            if not all(shutil.which(t) for t in ('pdfinfo', 'pdftoppm')):
                raise ValueError('PDF 预览需要 pdfinfo 和 pdftoppm；可由调用者使用等效工具渲染。')
            info = subprocess.run(['pdfinfo', str(p)], check=True, capture_output=True, text=True, env=env).stdout
            pages = re.search(r'^Pages:\s*(\d+)', info, re.M)
            if not pages or int(pages[1]) != 1:
                raise ValueError(f'不是单页图 PDF，必须明确提取全部图页后再处理，不能静默只取第一页：{p}')
        target = dest / p.name
        if target.exists() and (not target.is_file() or not same(p, target)):
            raise ValueError(f'目标已存在且内容不同：{target}')
    dest.mkdir(parents=True, exist_ok=True)
    result = []
    with tempfile.TemporaryDirectory(prefix='paper-images-') as temp:
        for i, p in enumerate(sources):
            target = dest / p.name
            preview = None
            if p.suffix.lower() == '.pdf':
                prefix = Path(temp) / str(i)
                subprocess.run(['pdftoppm', '-scale-to', '2600', '-singlefile', '-png', str(p), str(prefix)], check=True, capture_output=True)
                preview = dest / (p.stem + '.preview.png')
                copy_checked(prefix.with_suffix('.png'), preview)
            copy_checked(p, target)
            embed = preview or target
            relative = os.path.relpath(embed, markdown_dir or dest.parent)
            result.append({'source': str(p), 'copied': str(target), 'preview': str(preview) if preview else None,
                           'markdown': f'![图注]({quote(Path(relative).as_posix(), safe="/")})'})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dest', type=Path, required=True, help='Image directory, normally next to Markdown')
    parser.add_argument('--markdown-dir', type=Path, help='Directory containing Markdown; defaults to image directory parent')
    parser.add_argument('sources', nargs='+', type=Path)
    args = parser.parse_args()
    try:
        result = prepare(args.sources, args.dest.resolve(), args.markdown_dir.resolve() if args.markdown_dir else None)
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        parser.exit(1, f'{e}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
