# app/notion_scraper.py
import os
import json
from typing import List, Dict, Any, Literal, Optional
from dotenv import load_dotenv
from notion_client import Client
from notion_client.errors import APIResponseError

# -----------------------------
# Environment & client
# -----------------------------
load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
ROOT_ID = os.getenv("PAGE_ID")  # can be a database or a page

if not NOTION_TOKEN or not ROOT_ID:
    raise RuntimeError("Missing NOTION_TOKEN or PAGE_ID in environment.")

notion = Client(auth=NOTION_TOKEN)

# -----------------------------
# Output & state
# -----------------------------
os.makedirs("data", exist_ok=True)
OUTPUT_FILE = "data/notion_extracted.txt"
PROCESSED_IDS_FILE = "data/processed_ids.json"

if os.path.exists(PROCESSED_IDS_FILE):
    with open(PROCESSED_IDS_FILE, "r", encoding="utf-8") as f:
        processed_ids = set(json.load(f))
else:
    processed_ids = set()

output_lines: List[str] = []

# -----------------------------
# Helpers
# -----------------------------
def normalize_id(raw_id: str) -> str:
    rid = raw_id.replace("-", "")
    if len(rid) != 32:
        return raw_id
    return f"{rid[0:8]}-{rid[8:12]}-{rid[12:16]}-{rid[16:20]}-{rid[20:32]}"

def flatten_rich_text(rich_text: Optional[List[Dict[str, Any]]]) -> str:
    if not rich_text:
        return ""
    return "".join(part.get("plain_text", "") for part in rich_text)

def identify_id_type(block_id: str) -> Literal["database", "page", "unknown"]:
    """Try to identify if an id is a database or a page, without raising."""
    try:
        notion.databases.retrieve(block_id)
        return "database"
    except APIResponseError as e:
        if e.code not in ("object_not_found", "validation_error"):
            # another error (e.g., no permission) – unknown
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
    """Extract human-readable text from a Notion property dict."""
    try:
        ptype = prop.get("type")
        if ptype == "title":
            return flatten_rich_text(prop.get("title", []))
        if ptype == "rich_text":
            return flatten_rich_text(prop.get("rich_text", []))
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
        if ptype == "url":
            return prop.get("url", "") or ""
        if ptype == "email":
            return prop.get("email", "") or ""
        if ptype == "phone_number":
            return prop.get("phone_number", "") or ""
        if ptype == "checkbox":
            return str(prop.get("checkbox", False))
        return ""
    except Exception as e:
        return f"[property parse error: {e}]"

def extract_text_from_block(block: Dict[str, Any]) -> str:
    """Return text contained in a block if text-based."""
    btype = block.get("type")
    data = block.get(btype, {})
    if "rich_text" in data:
        return flatten_rich_text(data.get("rich_text", []))

    # code blocks store text in 'rich_text' too
    if btype == "code":
        return flatten_rich_text(data.get("rich_text", []))

    # headings, quotes, callouts, to_do, list items all follow the same pattern of rich_text
    # If we needed more granularity, we could special-case them here.
    return ""

def log(msg: str) -> None:
    print(msg)

# -----------------------------
# Core processing
# -----------------------------
def process_page(page_id: str, indent: int = 0) -> None:
    """Retrieve a page, print and store its properties, then its block tree."""
    if page_id in processed_ids:
        log(f"Skipping already processed page: {page_id}")
        return

    try:
        page = notion.pages.retrieve(page_id)
    except APIResponseError as e:
        log(f"[Error accessing page {page_id}: {getattr(e, 'message', str(e))}]")
        output_lines.append(" " * indent + f"[error accessing page {page_id}: {getattr(e, 'message', str(e))}]")
        processed_ids.add(page_id)
        return

    title = extract_page_title(page)
    log(f"Processing page: {page_id} - {title}")

    output_lines.append(" " * indent + f"# Page: {title} (ID: {page_id})")

    # Dump properties
    props = page.get("properties", {})
    for pname, pvalue in props.items():
        value = extract_property_text(pvalue)
        if value:
            output_lines.append(" " * indent + f"- {pname}: {value}")

    processed_ids.add(page_id)

    # Process block tree
    fetch_and_process_block_children(page_id, indent + 2)

