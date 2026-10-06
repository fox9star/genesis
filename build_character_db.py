from __future__ import annotations

import html
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent
CHAT_DIR_A = ROOT / "KakaoTalk_Chats_2026-10-06_16.16.10_734080860"
CHAT_DIR_B = ROOT / "KakaoTalk_Chats_2026-10-06_16.29.22_-388686093"
CHAT_FILE = CHAT_DIR_B / "KakaoTalkChats.txt"
GMAP_BASE = "https://gmap.gg"
GMAP_LIST = f"{GMAP_BASE}/characters/"
OFFICIAL_LOUNGE = "https://game.naver.com/lounge/theplayofgenesis/"
BUILD_DATE = "2026-10-06"

IMAGE_FILES = [
    (CHAT_DIR_B, "46aa369ca0e3bcef86024a8fef47c04c1736fbb5285815f69afaed3a47626993.jpg", "캐릭터 초상/카드 참고"),
    (CHAT_DIR_B, "fbd481866606ebfd5eb375d1cae4d8bdde17b4a3fb4f4d25e0528a064440ea12.jpg", "캐릭터 일러스트 참고"),
    (CHAT_DIR_B, "12cb16c5b72d81e3095553db45a72513300475d064e8fdc1ff03d8dc6e252630.jpg", "클래스 트리 참고"),
    (CHAT_DIR_B, "9913c2f93a2c1a2a9be3b63dd9ccedc115c6bfa0bb7f6d333f4f795fb0db95cb.jpg", "룬 화면 참고"),
    (CHAT_DIR_B, "7d0e69a37543471613a8c19d28694aad3b93c2d1623608e60f420fd8a95bc4fb.png", "스탯/수치 화면 참고"),
    (CHAT_DIR_B, "7acc886a36e9b5fd4db7740e93e96e3e6a42b612de2ab0ac07fd71f776ea4061.jpg", "무기·스킬 화면 참고"),
    (CHAT_DIR_B, "d2bf3d6ec2c5a948d02dbac2b869a4285e93bbf05933c23d124919a97483a6c2.png", "편성 화면 참고"),
    (CHAT_DIR_B, "0896db1298b40a734c23e6303032abde91bd1d2818275a17bb2496143b705fc5.png", "용병·아티팩트 화면 참고"),
    (CHAT_DIR_B, "479dc0ad3bd88daeefd8a6f77d0347a201edb15b894884f5abd4e3acddb88aff.png", "캐릭터 목록 참고"),
    (CHAT_DIR_A, "1fa07271dff08c3c3e9ee09cb1ff05e2fad04ccf506cc58d0d0b9003cbdf159b.jpg", "대화방 캐릭터 목록 참고"),
    (CHAT_DIR_A, "1fa1666414a136f4f9e8a3fc56d6f238b740770f227c91ad330e296b78075c18.jpg", "대화방 클래스 화면 참고"),
]


def get_html(url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.get(
                url,
                timeout=45,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; GenesisMobileDB/1.0)",
                    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.6",
                },
            )
            response.raise_for_status()
            response.encoding = "utf-8"
            return response.text
        except Exception as exc:
            last_error = exc
            time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(f"fetch failed: {url}: {last_error}")


def unwrap(value: Any) -> Any:
    if isinstance(value, list) and len(value) == 2 and isinstance(value[0], int) and value[0] in (0, 1):
        return unwrap(value[1])
    if isinstance(value, list):
        return [unwrap(item) for item in value]
    if isinstance(value, dict):
        return {key: unwrap(item) for key, item in value.items()}
    return value


def astro_props(soup: BeautifulSoup, component_fragment: str) -> dict[str, Any]:
    for tag in soup.find_all("astro-island"):
        if component_fragment.lower() in (tag.get("component-url") or "").lower():
            return unwrap(json.loads(html.unescape(tag.get("props", "{}"))))
    raise ValueError(f"Astro props not found: {component_fragment}")


def list_characters() -> list[dict[str, Any]]:
    soup = BeautifulSoup(get_html(GMAP_LIST), "html.parser")
    props = astro_props(soup, "CharacterListFilters")
    characters = props.get("characters", [])
    if not isinstance(characters, list):
        raise ValueError("Unexpected character list shape")
    return characters


def fetch_character(item: dict[str, Any]) -> dict[str, Any]:
    href = item.get("detail_href") or f"/characters/{quote(str(item.get('slug', '')), safe='')}/"
    url = urljoin(GMAP_BASE, href)
    soup = BeautifulSoup(get_html(url), "html.parser")
    props = astro_props(soup, "CharacterDetail")
    character = props.get("character")
    if not isinstance(character, dict):
        raise ValueError(f"Unexpected character detail shape: {url}")
    character["_gmap_url"] = url
    return character


KAY_OFFICIAL_URL = "https://game.naver.com/lounge/theplayofgenesis/board/detail/8289924"
KAY_IMAGE_URL = "https://nng-phinf.pstatic.net/MjAyNjEwMDRfMTQ3/MDAxNzkxMTE0MDMyODUw.JtYyF7TCRXKspazKcmFdJAxTHwTMa5YYuCG7gQRL6s8g.wLk2JRLQsK92fPf8nop8EbVDQ4whkeb6iBfuI5GUL1Mg.PNG/1.png?type=w1678"


