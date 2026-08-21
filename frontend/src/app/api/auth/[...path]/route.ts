import { createNeonAuth } from "@neondatabase/auth/next/server";

export const dynamic = "force-dynamic";

const baseUrl = process.env.NEON_AUTH_BASE_URL;
const cookieSecret = process.env.NEON_AUTH_COOKIE_SECRET;

if (!baseUrl) {
  throw new Error(
    "Missing required environment variable: NEON_AUTH_BASE_URL. Please configure it in your environment (e.g. Vercel project settings or .env.local)."
  );
}

if (!cookieSecret) {
  throw new Error(
    "Missing required environment variable: NEON_AUTH_COOKIE_SECRET. Please configure a 32+ character secret in your environment."
  );
}

if (baseUrl.includes("hf.space") || baseUrl.includes("localhost:8000")) {
  throw new Error(
    "Invalid NEON_AUTH_BASE_URL: It must point to your Neon Auth endpoint (e.g. https://ep-xxx.neon.tech/auth), not your Hugging Face Space or FastAPI backend."
  );
}

const auth = createNeonAuth({
  baseUrl,
  cookies: {
    secret: cookieSecret,
  },
});

export const { GET, POST, PUT, DELETE, PATCH } = auth.handler();
