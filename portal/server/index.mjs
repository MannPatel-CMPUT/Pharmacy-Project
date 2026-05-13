import path from "path";
import fs from "fs";
import http from "http";
import { fileURLToPath } from "url";
import express from "express";
import cookieParser from "cookie-parser";
import jwt from "jsonwebtoken";
import bcrypt from "bcryptjs";
import { createProxyMiddleware } from "http-proxy-middleware";
import { createUser, findUserByUsername } from "./db.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const portalRoot = path.join(__dirname, "..");
const clientRoot = path.join(portalRoot, "client");
const distDir = path.join(clientRoot, "dist");
const repoRoot = path.join(portalRoot, "..");
const pharmacyHtmlPath = process.env.PHARMACY_HTML_PATH
  ? path.resolve(process.env.PHARMACY_HTML_PATH)
  : path.join(repoRoot, "frontend", "index.html");

const requestedPort = Number(process.env.PORT || 3000);
const isProd = process.env.NODE_ENV === "production";
const DEV_JWT_DEFAULTS = new Set([
  "dev-only-change-in-production",
  "dev-jwt-change-me",
]);
const jwtSecretEnv = process.env.JWT_SECRET;
let JWT_SECRET;
if (isProd) {
  if (!jwtSecretEnv || DEV_JWT_DEFAULTS.has(jwtSecretEnv)) {
    console.error(
      "JWT_SECRET must be set to a strong non-default value when NODE_ENV=production.",
    );
    process.exit(1);
  }
  JWT_SECRET = jwtSecretEnv;
} else {
  JWT_SECRET = jwtSecretEnv || "dev-only-change-in-production";
  if (!jwtSecretEnv) {
    console.warn(
      "JWT_SECRET is unset; using a dev-only fallback. Set JWT_SECRET in production.",
    );
  }
}
const COOKIE_NAME = "pharma_auth";
const FASTAPI_URL = process.env.FASTAPI_URL || "http://127.0.0.1:8000";

const app = express();
app.disable("x-powered-by");
app.use(cookieParser());
app.use(express.json());

function signToken(payload) {
  return jwt.sign(payload, JWT_SECRET, { expiresIn: "7d" });
}

function readCookieToken(req) {
  const raw = req.cookies[COOKIE_NAME];
  if (!raw) return null;
  try {
    return jwt.verify(raw, JWT_SECRET);
  } catch {
    return null;
  }
}

function setAuthCookie(res, token) {
  res.cookie(COOKIE_NAME, token, {
    httpOnly: true,
    sameSite: "lax",
    maxAge: 7 * 24 * 60 * 60 * 1000,
    path: "/",
  });
}

function clearAuthCookie(res) {
  res.clearCookie(COOKIE_NAME, { path: "/" });
}

app.post("/api/auth/signup", (req, res) => {
  const { username, email, phone, password } = req.body || {};
  if (!username || !email || !phone || !password) {
    return res.status(400).json({ error: "All fields are required." });
  }
  if (String(username).trim().length < 2) {
    return res.status(400).json({ error: "Username must be at least 2 characters." });
  }
  if (String(password).length < 8) {
    return res.status(400).json({ error: "Password must be at least 8 characters." });
  }
  const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(email).trim());
  if (!emailOk) {
    return res.status(400).json({ error: "Enter a valid email address." });
  }
  const digits = String(phone).replace(/\D/g, "");
  if (digits.length < 10) {
    return res.status(400).json({ error: "Enter a phone number with at least 10 digits." });
  }
  if (findUserByUsername(username)) {
    return res.status(409).json({ error: "That username is already taken." });
  }
  const passwordHash = bcrypt.hashSync(String(password), 10);
  try {
    const { id } = createUser({
      username,
      email,
      phone: digits,
      passwordHash,
    });
    const token = signToken({ sub: id, u: username.trim() });
    setAuthCookie(res, token);
    return res.status(201).json({ ok: true, username: username.trim() });
  } catch (e) {
    if (String(e.message || "").includes("UNIQUE")) {
      return res.status(409).json({ error: "That username is already taken." });
    }
    console.error(e);
    return res.status(500).json({ error: "Could not create account." });
  }
});

