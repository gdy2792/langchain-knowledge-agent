"""Two Supabase clients for two different jobs, kept deliberately separate:
- the anon-key client only ever verifies a user's own login token
- the service-role client is the only thing allowed to read/write the
  `conversations` table directly, since it bypasses Row Level Security —
  safe here because it's never exposed outside this backend process.
"""

from agent.config import SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL
from supabase import Client, create_client


def build_auth_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def build_service_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
