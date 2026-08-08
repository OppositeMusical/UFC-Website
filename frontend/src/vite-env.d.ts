/// <reference types="vite/client" />

// tsconfig.json sets an explicit `types` array, which switches off automatic
// @types inclusion, so Vite's client types have to be pulled in by reference.
// Without this, `import.meta.env` is a type error even though it is perfectly
// valid at runtime.

interface ImportMetaEnv {
  /** Base URL of the accounts service. Falls back to localhost in development. */
  readonly VITE_ACCOUNTS_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
