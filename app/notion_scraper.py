# app/notion_scraper_live.py
import os
import json
from typing import List, Dict, Any, Literal, Optional
from dotenv import load_dotenv
from notion_client import Client
from notion_client.errors import APIResponseError, HTTPResponseError

# -----------------------------
# Environment & client
# -----------------------------
load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
ROOT_ID = os.getenv("PAGE_ID")

if not NOTION_TOKEN or not ROOT_ID:
    raise RuntimeError("Missing NOTION_TOKEN or PAGE_ID in environment.")

notion = Client(auth=NOTION_TOKEN)

# -----------------------------
# Output & state
# -----------------------------
os.makedirs("data", exist_ok=True)
OUTPUT_FILE = "data/notion_extracted.txt"
PROCESSED_IDS_FILE = "data/processed_ids.json"

# Cargar processed_ids existente
if os.path.exists(PROCESSED_IDS_FILE):
    with open(PROCESSED_IDS_FILE, "r", encoding="utf-8") as f:
        processed_ids = set(json.load(f))
else:
    processed_ids = set()

# Limpiar fichero de salida al inicio
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write("")

# -----------------------------
# Helpers
# -----------------------------
def write_line(line: str) -> None:
    """Añade una línea al fichero y fuerza escritura inmediata."""
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def normalize_id(raw_id: str) -> str:
    rid = raw_id.replace("-", "")
    if len(rid) != 32:
        return raw_id
    return f"{rid[0:8]}-{rid[8:12]}-{rid[12:16]}-{rid[16:20]}-{rid[20:32]}"

def flatten_rich_text(rich_text: Optional[List[Dict[str, Any]]]) -> str:
    if not rich_text:
        return ""
    return "".join(part.get("plain_text", "") for part in rich_text)

def identify_id_type(block_id: str) -> Literal["database", "page", "unknown", "linked_database"]:
    try:
        db = notion.databases.retrieve(block_id)
        if db.get("is_linked_database"):
            return "linked_database"
        return "database"
    except APIResponseError as e:
        if e.code not in ("object_not_found", "validation_error"):
            return "unknown"
    try:
        notion.pages.retrieve(block_id)
        return "page"
    except APIResponseError:
        return "unknown"

def extract_page_title(page: Dict[str, Any]) -> str:
    props = page.get("properties", {})
    for _, prop in props.items():
        if prop.get("type") == "title":
            return flatten_rich_text(prop.get("title", [])) or "(untitled)"
    return "(untitled)"

def extract_database_title(db: Dict[str, Any]) -> str:
    return flatten_rich_text(db.get("title", [])) or "(untitled database)"

def extract_property_text(prop: Dict[str, Any]) -> str:
    try:
        ptype = prop.get("type")
        if ptype in ("title", "rich_text"):
            return flatten_rich_text(prop.get(ptype, []))
        if ptype == "select":
            return prop.get("select", {}).get("name", "")
        if ptype == "multi_select":
            return ", ".join(i.get("name", "") for i in prop.get("multi_select", []))
        if ptype == "people":
            return ", ".join(p.get("name", "") for p in prop.get("people", []))
        if ptype == "relation":
            return ", ".join(r.get("id", "") for r in prop.get("relation", []))
        if ptype == "status":
            return prop.get("status", {}).get("name", "")
        if ptype == "number":
            return str(prop.get("number", ""))
        if ptype == "date":
            d = prop.get("date", {})
            return f"{d.get('start')} -> {d.get('end')}" if d.get("end") else d.get("start", "")
        if ptype in ("url", "email", "phone_number"):
            return prop.get(ptype, "") or ""
        if ptype == "checkbox":
            return str(prop.get("checkbox", False))
        return ""
    except Exception as e:
        return f"[property parse error: {e}]"

def extract_text_from_block(block: Dict[str, Any]) -> str:
    btype = block.get("type")
    data = block.get(btype, {})
    if "rich_text" in data:
        return flatten_rich_text(data.get("rich_text", []))
    return ""

def log(msg: str) -> None:
    print(msg)

# -----------------------------
# Core processing
# -----------------------------
def process_page(page_id: str, indent: int = 0) -> None:
    if page_id in processed_ids:
        log(f"Skipping already processed page: {page_id}")
        return
    try:
        page = notion.pages.retrieve(page_id)
    except (APIResponseError, HTTPResponseError) as e:
        log(f"[Error accessing page {page_id}: {getattr(e, 'message', str(e))}]")
        processed_ids.add(page_id)
        return

    title = extract_page_title(page)
    log(f"Processing page: {page_id} - {title}")
    write_line(" " * indent + f"# Page: {title} (ID: {page_id})")

    for pname, pvalue in page.get("properties", {}).items():
        value = extract_property_text(pvalue)
        if value:
            write_line(" " * indent + f"- {pname}: {value}")

    processed_ids.add(page_id)
    fetch_and_process_block_children(page_id, indent + 2)

def process_database(database_id: str, indent: int = 0) -> None:
    if database_id in processed_ids:
        log(f"Skipping already processed database: {database_id}")
        return
    try:
        db = notion.databases.retrieve(database_id)
        if db.get("is_linked_database"):
            log(f"Skipping linked database: {database_id}")
            return
        db_title = extract_database_title(db)
        log(f"Processing database: {database_id} - {db_title}")
        write_line(" " * indent + f"# Database: {db_title} (ID: {database_id})")
    except (APIResponseError, HTTPResponseError) as e:
        log(f"[Error accessing database {database_id}: {getattr(e, 'message', str(e))}]")
        processed_ids.add(database_id)
        return

    processed_ids.add(database_id)
    cursor = None
    while True:
        try:
            resp = notion.databases.query(database_id=database_id, start_cursor=cursor)
        except (APIResponseError, HTTPResponseError) as e:
            log(f"[Error querying database {database_id}: {getattr(e, 'message', str(e))}]")
            return
        for page in resp.get("results", []):
            pid = page["id"]
            t = identify_id_type(pid)
            if t == "database":
                process_database(pid, indent + 2)
            elif t == "page":
                process_page(pid, indent + 2)
            else:
                log(f"Skipping unknown type: {pid}")
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")

def fetch_and_process_block_children(block_id: str, indent: int) -> None:
    cursor = None
    while True:
        try:
            resp = notion.blocks.children.list(block_id=block_id, start_cursor=cursor)
        except (APIResponseError, HTTPResponseError) as e:
            log(f"[Error listing children of {block_id}: {getattr(e, 'message', str(e))}]")
            return
        for block in resp.get("results", []):
            bid = block["id"]
            btype = block.get("type", "")
            if btype == "child_page":
                t = identify_id_type(bid)
                if t == "page":
                    process_page(bid, indent + 2)
                elif t == "database":
                    process_database(bid, indent + 2)
            elif btype == "child_database":
                t = identify_id_type(bid)
                if t == "database":
                    process_database(bid, indent + 2)
            else:
                text = extract_text_from_block(block)
                if text:
                    write_line(" " * indent + text)
                if block.get("has_children"):
                    fetch_and_process_block_children(bid, indent + 2)
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")

# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    root_id = normalize_id(ROOT_ID)
    root_type = identify_id_type(root_id)
    log(f"Checking ID: {root_id}")

    if root_type == "database":
        process_database(root_id)
    elif root_type == "page":
        process_page(root_id)
    else:
        log("Unknown root type. Trying as page.")
        process_page(root_id)

    with open(PROCESSED_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(processed_ids), f, indent=2)

    log(f"Done. Output written to {OUTPUT_FILE}")
