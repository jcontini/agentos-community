#!/usr/bin/env python3
"""
Conversation History - Queries conversation history from AI agents.

Supports:
- Cursor (macOS, with Linux/Windows paths ready to add)
- Claude Desktop (planned)

Usage:
    python history.py <action> [--agent cursor] [--query "search term"] [--limit 30]
"""

import os
import sys
import json
import sqlite3
import argparse
from datetime import datetime
from collections import Counter
from pathlib import Path
from abc import ABC, abstractmethod


# =============================================================================
# Platform Detection
# =============================================================================

def get_platform():
    """Detect current platform."""
    if sys.platform == "darwin":
        return "macos"
    elif sys.platform.startswith("linux"):
        return "linux"
    elif sys.platform == "win32":
        return "windows"
    return "unknown"


# =============================================================================
# Agent Base Class
# =============================================================================

class AgentHistory(ABC):
    """Base class for agent conversation history."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Agent name."""
        pass
    
    @abstractmethod
    def get_storage_paths(self) -> list:
        """Return list of storage paths to check."""
        pass
    
    @abstractmethod
    def list_conversations(self, limit: int = 30) -> list:
        """List recent conversations."""
        pass
    
    @abstractmethod
    def search_conversations(self, query: str, limit: int = 30) -> list:
        """Search conversations by keyword."""
        pass


# =============================================================================
# Cursor Agent
# =============================================================================

