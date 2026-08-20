import { createNeonAuth } from "@neondatabase/auth/next/server";

const baseUrl = process.env.NEON_AUTH_BASE_URL;
const cookieSecret = process.env.NEON_AUTH_COOKIE_SECRET;

if (!baseUrl) {
  throw new Error("Missing required environment variable: NEON_AUTH_BASE_URL");
}

if (!cookieSecret) {
  throw new Error("Missing required environment variable: NEON_AUTH_COOKIE_SECRET");
}

const auth = createNeonAuth({
  baseUrl,
  cookies: {
    secret: cookieSecret,
  },
});

export const { GET, POST, PUT, DELETE, PATCH } = auth.handler();
