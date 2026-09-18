-- One-time cleanup: run this in the Supabase SQL Editor before deleting
-- the alice/bob test accounts in Authentication -> Users. Deleting a user
-- fails with "Database error deleting user" while their conversations
-- table rows still reference them (user_id has a foreign key to
-- auth.users(id) with no cascade behavior) — this just removes those rows
-- first, then the user deletion in the dashboard will succeed normally.

delete from conversations
where user_id in (
  select id from auth.users where email in ('alice@example.com', 'bob@example.com')
);
