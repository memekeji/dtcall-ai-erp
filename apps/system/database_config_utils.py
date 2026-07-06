DEFAULT_MYSQL_INIT_COMMAND = "SET sql_mode='STRICT_TRANS_TABLES'"


def normalize_mysql_init_command(value):
    raw = str(value or '').strip()
    if not raw:
        return DEFAULT_MYSQL_INIT_COMMAND

    normalized = raw
    while normalized:
        stripped = normalized.strip().rstrip(';').strip()
        if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
            normalized = stripped[1:-1]
            continue
        normalized = stripped
        break

    if not normalized:
        return DEFAULT_MYSQL_INIT_COMMAND

    lowered = normalized.lower()
    if lowered.startswith('set '):
        return normalized
    if lowered.startswith('session sql_mode='):
        return f'SET {normalized}'
    if lowered.startswith('sql_mode='):
        return f'SET {normalized}'

    escaped = normalized.strip("'\"").replace("'", "\\'")
    if not escaped:
        return DEFAULT_MYSQL_INIT_COMMAND
    return f"SET sql_mode='{escaped}'"
