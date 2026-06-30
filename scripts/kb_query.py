# -*- coding: utf-8 -*-
"""Project KB Query Tool - fast lookups for code modifications."""
import sqlite3, sys, json, os

DB = r"E:\研发\dtcall\project_knowledge.db"

def query(usage=None):
    usage = usage or sys.argv[1] if len(sys.argv) > 1 else "help"

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    if usage == "func":
        name = sys.argv[2]
        c.execute("""
            SELECT f.relpath, fn.line_start, fn.type, fn.class_name, fn.args, fn.docstring
            FROM functions fn JOIN files f ON fn.file_id=f.id
            WHERE fn.name=? LIMIT 20""", (name,))
        for row in c.fetchall():
            print(f"{row[0]}:{row[1]}  [{row[2]} in {row[3] or '-'}] {name}({row[4]})")
            if row[5]:
                print(f"  {row[5][:120]}")

    elif usage == "callers":
        name = sys.argv[2]
        c.execute("""
            SELECT DISTINCT caller_file, caller_func FROM call_graph
            WHERE callee_func=? LIMIT 20""", (name,))
        for row in c.fetchall():
            print(f"  {row[0]} -> {row[1]}()")

    elif usage == "model":
        name = sys.argv[2]
        c.execute("""
            SELECT f.relpath, m.table_name, m.fields FROM models m
            JOIN files f ON m.file_id=f.id
            WHERE m.class_name LIKE ? LIMIT 5""", (f"%{name}%",))
        for row in c.fetchall():
            print(f"{row[0]}  table={row[1]}")
            fields = json.loads(row[2])
            for fd in fields[:20]:
                print(f"  {fd['name']}: {fd['type']}")

    elif usage == "route":
        pattern = sys.argv[2] if len(sys.argv) > 2 else ""
        c.execute("""
            SELECT f.relpath, u.path, u.view_name, u.url_name FROM urls u
            JOIN files f ON u.file_id=f.id WHERE u.path LIKE ? LIMIT 30""",
            (f"%{pattern}%",))
        for row in c.fetchall():
            print(f"  {row[0]:50s} {row[1]:30s} -> {row[2] or '?'}")

    elif usage == "file":
        pattern = sys.argv[2] if len(sys.argv) > 2 else ""
        c.execute("""
            SELECT fn.name, fn.type, fn.line_start, fn.args FROM functions fn
            JOIN files f ON fn.file_id=f.id
            WHERE f.relpath LIKE ? ORDER BY fn.line_start LIMIT 50""",
            (f"%{pattern}%",))
        for row in c.fetchall():
            print(f"  L{row[2]:5d} [{row[1]:8s}] {row[0]}({row[3]})")

    elif usage == "tag":
        tagname = sys.argv[2]
        c.execute("""
            SELECT DISTINCT f.relpath, fn.name, fn.type FROM functions fn
            JOIN files f ON fn.file_id=f.id
            JOIN function_tags ft ON fn.id=ft.function_id
            JOIN knowledge_tags kt ON ft.tag_id=kt.id
            WHERE kt.name=? LIMIT 30""", (tagname,))
        for row in c.fetchall():
            print(f"  {row[0]:50s} [{row[2]:8s}] {row[1]}")

    elif usage == "imports":
        pattern = sys.argv[2] if len(sys.argv) > 2 else ""
        c.execute("""
            SELECT f.relpath, i.module, i.import_type FROM imports i
            JOIN files f ON i.file_id=f.id
            WHERE i.module LIKE ? LIMIT 30""", (f"%{pattern}%",))
        for row in c.fetchall():
            print(f"  {row[0]:55s} imports {row[1]} ({row[2]})")

    elif usage == "doc":
        pattern = sys.argv[2] if len(sys.argv) > 2 else ""
        c.execute("""SELECT filepath, title, sections FROM documents
                     WHERE title LIKE ? OR sections LIKE ?""",
                  (f"%{pattern}%", f"%{pattern}%"))
        for row in c.fetchall():
            print(f"{row[0]}")
            print(f"  {row[1]}")
            secs = json.loads(row[2])
            for s in secs[:10]:
                print(f"    - {s}")

    elif usage == "apps":
        c.execute("""SELECT DISTINCT
                     CASE WHEN relpath LIKE 'apps/%' THEN
                       substr(relpath, 6, instr(substr(relpath, 6), '/') - 1)
                     ELSE relpath END as app,
                     COUNT(*) as file_count
                     FROM files GROUP BY 1 ORDER BY 2 DESC""")
        for row in c.fetchall():
            print(f"  {row[0]:25s} {row[1]} files")

    else:
        print("""Knowledge Base Query Tool:
  func <name>     - Find function/class definition
  callers <name>  - Who calls this function
  model <name>    - Django model details
  route <path>    - URL routes matching pattern
  file <pattern>  - Functions in a file
  tag <name>      - Functions by business tag (message,customer,project,etc)
  imports <mod>   - Files importing a module
  doc <pattern>   - Search documents
  apps            - App file counts
  stats           - Overall statistics""")

    if usage == "stats":
        c.execute("SELECT COUNT(*) FROM files"); print(f"Files: {c.fetchone()[0]}")
        c.execute("SELECT COUNT(*) FROM functions"); print(f"Functions: {c.fetchone()[0]}")
        c.execute("SELECT COUNT(*) FROM models"); print(f"Models: {c.fetchone()[0]}")
        c.execute("SELECT COUNT(*) FROM urls"); print(f"Routes: {c.fetchone()[0]}")

    conn.close()

if __name__ == "__main__":
    query()
