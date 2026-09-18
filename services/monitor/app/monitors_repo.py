"""Repository layer for public.monitors with Supabase persistence and last-known-good resilience."""

from typing import Any, Dict, List, Optional
from app.matching import MonitorPreferences, UserMonitor
from app.utils.logger import logger


class SupabaseMonitorRepository:
    """Handles CRUD operations for public.monitors in Supabase with resilient in-memory fallback."""

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_service_role_key: Optional[str] = None,
        supabase_client: Optional[Any] = None,
    ):
        self.supabase: Optional[Any] = None

        if supabase_client is not None:
            self.supabase = supabase_client
        elif supabase_url and supabase_service_role_key:
            try:
                from supabase import create_client
                self.supabase = create_client(supabase_url, supabase_service_role_key)
                logger.info("SupabaseMonitorRepository inicializado com cliente Supabase.")
            except Exception as err:
                logger.error(f"Falha ao inicializar cliente Supabase no repositório de monitores: {err}")
                self.supabase = None

        # In-memory storage (used for tests or when Supabase client is not available)
        self._in_memory_monitors: Dict[str, UserMonitor] = {}

    def _row_to_monitor(self, row: Dict[str, Any]) -> UserMonitor:
        """Maps a public.monitors database row to a UserMonitor domain model."""
        channels = row.get("notify_channels") or ["dashboard", "telegram"]
        prefs = MonitorPreferences()

        return UserMonitor(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            institution_id=str(row["institution_id"]) if row.get("institution_id") else None,
            location_id=str(row["location_id"]) if row.get("location_id") else None,
            course_id=str(row["course_id"]) if row.get("course_id") else None,
            shift=row.get("shift"),
            active=bool(row.get("active", True)),
            preferences=prefs,
            all_providers=bool(row.get("all_providers", False)),
            query_text=row.get("query_text"),
            city=row.get("city"),
            state=row.get("state") or "SP",
            modality=row.get("modality") or "all",
            opportunity_type=row.get("opportunity_type") or "all",
        )

    async def list_active_monitors(self) -> List[UserMonitor]:
        """Fetches all active monitors (active = true) from Supabase."""
        if self.supabase:
            try:
                res = (
                    self.supabase.table("monitors")
                    .select("*")
                    .eq("active", True)
                    .execute()
                )
                monitors = [self._row_to_monitor(row) for row in (res.data or [])]
                # Update in-memory mirror
                for m in monitors:
                    self._in_memory_monitors[m.id] = m
                return monitors
            except Exception as err:
                logger.error(f"Erro ao buscar monitores ativos no Supabase: {err}")
                raise err

        return [m for m in self._in_memory_monitors.values() if m.active]

    async def get_user_monitors(self, user_id: str, active_only: bool = False) -> List[UserMonitor]:
        """Fetches all monitors for a specific user ID."""
        if self.supabase:
            try:
                query = self.supabase.table("monitors").select("*").eq("user_id", user_id)
                if active_only:
                    query = query.eq("active", True)
                res = query.execute()
                monitors = [self._row_to_monitor(row) for row in (res.data or [])]
                for m in monitors:
                    self._in_memory_monitors[m.id] = m
                return monitors
            except Exception as err:
                logger.error(f"Erro ao buscar monitores do usuário {user_id} no Supabase: {err}")
                raise err

        return [
            m for m in self._in_memory_monitors.values()
            if m.user_id == user_id and (not active_only or m.active)
        ]

    async def set_monitor_active(self, monitor_id: str, active: bool, user_id: Optional[str] = None) -> bool:
        """Updates the active status of a specific monitor."""
        if self.supabase:
            try:
                query = self.supabase.table("monitors").update({"active": active}).eq("id", monitor_id)
                if user_id:
                    query = query.eq("user_id", user_id)
                res = query.execute()
                success = bool(res.data and len(res.data) > 0)
                if success and monitor_id in self._in_memory_monitors:
                    self._in_memory_monitors[monitor_id].active = active
                return success
            except Exception as err:
                logger.error(f"Erro ao atualizar status do monitor {monitor_id} no Supabase: {err}")
                return False

        if monitor_id in self._in_memory_monitors:
            if user_id and self._in_memory_monitors[monitor_id].user_id != user_id:
                return False
            self._in_memory_monitors[monitor_id].active = active
            return True
        return False

    def seed_in_memory_monitor(self, monitor: UserMonitor) -> None:
        """Helper to seed monitors for testing or offline mode."""
        self._in_memory_monitors[monitor.id] = monitor
