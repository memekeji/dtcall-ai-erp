DEFAULT_MYSQL_INIT_COMMAND = "SET sql_mode='STRICT_TRANS_TABLES'"


def normalize_mysql_init_command(value):
    raw = str(value or '').strip()
    if not raw:
        return DEFAULT_MYSQL_INIT_COMMAND

    normalized = raw
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"'", '"'}:
        normalized = normalized[1:-1]
    normalized = normalized.strip()
    if not normalized:
        return DEFAULT_MYSQL_INIT_COMMAND

    lowered = normalized.lower()
    if lowered.startswith('set '):
        return normalized
    if lowered.startswith('sql_mode='):
        return f'SET {normalized}'

    escaped = normalized.replace("'", "\\'")
    return f"SET sql_mode='{escaped}'"
