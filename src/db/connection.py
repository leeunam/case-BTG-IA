import os
import contextlib
import psycopg
from dotenv import load_dotenv

load_dotenv()

_DATABASE_URL = os.getenv("DATABASE_URL")

# Supabase note:
#   If db.[ref].supabase.co (direct) fails with "Network unreachable" (IPv6-only host),
#   use the Session Pooler URL instead:
#   Settings → Database → Connection Pooling → Session mode → URI
#   Format: postgresql://postgres.[ref]:[senha]@aws-0-[region].pooler.supabase.com:5432/postgres
#
#   Session pooler supports persistent connections and prepared statements (unlike Transaction pooler).


@contextlib.contextmanager
def get_conn(autocommit: bool = False):
    if not _DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL não configurada.\n"
            "Supabase → Settings → Database → Connection Pooling → Session mode → URI\n"
            "Formato: postgresql://postgres.[ref]:[senha]@aws-0-[região].pooler.supabase.com:5432/postgres"
        )
    with psycopg.connect(
        _DATABASE_URL,
        autocommit=autocommit,
        # Disable prepared statements — required for Session Pooler (PgBouncer)
        prepare_threshold=None,
    ) as conn:
        yield conn
