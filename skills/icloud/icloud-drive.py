#!/usr/bin/env python3
import io
import json
import sys
from datetime import datetime


def fail(message, code=1):
    print(json.dumps({"error": message}))
    sys.exit(code)


def read_payload():
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


def load_pyicloud():
    try:
        from pyicloud import PyiCloudService
    except Exception:
        fail("pyicloud is not installed. Run `python3 -m pip install pyicloud` and create a session with `icloud --username you@example.com` first.")
    return PyiCloudService


def iso(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def build_path(parent, name):
    if not parent or parent == "/":
        return f"/{name}"
    return f"{parent.rstrip('/')}/{name}"


def normalize(node, path, parent_path):
    data = getattr(node, "data", {}) or {}
    extension = data.get("extension")
    return {
        "id": data.get("docwsid") or data.get("drivewsid") or path,
        "name": getattr(node, "name", path.rsplit("/", 1)[-1] or "/"),
        "path": path,
        "parent_path": parent_path,
        "kind": getattr(node, "type", None),
        "size": getattr(node, "size", None),
        "extension": extension,
        "etag": data.get("etag"),
        "modified_at": iso(getattr(node, "date_modified", None)),
        "preview": None,
        "content": None,
        "url": f"https://www.icloud.com/iclouddrive/{data.get('docwsid')}" if data.get("docwsid") else None,
    }


def connect(params):
    PyiCloudService = load_pyicloud()
    username = params.get("username")
    if not username:
        fail("Missing account param `username`")
    china_mainland = bool(params.get("china_mainland"))
    try:
        api = PyiCloudService(username, china_mainland=china_mainland)
    except Exception as exc:
        fail(str(exc))
    if getattr(api, "requires_2fa", False):
        fail("iCloud requires 2FA verification. Refresh the saved pyicloud session with `icloud --username your-apple-id@example.com`.")
    if getattr(api, "requires_2sa", False):
        fail("iCloud requires two-step verification. Refresh the saved pyicloud session with the `icloud` CLI first.")
    return api


def resolve_node(root, path):
    node = root
    if not path or path == "/":
        return node, "/"
    normalized = "/" + path.strip("/")
    for part in [p for p in normalized.strip("/").split("/") if p]:
        node = node[part]
    return node, normalized


def list_documents(api, path):
    node, normalized_path = resolve_node(api.drive, path)
    if getattr(node, "type", "folder") != "folder":
        fail(f"{normalized_path} is not a folder")
    items = []
    for child in node.get_children():
        child_path = build_path(normalized_path, child.name)
        items.append(normalize(child, child_path, normalized_path))
    print(json.dumps(items))


def get_document(api, path):
    node, normalized_path = resolve_node(api.drive, path)
    parent_path = "/" if normalized_path.count("/") <= 1 else normalized_path.rsplit("/", 1)[0]
    print(json.dumps(normalize(node, normalized_path, parent_path)))


def read_document(api, path):
    node, normalized_path = resolve_node(api.drive, path)
    item = normalize(node, normalized_path, "/" if normalized_path.count("/") <= 1 else normalized_path.rsplit("/", 1)[0])
    if getattr(node, "type", None) != "file":
        print(json.dumps(item))
        return
    try:
        response = node.open()
        raw = response.content
        text = raw.decode("utf-8", errors="replace")
    except Exception as exc:
        fail(f"Unable to read {normalized_path}: {exc}")
    item["preview"] = text[:4000]
    item["content"] = text
    print(json.dumps(item))


def create_document(api, path, filename, content):
    folder, normalized_path = resolve_node(api.drive, path)
    if getattr(folder, "type", "folder") != "folder":
        fail(f"{normalized_path} is not a folder")
    file_like = io.BytesIO(content.encode("utf-8"))
    file_like.name = filename
    folder.upload(file_like)
    created_path = build_path(normalized_path, filename)
    created_node, _ = resolve_node(api.drive, created_path)
    item = normalize(created_node, created_path, normalized_path)
    item["preview"] = content[:4000]
    item["content"] = content
    print(json.dumps(item))


def create_folder(api, path, name):
    folder, normalized_path = resolve_node(api.drive, path)
    folder.mkdir(name)
    print(json.dumps({"ok": True, "path": build_path(normalized_path, name)}))


def rename_document(api, path, name):
    node, normalized_path = resolve_node(api.drive, path)
    parent_path = "/" if normalized_path.count("/") <= 1 else normalized_path.rsplit("/", 1)[0]
    node.rename(name)
    print(json.dumps({"ok": True, "old_path": normalized_path, "path": build_path(parent_path, name)}))


def delete_document(api, path):
    node, normalized_path = resolve_node(api.drive, path)
    node.delete()
    print(json.dumps({"ok": True, "path": normalized_path}))


def main():
    if len(sys.argv) < 2:
        fail("Missing operation")
    operation = sys.argv[1]
    payload = read_payload()
    params = payload.get("params") or {}
    api = connect(params)

    if operation == "list":
        list_documents(api, params.get("path", "/"))
        return
    if operation == "get":
        get_document(api, params.get("path"))
        return
    if operation == "read":
        read_document(api, params.get("path"))
        return
    if operation == "create":
        create_document(api, params.get("path", "/"), params.get("filename"), params.get("content", ""))
        return
    if operation == "mkdir":
        create_folder(api, params.get("path", "/"), params.get("name"))
        return
    if operation == "rename":
        rename_document(api, params.get("path"), params.get("name"))
        return
    if operation == "delete":
        delete_document(api, params.get("path"))
        return
    fail(f"Unknown operation: {operation}")


if __name__ == "__main__":
    main()
