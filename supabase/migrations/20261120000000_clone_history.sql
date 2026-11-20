-- ChromaSwarm · Clone mode history (sessions, conversation, Chroma's activity).
-- Written and read only by the backend with the service-role key: RLS is on and no policy is granted,
-- so the anon / authenticated keys cannot read or change anything here.

create table if not exists public.clone_sessions (
  id          text primary key,                 -- the Studio session id (s-xxxx)
  url         text,                             -- reference page
  title       text,
  domain      text,                             -- guessed kind of site (saas, portfolio, ...)
  step        text,                             -- B1 ... B12
  status      text,                             -- reading | planning | building | handed-over | finished | error
  fidelity    real,                             -- 1:1 acceptance score (0-100) once measured
  state       jsonb not null,                   -- full PipelineState: what a restart resumes from
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists clone_sessions_updated_idx on public.clone_sessions (updated_at desc);

create table if not exists public.clone_messages (
  id          bigint generated always as identity primary key,
  session_id  text not null references public.clone_sessions (id) on delete cascade,
  role        text not null check (role in ('user', 'assistant')),
  kind        text not null,                    -- answer | notice | question
  step        text,
  text        text not null,
  payload     jsonb,
  created_at  timestamptz not null default now()
);
create index if not exists clone_messages_session_idx on public.clone_messages (session_id, id);

create table if not exists public.clone_events (
  id          bigint generated always as identity primary key,
  session_id  text not null references public.clone_sessions (id) on delete cascade,
  step        text,
  type        text not null,                    -- step | notice | analysis | motion | qa | compare | handover ...
  data        jsonb,
  created_at  timestamptz not null default now()
);
create index if not exists clone_events_session_idx on public.clone_events (session_id, id);

alter table public.clone_sessions enable row level security;
alter table public.clone_messages enable row level security;
alter table public.clone_events enable row level security;