def fetch_and_process_block_children(block_id: str, indent: int) -> None:
    """Paginate through block children, write text, recurse into kids and child databases/pages."""
    cursor = None
    while True:
        try:
            resp = notion.blocks.children.list(block_id=block_id, start_cursor=cursor)
        except APIResponseError as e:
            log(f"[Error listing children of {block_id}: {getattr(e, 'message', str(e))}]")
            output_lines.append(" " * indent + f"[error listing children of {block_id}: {getattr(e, 'message', str(e))}]")
            return

        for block in resp.get("results", []):
            bid = block["id"]
            btype = block.get("type", "unknown")
            has_children = block.get("has_children", False)

            # child_page / child_database
            if btype == "child_page":
                child_title = block["child_page"].get("title", "(untitled)")
                output_lines.append(" " * indent + f"## Child page: {child_title} (ID: {bid})")
                log(f"Discovered child page: {bid} - {child_title}")
                # Decide whether to treat as page or database (should be page, but we are defensive)
                t = identify_id_type(bid)
                if t == "page":
                    process_page(bid, indent + 2)
                elif t == "database":
                    process_database(bid, indent + 2)
                else:
                    # try as page anyway
                    process_page(bid, indent + 2)
                continue

            if btype == "child_database":
                db_title = block["child_database"].get("title", "(untitled database)")
                output_lines.append(" " * indent + f"## Child database: {db_title} (ID: {bid})")
                log(f"Discovered child database: {bid} - {db_title}")
                process_database(bid, indent + 2)
                continue

            # text-based blocks
            text = extract_text_from_block(block)
            if text:
                output_lines.append(" " * indent + f"{text}")

            # recurse into block's children if any
            if has_children:
                fetch_and_process_block_children(bid, indent + 2)

        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")

def process_database(database_id: str, indent: int = 0) -> None:
    """Query a database, iterate its pages, and recurse."""
    if database_id in processed_ids:
        log(f"Skipping already processed database: {database_id}")
        return

    try:
        db = notion.databases.retrieve(database_id)
        db_title = extract_database_title(db)
        log(f"Processing database: {database_id} - {db_title}")
        output_lines.append(" " * indent + f"# Database: {db_title} (ID: {database_id})")
    except APIResponseError as e:
        log(f"[Error accessing database {database_id}: {getattr(e, 'message', str(e))}]")
        output_lines.append(" " * indent + f"[error accessing database {database_id}: {getattr(e, 'message', str(e))}]")
        processed_ids.add(database_id)
        return

    processed_ids.add(database_id)

    cursor = None
    total = 0
    while True:
        try:
            resp = notion.databases.query(database_id=database_id, start_cursor=cursor)
        except APIResponseError as e:
            log(f"[Error querying database {database_id}: {getattr(e, 'message', str(e))}]")
            output_lines.append(" " * indent + f"[error querying database {database_id}: {getattr(e, 'message', str(e))}]")
            return

        results = resp.get("results", [])
        for i, page in enumerate(results, 1):
            pid = page["id"]
            title = extract_page_title(page)
            total += 1
            log(f"Processed entry {total}: {title}")
            # Even though database.query returns pages, be defensive and detect type
            t = identify_id_type(pid)
            if t == "database":
                process_database(pid, indent + 2)
            else:
                process_page(pid, indent + 2)

        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")

# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    root_id = normalize_id(ROOT_ID)
    root_type = identify_id_type(root_id)

    print(f"Checking ID: {root_id}")

    if root_type == "database":
        process_database(root_id, indent=0)
    elif root_type == "page":
        process_page(root_id, indent=0)
    else:
        # Try page first, then database, but report unknown
        print("Root ID type could not be determined with certainty. Trying page first.")
        try:
            process_page(root_id, indent=0)
        except Exception:
            try:
                process_database(root_id, indent=0)
            except Exception as e:
                print(f"Unable to process root id: {e}")

    # Save outputs
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))

    with open(PROCESSED_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(processed_ids), f, indent=2)

    print(f"Done. Output written to {OUTPUT_FILE}")
