-- Friday Phase 1/2 schema baseline (Postgres + pgvector-ready)

create table if not exists runs (
  run_id text primary key,
  org_id text not null,
  user_id text not null,
  conversation_id text not null,
  planner_json jsonb not null,
  selected_agents jsonb not null,
  tool_calls jsonb not null,
  specialist_memos jsonb not null,
  critic_report jsonb not null,
  final_answer jsonb not null,
  confidence double precision not null,
  feedback jsonb not null,
  outcome jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists approvals (
  approval_id text primary key,
  run_id text not null references runs(run_id),
  reason text not null,
  action_summary text not null,
  requested_scopes jsonb not null,
  status text not null,
  created_at timestamptz not null default now()
);

create table if not exists semantic_memories (
  id bigserial primary key,
  org_id text not null,
  memory_key text not null,
  memory_value jsonb not null,
  created_at timestamptz not null default now(),
  unique(org_id, memory_key)
);

create table if not exists episodic_memories (
  id bigserial primary key,
  org_id text not null,
  run_id text not null,
  event_json jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists procedural_memories (
  id bigserial primary key,
  memory_name text not null unique,
  content jsonb not null,
  approved_by text,
  created_at timestamptz not null default now()
);

create table if not exists memory_candidates (
  candidate_id text primary key,
  run_id text not null,
  candidate_type text not null,
  content jsonb not null,
  risk_level text not null,
  auto_accepted boolean not null,
  promoted boolean not null default false,
  created_at timestamptz not null default now()
);