class CursorHistory(AgentHistory):
    """Cursor conversation history handler."""
    
    name = "cursor"
    
    PATHS = {
        "macos": "~/Library/Application Support/Cursor/User/workspaceStorage",
        "linux": "~/.config/Cursor/User/workspaceStorage",
        "windows": "%APPDATA%/Cursor/User/workspaceStorage",
    }
    
    def get_storage_paths(self) -> list:
        platform = get_platform()
        base_path = self.PATHS.get(platform)
        if not base_path:
            return []
        
        expanded = os.path.expanduser(os.path.expandvars(base_path))
        if os.path.exists(expanded):
            return [expanded]
        return []
    
    def _get_workspace_path(self, workspace_dir: str, db_path: str) -> str:
        """Get workspace path from workspace.json or infer from history."""
        workspace_json = os.path.join(os.path.dirname(db_path), "workspace.json")
        
        if os.path.exists(workspace_json):
            try:
                with open(workspace_json) as f:
                    data = json.load(f)
                    return data.get("folder", "").replace("file://", "")
            except:
                pass
        
        # Try to infer from history entries
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM ItemTable WHERE key = 'history.entries' LIMIT 1")
            result = cursor.fetchone()
            conn.close()
            
            if result:
                entries = json.loads(result[0])
                if entries and isinstance(entries, list):
                    for entry in entries[:3]:
                        if isinstance(entry, dict):
                            resource = entry.get("editor", {}).get("resource", "")
                            if resource.startswith("file://"):
                                path = resource.replace("file://", "")
                                return os.path.dirname(path)
        except:
            pass
        
        return "Unknown"
    
    def _extract_conversations(self, db_path: str) -> list:
        """Extract conversations from a single database."""
        conversations = []
        
        try:
            workspace_path = self._get_workspace_path(
                os.path.dirname(db_path), db_path
            )
            workspace_name = os.path.basename(workspace_path) if workspace_path != "Unknown" else "Unknown"
            
            mod_time = os.path.getmtime(db_path)
            mod_date = datetime.fromtimestamp(mod_time)
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get prompt count
            prompt_count = 0
            cursor.execute("SELECT value FROM ItemTable WHERE key = 'aiService.prompts'")
            result = cursor.fetchone()
            if result:
                try:
                    prompts = json.loads(result[0])
                    if isinstance(prompts, list):
                        prompt_count = len(prompts)
                except:
                    pass
            
            # Get composer conversations
            cursor.execute("SELECT value FROM ItemTable WHERE key = 'composer.composerData'")
            result = cursor.fetchone()
            if result:
                composer = json.loads(result[0])
                composers = composer.get("allComposers", [])
                
                for comp in composers:
                    name = comp.get("name", "")
                    if name:
                        # Parse file types from subtitle
                        subtitle = comp.get("subtitle", "")
                        file_types = Counter()
                        if subtitle:
                            parts = subtitle.replace(",", " ").split()
                            for part in parts:
                                if "." in part:
                                    ext = part.split(".")[-1].lower()
                                    if ext and len(ext) < 8 and ext.isalnum():
                                        file_types[ext] += 1
                        
                        # Get per-conversation timestamp
                        updated_at = comp.get("lastUpdatedAt")
                        created_at = comp.get("createdAt")
                        
                        if updated_at:
                            conv_ts = updated_at / 1000  # Convert from milliseconds
                        elif created_at:
                            conv_ts = created_at / 1000
                        else:
                            conv_ts = mod_time  # Fallback to workspace mod time
                        
                        conv_date = datetime.fromtimestamp(conv_ts)
                        
                        conversations.append({
                            "agent": "cursor",
                            "workspace": workspace_name,
                            "workspace_path": workspace_path,
                            "name": name,
                            "modified": conv_date.isoformat(),
                            "modified_ts": conv_ts,
                            "modified_date": conv_date.strftime("%Y-%m-%d"),
                            "modified_time": conv_date.strftime("%H:%M"),
                            "lines_added": comp.get("totalLinesAdded", 0),
                            "lines_removed": comp.get("totalLinesRemoved", 0),
                            "files_changed": comp.get("filesChangedCount", 0),
                            "file_types": dict(file_types),
                            "messages": prompt_count,
                            "subtitle": subtitle,
                            "archived": comp.get("isArchived", False),
                        })
            
            conn.close()
        except Exception as e:
            pass
        
        return conversations
    
    def list_conversations(self, limit: int = 30) -> list:
        """List recent Cursor conversations."""
        all_conversations = []
        
        for storage_path in self.get_storage_paths():
            for workspace_dir in os.listdir(storage_path):
                db_path = os.path.join(storage_path, workspace_dir, "state.vscdb")
                if os.path.exists(db_path):
                    all_conversations.extend(self._extract_conversations(db_path))
        
        # Sort by modified date, dedupe
        all_conversations.sort(key=lambda x: x["modified_ts"], reverse=True)
        
        seen = set()
        unique = []
        for conv in all_conversations:
            key = f"{conv['workspace']}:{conv['name']}"
            if key not in seen:
                seen.add(key)
                unique.append(conv)
        
        return unique[:limit]
    
    def search_conversations(self, query: str, limit: int = 30) -> list:
        """Search Cursor conversations by keyword."""
        query_lower = query.lower()
        all_conversations = self.list_conversations(limit=500)  # Get more to search
        
        matches = []
        for conv in all_conversations:
            # Search in name, workspace, subtitle
            searchable = " ".join([
                conv["name"],
                conv["workspace"],
                conv.get("subtitle", ""),
            ]).lower()
            
            if query_lower in searchable:
                matches.append(conv)
        
        return matches[:limit]


# =============================================================================
# Claude Desktop Agent (placeholder for future)
# =============================================================================

class ClaudeHistory(AgentHistory):
    """Claude Desktop conversation history handler (planned)."""
    
    name = "claude"
    
    PATHS = {
        "macos": "~/Library/Application Support/Claude",
        "linux": "~/.config/claude",
        "windows": "%APPDATA%/Claude",
    }
    
    def get_storage_paths(self) -> list:
        platform = get_platform()
        base_path = self.PATHS.get(platform)
        if not base_path:
            return []
        
        expanded = os.path.expanduser(os.path.expandvars(base_path))
        if os.path.exists(expanded):
            return [expanded]
        return []
    
    def list_conversations(self, limit: int = 30) -> list:
        # TODO: Implement Claude Desktop history extraction
        return []
    
    def search_conversations(self, query: str, limit: int = 30) -> list:
        # TODO: Implement Claude Desktop search
        return []


# =============================================================================
# Registry
# =============================================================================

AGENTS = {
    "cursor": CursorHistory,
    "claude": ClaudeHistory,
}


