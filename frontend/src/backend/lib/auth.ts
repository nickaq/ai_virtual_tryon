/**
 * NextAuth configuration.
 * Provides authentication handlers (GET/POST) for the /api/auth/* routes.
 * Currently configured with no providers — acts as a placeholder until
 * OAuth providers (Google, GitHub, etc.) are added.
 */
import NextAuth from 'next-auth';
import type { NextAuthConfig } from 'next-auth';

const authConfig: NextAuthConfig = {
    providers: [],
    session: { strategy: 'jwt' },
    pages: {
        signIn: '/auth/signin',
        error: '/auth/error',
    },
};

const { handlers } = NextAuth(authConfig);
export { handlers };