def kay_character() -> dict[str, Any]:
    class_base = {
        "weapons": ["대검"],
        "defense_type": "미디엄",
        "attack_range": 1,
        "move_range": 3,
        "role_tags": ["딜러"],
        "passives": [],
        "actives": [],
    }
    return {
        "name": "카이",
        "attribute": "자유의 불꽃 (적)",
        "unique_passive_name": "잿불의 심장",
        "description": "방주의 넘버 시즈 중, 카이. 원인 불명의 에러로 인해 다른 세계에서 이너월드로 넘어온 칼스와 헬카이트. 용자의 무덤에서 얻게 된 전용 무장을 착용한 채, 그의 곁에는 언제나 작은 헬카이트가 함께한다. 과거 자신의 손으로 성체 헬카이트를 쓰러뜨렸던 칼스는 이제 그녀와 서로 소중한 존재가 되어 새로운 운명을 함께 걸어간다.",
        "portrait_image": {"src": KAY_IMAGE_URL, "width": 1678, "height": 1678, "format": "png"},
        "ultimate_name": "천지파열무 용성락",
        "exclusive_weapon": "기가데스",
        "grade": "전설",
        "release_date": "2026-10-06",
        "class_entries": [
            {**class_base, "tier": 1, "name": "파이터", "description": "대검을 사용하는 근접 전투의 기본 클래스입니다."},
            {**class_base, "tier": 2, "name": "글라디에이터", "description": "대검을 활용하는 근접 공격 클래스입니다."},
            {
                **class_base,
                "tier": 2,
                "name": "엠버나이트",
                "description": "화염과 디버프를 공격력으로 전환하는 기사 클래스입니다.",
                "passives": [{
                    "name": "불꽃의 기사",
                    "ranks": [{"rank": 1, "description": "치명타 확률이 5% 증가하고, 보유한 디버프 개수당 공격 시 공격력이 5%만큼 증가합니다(최대 25%). 작렬의 검 효과를 보유합니다."}],
                }],
            },
            {
                **class_base,
                "tier": 3,
                "name": "드래곤슬레이어",
                "description": "대형 몬스터와 저체력 상황에서 화력을 끌어올리는 클래스입니다.",
                "passives": [{
                    "name": "광란",
                    "ranks": [{"rank": 1, "description": "전투 공격 시 공격력이 40% 증가하고 치명타 확률이 15% 증가합니다. 체력이 50% 이하라면 초필살기 피해량이 40% 증가하고 받는 피해가 25% 감소합니다. 대형 몬스터 공격 시 적이 받는 참격 피해량이 50% 증가하며 턴당 한 번 추가 행동을 얻습니다."}],
                }],
            },
            {
                **class_base,
                "tier": 3,
                "name": "인퍼널 듀얼리스트",
                "description": "디버프와 반격을 이용해 일대일 전투를 강화하는 클래스입니다.",
                "passives": [{
                    "name": "결투의 화신",
                    "ranks": [{"rank": 1, "description": "공격력과 치명타 확률이 20% 증가하고 받는 피해량이 25% 감소합니다. 디버프를 획득하면 전세역전 효과를 획득합니다. 디버프를 보유한 적으로부터 공격받으면 적의 공격력·주문력·치명타 확률이 30% 감소합니다. 클래스 패시브 봉쇄 불가."}],
                }],
            },
            {
                **class_base,
                "tier": 3,
                "name": "헬카이트 나이트",
                "description": "작은 헬카이트 소환과 잿불 효과를 연계하는 클래스입니다.",
                "passives": [{
                    "name": "용기사의 맹약",
                    "ranks": [{"rank": 1, "description": "공격력과 치명타 확률이 20% 증가하고 받는 피해량이 25% 감소합니다. 턴 시작 시 잿불의 역류 효과를 획득합니다. 잿불의 검 효과를 보유합니다. 클래스 패시브 봉쇄 불가."}],
                }],
            },
        ],
        "unique_passive_detail": {
            "levels": {
                "3": {
                    "description": "공격력·방어력·저항력이 20% 증가합니다. 불꽃의 부름·잿불의 소생 1·재의 공명 1 효과를 보유합니다.",
                    "estimated": False,
                }
            }
        },
        "active_skills": [
            {
                "name": "달구어진 칼날",
                "description": "스킬 사용 전 달구어진 칼날 효과를 획득합니다. 이동 공격 스킬 사용 시 집중 효과를 획득합니다.",
                "meta": {"tp": None, "range": "자신", "area": "단일", "cooldown": "3턴"},
                "tags": ["장비 일반 스킬"],
            },
            {
                "name": "초열 강화",
                "description": "물리 관통과 최대 체력이 10% 증가합니다. 기본 공격 또는 스킬 사용 전 초열 강화 1 효과를 획득합니다. 이동 공격 스킬 사용 시 집중 효과와 초열 강화 1 효과를 최대 중첩으로 획득합니다.",
                "meta": {"tp": None, "range": "자신", "area": "단일", "cooldown": "2턴"},
                "tags": ["기가데스 전용 스킬"],
            },
        ],
        "ultimate_detail": {
            "levels": {
                "3": {
                    "description": "방향을 지정해 범위 내 적들에게 공격력의 120%만큼 화염 피해를 가합니다. 3x5 범위에는 150%의 피해를 입힙니다. 대형 몬스터에게는 피해가 두 배로 적용되며 설치물에게는 5의 피해를 가합니다. 범위 내에 25% 확률로 타오르는 대지 타일을 생성합니다. 스킬 사용 시 작은 헬카이트가 있다면 소환 해제되고, 스킬 사용 후 불꽃의 귀환 효과 중첩을 최대로 획득합니다.",
                    "estimated": False,
                }
            }
        },
        "artifacts": [
            {
                "name": "루멘 코어",
                "grade": "공식 공지 표기 없음",
                "star_tiers": [{"star": 1, "description": "공격력·최대 체력 +5%. 게임 시작 시 잔광의 수호 1 효과 2중첩 획득."}],
            },
            {
                "name": "헬카이트의 시선",
                "grade": "공식 공지 표기 없음",
                "star_tiers": [{"star": 1, "description": "치명타 확률 +15%, 받는 치명타 확률 −15%. 공격 전 적에게 압도하는 시선 1 효과를 부여하고 공격 후 앙금 효과를 획득합니다."}],
            },
            {
                "name": "재기의 바람",
                "grade": "공식 공지 표기 없음",
                "star_tiers": [{"star": 1, "description": "공격력·물리 관통·방어력·저항력 +10%. 행동제어 효과를 받으면 재기의 바람 1 효과를 획득합니다."}],
            },
        ],
        "armor_info": "드레드노트 방어구 세트(전설, 미디엄): 2세트 최대 체력 +15%·물리 관통 +15%; 4세트 공격력·최대 체력 +20%, 공격으로 치명타 적중 시 철갑 파쇄를 부여합니다. 철갑 파쇄는 방어력·저항력 −15%, 받는 참격 피해 +15%, 2턴 지속·해제 불가입니다.",
        "accessory_info": "용의 문장(전설, 카이 특화 장신구): 공격력 +10%·치명타 확률 +10%·최대 체력 +5%; 최초 획득 시 초필살기 피해량 +10%와 불꽃의 온기 1 효과를 얻습니다.",
        "rune_info": "카이의 룬(전설, 2세트): 공격력 +1%, 최대 체력 +2%. 연금 및 룬 상자로는 획득할 수 없습니다.",
        "source": {"url": KAY_OFFICIAL_URL, "post_title": "10월 둘째 주 업데이트 안내 (10/06(화) 15:38 추가)"},
        "_gmap_url": KAY_OFFICIAL_URL,
    }


