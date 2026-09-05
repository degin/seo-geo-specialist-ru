#!/usr/bin/env python3
"""
Проверка частотности ключевых слов через Yandex Cloud Search API v2 (Wordstat).

Официальный платный метод Яндекса, НЕ парсинг: https://aistudio.yandex.ru/docs/ru/search-api/
~20 руб. за 1000 запросов topRequests. Дерево регионов (--regions-tree) бесплатно.

Настройка:
    Скопируй .env.example в .env рядом со скриптом и впиши:
        YANDEX_SEARCH_FOLDER_ID=...
        YANDEX_SEARCH_API_KEY=...
    (folder + сервисный аккаунт с ролью search-api.webSearch.user + API-ключ —
    см. references/wordstat-check.md в этом скилле)

Использование:
    python wordstat_check.py "купить телефон"
    python wordstat_check.py "купить телефон" --regions 213,1 --num-phrases 20
    python wordstat_check.py --regions-tree                    # список регионов (бесплатно)
    python wordstat_check.py "купить телефон" --json           # машиночитаемый вывод

    # Пакетная проверка — вместо разового скрипта на каждый разбор ядра:
    python wordstat_check.py --batch-file phrases.txt --regions 38 --out results.json
    (phrases.txt — по одной фразе на строку; --delay регулирует паузу между запросами,
     по умолчанию 1 сек — этого достаточно, чтобы не упираться в лимит 10 запросов/сек;
     повтор на 429 уже встроен, отдельный backoff в вызывающем коде не нужен)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

API_HOST = "https://searchapi.api.cloud.yandex.net"
ENDPOINT_TOP = "/v2/wordstat/topRequests"
ENDPOINT_REGIONS = "/v2/wordstat/getRegionsTree"

DEVICE_ENUM = {
    "all": "DEVICE_ALL",
    "desktop": "DEVICE_DESKTOP",
    "mobile": "DEVICE_MOBILE",
    "phone": "DEVICE_PHONE",
    "tablet": "DEVICE_TABLET",
}


def load_env_file(path: Path) -> None:
    """Простой .env-лоадер (без зависимости от python-dotenv)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def get_config() -> tuple[str, str]:
    load_env_file(Path(__file__).parent / ".env")
    folder_id = os.environ.get("YANDEX_SEARCH_FOLDER_ID", "")
    api_key = os.environ.get("YANDEX_SEARCH_API_KEY", "")
    if not folder_id or not api_key:
        sys.exit(
            "Нет учётных данных Yandex Cloud.\n"
            "Создай .env рядом со скриптом (см. .env.example) и укажи:\n"
            "  YANDEX_SEARCH_FOLDER_ID=...\n"
            "  YANDEX_SEARCH_API_KEY=...\n"
            "Как получить — references/wordstat-check.md."
        )
    return folder_id, api_key


def call_api(endpoint: str, folder_id: str, api_key: str, body: dict, max_retries: int = 5, base_delay: float = 3.0) -> dict:
    """Официальный лимит — 10 запросов/сек, 10 000/час на topRequests (aistudio.yandex.ru/docs/ru/search-api/concepts/limits).
    429 при аккуратном использовании — это всплеск, не исчерпанная квота: ждём и повторяем сами,
    вместо того чтобы каждый вызывающий скрипт заново изобретал бэкофф."""
    for attempt in range(max_retries + 1):
        resp = requests.post(
            f"{API_HOST}{endpoint}",
            json={**body, "folderId": folder_id},
            headers={
                "Authorization": f"Api-Key {api_key}",
                "Content-Type": "application/json; charset=utf-8",
            },
            timeout=30,
        )
        if resp.status_code == 429:
            if attempt >= max_retries:
                sys.exit(f"Rate limit (429) — не отступил после {max_retries} повторов, попробуй позже.")
            retry_after = resp.headers.get("Retry-After")
            delay = float(retry_after) if retry_after else base_delay * (2 ** attempt)
            print(f"429, жду {delay:.0f} сек и повторяю ({attempt + 1}/{max_retries})…", file=sys.stderr)
            time.sleep(delay)
            continue
        if resp.status_code == 401:
            sys.exit("401: недействительный API-ключ.")
        if resp.status_code == 403:
            sys.exit("403: доступ запрещён — проверь роль search-api.webSearch.user у сервисного аккаунта.")
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except ValueError:
                detail = resp.text
            sys.exit(f"Ошибка API {resp.status_code}: {detail}")
        return resp.json()


def top_requests(phrase: str, folder_id: str, api_key: str, regions: list[str], devices: list[str], num_phrases: int) -> dict:
    body = {"phrase": phrase, "numPhrases": num_phrases}
    if regions:
        body["regions"] = regions
    body["devices"] = [DEVICE_ENUM.get(d.lower(), "DEVICE_ALL") for d in devices] if devices else ["DEVICE_ALL"]
    return call_api(ENDPOINT_TOP, folder_id, api_key, body)


