import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dataDir = path.join(__dirname, "..", "data");
fs.mkdirSync(dataDir, { recursive: true });

const usersFile = process.env.PORTAL_USERS_PATH
  ? path.resolve(process.env.PORTAL_USERS_PATH)
  : path.join(dataDir, "users.json");

/** @typedef {{ id: number, username: string, email: string, phone: string, password_hash: string, created_at: string }} UserRow */

function load() {
  if (!fs.existsSync(usersFile)) {
    return { users: /** @type {UserRow[]} */ ([]) };
  }
  try {
    const raw = JSON.parse(fs.readFileSync(usersFile, "utf8"));
    if (!raw || !Array.isArray(raw.users)) return { users: [] };
    return { users: raw.users };
  } catch {
    return { users: [] };
  }
}

function save(data) {
  fs.mkdirSync(path.dirname(usersFile), { recursive: true });
  fs.writeFileSync(usersFile, JSON.stringify(data, null, 2), "utf8");
}

export function findUserByUsername(username) {
  const u = username.trim().toLowerCase();
  const { users } = load();
  return users.find((x) => x.username.toLowerCase() === u) ?? null;
}

export function createUser({ username, email, phone, passwordHash }) {
  const data = load();
  const un = username.trim();
  if (data.users.some((x) => x.username.toLowerCase() === un.toLowerCase())) {
    const err = new Error("UNIQUE");
    throw err;
  }
  const id = data.users.reduce((m, x) => Math.max(m, x.id), 0) + 1;
  const row = {
    id,
    username: un,
    email: email.trim(),
    phone: phone.trim(),
    password_hash: passwordHash,
    created_at: new Date().toISOString(),
  };
  data.users.push(row);
  save(data);
  return { id };
}
