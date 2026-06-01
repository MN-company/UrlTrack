create extension if not exists pgcrypto;

create type team_role as enum ('owner', 'admin', 'editor', 'analyst', 'viewer');
create type campaign_status as enum ('draft', 'active', 'paused', 'completed', 'archived');
create type domain_type as enum ('primary', 'branded', 'fallback');
create type verification_status as enum ('pending', 'verified', 'failed');
create type ssl_status as enum ('pending', 'active', 'failed');
create type link_status as enum ('active', 'paused', 'archived');
create type source_type as enum ('link', 'qr');
create type webhook_delivery_status as enum ('pending', 'delivered', 'retrying', 'failed');

create table workspaces (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text not null unique,
  owner_user_id text not null,
  settings_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table team_members (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  user_id text not null,
  role team_role not null default 'viewer',
  created_at timestamptz not null default now(),
  unique (workspace_id, user_id)
);
create index team_members_user_id_idx on team_members(user_id);

create table campaigns (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  name text not null,
  description text,
  status campaign_status not null default 'draft',
  goal text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index campaigns_workspace_id_status_idx on campaigns(workspace_id, status);

create table domains (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  domain text not null,
  type domain_type not null default 'branded',
  verification_status verification_status not null default 'pending',
  ssl_status ssl_status not null default 'pending',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, domain)
);

create table links (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  campaign_id uuid references campaigns(id) on delete set null,
  domain_id uuid references domains(id) on delete set null,
  slug text not null,
  destination_url text not null,
  access_control_config jsonb not null default '{}'::jsonb,
  routing_config jsonb not null default '{}'::jsonb,
  notification_config jsonb not null default '{}'::jsonb,
  qr_config jsonb not null default '{}'::jsonb,
  flow_config jsonb not null default '{}'::jsonb,
  status link_status not null default 'active',
  created_by text not null,
  click_count integer not null default 0,
  archived_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, slug)
);
create index links_workspace_id_status_idx on links(workspace_id, status);
create index links_campaign_id_idx on links(campaign_id);

