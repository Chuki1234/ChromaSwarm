-- ChromaSwarm · LangGraph state of Clone sessions (the latest checkpoint per thread).
-- The graph runs on an in-memory saver; every new checkpoint of a Clone thread is mirrored here, and a thread
-- missing from memory (backend restarted) is loaded back from here. Backend-only: RLS on, no policies.

create table if not exists public.clone_graph_checkpoints (
  thread_id   text primary key references public.clone_sessions (id) on delete cascade,
  step        text,                          -- pipeline step at this checkpoint (for humans; not read back)
  serde_type  text not null,                 -- LangGraph serializer type tag
  data        text not null,                 -- base64 of the serialized latest checkpoint + channel blobs + writes
  updated_at  timestamptz not null default now()
);

alter table public.clone_graph_checkpoints enable row level security;
