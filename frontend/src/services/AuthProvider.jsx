import { createContext, useContext, useEffect, useState } from 'react';
import { supabase } from './supabaseClient';
import { setAuthToken, getWhoAmI } from './api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [role, setRole] = useState(null);
  const [loading, setLoading] = useState(true);
  // Tracks whether /whoami has resolved for the *current* session -- distinct
  // from `loading` (which only covers the very first getSession() check on
  // mount). Every subsequent sign-in fires onAuthStateChange and re-resolves
  // the role asynchronously; consumers like Sidebar must not treat role===null
  // during that window as "no role" (which used to render the full,
  // unscoped nav for a flash) -- they need to know a resolution is in flight.
  const [roleLoading, setRoleLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    async function applySession(newSession) {
      setSession(newSession);
      setAuthToken(newSession?.access_token ?? null);

      if (!newSession) {
        if (mounted) { setRole(null); setRoleLoading(false); }
        return;
      }
      if (mounted) setRoleLoading(true);
      try {
        const who = await getWhoAmI(newSession.access_token);
        if (mounted) setRole(who.role);
      } catch {
        if (mounted) setRole(null);
      } finally {
        if (mounted) setRoleLoading(false);
      }
    }

    supabase.auth.getSession().then(({ data }) => {
      applySession(data.session).then(() => {
        if (mounted) setLoading(false);
      });
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, newSession) => {
      applySession(newSession);
    });

    return () => {
      mounted = false;
      listener.subscription.unsubscribe();
    };
  }, []);

  return (
    <AuthContext.Provider value={{ session, role, loading, roleLoading, signOut: () => supabase.auth.signOut() }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
