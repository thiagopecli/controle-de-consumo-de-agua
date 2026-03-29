import os


def missing_required_env(required_keys):
    return [key for key in required_keys if not str(os.getenv(key, "")).strip()]


def env_status_line(required_keys):
    missing = set(missing_required_env(required_keys))
    itens = [f"{key}={'MISSING' if key in missing else 'OK'}" for key in required_keys]
    return " | ".join(itens)


def ensure_required_env(required_keys, context):
    missing = missing_required_env(required_keys)
    if missing:
        raise RuntimeError(
            f"[{context}] variaveis obrigatorias ausentes: {', '.join(missing)}"
        )