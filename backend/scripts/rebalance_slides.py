import json
from pathlib import Path

# Simple utility: trim bullets for slides that include an image

def rebalance_slides(input_path: str, output_path: str = None, max_image_bullets: int = 3):
    p = Path(input_path)
    if not p.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    data = json.loads(p.read_text(encoding='utf-8'))
    slides = data.get('slides', [])

    changed = 0
    for s in slides:
        img = s.get('image_index')
        content = s.get('content')
        if img is not None and isinstance(content, list) and len(content) > max_image_bullets:
            s['content'] = content[:max_image_bullets]
            changed += 1

    if output_path is None:
        output_path = str(p.with_name(p.stem + '_balanced' + p.suffix))

    Path(output_path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"Processed {len(slides)} slides, trimmed {changed} slides with images. Output: {output_path}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('input', help='Path to slides.json')
    parser.add_argument('--output', help='Output path (optional)')
    parser.add_argument('--max', type=int, default=3, help='Max bullets for image slides')
    args = parser.parse_args()
    rebalance_slides(args.input, args.output, args.max)
