from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "index.html"
DOCS = [
    ("00_README.md", "안내 및 작성 기준", "readme"),
    ("01_character_index.md", "캐릭터 인덱스", "index"),
    ("07_equipment_rune_stats.md", "장비·룬·재련·스탯 도감", "equipment-reference"),
    ("05_common_build_guide.md", "공통 세팅 가이드", "common-guide"),
    ("06_source_and_image_map.md", "출처 및 이미지 맵", "image-map"),
    ("02_character_db_081-120.md", "표시 1부 · 번호 081–120", "db-081-120"),
    ("03_character_db_041-080.md", "표시 2부 · 번호 041–080", "db-041-080"),
    ("04_character_db_001-040.md", "표시 3부 · 번호 001–040", "db-001-040"),
]
MD_IDS = {filename.lower(): anchor for filename, _, anchor in DOCS}
SECTION_IDS = {
    "장비도감": "equipment-codex",
    "룬도감": "rune-codex",
    "무기재련표": "weapon-refinement",
    "방어구재련표": "armor-refinement",
    "스탯 분석실": "stats-lab",
    "스탯-분석실": "stats-lab",
}


def markdown_url(target: str) -> str:
    parts = urlsplit(target)
    if not parts.path and parts.fragment in SECTION_IDS:
        return f"#{SECTION_IDS[parts.fragment]}"
    filename = Path(parts.path).name.lower()
    anchor = MD_IDS.get(filename)
    if anchor:
        if parts.fragment in SECTION_IDS:
            return f"#{SECTION_IDS[parts.fragment]}"
        return f"#{anchor}" + (f"-{parts.fragment}" if parts.fragment else "")
    return target


def inline(text: str) -> str:
    tokens: dict[str, str] = {}

    def stash(value: str) -> str:
        key = f"@@TOKEN{len(tokens)}@@"
        tokens[key] = value
        return key

    image_pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    def image_replace(match: re.Match[str]) -> str:
        alt, raw_url = match.groups()
        url = markdown_url(raw_url.strip())
        return stash(
            f'<img src="{html.escape(url, quote=True)}" '
            f'alt="{html.escape(alt, quote=True)}" loading="lazy">'
        )

    def link_replace(match: re.Match[str]) -> str:
        label, raw_url = match.groups()
        url = markdown_url(raw_url.strip())
        external = url.startswith(("https://", "http://"))
        rel = ' rel="noopener noreferrer" target="_blank"' if external else ""
        return stash(
            f'<a href="{html.escape(url, quote=True)}"{rel}>'
            f"{inline(label)}</a>"
        )

    text = image_pattern.sub(image_replace, text)
    text = link_pattern.sub(link_replace, text)

    code_pattern = re.compile(r"`([^`]+)`")
    text = code_pattern.sub(
        lambda m: stash(f"<code>{html.escape(m.group(1))}</code>"), text
    )
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    for key, value in tokens.items():
        text = text.replace(key, value)
    return text


def is_table_separator(line: str) -> bool:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def render_table(lines: list[str]) -> str:
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
    if len(rows) > 1 and is_table_separator(lines[1]):
        headers, body = rows[0], rows[2:]
    else:
        headers, body = rows[0], rows[1:]
    is_character_index = len(headers) > 1 and headers[:2] == ["번호", "캐릭터"]
    out = ['<div class="table-wrap"><table><thead><tr>']
    out.extend(f"<th>{inline(cell)}</th>" for cell in headers)
    out.append("</tr></thead><tbody>")
    for row in body:
        out.append("<tr>")
        number_match = re.fullmatch(r"\s*(\d{3})\s*", row[0]) if is_character_index and row else None
        character_number = number_match.group(1) if number_match else None
        for index, cell in enumerate(row):
            tag = "th" if index == 0 and len(headers) == 1 else "td"
            character_link = re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)", cell)
            if is_character_index and index == 1 and character_number and character_link:
                rendered = f'<a href="#char-{character_number}">{inline(character_link.group(1))}</a>'
            else:
                rendered = inline(cell)
            out.append(f"<{tag}>{rendered}</{tag}>")
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def render_blocks(lines: list[str], character_heading: bool = False) -> str:
    out: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    list_kind: str | None = None
    index = 0

    def flush_paragraph() -> None:
        if paragraph:
            out.append("<p>" + " ".join(inline(part) for part in paragraph) + "</p>")
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_kind
        if list_items:
            tag = list_kind or "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{item}</li>" for item in list_items) + f"</{tag}>")
            list_items.clear()
        list_kind = None

    while index < len(lines):
        line = lines[index].rstrip()
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            flush_list()
            index += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", stripped)
        if heading:
            flush_paragraph()
            flush_list()
            level = len(heading.group(1))
            content = heading.group(2)
            attrs_list = []
            if character_heading and level == 2:
                attrs_list.append('class="character-title"')
            if level == 2 and content in SECTION_IDS:
                attrs_list.append(f'id="{html.escape(SECTION_IDS[content], quote=True)}"')
            attrs = f" {' '.join(attrs_list)}" if attrs_list else ""
            out.append(f"<h{level}{attrs}>{inline(content)}</h{level}>")
            index += 1
            continue

        if stripped.startswith("|"):
            flush_paragraph()
            flush_list()
            table_lines = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            out.append(render_table(table_lines))
            continue

        if re.fullmatch(r"(?:---+|___+|\*\*\*+)", stripped):
            flush_paragraph()
            flush_list()
            out.append("<hr>")
            index += 1
            continue

        unordered = re.match(r"^\s*[-*+]\s+(.+)$", line)
        ordered = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
        if unordered or ordered:
            flush_paragraph()
            kind = "ol" if ordered else "ul"
            if list_kind and list_kind != kind:
                flush_list()
            list_kind = kind
            item = (ordered or unordered).group(1)
            list_items.append(inline(item))
            index += 1
            continue

        flush_list()
        paragraph.append(stripped)
        index += 1

    flush_paragraph()
    flush_list()
    return "\n".join(out)


