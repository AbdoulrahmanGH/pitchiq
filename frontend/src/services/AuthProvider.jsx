import { createContext, useContext, useEffect, useRef, useState } from 'react';
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
  // Tracks the user id the app has actually resolved into state, so the
  // onAuthStateChange handler below can tell "the user changed" apart from
  // "Supabase re-fired SIGNED_IN for the same user" (which happens on every
  // browser tab refocus). Only the latter should be a no-op.
  const currentUserIdRef = useRef(undefined);

  useEffect(() => {
    let mounted = true;

    async function applySession(newSession) {
      currentUserIdRef.current = newSession?.user?.id ?? null;
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
      const incomingUserId = newSession?.user?.id ?? null;
      if (incomingUserId === currentUserIdRef.current) {
        // Same user as already resolved -- e.g. a refocus-triggered SIGNED_IN
        // with no real change. Keep the access token current (it may have
        // rotated) without cascading a state update through role/session
        // consumers like the sidebar.
        setAuthToken(newSession?.access_token ?? null);
        return;
      }
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