def decode_chat(path: Path) -> str:
    data = path.read_bytes()
    candidates = []
    for encoding in ("utf-8-sig", "cp949", "euc-kr"):
        text = data.decode(encoding, errors="replace")
        score = sum(1 for char in text if "\uac00" <= char <= "\ud7a3") - text.count("\ufffd") * 20
        candidates.append((score, text))
    return max(candidates, key=lambda pair: pair[0])[1]


def content_only(line: str) -> str:
    line = line.strip()
    if ", " in line:
        line = line.split(", ", 1)[1]
    if ": " in line:
        line = line.split(": ", 1)[1]
    line = re.sub(r"https?://\S+", "", line)
    line = re.sub(r"\s+", " ", line).strip()
    return line


def is_relevant_chat_line(line: str) -> bool:
    if not line or len(line) < 4:
        return False
    banned = ("입장했습니다", "나갔습니다", "공지의", "매너채팅", "저장한 날짜", "사진", "동영상")
    if any(word in line for word in banned):
        return False
    keywords = (
        "티어", "추천", "평가", "좋", "나쁘", "구림", "필수", "전무", "전용", "클래스",
        "룬", "아티팩트", "조합", "딜", "탱", "힐", "서포", "유틸", "AI", "초필",
        "스킬", "상향", "하향", "너프", "버프", "픽업", "뽑", "각성", "장비",
    )
    return any(word in line for word in keywords)


def read_chat_lines() -> list[str]:
    if not CHAT_FILE.exists():
        return []
    text = decode_chat(CHAT_FILE)
    result: list[str] = []
    for raw_line in text.splitlines():
        line = content_only(raw_line)
        if is_relevant_chat_line(line):
            result.append(line)
    return result


def aliases_for(name: str) -> list[str]:
    aliases = [name]
    parts = name.split()
    if len(parts) > 1 and len(parts[0]) >= 2:
        aliases.append(parts[0])
    if len(parts) > 1 and len(parts[-1]) >= 2:
        aliases.append(parts[-1])
    aliases.extend({
        "샤른호스트": ["샤른"],
        "클라우제비츠": ["클라우"],
        "메르세데스 프레데릭": ["메르세데스"],
        "라시드 팬드래건(청년)": ["청년 라시드", "라시드"],
        "알테어 유스티나 카이엔": ["알테어"],
        "수제자 쿤 그리어": ["수제자 쿤"],
        "성왕 라시드 팬드래건": ["성왕 라시드"],
    }.get(name, []))
    return list(dict.fromkeys(aliases))


def chat_notes(name: str, lines: list[str]) -> list[str]:
    matches: list[str] = []
    for line in lines:
        if any(alias and alias in line for alias in aliases_for(name)):
            if line not in matches:
                matches.append(line)
        if len(matches) >= 4:
            break
    return matches


def clean(value: Any, fallback: str = "확인되지 않음") -> str:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return fallback
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or fallback


