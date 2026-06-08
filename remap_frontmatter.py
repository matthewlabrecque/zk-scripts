#!/usr/bin/env python3
"""
Remap Markdown YAML frontmatter based on a template file.

Usage:
    python remap_frontmatter.py --template ../templates/note.md file.md
    python remap_frontmatter.py --template note.md --all
"""
import argparse
import datetime
import os
import re
import sys

import yaml

# Matches the opening frontmatter fence and captures everything up to the closing fence.
# The body follows immediately after the closing fence.
FRONTMATTER_RE = re.compile(r'^---\r?\n(.*?)\r?\n---(?:\r?\n|$)', re.DOTALL)

# Used to quote bare %s / %d in template frontmatter so PyYAML can parse them.
PLACEHOLDER_RE = re.compile(r'^(\s*[^\s:]+\s*:\s*)(%s|%d)\s*$', re.MULTILINE)


def split_frontmatter(content):
    """Return (raw_frontmatter_text, body) or (None, content) if no frontmatter."""
    m = FRONTMATTER_RE.match(content)
    if not m:
        return None, content
    return m.group(1), content[m.end():]


def resolve_template_path(arg):
    """Resolve the template argument to an actual file path."""
    if os.path.isfile(arg):
        return arg
    candidates = [
        os.path.join('..', 'templates', arg),
        os.path.join('..', 'templates', arg + '.md'),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def is_placeholder(value):
    """Return True if a template value should be overwritten from the source file."""
    if isinstance(value, str):
        return value in ('%s', '%d') or value == ''
    if isinstance(value, list):
        return len(value) == 0 or all(is_placeholder(v) for v in value)
    if value is None:
        return True
    return False


def normalize_created(value):
    """Standardize the created field to a datetime.date (renders as YYYY-MM-DD)."""
    if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, str):
        value = value.strip()
        if 'T' in value:
            value = value.split('T')[0]
        elif ' ' in value:
            value = value.split(' ')[0]
        return datetime.date.fromisoformat(value)
    raise ValueError(f"Cannot normalize 'created' value: {value!r}")


def flatten_tags(value):
    """Recursively flatten a tag value into a deduplicated list of strings."""
    result = []

    def recurse(v):
        if v is None:
            return
        if isinstance(v, str):
            v = v.strip()
            if v:
                result.append(v)
            return
        if isinstance(v, list):
            for item in v:
                recurse(item)
            return
        s = str(v).strip()
        if s:
            result.append(s)

    recurse(value)

    seen = set()
    out = []
    for t in result:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


class IndentDumper(yaml.SafeDumper):
    """Custom YAML dumper that indents block sequence items."""
    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def dump_frontmatter(data):
    """Serialize frontmatter dict to YAML with 4-space list indentation."""
    text = yaml.dump(
        data,
        Dumper=IndentDumper,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        indent=4,
    )
    # Remove quotes around placeholder strings so external tools can match %s / %d.
    text = re.sub(r"'(%s|%d)'", r'\1', text)
    return text


def load_template(template_path):
    """Read a template Markdown file and return its parsed frontmatter as an ordered dict."""
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()

    raw, _ = split_frontmatter(content)
    if raw is None:
        raise ValueError(f"Template file '{template_path}' has no YAML frontmatter")

    # Quote %s / %d so yaml.safe_load treats them as strings.
    processed = PLACEHOLDER_RE.sub(r'\1"\2"', raw)
    data = yaml.safe_load(processed)
    if data is None:
        data = {}
    return data


def process_file(filepath, template_data):
    """Remap the frontmatter of a single Markdown file in place."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    source_raw, body = split_frontmatter(content)
    if source_raw is None:
        print(f"Skipping {filepath}: no YAML frontmatter found", file=sys.stderr)
        return False

    source_data = yaml.safe_load(source_raw) or {}
    new_data = {}

    for key, t_val in template_data.items():
        if is_placeholder(t_val):
            if key in source_data:
                val = source_data[key]
                if key == 'created':
                    val = normalize_created(val)
                elif key == 'tags':
                    val = flatten_tags(val)
                new_data[key] = val
            else:
                # Source doesn't provide this key; keep the template placeholder.
                new_data[key] = t_val
        else:
            # Template has a real fixed value; keep it.
            if key == 'tags':
                # Merge template tags with source tags, preserving order and deduping.
                source_tags = flatten_tags(source_data.get(key, [])) if key in source_data else []
                merged = list(t_val)
                seen = set(merged)
                for t in source_tags:
                    if t not in seen:
                        merged.append(t)
                        seen.add(t)
                new_data[key] = merged
            else:
                new_data[key] = t_val

    yaml_text = dump_frontmatter(new_data)
    if not yaml_text.endswith('\n'):
        yaml_text += '\n'

    new_content = f"---\n{yaml_text}---\n{body}"

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"Updated {filepath}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Remap Markdown YAML frontmatter based on a template."
    )
    parser.add_argument(
        '--template', required=True,
        help='Path to a template Markdown file (or a basename under ../templates/)'
    )
    parser.add_argument('files', nargs='*', help='Markdown files to process')
    parser.add_argument('--all', action='store_true', help='Process all .md files in the current directory')
    args = parser.parse_args()

    if not args.all and not args.files:
        parser.error('Provide file paths or use --all')

    template_path = resolve_template_path(args.template)
    if not template_path:
        print(f"Template not found: {args.template}", file=sys.stderr)
        sys.exit(1)

    template_data = load_template(template_path)

    if args.all:
        targets = [f for f in os.listdir('.') if f.endswith('.md')]
        targets.sort()
    else:
        targets = args.files

    success = 0
    for t in targets:
        if not os.path.isfile(t):
            print(f"File not found: {t}", file=sys.stderr)
            continue
        try:
            if process_file(t, template_data):
                success += 1
        except Exception as e:
            print(f"Error processing {t}: {e}", file=sys.stderr)

    total = len(targets)
    print(f"Done. {success}/{total} file{'s' if total != 1 else ''} updated.")


if __name__ == '__main__':
    main()
