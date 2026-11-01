import { fileURLToPath } from "node:url";

export function validateBuildEnvironment(env) {
  if (env.RESUMEBOT_BUILD_TARGET !== "production") return;
  if (!env.VITE_API_BASE_URL) {
    throw new Error("Production frontend requires VITE_API_BASE_URL.");
  }
  let parsed;
  try {
    parsed = new URL(env.VITE_API_BASE_URL);
  } catch {
    throw new Error("VITE_API_BASE_URL must be an absolute HTTPS origin.");
  }
  if (
    parsed.protocol !== "https:" ||
    !parsed.hostname ||
    parsed.username ||
    parsed.password ||
    parsed.pathname !== "/" ||
    parsed.search ||
    parsed.hash ||
    parsed.port ||
    parsed.hostname === "localhost" ||
    parsed.hostname === "127.0.0.1" ||
    parsed.hostname.endsWith(".localhost")
  ) {
    throw new Error("Production VITE_API_BASE_URL must be an HTTPS origin without credentials, paths, or local hosts.");
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  try {
    validateBuildEnvironment(process.env);
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
