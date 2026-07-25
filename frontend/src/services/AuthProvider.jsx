import { createContext, useContext, useEffect, useState } from 'react';
import { supabase } from './supabaseClient';
import { setAuthToken, getWhoAmI } from './api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [role, setRole] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    async function applySession(newSession) {
      setSession(newSession);
      setAuthToken(newSession?.access_token ?? null);

      if (!newSession) {
        if (mounted) setRole(null);
        return;
      }
      try {
        const who = await getWhoAmI(newSession.access_token);
        if (mounted) setRole(who.role);
      } catch {
        if (mounted) setRole(null);
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
    <AuthContext.Provider value={{ session, role, loading, signOut: () => supabase.auth.signOut() }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