def short(value: Any, limit: int = 420) -> str:
    text = clean(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def level_description(detail: Any) -> tuple[str, bool]:
    if not isinstance(detail, dict):
        return clean(detail), False
    levels = detail.get("levels")
    if isinstance(levels, dict) and levels:
        numeric = []
        for key, value in levels.items():
            try:
                numeric.append((int(key), value))
            except (TypeError, ValueError):
                pass
        if numeric:
            _, data = sorted(numeric, key=lambda pair: pair[0])[0]
            if isinstance(data, dict):
                return short(data.get("description")), bool(data.get("estimated"))
            return short(data), False
    return short(detail.get("description")), bool(detail.get("estimated"))


def get_unique_passive(character: dict[str, Any]) -> tuple[str, bool]:
    detail = character.get("unique_passive_detail")
    text, estimated = level_description(detail)
    if text != "확인되지 않음":
        return text, estimated
    return short(character.get("unique_passive")), False


def get_ultimate(character: dict[str, Any]) -> tuple[str, bool]:
    detail = character.get("ultimate_detail")
    text, estimated = level_description(detail)
    if text != "확인되지 않음":
        return text, estimated
    return short(character.get("ultimate")), False


def all_class_entries(character: dict[str, Any]) -> list[dict[str, Any]]:
    entries = character.get("class_entries")
    return entries if isinstance(entries, list) else []


def class_path(character: dict[str, Any]) -> str:
    entries = all_class_entries(character)
    if not entries:
        return "확인되지 않음"
    grouped: dict[Any, list[str]] = {}
    order: list[Any] = []
    for entry in entries:
        tier = entry.get("tier", "?")
        if tier not in grouped:
            grouped[tier] = []
            order.append(tier)
        grouped[tier].append(clean(entry.get("name")))
    return " → ".join(
        f"T{tier} " + " / ".join(grouped[tier]) for tier in order
    )


def role_tags(character: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for entry in all_class_entries(character):
        for tag in entry.get("role_tags", []) or []:
            tag = clean(tag)
            if tag not in result and tag != "확인되지 않음":
                result.append(tag)
    return result


def infer_role(character: dict[str, Any]) -> str:
    tags = role_tags(character)
    text = " ".join(tags)
    if any(word in text for word in ("탱커", "방어", "수호")):
        return "방어·전열"
    if any(word in text for word in ("힐러", "치유", "서포터", "지원")):
        return "지원·치유"
    if any(word in text for word in ("마법", "주문")):
        return "마법 딜러"
    if any(word in text for word in ("딜러", "공격")):
        return "물리 딜러"
    return "전투·유틸리티"


def class_passive_lines(character: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for entry in all_class_entries(character):
        prefix = f"T{entry.get('tier', '?')} {clean(entry.get('name'))}"
        keystone = clean(entry.get("keystone"))
        if keystone != "확인되지 않음":
            result.append(f"**{prefix} 핵심 패시브/키스톤** — {short(keystone, 260)}")
        for passive in entry.get("passives", []) or []:
            ranks = passive.get("ranks", []) or []
            if not ranks:
                result.append(f"**{prefix} · {clean(passive.get('name'))}** — 효과 단계 정보 없음")
                continue
            first = ranks[0]
            last = ranks[-1]
            line = f"**{prefix} · {clean(passive.get('name'))}** — 1단계: {short(first.get('description'), 230)}"
            if last.get("rank") != first.get("rank"):
                line += f" / 공개 최고 단계({last.get('rank')}): {short(last.get('description'), 230)}"
            result.append(line)
    return result


def active_skill_lines(character: dict[str, Any]) -> list[str]:
    skills: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for entry in all_class_entries(character):
        for skill in entry.get("actives", []) or []:
            key = (clean(skill.get("name")), clean(skill.get("description")))
            if key not in seen:
                seen.add(key)
                skill["_class_context"] = f"T{entry.get('tier', '?')} {clean(entry.get('name'))}"
                skills.append(skill)
    flat = character.get("active_skills", [])
    if isinstance(flat, list):
        for skill in flat:
            key = (clean(skill.get("name")), clean(skill.get("description")))
            if key not in seen:
                seen.add(key)
                skill["_class_context"] = "도감 공통"
                skills.append(skill)
    result: list[str] = []
    for skill in skills:
        meta = skill.get("meta") or {}
        meta_parts = []
        for label, key in (("TP", "tp"), ("사거리", "range"), ("범위", "area"), ("쿨타임", "cooldown")):
            value = meta.get(key)
            if value not in (None, "", "없음"):
                meta_parts.append(f"{label} {value}")
        meta_text = ", ".join(meta_parts) if meta_parts else "세부 수치 없음"
        tags = skill.get("tags") or []
        tag_text = f" / 태그: {', '.join(map(str, tags))}" if tags else ""
        result.append(
            f"**{clean(skill.get('name'))}** [{skill.get('_class_context', '도감')}; {meta_text}{tag_text}] — "
            f"{short(skill.get('description'), 360)}"
        )
    return result


def weapon_lines(character: dict[str, Any]) -> list[str]:
    result = [f"전용무기: **{clean(character.get('exclusive_weapon'))}**"]
    weapons = character.get("weapons")
    if isinstance(weapons, list):
        names = []
        for weapon in weapons:
            if isinstance(weapon, dict):
                name = clean(weapon.get("name") or weapon.get("weapon_name") or weapon.get("id"))
            else:
                name = clean(weapon)
            if name not in names and name != "확인되지 않음":
                names.append(name)
        if names:
            result.append("도감에 연결된 사용 무기: " + ", ".join(names))
    return result


def armor_lines(character: dict[str, Any], notes: list[str]) -> list[str]:
    values = []
    for entry in all_class_entries(character):
        value = clean(entry.get("defense_type"))
        if value not in values and value != "확인되지 않음":
            values.append(value)
    if values:
        result = ["방어구 타입(클래스 기준): " + ", ".join(values)]
    else:
        result = ["방어구 타입: 도감에서 확인되지 않음"]
    armor_info = character.get("armor_info")
    if armor_info:
        result.append("공식 공지 장비 세트: " + short(armor_info, 520))
    accessory_info = character.get("accessory_info")
    if accessory_info:
        result.append("공식 공지 장신구: " + short(accessory_info, 420))
    equipment_notes = [line for line in notes if any(word in line for word in ("방어구", "갑옷", "아머"))]
    if equipment_notes:
        result.append("대화방 장비 메모:")
        result.extend(f"- {short(line, 260)}" for line in equipment_notes[:2])
    result.append("개별 방어구 세트명과 수치는 도감·게임 내 장비 화면에서 다시 확인해야 하므로 임의로 보완하지 않았습니다.")
    return result


def rune_lines(character: dict[str, Any], notes: list[str]) -> list[str]:
    role = infer_role(character)
    if role == "방어·전열":
        formula = "체력/방어력/피해감소를 우선하고, 행동 순서가 중요한 콘텐츠에서는 속도를 보완합니다."
    elif role == "지원·치유":
        formula = "주문력/치유·보호막 효과/체력을 우선하고, TP·쿨타임 운용에 맞춰 속도를 조정합니다."
    elif role == "마법 딜러":
        formula = "주문력/마법 관통/치명타 또는 스킬 피해를 우선하고, 생존이 끊기면 체력을 섞습니다."
    else:
        formula = "공격력/물리 관통/치명타 또는 스킬 피해를 우선하고, 선턴이 필요하면 속도를 보완합니다."
    result = [f"역할 기반 기본안({role}): {formula}", "정확한 세트명·슬롯 수치는 콘텐츠와 패치에 따라 달라지므로 실제 룬 화면에서 최종 조정합니다."]
    rune_notes = [line for line in notes if "룬" in line]
    if rune_notes:
        result.append("대화방 룬 메모:")
        result.extend(f"- {short(line, 280)}" for line in rune_notes[:3])
    rune_info = character.get("rune_info")
    if rune_info:
        result.append("공식 공지 전용 룬: " + short(rune_info, 360))
    return result


def artifact_lines(character: dict[str, Any]) -> list[str]:
    artifacts = character.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return ["연결된 아티팩트 정보가 도감에 없습니다."]
    result = []
    for artifact in artifacts:
        name = clean(artifact.get("name"))
        grade = clean(artifact.get("grade"), "")
        tiers = artifact.get("star_tiers") or []
        first = tiers[0] if tiers else {}
        last = tiers[-1] if tiers else {}
        line = f"**{name}**"
        if grade:
            line += f" ({grade})"
        line += f" — 1성: {short(first.get('description') or artifact.get('description'), 240)}"
        if last.get("star") and last.get("star") != first.get("star"):
            line += f" / {last.get('star')}성: {short(last.get('description'), 240)}"
        result.append(line)
    return result


def official_source(character: dict[str, Any]) -> str:
    source = character.get("source")
    if isinstance(source, dict) and source.get("url"):
        return str(source["url"]).replace("https://m.game.naver.com", "https://game.naver.com")
    return OFFICIAL_LOUNGE


def review_lines(character: dict[str, Any], notes: list[str]) -> list[str]:
    role = infer_role(character)
    tags = ", ".join(role_tags(character)) or "역할 태그 없음"
    classes = class_path(character)
    result = [
        f"도감 기반 평가: {role} 성향이며, 클래스 역할 태그는 {tags}입니다.",
        f"운용 포인트: {classes} 중 현재 보유 콘텐츠의 목표에 맞는 경로를 먼저 확정한 뒤, 전용무기·아티팩트·룬의 투자 순서를 맞추는 방식이 안전합니다.",
    ]
    if notes:
        result.append("대화방 원문에서 해당 캐릭터명/별칭과 평가·세팅 키워드가 함께 언급된 메모:")
        result.extend(f"- {short(note, 300)}" for note in notes)
    else:
        result.append("대화방에서 직접 확인되는 해당 캐릭터 평가 문장이 없어, 이 항목은 공개 도감의 역할·스킬 구조만으로 작성했습니다.")
    return result


def final_lines(character: dict[str, Any]) -> list[str]:
    role = infer_role(character)
    passive_name = clean(character.get("unique_passive_name"))
    ultimate_name = clean(character.get("ultimate_name"))
    return [
        f"{role} 포지션을 기준으로 **{passive_name}**의 발동 조건과 **{ultimate_name}**의 사용 타이밍을 먼저 익히면 캐릭터 성능을 안정적으로 끌어낼 수 있습니다.",
        "최종 육성 순서는 보유 클래스, 콘텐츠 규칙, 최신 밸런스 패치에 따라 바뀔 수 있으므로 아래 수치는 기준점으로 사용하고 실제 전투 기록으로 보정하세요.",
    ]


def character_image(character: dict[str, Any]) -> str | None:
    image = character.get("portrait_image")
    if isinstance(image, dict) and image.get("src"):
        return urljoin(GMAP_BASE, str(image["src"]))
    return None


def render_character(index: int, character: dict[str, Any], notes: list[str]) -> str:
    name = clean(character.get("name"), f"검증 대기 슬롯 {index}")
    image = character_image(character)
    data_url = character.get("_gmap_url", GMAP_LIST)
    data_label = "gmap 캐릭터 페이지" if str(data_url).startswith(GMAP_BASE) else "공식 업데이트 원문"
    unique_text, unique_estimated = get_unique_passive(character)
    ultimate_text, ultimate_estimated = get_ultimate(character)
    lines = [
        f"## {index:03d}. {name}",
        "",
    ]
    if image:
        lines.extend([f"![{name} 캐릭터 이미지]({image})", ""])
    lines.extend([
        f"- 등급: {clean(character.get('grade'))}",
        f"- 속성: {clean(character.get('attribute'))}",
        f"- 클래스 경로: {class_path(character)}",
        f"- 고유 패시브: {clean(character.get('unique_passive_name'))}",
        f"- 초필살기: {clean(character.get('ultimate_name'))}",
        f"- 전용무기: {clean(character.get('exclusive_weapon'))}",
        f"- 공개 도감 출시일: {clean(character.get('release_date'))}",
        f"- 원문 출처: [{clean((character.get('source') or {}).get('post_title') if isinstance(character.get('source'), dict) else '공식 라운지 공지')}]({official_source(character)})",
        f"- 보조 데이터 링크: [{data_label}]({data_url})",
        "",
        "### 캐릭터기본설명",
        short(character.get("description") or character.get("profile") or "공개 설명 없음", 520),
        "",
        "### 캐릭터 리뷰",
        *review_lines(character, notes),
        "",
        "### 고유패시브",
        f"**{clean(character.get('unique_passive_name'))}** — {unique_text}" + (" [도감 추정 표기]" if unique_estimated else ""),
        "",
        "### 클래스패시브",
    ])
    passive_lines = class_passive_lines(character)
    lines.extend(passive_lines or ["클래스 패시브 정보가 공개 도감에 없습니다."])
    lines.extend(["", "### 액티브스킬 및 초필살기"])
    skill_lines = active_skill_lines(character)
    lines.extend(skill_lines or ["액티브 스킬 정보가 공개 도감에 없습니다."])
    lines.append(
        f"- **초필살기 · {clean(character.get('ultimate_name'))}** — {ultimate_text}"
        + (" [도감 추정 표기]" if ultimate_estimated else "")
    )
    lines.extend(["", "### 방어구 및 전용무기"])
    lines.extend(f"- {line}" for line in armor_lines(character, notes))
    lines.extend(f"- {line}" for line in weapon_lines(character))
    lines.extend(["", "### 룬 셋팅"])
    lines.extend(f"- {line}" for line in rune_lines(character, notes))
    lines.extend(["", "### 아티팩트"])
    lines.extend(f"- {line}" for line in artifact_lines(character))
    lines.extend(["", "### 총평 및 마무리"])
    lines.extend(f"- {line}" for line in final_lines(character))
    lines.extend(["", "---", ""])
    return "\n".join(lines)


def tier_notes(lines: list[str]) -> list[str]:
    result = []
    for line in lines:
        if "티어" in line and len(line) >= 20:
            if line not in result:
                result.append(line)
        if len(result) >= 12:
            break
    return result


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def make_readme(total: int, failures: list[str], chat_size: int, image_count_a: int, image_count_b: int) -> str:
    failure_text = ", ".join(failures) if failures else "없음"
    return f"""# 창세기전 모바일 캐릭터 DB

작성 기준일: {BUILD_DATE}

이 폴더는 창세기전 모바일의 캐릭터 정보를 캐릭터별 Markdown 문서로 나눈 결과물입니다. 사용자가 제공한 두 카카오톡 자료 폴더의 이미지와 대화 원문을 검토하고, 공식 라운지 공지와 공개 구조화 도감을 교차 확인했습니다.

## 결과 요약

- 공개 구조화 도감에서 확인된 캐릭터: **119명**
- 최신 공식 업데이트 공지에서 추가 확인된 캐릭터: **카이 1명**
- 실제 데이터가 채워진 캐릭터 DB: **{total}명**
- 사용자 요청 기준 전체 슬롯: **120개**
- 공개 도감 누락 보정 캐릭터: 공식 10월 둘째 주 업데이트 공지의 **카이**로 반영
- 캐릭터 DB 표시 순서: 1부 081–120, 2부 041–080, 3부 001–040. 각 파일명 범위는 포함된 캐릭터 번호를 나타냅니다.
- KakaoTalk 자료 A 이미지: {image_count_a}개
- KakaoTalk 자료 B 이미지: {image_count_b}개, 대화 원문 {chat_size:,}바이트
- 상세 페이지 수집 실패: {failure_text}

## 문서 목차

1. [캐릭터 인덱스](01_character_index.md)
2. [장비·룬·재련·스탯 도감](07_equipment_rune_stats.md)
3. [공통 육성·룬·출처 가이드](05_common_build_guide.md)
4. [대화방 이미지 및 자료 매핑](06_source_and_image_map.md)
5. [캐릭터 DB 표시 1부 (번호 081–120)](02_character_db_081-120.md)
6. [캐릭터 DB 표시 2부 (번호 041–080)](03_character_db_041-080.md)
7. [캐릭터 DB 표시 3부 (번호 001–040)](04_character_db_001-040.md)

### 장비·룬·재련·스탯 세부 목차

- [장비도감](07_equipment_rune_stats.md#장비도감)
- [룬도감](07_equipment_rune_stats.md#룬도감)
- [무기재련표](07_equipment_rune_stats.md#무기재련표)
- [방어구재련표](07_equipment_rune_stats.md#방어구재련표)
- [스탯 분석실](07_equipment_rune_stats.md#스탯-분석실)

## 데이터 출처와 신뢰 경계

- 공식 기준: [창세기전 모바일 공식 라운지]({OFFICIAL_LOUNGE})
- 대표 공식 업데이트 근거: [10월 둘째 주 업데이트 안내](https://game.naver.com/lounge/theplayofgenesis/board/detail/8289924), [09월 넷째 주 업데이트 안내](https://game.naver.com/lounge/theplayofgenesis/board/detail/8219304), [2주년 업데이트 안내](https://game.naver.com/lounge/theplayofgenesis/board/detail/7177613)
- 보조 구조화 데이터: [gmap 캐릭터 도감](https://gmap.gg/characters/). 이 사이트는 비공식 정보 사이트이므로 공식 공지보다 낮은 신뢰도로 사용했으며, 공식 원문 링크가 연결된 경우 캐릭터 문서에 함께 표기했습니다.
- 캐릭터 초상은 보조 도감의 웹 이미지 링크를 사용하고, 대화방 스크린샷은 원본 폴더의 상대 경로로 첨부했습니다.
- 스킬·패시브·아티팩트의 단계별 공개 데이터에 추정 표시가 있는 경우 문서에도 표시했습니다.

## 대화방 자료 처리 원칙

대화방에서 캐릭터 평가·스킬·장비·룬·티어와 관련된 문장만 캐릭터 리뷰와 공통 가이드에 반영했습니다. 참여자 이름, 건강·일상 대화, 이미지와 무관한 사담은 결과 문서에 재노출하지 않았습니다. 원본 폴더와 원본 이미지·텍스트는 변경하지 않았습니다.

이 DB는 패치가 계속되는 게임의 기준일 스냅샷입니다. 실제 육성 전에는 게임 내 수치와 최신 공식 공지를 다시 확인하세요.
"""


def make_index(characters: list[dict[str, Any]]) -> str:
    lines = [
        "# 캐릭터 인덱스",
        "",
        "공개 구조화 도감에서 확인된 119명에 최신 공식 업데이트 공지로 확인한 카이를 더해 총 120명을 표시합니다. 목록은 요청된 표시 순서이며, 캐릭터 번호는 이 표시 순서에서 120부터 001까지 감소합니다. 등급·속성·출시일은 공개 도감 또는 공식 공지 기준이며, 최종 근거 링크는 각 캐릭터 문서에서 확인하세요.",
        "",
        "| 번호 | 캐릭터 | 등급 | 속성 | 출시일 | DB 파일 |",
        "|---:|---|---|---|---|---|",
    ]
    for display_position, character in enumerate(characters, 1):
        file_name = (
            "02_character_db_081-120.md" if display_position <= 40
            else "03_character_db_041-080.md" if display_position <= 80
            else "04_character_db_001-040.md"
        )
        character_number = int(character.get("_db_number", display_position))
        name = clean(character.get("name"), "공식 도감 추가 캐릭터(검증 대기)")
        lines.append(
            f"| {character_number:03d} | [{name}]({file_name}) | {clean(character.get('grade'))} | "
            f"{clean(character.get('attribute'))} | {clean(character.get('release_date'))} | [{file_name}]({file_name}) |"
        )
    lines.extend([
        "",
        "## 확인 메모",
        "",
        "- 카이는 작성 기준일 공개 도감에는 아직 반영되지 않았지만 공식 10월 둘째 주 업데이트 공지에서 이름·스킬·장비·아티팩트가 확인되어 공식 데이터로 반영했습니다.",
        "- 같은 이름의 변형 캐릭터는 공개 도감의 별도 항목을 별도 번호로 유지했습니다.",
    ])
    return "\n".join(lines) + "\n"


def make_common_guide(chat_lines: list[str]) -> str:
    tiers = tier_notes(chat_lines)
    lines = [
        "# 공통 육성·룬·출처 가이드",
        "",
        "## 역할별 룬 출발점",
        "",
        "| 역할 | 우선 고려 | 보완 고려 |",
        "|---|---|---|",
        "| 방어·전열 | 체력, 방어력, 피해감소 | 속도, 저항, 상태이상 대응 |",
        "| 지원·치유 | 주문력, 치유·보호막 효과, 체력 | 속도, TP 운용, 생존 |",
        "| 마법 딜러 | 주문력, 마법 관통, 치명타·스킬 피해 | 체력, 속도 |",
        "| 물리 딜러 | 공격력, 물리 관통, 치명타·스킬 피해 | 속도, 생존 |",
        "",
        "위 표는 캐릭터별 전용 세트 확정표가 아니라, 공개 클래스 역할을 기준으로 한 안전한 시작점입니다. 캐릭터 문서의 룬 섹션에 대화방에서 직접 확인되는 룬 메모가 있으면 별도로 표시했습니다.",
        "",
        "## 방어구·전용무기 확인 순서",
        "",
        "1. 먼저 사용할 T2/T3 클래스를 고릅니다.",
        "2. 해당 클래스의 방어 타입과 무기 제한을 확인합니다.",
        "3. 전용무기는 고유 패시브·초필살기의 실제 발동 조건과 함께 평가합니다.",
        "4. 마지막으로 아티팩트의 시작 TP, 보호막, 사망·처치 조건이 콘텐츠와 맞는지 확인합니다.",
        "",
        "## 대화방 티어 메모의 사용법",
        "",
        "아래는 자료에 들어 있던 시점별 커뮤니티 메모를 보존한 것으로, 현재 공식 등급표나 확정적인 서열이 아닙니다.",
    ]
    lines.extend(f"- {short(line, 360)}" for line in tiers)
    if not tiers:
        lines.append("- 관련 티어 문장을 추출하지 못했습니다.")
    lines.extend([
        "",
        "## 최신 공지 확인",
        "",
        f"- [공식 라운지]({OFFICIAL_LOUNGE})",
        "- [10월 둘째 주 업데이트 안내](https://game.naver.com/lounge/theplayofgenesis/board/detail/8289924): 신규 전설 캐릭터 카이, 기가데스, 드레드노트 방어구, 용의 문장, 카이의 룬 공지",
        "- [09월 넷째 주 업데이트 안내](https://game.naver.com/lounge/theplayofgenesis/board/detail/8219304): 메르세데스 프레데릭과 라크리모사, 클래스·초필살기 정보가 포함된 공식 공지",
        "- [2주년 업데이트 안내](https://game.naver.com/lounge/theplayofgenesis/board/detail/7177613): 시라노 번스타인, 낡은 엑스칼리버 등 신규 도감·장비 공지",
        "",
        "## 주의",
        "",
        "대화방 평가와 비공식 도감은 패치·콘텐츠·각성 단계에 따라 달라질 수 있습니다. 특히 룬·방어구 세트명은 캐릭터 문서에서 확인되지 않은 경우 의도적으로 임의 확정하지 않았습니다.",
    ])
    return "\n".join(lines) + "\n"


def make_image_map(image_count_a: int, image_count_b: int, chat_size: int) -> str:
    lines = [
        "# 대화방 자료 및 이미지 매핑",
        "",
        "## 원본 범위",
        "",
        f"- KakaoTalk 자료 A: 이미지 {image_count_a}개",
        f"- KakaoTalk 자료 B: 이미지 {image_count_b}개 + KakaoTalkChats.txt {chat_size:,}바이트",
        "",
        "원본은 그대로 보존했습니다. 아래는 문서에서 바로 확인하기 좋은 대표 첨부 이미지이며, 나머지 원본 이미지도 두 폴더에 남아 있습니다.",
        "",
    ]
    for folder, filename, caption in IMAGE_FILES:
        path = folder / filename
        if path.exists():
            rel = relative(path)
            lines.extend([f"### {caption}", "", f"![{caption}]({rel})", "", f"원본: {rel}", ""])
    lines.extend([
        "## 이미지 해석 범위",
        "",
        "- 대표 이미지는 캐릭터 목록, 클래스, 스킬·무기, 룬, 스탯, 편성, 아티팩트 화면을 우선 선택했습니다.",
        "- 이미지에 표시된 숫자나 이름이 공식 텍스트 데이터와 충돌하면 공식 라운지 공지와 게임 내 화면을 우선 확인해야 합니다.",
        "- 캐릭터별 초상은 각 DB 문서의 웹 링크 이미지로 연결되어 있어, 오프라인 환경에서는 대표 첨부 이미지와 원본 폴더를 함께 사용하세요.",
    ])
    return "\n".join(lines) + "\n"


def write_chunks(characters: list[dict[str, Any]], notes_by_name: dict[str, list[str]]) -> None:
    spans = [
        (1, 40, "02_character_db_081-120.md", "081–120"),
        (41, 80, "03_character_db_041-080.md", "041–080"),
        (81, 120, "04_character_db_001-040.md", "001–040"),
    ]
    for start, end, filename, number_range in spans:
        body = [
            f"# 창세기전 모바일 캐릭터 DB 번호 {number_range} (표시 순서 {start:03d}–{end:03d})",
            "",
            "이 문서는 요청된 표시 순서 기준으로 묶었습니다. 캐릭터 번호는 표시 순서에 따라 120부터 001까지 역순으로 부여했습니다.",
            "각 항목의 공통 섹션은 기본설명, 리뷰, 고유패시브, 클래스패시브, 액티브스킬 및 초필살기, 방어구 및 전용무기, 룬 셋팅, 아티팩트, 총평 및 마무리 순서입니다.",
            "",
        ]
        for display_position in range(start, end + 1):
            if display_position <= len(characters):
                character = characters[display_position - 1]
                notes = notes_by_name.get(clean(character.get("name")), [])
                character_number = int(character.get("_db_number", display_position))
            else:
                character_number = display_position
                character = {
                    "name": "공식 도감 추가 캐릭터(검증 대기)",
                    "description": "사용자 제공 자료 기준 120번째 캐릭터 슬롯입니다. 작성 기준일에 공개 공식 라운지와 공개 도감에서 이름·속성·스킬·장비를 확인하지 못했으므로 추정 데이터를 기재하지 않습니다.",
                    "unique_passive_name": "검증 대기",
                    "ultimate_name": "검증 대기",
                    "exclusive_weapon": "검증 대기",
                    "_gmap_url": GMAP_LIST,
                }
                notes = []
            body.append(render_character(character_number, character, notes))
        (ROOT / filename).write_text("\n".join(body), encoding="utf-8")


def main() -> None:
    print("Fetching public character index...")
    index_items = list_characters()
    print(f"Indexed characters: {len(index_items)}")
    characters: list[dict[str, Any] | None] = [None] * len(index_items)
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_character, item): position for position, item in enumerate(index_items)}
        for future in as_completed(futures):
            position = futures[future]
            try:
                characters[position] = future.result()
            except Exception as exc:
                item = index_items[position]
                name = clean(item.get("name"), f"index {position + 1}")
                failures.append(f"{name}: {type(exc).__name__}")
                characters[position] = dict(item)
                characters[position]["_gmap_url"] = urljoin(GMAP_BASE, item.get("detail_href", GMAP_LIST))
    public_characters = [character for character in characters if character is not None]
    cabin_hastings = next(
        (character for character in public_characters if clean(character.get("name")) == "캐빈 헤이스팅스"),
        None,
    )
    if cabin_hastings is None:
        raise RuntimeError("캐빈 헤이스팅스가 공개 도감 목록에서 확인되지 않아 요청된 번호순을 만들 수 없습니다.")
    other_public_characters = [character for character in public_characters if character is not cabin_hastings]
    for character_number, character in zip(range(119, 1, -1), other_public_characters):
        character["_db_number"] = character_number
    cabin_hastings["_db_number"] = 1
    kai = kay_character()
    kai["_db_number"] = 120
    final_characters = [kai, *other_public_characters, cabin_hastings]

    chat_lines = read_chat_lines()
    notes_by_name = {
        clean(character.get("name")): chat_notes(clean(character.get("name")), chat_lines)
        for character in final_characters
    }
    image_count_a = len([path for path in CHAT_DIR_A.iterdir() if path.is_file()]) if CHAT_DIR_A.exists() else 0
    image_count_b = len([path for path in CHAT_DIR_B.iterdir() if path.is_file() and path.name != CHAT_FILE.name]) if CHAT_DIR_B.exists() else 0
    chat_size = CHAT_FILE.stat().st_size if CHAT_FILE.exists() else 0

    (ROOT / "00_README.md").write_text(
        make_readme(len(final_characters), failures, chat_size, image_count_a, image_count_b),
        encoding="utf-8",
    )
    (ROOT / "01_character_index.md").write_text(make_index(final_characters), encoding="utf-8")
    write_chunks(final_characters, notes_by_name)
    (ROOT / "05_common_build_guide.md").write_text(make_common_guide(chat_lines), encoding="utf-8")
    (ROOT / "06_source_and_image_map.md").write_text(
        make_image_map(image_count_a, image_count_b, chat_size),
        encoding="utf-8",
    )
    print(f"Wrote Markdown DB for {len(final_characters)} characters; display order begins with Kai and ends with Cabin Hastings.")
    print(f"Failures: {failures}")


if __name__ == "__main__":
    main()