app.post("/api/auth/login", (req, res) => {
  const { username, password } = req.body || {};
  if (!username || !password) {
    return res.status(400).json({ error: "Username and password are required." });
  }
  const user = findUserByUsername(username);
  if (!user || !bcrypt.compareSync(String(password), user.password_hash)) {
    return res.status(401).json({ error: "Invalid username or password." });
  }
  const token = signToken({ sub: user.id, u: user.username });
  setAuthCookie(res, token);
  return res.json({ ok: true, username: user.username });
});

app.post("/api/auth/logout", (_req, res) => {
  clearAuthCookie(res);
  res.json({ ok: true });
});

app.get("/api/auth/me", (req, res) => {
  const payload = readCookieToken(req);
  if (!payload) {
    return res.status(401).json({ user: null });
  }
  const user = findUserByUsername(payload.u);
  if (!user) {
    clearAuthCookie(res);
    return res.status(401).json({ user: null });
  }
  return res.json({
    user: {
      id: user.id,
      username: user.username,
      email: user.email,
      phone: user.phone,
    },
  });
});

function requireAuthHtml(req, res, next) {
  const payload = readCookieToken(req);
  if (!payload) {
    return res.redirect(302, "/login?next=/workspace");
  }
  const user = findUserByUsername(payload.u);
  if (!user) {
    clearAuthCookie(res);
    return res.redirect(302, "/login?next=/workspace");
  }
  req.user = user;
  next();
}

app.get("/workspace", requireAuthHtml, (req, res) => {
  if (!fs.existsSync(pharmacyHtmlPath)) {
    return res.status(500).send("Pharmacy dashboard HTML not found. Set paths or add frontend/index.html.");
  }
  res.setHeader("Cache-Control", "no-store, no-cache, must-revalidate");
  res.sendFile(path.resolve(pharmacyHtmlPath));
});

const apiProxy = createProxyMiddleware({
  target: FASTAPI_URL,
  changeOrigin: true,
});

app.use("/intakes", apiProxy);
app.use("/health", apiProxy);
app.use("/config", apiProxy);

async function mountFrontend() {
  if (isProd) {
    if (!fs.existsSync(distDir)) {
      console.error("Run `npm run build` in portal/ before NODE_ENV=production.");
      process.exit(1);
    }
    app.use(
      express.static(distDir, {
        index: false,
        fallthrough: true,
      }),
    );
    app.use((req, res, next) => {
      if (req.method !== "GET") return next();
      const p = req.path;
      if (
        p.startsWith("/api") ||
        p.startsWith("/intakes") ||
        p === "/health" ||
        p.startsWith("/config") ||
        p === "/workspace"
      ) {
        return next();
      }
      if (res.headersSent) return next();
      res.sendFile(path.join(distDir, "index.html"));
    });
    return;
  }

  const { createServer: createViteServer } = await import("vite");
  const vite = await createViteServer({
    root: clientRoot,
    server: { middlewareMode: true },
    appType: "spa",
  });
  app.use(vite.middlewares);
}

await mountFrontend();

const maxTryPort = isProd ? requestedPort : requestedPort + 25;
let activePort = requestedPort;

const httpServer = http.createServer(app);

function onListening() {
  console.log(`Pharma Checker portal → http://localhost:${activePort}`);
  if (activePort !== requestedPort) {
    console.log(`  (Port ${requestedPort} was in use; open the URL above.)`);
  }
  console.log(`  FastAPI proxy target: ${FASTAPI_URL}`);
  console.log(`  Mode: ${isProd ? "production" : "development (Vite middleware)"}`);
}

httpServer.on("error", (err) => {
  if (err.code === "EADDRINUSE" && activePort < maxTryPort) {
    const busy = activePort;
    activePort += 1;
    console.warn(`Port ${busy} is in use; trying ${activePort}…`);
    httpServer.listen(activePort, onListening);
    return;
  }
  console.error(err);
  if (err.code === "EADDRINUSE") {
    console.error(
      `Could not bind a port (tried ${requestedPort}–${maxTryPort}). Free one with: lsof -i :${requestedPort}`,
    );
  }
  process.exit(1);
});

httpServer.listen(activePort, onListening);
