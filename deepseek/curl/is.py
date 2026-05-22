#!/usr/bin/env python3
"""
import_session.py - импорт сессий DeepSeek в файловую структуру
Группирует USER и ASSISTANT в пары.
Поддерживает оба формата API: прямой 'content' и старый 'fragments'.
Сохраняет структуру ветвления (дерево диалога) с помощью трёхпроходного импорта.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ============================================================
# Slugify
# ============================================================

CYRILLIC_MAP = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}

REPLACE_WITH_HYPHEN = set(" -_—–/\\|")


def slugify(text: str, max_length: int = 60) -> str:
    """Преобразует текст в slug с сохранением двоеточия"""
    if not text:
        return "empty"

    text = text.lower()
    result = []

    for char in text:
        if char == ":":
            result.append(":")
        elif char in CYRILLIC_MAP:
            result.append(CYRILLIC_MAP[char])
        elif char.isalnum():
            result.append(char)
        elif char in REPLACE_WITH_HYPHEN:
            result.append("-")

    slug = "".join(result)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")

    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")

    return slug if slug else "empty"


# ============================================================
# Парсинг API-дампов
# ============================================================


def unix_to_iso(timestamp: float) -> str:
    """Конвертирует Unix timestamp в ISO 8601"""
    if not timestamp:
        return ""
    return datetime.fromtimestamp(timestamp).isoformat()


def extract_message_content(message: Dict) -> str:
    """Извлекает текст сообщения из content или fragments"""
    content = message.get("content", "")
    if content:
        return content

    fragments = message.get("fragments", [])
    if fragments:
        contents = []
        for frag in fragments:
            frag_content = frag.get("content", "")
            if frag_content:
                contents.append(frag_content)
        return "\n\n".join(contents)

    return ""


def format_search_results(search_results: List[Dict]) -> str:
    """Форматирует результаты поиска в виде markdown-списка"""
    if not search_results:
        return ""

    lines = ["", "## Источники", ""]
    for idx, result in enumerate(search_results, start=1):
        title = result.get("title", "Без названия")
        url = result.get("url", "")
        snippet = result.get("snippet", "")
        lines.append(f"**{idx}. [{title}]({url})**")
        if snippet:
            snippet_short = snippet[:500] + "..." if len(snippet) > 500 else snippet
            lines.append(f"> {snippet_short}")
        lines.append("")

    return "\n".join(lines)


def group_messages(messages: List[Dict]) -> List[Dict]:
    """Группирует сообщения в пары (USER + ASSISTANT)"""
    children_map = {}
    for msg in messages:
        parent_id = msg.get("parent_id")
        if parent_id and msg["role"] == "ASSISTANT":
            if parent_id not in children_map:
                children_map[parent_id] = []
            children_map[parent_id].append(msg)

    pairs = []
    processed = set()

    for msg in messages:
        msg_id = msg["message_id"]
        if msg_id in processed:
            continue

        if msg["role"] == "USER":
            assistant_list = children_map.get(msg_id, [])
            assistant = assistant_list[0] if assistant_list else None

            if len(assistant_list) > 1:
                print(
                    f"  Предупреждение: на сообщение {msg_id} несколько ответов, беру первый"
                )

            pair = {
                "user_message": msg,
                "assistant_message": assistant,
            }
            pairs.append(pair)
            processed.add(msg_id)
            if assistant:
                processed.add(assistant["message_id"])

        elif msg["role"] == "ASSISTANT":
            parent_id = msg.get("parent_id")
            if parent_id is None or parent_id not in [
                m["message_id"] for m in messages if m["role"] == "USER"
            ]:
                is_orphan = True
                for other_pair in pairs:
                    if (
                        other_pair["assistant_message"]
                        and other_pair["assistant_message"]["message_id"] == msg_id
                    ):
                        is_orphan = False
                        break

                if is_orphan:
                    pair = {
                        "user_message": None,
                        "assistant_message": msg,
                    }
                    pairs.append(pair)
                    processed.add(msg_id)

    def get_sort_key(pair):
        if pair["user_message"]:
            return pair["user_message"].get("inserted_at", 0)
        else:
            return pair["assistant_message"].get("inserted_at", 0)

    pairs.sort(key=get_sort_key)

    for idx, pair in enumerate(pairs, start=1):
        pair["pair_id"] = idx

    return pairs


def build_parent_map(
    pairs: List[Dict],
) -> Tuple[Dict[int, List[int]], Dict[int, Optional[int]]]:
    """Строит карту родителей и детей на основе parent_id сообщений"""
    msg_to_pair = {}
    for pair in pairs:
        if pair["user_message"]:
            msg_to_pair[pair["user_message"]["message_id"]] = pair["pair_id"]
        if pair["assistant_message"]:
            msg_to_pair[pair["assistant_message"]["message_id"]] = pair["pair_id"]

    children_map = {pair["pair_id"]: [] for pair in pairs}
    parent_map = {pair["pair_id"]: None for pair in pairs}

    for pair in pairs:
        pair_id = pair["pair_id"]
        user_msg = pair["user_message"]

        if user_msg:
            parent_msg_id = user_msg.get("parent_id")
            if parent_msg_id is not None:
                if (
                    parent_msg_id in msg_to_pair
                    and parent_msg_id != user_msg["message_id"]
                ):
                    parent_pair_id = msg_to_pair[parent_msg_id]
                    if parent_pair_id != pair_id:
                        parent_map[pair_id] = parent_pair_id
                        if parent_pair_id in children_map:
                            children_map[parent_pair_id].append(pair_id)

    for parent_id in children_map:
        children_map[parent_id].sort()

    return children_map, parent_map


def generate_display_and_filename(pair: Dict) -> Tuple[str, str]:
    """Генерирует display текст и имя файла для пары"""
    user_msg = pair["user_message"]
    assistant_msg = pair["assistant_message"]
    pair_id = pair["pair_id"]

    user_content = extract_message_content(user_msg) if user_msg else None
    assistant_content = (
        extract_message_content(assistant_msg) if assistant_msg else None
    )

    if user_content:
        preview = user_content[:60].strip()
        if preview:
            tmp = preview.replace("\n", " ")
            display = tmp
            slug_base = preview
        else:
            display = f"Пара {pair_id}"
            slug_base = f"pair_{pair_id}"
    elif assistant_content:
        preview = assistant_content[:60].strip()
        if preview:
            tmp = preview.replace("\n", " ")
            display = f"Ответ: {tmp}"
            slug_base = preview
        else:
            display = f"Пара {pair_id}"
            slug_base = f"pair_{pair_id}"
    else:
        display = f"Пара {pair_id}"
        slug_base = f"pair_{pair_id}"

    if not slug_base or slug_base.isspace() or len(slug_base) < 3:
        slug_base = f"pair_{pair_id}"

    slug = slugify(slug_base)

    if not slug or slug == "empty" or len(slug) < 3:
        slug = f"pair_{pair_id}"

    filename = f"{pair_id:04d}--{slug}.md"

    return display, filename


def create_pair_file(
    pair: Dict,
    session_id: str,
    pairs_dir: Path,
    parent_id: Optional[int],
    parent_filename: Optional[str],
    parent_display: Optional[str],
    filename: str,
    display: str,
) -> None:
    """Создаёт файл пары без раздела 'Ответвления'"""
    user_msg = pair["user_message"]
    assistant_msg = pair["assistant_message"]
    pair_id = pair["pair_id"]

    user_content = extract_message_content(user_msg) if user_msg else None
    assistant_content = (
        extract_message_content(assistant_msg) if assistant_msg else None
    )

    search_results = []
    if assistant_msg:
        search_results = assistant_msg.get("search_results", [])

    filepath = pairs_dir / filename

    frontmatter = {
        "pair_id": pair_id,
        "session": session_id,
        "parent_pair_id": parent_id if parent_id else None,
        "user_message_id": user_msg["message_id"] if user_msg else None,
        "assistant_message_id": assistant_msg["message_id"] if assistant_msg else None,
        "user_timestamp": unix_to_iso(user_msg.get("inserted_at", 0))
        if user_msg
        else None,
        "assistant_timestamp": unix_to_iso(assistant_msg.get("inserted_at", 0))
        if assistant_msg
        else None,
    }

    content_lines = []
    content_lines.append("---")
    for key, value in frontmatter.items():
        if value is not None:
            content_lines.append(f"{key}: {value}")
    content_lines.append("---")
    content_lines.append("")

    # Ссылка на родителя
    if parent_id and parent_filename and parent_display:
        link_target = parent_filename.replace(".md", "")
        content_lines.append(f"**Родитель:** [[{link_target}|{parent_display}]]")
        content_lines.append("")
    elif parent_id:
        content_lines.append(f"**Родитель:** [[{parent_id:04d}--...|Пара {parent_id}]]")
        content_lines.append("")

    if user_content:
        content_lines.append("**Вопрос:**")
        content_lines.append("")
        content_lines.append(user_content)
        content_lines.append("")
    else:
        content_lines.append("**Вопрос:**")
        content_lines.append("")
        content_lines.append("*Нет вопроса*")
        content_lines.append("")

    if assistant_content:
        content_lines.append("**Ответ:**")
        content_lines.append("")
        content_lines.append(assistant_content)
        content_lines.append("")
    else:
        content_lines.append("**Ответ:**")
        content_lines.append("")
        content_lines.append("*Нет ответа*")
        content_lines.append("")

    if search_results:
        content_lines.append(format_search_results(search_results))

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(content_lines))

    user_len = len(user_content) if user_content else 0
    assistant_len = len(assistant_content) if assistant_content else 0
    print(f"    Пара {pair_id:04d}: {filename} (в: {user_len} с, о: {assistant_len} с)")


def add_children_to_pair_file(
    pairs_dir: Path,
    pair_id: int,
    display: str,
    children_ids: List[int],
    child_filename_map: Dict[int, str],
    child_display_map: Dict[int, str],
) -> None:
    """Добавляет в конец файла пары раздел 'Ответвления' со ссылками на дочерние пары"""
    if not children_ids:
        return

    # Находим родительский файл
    slug = slugify(display)
    filename = f"{pair_id:04d}--{slug}.md"
    filepath = pairs_dir / filename

    if not filepath.exists():
        found = list(pairs_dir.glob(f"{pair_id:04d}--*.md"))
        if found:
            filepath = found[0]
        else:
            print(f"    Предупреждение: файл для пары {pair_id} не найден")
            return

    children_links = []
    for child_id in children_ids:
        child_filename = child_filename_map.get(child_id)
        child_display = child_display_map.get(child_id)

        if not child_filename:
            found = list(pairs_dir.glob(f"{child_id:04d}--*.md"))
            if found:
                child_filename = found[0].name
                if "--" in child_filename:
                    name_part = child_filename.split("--", 1)[1].replace(".md", "")
                    child_display = name_part.replace("-", " ")
                else:
                    child_display = f"Пара {child_id}"
            else:
                child_filename = f"{child_id:04d}--.md"
                child_display = f"Пара {child_id}"

        if not child_display:
            child_display = f"Пара {child_id}"

        link_target = child_filename.replace(".md", "")
        children_links.append(f"- [[{link_target}|{child_display}]]")

    with open(filepath, "a", encoding="utf-8") as f:
        f.write("\n\n## Ответвления\n\n")
        f.write("\n".join(children_links))
        f.write("\n")

    print(f"    Пара {pair_id:04d}: добавлено {len(children_ids)} ответвлений")


def import_session_from_api(json_path: Path, session_id: str = None) -> None:
    """Импорт сессии из API-дампа с трёхпроходной логикой"""

    print(f"Чтение файла: {json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "data" in data and "biz_data" in data["data"]:
        biz_data = data["data"]["biz_data"]
    elif "biz_data" in data:
        biz_data = data["biz_data"]
    else:
        biz_data = data

    session = biz_data.get("chat_session", {})
    messages = biz_data.get("chat_messages", [])

    if not session and not messages:
        if "chat_messages" in data:
            messages = data["chat_messages"]
        if "chat_session" in data:
            session = data["chat_session"]

    if not session_id:
        session_id = session.get("id")
        if not session_id:
            print("Ошибка: не удалось определить session_id")
            print("Доступные ключи в JSON:", list(data.keys()))
            sys.exit(1)

    title = session.get("title", "Untitled")
    title_slug = slugify(title)

    session_dir_name = f"{session_id}--{title_slug}"
    if len(session_dir_name) > 200:
        session_dir_name = session_dir_name[:200]

    session_dir = Path("sessions") / session_dir_name
    pairs_dir = session_dir / "pairs"

    if session_dir.exists() and pairs_dir.exists() and any(pairs_dir.iterdir()):
        print(f"Предупреждение: сессия {session_id} уже импортирована")
        response = input("Перезаписать? (y/N): ")
        if response.lower() != "y":
            print("Отменено")
            return

    session_dir.mkdir(parents=True, exist_ok=True)
    pairs_dir.mkdir(exist_ok=True)

    if any(pairs_dir.iterdir()):
        print(f"  Очищаю каталог pairs/...")
        for f in pairs_dir.iterdir():
            f.unlink()

    pairs = group_messages(messages)
    children_map, parent_map = build_parent_map(pairs)
    root_pairs = [
        pair_id for pair_id, parent_id in parent_map.items() if parent_id is None
    ]

    print(f"\nСессия: {session_id}")
    print(f"Заголовок: {title}")
    print(f"Всего сообщений в API: {len(messages)}")
    print(f"Сформировано пар: {len(pairs)}")
    print(f"Корневых пар: {len(root_pairs)}")
    print()

    # === ПЕРВЫЙ ПРОХОД: генерируем имена файлов ===
    print("Первый проход: генерация имён файлов...")

    pair_filename_map = {}
    pair_display_map = {}

    for pair in pairs:
        pair_id = pair["pair_id"]
        display, filename = generate_display_and_filename(pair)
        pair_filename_map[pair_id] = filename
        pair_display_map[pair_id] = display

    # === ВТОРОЙ ПРОХОД: создаём файлы пар ===
    print("\nВторой проход: создание файлов пар...")

    for pair in pairs:
        pair_id = pair["pair_id"]
        parent_id = parent_map.get(pair_id)
        parent_filename = pair_filename_map.get(parent_id) if parent_id else None
        parent_display = pair_display_map.get(parent_id) if parent_id else None
        filename = pair_filename_map[pair_id]
        display = pair_display_map[pair_id]
        create_pair_file(
            pair,
            session_id,
            pairs_dir,
            parent_id,
            parent_filename,
            parent_display,
            filename,
            display,
        )

    # === ТРЕТИЙ ПРОХОД: добавляем "Ответвления" ===
    print("\nТретий проход: добавление ответвлений...")

    for pair in pairs:
        pair_id = pair["pair_id"]
        children_ids = children_map.get(pair_id, [])
        display = pair_display_map[pair_id]
        add_children_to_pair_file(
            pairs_dir,
            pair_id,
            display,
            children_ids,
            pair_filename_map,
            pair_display_map,
        )

    # === СОЗДАЁМ session.md ===
    print("\nСоздание session.md...")

    session_md = session_dir / "session.md"
    with open(session_md, "w", encoding="utf-8") as f:
        updated_val = unix_to_iso(session.get("updated_at", 0))

        f.write("---\n")
        f.write(f"uuid: {session_id}\n")
        f.write(f"title: {title}\n")
        f.write(f"updated: {updated_val}\n")
        f.write(f"total_pairs: {len(pairs)}\n")
        f.write(f"root_pairs: {len(root_pairs)}\n")
        f.write("---\n\n")
        f.write(f"# {title}\n\n")
        f.write(f"Обновлено: {updated_val}\n\n")

        if root_pairs:
            f.write("## Корневые пары диалога\n\n")
            for root_pair_id in root_pairs:
                filename = pair_filename_map.get(root_pair_id)
                display = pair_display_map.get(root_pair_id)
                if filename and display:
                    f.write(f"- [[pairs/{filename}|{display}]]\n")
        else:
            f.write("*Нет корневых пар*\n")

    print(f"Создан: {session_md}")
    print(f"\n✅ Импорт завершён. Сессия: {session_dir}")


def import_session_list(json_path: Path) -> None:
    """Импорт списка сессий: создание каталогов и session.md"""

    print(f"Чтение списка сессий: {json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "data" in data and "biz_data" in data["data"]:
        sessions = data["data"]["biz_data"].get("chat_sessions", [])
    elif "biz_data" in data:
        sessions = data["biz_data"].get("chat_sessions", [])
    else:
        sessions = data.get("chat_sessions", [])

    print(f"Найдено сессий в списке: {len(sessions)}")

    created_count = 0
    skipped_count = 0

    for sess in sessions:
        session_id = sess.get("id")
        title = sess.get("title", "Untitled")
        updated = sess.get("updated_at", 0)
        title_slug = slugify(title)

        session_dir_name = f"{session_id}--{title_slug}"
        if len(session_dir_name) > 200:
            session_dir_name = session_dir_name[:200]

        session_dir = Path("sessions") / session_dir_name

        session_md = session_dir / "session.md"
        if session_md.exists():
            print(f"  Пропуск (уже есть): {title[:50]}...")
            skipped_count += 1
            continue

        session_dir.mkdir(parents=True, exist_ok=True)

        updated_val = unix_to_iso(updated)
        with open(session_md, "w", encoding="utf-8") as f:
            f.write("---\n")
            f.write(f"uuid: {session_id}\n")
            f.write(f"title: {title}\n")
            f.write(f"updated: {updated_val}\n")
            f.write("---\n\n")
            f.write(f"# {title}\n\n")
            f.write(f"Обновлено: {updated_val}\n\n")
            f.write("## Пары диалога\n\n")
            f.write("*Не загружены. Запустите `import-session <uuid>` для загрузки.*\n")

        print(f"  Создан: {session_md}")
        created_count += 1

    print(f"\n✅ Создано каталогов: {created_count}, пропущено: {skipped_count}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Использование:")
        print("  import_session.py --list <sessions_list.json>")
        print("  import_session.py <session_dump.json> [session_id]")
        print()
        print("Примеры:")
        print("  import_session.py --list tmp/sessions_page.json")
        print("  import_session.py tmp/session_uuid.json")
        print("  import_session.py tmp/session_uuid.json bc31acff-...")
        sys.exit(1)

    if sys.argv[1] == "--list":
        if len(sys.argv) != 3:
            print("Ошибка: --list требует путь к JSON-файлу")
            sys.exit(1)
        import_session_list(Path(sys.argv[2]))
    else:
        json_path = Path(sys.argv[1])
        if not json_path.exists():
            print(f"Ошибка: файл не найден: {json_path}")
            sys.exit(1)
        session_id = sys.argv[2] if len(sys.argv) > 2 else None
        import_session_from_api(json_path, session_id)


if __name__ == "__main__":
    main()