def render_document(filename: str, title: str, anchor: str) -> str:
    source = (ROOT / filename).read_text(encoding="utf-8-sig")
    lines = source.splitlines()
    if anchor.startswith("db-"):
        pieces: list[tuple[str | None, list[str]]] = []
        current: list[str] = []
        current_number: str | None = None
        for line in lines:
            match = re.match(r"^##\s+(\d{3})\.\s+(.+)$", line)
            if match:
                if current or current_number:
                    pieces.append((current_number, current))
                current_number = match.group(1)
                current = [line]
            else:
                current.append(line)
        if current or current_number:
            pieces.append((current_number, current))

        parts = []
        for number, content in pieces:
            if number:
                match = re.match(r"^##\s+\d{3}\.\s+(.+)$", content[0])
                name = match.group(1).strip() if match else ""
                safe_name = html.escape(name, quote=True)
                parts.append(
                    f'<article class="character-card" id="char-{number}" '
                    f'data-name="{safe_name}">{render_blocks(content, character_heading=True)}</article>'
                )
            else:
                intro = render_blocks(content)
                if intro.strip():
                    parts.append(f'<div class="doc-intro">{intro}</div>')
        return f'<section class="doc-section db-section" id="{anchor}" aria-label="{html.escape(title)}">' + "\n".join(parts) + "</section>"

    body = render_blocks(lines)
    return f'<section class="doc-section" id="{anchor}" aria-label="{html.escape(title)}">{body}</section>'


STYLE = r"""
:root{color-scheme:light;--ink:#20283a;--muted:#67728a;--line:#dce3ed;--paper:#f4f6fa;--card:#fff;--blue:#244a83;--accent:#d89a3a;--soft:#edf3fb}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:1rem}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.68 system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:#1c5795;text-decoration-thickness:1px;text-underline-offset:3px}a:hover{color:#a46610}header{padding:1.6rem clamp(1rem,4vw,3.5rem);background:linear-gradient(120deg,#172a49,#294f81 65%,#466c97);color:white}
.topline{max-width:1600px;margin:auto}header h1{margin:0 0 .25rem;font-size:clamp(1.45rem,3vw,2.2rem);line-height:1.25}header p{margin:.25rem 0;color:#e1eafa}.toolbar{display:flex;gap:.7rem;align-items:center;flex-wrap:wrap;margin-top:1rem}.toolbar input{flex:1 1 280px;max-width:650px;padding:.8rem 1rem;border:1px solid #c8d4e5;border-radius:10px;font:inherit;background:#fff;color:var(--ink)}.counter{font-size:.92rem;color:#f2f5fb}
.layout{max-width:1600px;margin:auto;padding:1.25rem clamp(.8rem,2vw,1.5rem);display:grid;grid-template-columns:245px minmax(0,1fr);gap:1.3rem;align-items:start}.sidebar{position:sticky;top:1rem;padding:1rem;background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:0 5px 22px #1b2a4010}.sidebar h2{font-size:.98rem;margin:.1rem 0 .7rem}.sidebar nav{display:grid;gap:.25rem}.sidebar a{padding:.45rem .55rem;border-radius:8px;text-decoration:none;font-size:.93rem}.sidebar a:hover{background:var(--soft)}main{min-width:0}.doc-section{scroll-margin-top:1rem}.doc-section>h1{margin:0 0 1rem;padding:1rem 1.25rem;background:var(--blue);color:white;border-radius:12px;font-size:1.45rem}.doc-section>h2{margin:1.7rem 0 .7rem}.doc-intro{margin:0 0 1rem;padding:1rem 1.25rem;background:var(--card);border:1px solid var(--line);border-radius:12px}
.character-card{margin:1rem 0;padding:1.25rem clamp(1rem,2.4vw,2rem);background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:0 4px 18px #1b2a4008;scroll-margin-top:1rem}.character-title{margin:0 0 1rem;padding-bottom:.65rem;border-bottom:2px solid #e4eaf2;color:#183b68;font-size:1.45rem}.character-card h3{margin:1.15rem 0 .4rem;color:#294f81;font-size:1.08rem}.character-card p{margin:.45rem 0}.character-card ul,.character-card ol{padding-left:1.5rem}.character-card li{padding-left:.12rem;margin:.16rem 0}.character-card img{display:block;max-width:min(100%,520px);max-height:460px;object-fit:contain;object-position:left center;margin:.7rem 0 1rem;border-radius:10px;background:#eef1f5}.table-wrap{max-width:100%;overflow:auto;margin:.8rem 0}table{width:100%;border-collapse:collapse;background:#fff;font-size:.94rem}th,td{padding:.55rem .7rem;border:1px solid var(--line);text-align:left;vertical-align:top}th{background:var(--soft)}code{padding:.12rem .35rem;border-radius:4px;background:#eef1f5;font-size:.92em}hr{border:0;border-top:1px solid var(--line);margin:1rem 0}.filter-hidden{display:none!important}.notice{padding:.7rem .9rem;border-left:3px solid var(--accent);background:#fff7e9;color:#554126;border-radius:5px;font-size:.9rem;margin:0 0 1rem}footer{max-width:1600px;margin:auto;padding:0 clamp(1rem,3vw,2rem) 2rem;color:var(--muted);font-size:.9rem}
@media(max-width:850px){.layout{grid-template-columns:1fr}.sidebar{position:static}.sidebar nav{grid-template-columns:repeat(2,minmax(0,1fr))}.character-card{padding:1rem}.doc-section>h1{font-size:1.25rem}}
"""