def get_agent(name: str) -> AgentHistory:
    """Get agent history handler by name."""
    if name not in AGENTS:
        raise ValueError(f"Unknown agent: {name}. Available: {list(AGENTS.keys())}")
    return AGENTS[name]()


def get_all_agents() -> list:
    """Get all available agent handlers."""
    return [cls() for cls in AGENTS.values()]


# =============================================================================
# Output Formatting
# =============================================================================

def format_table(conversations: list) -> str:
    """Format conversations as a table, grouped by date."""
    if not conversations:
        return "No conversations found."
    
    from datetime import datetime as dt
    from collections import defaultdict
    
    # Group by date
    by_date = defaultdict(list)
    for conv in conversations:
        date_str = conv.get("modified_date", conv["modified"][:10])
        by_date[date_str].append(conv)
    
    # Format date headers
    today = dt.now().strftime("%Y-%m-%d")
    yesterday = (dt.now().replace(hour=0, minute=0, second=0) 
                 - __import__('datetime').timedelta(days=1)).strftime("%Y-%m-%d")
    
    def date_header(date_str):
        if date_str == today:
            return "Today"
        elif date_str == yesterday:
            return "Yesterday"
        else:
            return dt.strptime(date_str, "%Y-%m-%d").strftime("%A, %B %d")
    
    lines = []
    
    for date_str in sorted(by_date.keys(), reverse=True):
        convs = by_date[date_str]
        # Sort by time within the day (most recent first)
        convs.sort(key=lambda x: x["modified_ts"], reverse=True)
        
        lines.append(f"\n## {date_header(date_str)}")
        lines.append("")
        lines.append("| Time | Name | Files |")
        lines.append("|------|------|-------|")
        
        for conv in convs:
            time_str = conv.get("modified_time", conv["modified"][11:16])
            name = conv["name"]
            if len(name) > 40:
                name = name[:37] + "…"
            
            # Format file types with total count
            ft = conv.get("file_types", {})
            total_files = sum(ft.values())
            if ft:
                parts = [f".{ext}" for ext, _ in sorted(ft.items(), key=lambda x: -x[1])[:4]]
                files_str = ", ".join(parts)
                if total_files > 0:
                    files_str = f"{files_str} ({total_files})"
            else:
                files_str = "—"
            
            lines.append(f"| {time_str} | {name} | {files_str} |")
    
    return "\n".join(lines)


def format_json(conversations: list) -> str:
    """Format conversations as JSON."""
    return json.dumps(conversations, indent=2)


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Query AI agent conversation history")
    parser.add_argument("action", choices=["list", "search", "agents"], 
                        help="Action to perform")
    parser.add_argument("--agent", "-a", default="cursor",
                        help="Agent to query (cursor, claude, or 'all')")
    parser.add_argument("--query", "-q", default="",
                        help="Search query (for search action)")
    parser.add_argument("--limit", "-l", type=int, default=30,
                        help="Maximum results to return")
    parser.add_argument("--format", "-f", choices=["table", "json"], default="table",
                        help="Output format")
    
    args = parser.parse_args()
    
    if args.action == "agents":
        # List available agents
        info = []
        for name, cls in AGENTS.items():
            agent = cls()
            paths = agent.get_storage_paths()
            info.append({
                "name": name,
                "available": len(paths) > 0,
                "paths": paths,
            })
        print(json.dumps(info, indent=2))
        return
    
    # Get conversations
    if args.agent == "all":
        agents = get_all_agents()
    else:
        agents = [get_agent(args.agent)]
    
    all_results = []
    for agent in agents:
        if args.action == "list":
            results = agent.list_conversations(limit=args.limit)
        elif args.action == "search":
            if not args.query:
                print("Error: --query required for search action", file=sys.stderr)
                sys.exit(1)
            results = agent.search_conversations(args.query, limit=args.limit)
        else:
            results = []
        
        all_results.extend(results)
    
    # Sort combined results by date
    all_results.sort(key=lambda x: x["modified_ts"], reverse=True)
    all_results = all_results[:args.limit]
    
    # Output
    if args.format == "json":
        print(format_json(all_results))
    else:
        print(format_table(all_results))


if __name__ == "__main__":
    main()
