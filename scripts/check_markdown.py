#!/usr/bin/env python3
"""Read-only structural checks; not a LaTeX parser or semantic/rendering verifier."""
import argparse
import collections
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit


def table_cells(line):
    return [x.strip() for x in re.split(r'(?<!\\)\|', line.strip().strip('|'))]


def check(path, expect_images=None, expect_tables=None, expected_tags=None, allow_block_ids=False):
    text = path.read_text(encoding='utf-8')
    errors, warnings, prose, formulas = [], [], [], []
    counts = {'images': 0, 'tables': 0, 'display_formulas': 0}
    fence = None
    math = None
    table_width = None
    formula_lines = []
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r'^\s*(`{3,}|~{3,})(.*)$', line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            prose.append('')
            continue
        if math is None and marker:
            fence = marker[1]
            prose.append('')
            table_width = None
            continue
        if line.strip() == '$$':
            if math is None:
                math = number
                formula_lines = []
            else:
                formulas.append((math, '\n'.join(formula_lines)))
                math = None
            prose.append('')
            table_width = None
            continue
        if math is not None:
            formula_lines.append(line)
            prose.append('')
            continue
        code_free = re.sub(r'(`+).*?\1', '', line)
        if re.search(r'\\[()\[\]]', code_free):
            errors.append(f'L{number}: 使用了非约定的数学分隔符，请改用美元符号。')
        if '$$' in code_free:
            errors.append(f'L{number}: 独立公式的双美元分隔符须单独成行。')
        dollars = list(re.finditer(r'(?<!\\)\$', code_free))
        if len(dollars) % 2:
            errors.append(f'L{number}: 行内数学分隔符未配对。')
        plain = re.sub(r'(?<!\\)\$.*?(?<!\\)\$', '', code_free)
        if len(re.findall(r'\*\*', plain)) % 2:
            errors.append(f'L{number}: 加粗标记未配对。')
        for bold in re.finditer(r'\*\*([^*\n]+)\*\*', plain):
            if re.search(r'[：。；，！？、]$', bold[1]):
                errors.append(f'L{number}: 请把加粗末尾的中文标点移到 ** 外。')
        if re.search(r'\{\{(?:E|F|T)\d+\}\}|\bTODO\b|\bPLACEHOLDER\b', plain):
            errors.append(f'L{number}: 存在转换占位符。')
        if not allow_block_ids and re.search(r'(?:^|\s)\^eq-[\w.-]+\s*$', plain):
            warnings.append(f'L{number}: 存在可见公式块标识符；仅在用户需要块跳转时保留。')
        if re.fullmatch(r'\s*[（(]\d+(?:[–-]\d+)?[）)]\s*', plain):
            warnings.append(f'L{number}: 疑似公式外编号，请对照原文并改用 tag。')
        if line.lstrip().startswith('|'):
            cells = table_cells(line)
            if table_width is None:
                counts['tables'] += 1
                table_width = len(cells)
                if any(not x for x in cells):
                    warnings.append(f'L{number}: 表头有空列，请核对合并表头。')
            elif len(cells) != table_width:
                errors.append(f'L{number}: 表格列数 {len(cells)}，预期 {table_width}。')
        else:
            table_width = None
        prose.append(code_free)
    if fence:
        errors.append('代码围栏未闭合。')
    if math is not None:
        errors.append(f'L{math}: 独立公式未闭合。')
    counts['display_formulas'] = len(formulas)
    tags = []
    for start, formula in formulas:
        tags.extend(re.findall(r'\\tag\*?\{([^{}]+)\}', formula))
        if re.search(r'\\(?:label|ref|eqref|bm)\b', formula):
            warnings.append(f'L{start}: 公式仍有依赖 LaTeX 工程的命令，请核对兼容性。')
    duplicates = [k for k, n in collections.Counter(tags).items() if n > 1]
    if duplicates:
        errors.append('公式编号重复：' + ', '.join(duplicates))
    if expected_tags is not None and tags != expected_tags:
        errors.append(f'公式编号序列不匹配：实际 {tags}；预期 {expected_tags}。')
    visible = '\n'.join(prose)
    # These are inline image links; reference-style embeds need a separate renderer check.
    for n, line in enumerate(prose, 1):
        matches = list(re.finditer(r'!\[(.*?)\]\((<[^>]+>|[^\s)]+)(?:\s+"[^"]*")?\)', line))
        if len(matches) != line.count('!['):
            errors.append(f'L{n}: 图片引用未能解析；检查路径和替代文本。')
        for m in matches:
            counts['images'] += 1
            alt = re.sub(r'\\.', '', m[1])
            depth = 0
            for c in alt:
                depth += (c == '[') - (c == ']')
                if depth < 0:
                    break
            if depth != 0:
                errors.append(f'L{n}: 图片替代文本中的方括号未配对。')
            target = m[2].strip('<>')
            url = urlsplit(target)
            if url.scheme or url.netloc:
                errors.append(f'L{n}: 图片必须是交付目录内的相对路径：{target}')
                continue
            local = Path(unquote(url.path))
            if local.is_absolute():
                errors.append(f'L{n}: 图片使用了绝对路径：{target}')
            resolved = (path.parent / local).resolve()
            if not resolved.is_relative_to(path.parent.resolve()):
                errors.append(f'L{n}: 图片位于交付目录之外：{target}')
            if not resolved.is_file():
                errors.append(f'L{n}: 图片不存在：{target}')
    definitions = re.findall(r'^\[\^([^\]]+)\]:', visible, re.M)
    uses = re.findall(r'\[\^([^\]]+)\](?!:)', visible)
    missing = set(uses) - set(definitions)
    if missing:
        errors.append('脚注缺少定义：' + ', '.join(sorted(missing)))
    if len(definitions) != len(set(definitions)):
        errors.append('脚注定义重复。')
    targets = set(re.findall(r'(?:^| )\^([A-Za-z0-9-]+)$', visible, re.M))
    for block in re.findall(r'\]\(#\^([^)]+)\)', visible):
        if block not in targets:
            errors.append('块链接缺少目标：' + block)
    for label, expected in [('images', expect_images), ('tables', expect_tables)]:
        if expected is not None and counts[label] != expected:
            errors.append(f'{label} 数量为 {counts[label]}，预期 {expected}。')
    return {'file': str(path), 'counts': counts, 'tags': tags, 'errors': errors, 'warnings': warnings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('markdown', type=Path)
    parser.add_argument('--expect-images', type=int)
    parser.add_argument('--expect-tables', type=int)
    parser.add_argument('--expected-tags', type=Path, help='JSON array of source equation labels')
    parser.add_argument('--allow-block-ids', action='store_true')
    args = parser.parse_args()
    try:
        expected = json.loads(args.expected_tags.read_text()) if args.expected_tags else None
        if expected is not None and (not isinstance(expected, list) or not all(isinstance(x, str) for x in expected)):
            raise ValueError('expected-tags 必须是字符串数组。')
        result = check(args.markdown.resolve(), args.expect_images, args.expect_tables, expected, args.allow_block_ids)
    except (OSError, ValueError) as e:
        parser.exit(2, f'{e}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result['errors'] else 0


if __name__ == '__main__':
    sys.exit(main())