def main() -> None:
    nav = "\n".join(
        f'<a href="#{anchor}">{html.escape(title)}</a>'
        for _, title, anchor in DOCS
    )
    content = "\n".join(render_document(*doc) for doc in DOCS)
    html_doc = f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="창세기전 모바일 120개 캐릭터 데이터베이스와 공통 세팅 가이드">
<title>창세기전 모바일 공략집 by 여름소나기 in 성심당</title><style>{STYLE}</style></head>
<body><header><div class="topline"><h1>창세기전 모바일 캐릭터 DB</h1><p>120명 캐릭터 · 기본 설명부터 스킬, 장비, 룬, 아티팩트까지</p>
<div class="toolbar"><input id="search" type="search" placeholder="캐릭터 이름·스킬·장비 내용 검색" aria-label="캐릭터 데이터베이스 검색"><span class="counter" id="counter">120명 캐릭터</span></div></div></header>
<div class="layout"><aside class="sidebar"><h2>문서 목차</h2><nav>{nav}</nav></aside><main>
<p class="notice">캐릭터 초상화는 외부 게임 정보 사이트의 이미지를 사용하므로 인터넷 연결이 필요할 수 있습니다. 카카오톡 원본 자료의 상대경로 이미지는 이 HTML 파일과 같은 폴더 구조에서 열립니다.</p>
{content}</main></div><footer>자료 기준: Markdown 원본 7개 문서 · 검색과 목차는 이 HTML 파일 안에서 동작합니다.</footer>
<script>
const input=document.getElementById('search');
const cards=[...document.querySelectorAll('.character-card')];
const counter=document.getElementById('counter');
const docs=[...document.querySelectorAll('.doc-section')];
function applyFilter(){{
  const query=input.value.trim().toLocaleLowerCase('ko');
  let visible=0;
  for(const card of cards){{
    const match=!query||card.textContent.toLocaleLowerCase('ko').includes(query);
    card.classList.toggle('filter-hidden',!match);
    if(match)visible++;
  }}
  for(const doc of docs){{
    if(doc.classList.contains('db-section')){{
      const hasVisible=[...doc.querySelectorAll('.character-card')].some(card=>!card.classList.contains('filter-hidden'));
      doc.classList.toggle('filter-hidden',Boolean(query)&&!hasVisible);
    }}else{{doc.classList.toggle('filter-hidden',Boolean(query));}}
  }}
  counter.textContent=query?`${{visible}} / ${{cards.length}}명 표시`:`${{cards.length}}명 캐릭터`;
}}
input.addEventListener('input',applyFilter);
</script></body></html>'''
    OUTPUT.write_text(html_doc, encoding="utf-8", newline="\n")
    character_ids = re.findall(r'id="char-(\d{3})"', html_doc)
    print(f"Saved: {OUTPUT}")
    print(f"Characters: {len(character_ids)} unique={len(set(character_ids))}")
    print(f"Size: {OUTPUT.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