create table visitors (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  primary_email text,
  primary_ip text,
  primary_canvas_hash text,
  primary_fingerprint_hash text,
  first_seen timestamptz not null default now(),
  last_seen timestamptz not null default now(),
  total_visits integer not null default 0,
  confidence_score integer not null default 0,
  traffic_quality_average integer not null default 100,
  attributes_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index visitors_workspace_id_primary_email_idx on visitors(workspace_id, primary_email);
create index visitors_workspace_id_primary_fingerprint_hash_idx on visitors(workspace_id, primary_fingerprint_hash);

create table visits (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  link_id uuid not null references links(id) on delete cascade,
  visitor_id uuid references visitors(id) on delete set null,
  source_type source_type not null default 'link',
  traffic_quality_score integer not null default 100,
  identity_confidence_score integer not null default 0,
  event_type text not null default 'visit.created',
  raw_fingerprint_json jsonb not null default '{}'::jsonb,
  ip text,
  user_agent text,
  referrer text,
  country_code text,
  device_type text,
  is_vpn boolean not null default false,
  is_bot boolean not null default false,
  is_datacenter boolean not null default false,
  visit_token_hash text unique,
  match_reasons text[] not null default array[]::text[],
  review_suggested boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index visits_workspace_id_created_at_idx on visits(workspace_id, created_at);
create index visits_link_id_created_at_idx on visits(link_id, created_at);
create index visits_visitor_id_idx on visits(visitor_id);

create table visitor_signals (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  visitor_id uuid not null references visitors(id) on delete cascade,
  visit_id uuid references visits(id) on delete set null,
  signal_type text not null,
  signal_value_hash text not null,
  confidence_weight integer not null,
  created_at timestamptz not null default now(),
  unique (visitor_id, signal_type, signal_value_hash)
);
create index visitor_signals_workspace_id_signal_type_idx on visitor_signals(workspace_id, signal_type);
create index visitor_signals_signal_type_signal_value_hash_idx on visitor_signals(signal_type, signal_value_hash);

create table leads (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  visitor_id uuid references visitors(id) on delete set null,
  score integer not null default 0,
  confidence_score integer not null default 0,
  tags text[] not null default array[]::text[],
  lifecycle_stage text not null default 'new',
  consent_status text not null default 'unknown',
  custom_fields_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index leads_workspace_id_score_idx on leads(workspace_id, score);

create table api_keys (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  key_hash text not null unique,
  name text not null,
  scopes text[] not null default array[]::text[],
  last_used_at timestamptz,
  expires_at timestamptz,
  created_at timestamptz not null default now()
);
create index api_keys_workspace_id_idx on api_keys(workspace_id);

create table webhook_endpoints (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  url text not null,
  secret text not null,
  name text not null,
  enabled boolean not null default true,
  events text[] not null default array[]::text[],
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index webhook_endpoints_workspace_id_enabled_idx on webhook_endpoints(workspace_id, enabled);

create table webhook_deliveries (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  endpoint_id uuid not null references webhook_endpoints(id) on delete cascade,
  event_type text not null,
  payload_json jsonb not null,
  status webhook_delivery_status not null default 'pending',
  response_code integer,
  attempts integer not null default 0,
  next_retry_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index webhook_deliveries_workspace_id_status_idx on webhook_deliveries(workspace_id, status);
create index webhook_deliveries_endpoint_id_status_idx on webhook_deliveries(endpoint_id, status);
create index webhook_deliveries_next_retry_at_idx on webhook_deliveries(next_retry_at);

create table notification_rules (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  campaign_id uuid references campaigns(id) on delete cascade,
  link_id uuid references links(id) on delete cascade,
  event_type text not null,
  channel text not null,
  threshold_config jsonb not null default '{}'::jsonb,
  enabled boolean not null default true,
  created_at timestamptz not null default now()
);
create index notification_rules_workspace_id_event_type_idx on notification_rules(workspace_id, event_type);

create table ai_insights (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  campaign_id uuid references campaigns(id) on delete set null,
  link_id uuid references links(id) on delete set null,
  insight_type text not null,
  title text not null,
  summary text not null,
  severity text not null default 'info',
  metadata_json jsonb not null default '{}'::jsonb,
  dismissed_at timestamptz,
  created_at timestamptz not null default now()
);
create index ai_insights_workspace_id_severity_idx on ai_insights(workspace_id, severity);

create table audit_logs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  user_id text,
  action text not null,
  entity_type text not null,
  entity_id text,
  metadata_json jsonb not null default '{}'::jsonb,
  ip text,
  created_at timestamptz not null default now()
);
create index audit_logs_workspace_id_created_at_idx on audit_logs(workspace_id, created_at);

create or replace function public.is_workspace_member(target_workspace_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from workspaces
    where id = target_workspace_id
      and owner_user_id = auth.uid()::text
  )
  or exists (
    select 1 from team_members
    where workspace_id = target_workspace_id
      and user_id = auth.uid()::text
  );
$$;

create or replace function public.can_manage_workspace(target_workspace_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from workspaces
    where id = target_workspace_id
      and owner_user_id = auth.uid()::text
  )
  or exists (
    select 1 from team_members
    where workspace_id = target_workspace_id
      and user_id = auth.uid()::text
      and role in ('owner', 'admin', 'editor')
  );
$$;

alter table workspaces enable row level security;
create policy workspaces_select on workspaces
  for select using (public.is_workspace_member(id));
create policy workspaces_insert on workspaces
  for insert with check (owner_user_id = auth.uid()::text);
create policy workspaces_update on workspaces
  for update using (public.can_manage_workspace(id))
  with check (public.can_manage_workspace(id));

alter table team_members enable row level security;
create policy team_members_select on team_members
  for select using (public.is_workspace_member(workspace_id));
create policy team_members_insert on team_members
  for insert with check (public.can_manage_workspace(workspace_id));
create policy team_members_update on team_members
  for update using (public.can_manage_workspace(workspace_id))
  with check (public.can_manage_workspace(workspace_id));
create policy team_members_delete on team_members
  for delete using (public.can_manage_workspace(workspace_id));

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'campaigns',
    'domains',
    'links',
    'visits',
    'visitors',
    'visitor_signals',
    'leads',
    'api_keys',
    'webhook_endpoints',
    'webhook_deliveries',
    'notification_rules',
    'ai_insights',
    'audit_logs'
  ]
  loop
    execute format('alter table %I enable row level security', table_name);
    execute format('create policy %I on %I for select using (public.is_workspace_member(workspace_id))', table_name || '_select', table_name);
    execute format('create policy %I on %I for insert with check (public.can_manage_workspace(workspace_id))', table_name || '_insert', table_name);
    execute format('create policy %I on %I for update using (public.can_manage_workspace(workspace_id)) with check (public.can_manage_workspace(workspace_id))', table_name || '_update', table_name);
    execute format('create policy %I on %I for delete using (public.can_manage_workspace(workspace_id))', table_name || '_delete', table_name);
  end loop;
end $$;
