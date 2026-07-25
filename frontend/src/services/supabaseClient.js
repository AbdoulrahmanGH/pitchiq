import { createClient } from '@supabase/supabase-js';

// Safe to expose client-side: the anon/publishable key is designed for
// browser use and grants nothing on its own -- this project deliberately
// has no Row Level Security (see schema_v2.sql), because the frontend
// never talks to Supabase for data, only for auth. All real data access
// goes through FastAPI, which checks the caller's role itself.
const SUPABASE_URL = 'https://eediqchfvebykdyidbdk.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_QgX_qUdGGp05HNRkgKV9ww_jDz90TdS';

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
