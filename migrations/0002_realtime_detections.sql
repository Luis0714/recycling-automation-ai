-- =====================================================================
-- Add detections to the supabase_realtime publication so the dashboard
-- can subscribe to INSERTs from the browser. Idempotent.
-- =====================================================================
do $$
begin
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime'
      and tablename = 'detections'
  ) then
    execute 'alter publication supabase_realtime add table detections';
  end if;
end $$;
