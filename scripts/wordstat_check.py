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


def call_api(endpoint: str, folder_id: str, api_key: str, body: dict) -> dict:
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
        sys.exit("Rate limit (429) — подожди и повтори запрос.")
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("phrase", nargs="?", help="Фраза для проверки частотности")
    parser.add_argument("--regions", default="", help="ID регионов через запятую (напр. 213,1). По умолчанию — вся Россия")
    parser.add_argument("--devices", default="", help="desktop,mobile,tablet через запятую. По умолчанию — все")
    parser.add_argument("--num-phrases", type=int, default=50, help="Сколько связанных фраз вернуть (по умолчанию 50, максимум 2000)")
    parser.add_argument("--regions-tree", action="store_true", help="Показать дерево регионов (бесплатно) вместо проверки частотности")
    parser.add_argument("--json", action="store_true", help="Вывести сырой JSON вместо форматированного текста")
    args = parser.parse_args()

    folder_id, api_key = get_config()

    if args.regions_tree:
        data = regions_tree(folder_id, api_key)
        print(json.dumps(data, ensure_ascii=False, indent=2)) if args.json else print_regions(data)
        return

    if not args.phrase:
        parser.error("укажи фразу для проверки, либо используй --regions-tree")

    regions = [r.strip() for r in args.regions.split(",") if r.strip()]
    devices = [d.strip() for d in args.devices.split(",") if d.strip()]

    data = top_requests(args.phrase, folder_id, api_key, regions, devices, args.num_phrases)
    print(json.dumps(data, ensure_ascii=False, indent=2)) if args.json else print_top_requests(args.phrase, data)


if __name__ == "__main__":
    main()
