# SQL injection + path traversal — triggers Cisco (AST dataflow),
# Aguara (SQL injection, path traversal), PipeLock (credential paths,
# eval/exec), detect-secrets (Slack token, GitHub token)

import os
import sqlite3

# detect-secrets: embedded tokens
SLACK_BOT_TOKEN = "xoxb-1234567890123-1234567890123-ABCDEFGHIJKLMNOPqrstuv"
GITHUB_TOKEN = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef01"


def search_users(search_term, table_name):
    """SQL injection via string concatenation."""
    conn = sqlite3.connect("users.db")
    query = f"SELECT * FROM {table_name} WHERE name LIKE '%{search_term}%'"
    cursor = conn.execute(query)
    return cursor.fetchall()


def read_file(file_path):
    """Path traversal — no sanitization."""
    with open(file_path) as f:
        return f.read()


def read_sensitive_files():
    """Read credential files from the host."""
    targets = [
        os.path.expanduser("~/.aws/credentials"),
        os.path.expanduser("~/.ssh/id_rsa"),
        "/etc/shadow",
        ".env",
    ]
    data = {}
    for path in targets:
        try:
            data[path] = read_file(path)
        except OSError:
            pass
    return data


def execute_query(raw_input):
    """Eval user input directly."""
    return eval(raw_input)
