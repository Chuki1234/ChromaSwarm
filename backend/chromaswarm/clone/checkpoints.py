"""LangGraph state of Clone sessions, kept in Supabase (table `clone_graph_checkpoints`).

`SupabaseCloneSaver` is the graph's checkpointer. It *is* an `InMemorySaver` — the graph keeps running on memory,
with LangGraph's own semantics — and it mirrors Clone threads to Supabase:

* after every checkpoint of a thread whose pipeline is in Clone mode, the latest checkpoint of each namespace,
  the channel blobs it points at and its pending writes are serialized with the graph's own serializer and
  upserted as one row (in the background, newest wins, so a build never waits on the network);
* when the graph asks for a thread that memory does not have (the backend restarted), the row is loaded back
  into memory first — the graph continues exactly where it stopped, a pending question included.

Creative threads are never written (that mode keeps its in-memory state; it belongs to its own owner).
Without Supabase settings this is a plain `InMemorySaver`.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from chromaswarm.clone.history import CloneHistory

log = logging.getLogger(__name__)
TABLE = "clone_graph_checkpoints"


def _mode_of(value: Any) -> str | None:
    """The pipeline's mode from a channel value (a PipelineState or its dict)."""
    if value is None:
        return None
    mode = value.get("mode") if isinstance(value, dict) else getattr(value, "mode", None)
    return getattr(mode, "value", mode)


class SupabaseCloneSaver(InMemorySaver):
    def __init__(self, *, store: CloneHistory | None = None, **kw: Any) -> None:
        super().__init__(**kw)
        self.store = store or CloneHistory()
        self.clone_threads: set[str] = set()
        self._loaded: set[str] = set()
        self._pending: dict[str, asyncio.Task] = {}
        self._dirty: set[str] = set()

    # ---------------------------------------------------------------- serialization
    def snapshot_thread(self, thread_id: str) -> tuple[str, bytes, str | None] | None:
        """The latest checkpoint of each namespace of a thread + its blobs and writes, serialized."""
        namespaces = self.storage.get(thread_id)
        if not namespaces:
            return None
        storage, blobs, writes, step = {}, [], [], None
        for ns, checkpoints in namespaces.items():
            if not checkpoints:
                continue
            cid = max(checkpoints)  # checkpoint ids are time-ordered (uuid6)
            saved, metadata, parent = checkpoints[cid]
            storage[ns] = [cid, list(saved), list(metadata), parent]
            versions = self.serde.loads_typed(saved).get("channel_versions", {})
            for channel, version in versions.items():
                blob = self.blobs.get((thread_id, ns, channel, version))
                if blob is not None:
                    blobs.append([ns, channel, version, list(blob)])
            for (inner, value) in (self.writes.get((thread_id, ns, cid)) or {}).items():
                writes.append([ns, cid, list(inner), [value[0], value[1], list(value[2]), value[3]]])
            if ns == "":
                with _quiet():
                    pv = self.serde.loads_typed(tuple(next(b[3] for b in blobs if b[0] == "" and b[1] == "pipeline")))
                    step = getattr(getattr(pv, "step", None), "value", None) or (pv.get("step") if isinstance(pv, dict) else None)
        kind, data = self.serde.dumps_typed({"storage": storage, "blobs": blobs, "writes": writes})
        return kind, data, step

    def restore_thread(self, thread_id: str, kind: str, data: bytes) -> None:
        payload = self.serde.loads_typed((kind, data))
        for ns, (cid, saved, metadata, parent) in payload["storage"].items():
            self.storage[thread_id][ns][cid] = (tuple(saved), tuple(metadata), parent)
        for ns, channel, version, blob in payload["blobs"]:
            self.blobs[(thread_id, ns, channel, version)] = tuple(blob)
        for ns, cid, inner, (task_id, channel, value, path) in payload["writes"]:
            self.writes.setdefault((thread_id, ns, cid), {})[tuple(inner)] = (task_id, channel, tuple(value), path)
        self.clone_threads.add(thread_id)

    # ---------------------------------------------------------------- Supabase mirror
    async def _flush(self, thread_id: str) -> None:
        while thread_id in self._dirty:
            self._dirty.discard(thread_id)
            snap = self.snapshot_thread(thread_id)
            if snap is None:
                return
            kind, data, step = snap
            # The session row must exist first (foreign key); never overwrite a real one.
            await self.store._post("clone_sessions", {"id": thread_id, "state": {}}, "resolution=ignore-duplicates,return=minimal",
                                   "?on_conflict=id")
            await self.store._post(TABLE, {"thread_id": thread_id, "step": step, "serde_type": kind,
                                           "data": base64.b64encode(data).decode(), "updated_at": _now()},
                                   "resolution=merge-duplicates,return=minimal", "?on_conflict=thread_id")

    def _schedule(self, thread_id: str) -> None:
        if not self.store.enabled or thread_id not in self.clone_threads:
            return
        self._dirty.add(thread_id)
        task = self._pending.get(thread_id)
        if task is None or task.done():
            self._pending[thread_id] = asyncio.get_running_loop().create_task(self._flush(thread_id))

    async def flush_all(self) -> None:
        """Wait for every mirror write in flight (tests, shutdown)."""
        while any(not t.done() for t in self._pending.values()):
            await asyncio.gather(*[t for t in self._pending.values() if not t.done()], return_exceptions=True)

    async def _ensure_loaded(self, config: Any) -> None:
        thread_id = (config.get("configurable") or {}).get("thread_id")
        if not thread_id or thread_id in self._loaded or not self.store.enabled:
            return
        self._loaded.add(thread_id)
        if self.storage.get(thread_id):
            return
        rows = await self.store._get(TABLE, f"select=serde_type,data&thread_id=eq.{_q(thread_id)}")
        if rows:
            try:
                self.restore_thread(thread_id, rows[0]["serde_type"], base64.b64decode(rows[0]["data"]))
                log.info("clone thread %s restored from Supabase", thread_id)
            except Exception as e:  # noqa: BLE001 — a bad row means a fresh session, never a crash
                log.warning("could not restore clone thread %s: %s", thread_id, e)

    # ---------------------------------------------------------------- saver API
    async def aget_tuple(self, config):  # type: ignore[override]
        await self._ensure_loaded(config)
        return await super().aget_tuple(config)

    async def alist(self, config, **kw):  # type: ignore[override]
        if config:
            await self._ensure_loaded(config)
        async for item in super().alist(config, **kw):
            yield item

    async def aput(self, config, checkpoint, metadata, new_versions):  # type: ignore[override]
        await self._ensure_loaded(config)
        out = await super().aput(config, checkpoint, metadata, new_versions)
        thread_id = (config.get("configurable") or {})["thread_id"]
        mode = _mode_of((checkpoint.get("channel_values") or {}).get("pipeline"))
        if mode == "clone":
            self.clone_threads.add(thread_id)
        elif mode is not None:
            self.clone_threads.discard(thread_id)
        self._schedule(thread_id)
        return out

    async def aput_writes(self, config, writes, task_id, task_path=""):  # type: ignore[override]
        await super().aput_writes(config, writes, task_id, task_path)
        self._schedule((config.get("configurable") or {})["thread_id"])


class _quiet:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return True  # the step label is optional


def _now() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat()


def _q(value: str) -> str:
    from urllib.parse import quote
    return quote(value, safe="")