def regions_tree(folder_id: str, api_key: str) -> dict:
    return call_api(ENDPOINT_REGIONS, folder_id, api_key, {})


def print_top_requests(phrase: str, data: dict) -> None:
    total = int(data.get("totalCount", 0) or 0)
    print(f'\nЧастотность «{phrase}»: {total:,}'.replace(",", " "))

    results = data.get("results", [])
    if results:
        print(f"\nСвязанные запросы (топ {len(results)}):")
        for item in results:
            count = int(item.get("count", 0) or 0)
            print(f"  {count:>8,}  {item.get('phrase', '')}".replace(",", " "))

    associations = data.get("associations", [])
    if associations:
        print(f"\nАссоциации ({len(associations)}):")
        for item in associations:
            count = int(item.get("count", 0) or 0)
            print(f"  {count:>8,}  {item.get('phrase', '')}".replace(",", " "))


def print_regions(data: dict, limit: int = 60) -> None:
    nodes = data if isinstance(data, list) else data.get("regions", [])

    def walk(items, depth=0, budget=[limit]):
        for node in items:
            if budget[0] <= 0:
                return
            budget[0] -= 1
            rid = node.get("id") or node.get("value")
            name = node.get("name") or node.get("label")
            print(f"{'  ' * depth}{rid}\t{name}")
            children = node.get("children") or node.get("regions") or []
            if children:
                walk(children, depth + 1, budget)

    walk(nodes)
    print(f"\n(показаны первые {limit}; используй --json для полного списка)")


def run_batch(phrases: list[str], folder_id: str, api_key: str, regions: list[str], devices: list[str],
              num_phrases: int, delay: float, out_path: str | None) -> None:
    """Частотность по списку фраз за один прогон — вместо одноразового скрипта на каждый разбор.
    delay между вызовами держим консервативным (лимит API — 10/сек), retry на 429 уже внутри call_api."""
    results = []
    for i, phrase in enumerate(phrases):
        try:
            data = top_requests(phrase, folder_id, api_key, regions, devices, num_phrases)
            total = int(data.get("totalCount", 0) or 0)
            results.append({"phrase": phrase, "totalCount": total})
            print(f"{total:>8,}  {phrase}".replace(",", " "), flush=True)
        except SystemExit as e:
            print(f"ERROR  {phrase}: {e}", file=sys.stderr, flush=True)
            results.append({"phrase": phrase, "totalCount": None, "error": str(e)})
        if i < len(phrases) - 1:
            time.sleep(delay)

    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\nСохранено: {out_path}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("phrase", nargs="?", help="Фраза для проверки частотности")
    parser.add_argument("--regions", default="", help="ID регионов через запятую (напр. 213,1). По умолчанию — вся Россия")
    parser.add_argument("--devices", default="", help="desktop,mobile,tablet через запятую. По умолчанию — все")
    parser.add_argument("--num-phrases", type=int, default=50, help="Сколько связанных фраз вернуть (по умолчанию 50, максимум 2000)")
    parser.add_argument("--regions-tree", action="store_true", help="Показать дерево регионов (бесплатно) вместо проверки частотности")
    parser.add_argument("--json", action="store_true", help="Вывести сырой JSON вместо форматированного текста")
    parser.add_argument("--batch-file", default="", help="Файл со списком фраз (по одной на строку) — частотность по всем за один прогон")
    parser.add_argument("--delay", type=float, default=1.0, help="Пауза между запросами в батче, сек (по умолчанию 1.0 — держит нас в пределах 10 запросов/сек)")
    parser.add_argument("--out", default="", help="Путь для сохранения результатов батча в JSON")
    args = parser.parse_args()

    folder_id, api_key = get_config()

    if args.regions_tree:
        data = regions_tree(folder_id, api_key)
        print(json.dumps(data, ensure_ascii=False, indent=2)) if args.json else print_regions(data)
        return

    if args.batch_file:
        regions = [r.strip() for r in args.regions.split(",") if r.strip()]
        devices = [d.strip() for d in args.devices.split(",") if d.strip()]
        phrases = [line.strip() for line in Path(args.batch_file).read_text(encoding="utf-8").splitlines() if line.strip()]
        run_batch(phrases, folder_id, api_key, regions, devices, args.num_phrases, args.delay, args.out or None)
        return

    if not args.phrase:
        parser.error("укажи фразу для проверки, либо используй --regions-tree / --batch-file")

    regions = [r.strip() for r in args.regions.split(",") if r.strip()]
    devices = [d.strip() for d in args.devices.split(",") if d.strip()]

    data = top_requests(args.phrase, folder_id, api_key, regions, devices, args.num_phrases)
    print(json.dumps(data, ensure_ascii=False, indent=2)) if args.json else print_top_requests(args.phrase, data)


if __name__ == "__main__":
    main()
