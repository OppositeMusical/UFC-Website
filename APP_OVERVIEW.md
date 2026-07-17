# App Overview

A small React single-page app where users create an account, log in, and store API keys for LLM providers (OpenAI, Anthropic, Gemini, DeepSeek). Auth and data live entirely in Firebase — there is no custom backend yet (the empty `backend/` folder is reserved for a future FastAPI service).

**Stack:** React 19 + Vite 8, Firebase (Auth, Firestore, Analytics), lucide-react icons, hand-written CSS (dark glassmorphism theme). No router, no state library, no tests.

## How it works

### Entry and routing

- [main.jsx](frontend/src/main.jsx) mounts `<App />` in StrictMode.
- [App.jsx](frontend/src/App.jsx) is the entire "router." It subscribes to Firebase `onAuthStateChanged` and keeps two pieces of state:
  - `user` — the Firebase auth user (or `null`)
  - `currentView` — `'login'` or `'signup'`, toggled by callbacks passed into the child components
- Render logic: show a **Loading** screen until the first auth callback fires → then **Dashboard** if signed in, otherwise **Login** or **Signup**. There are no URLs — refreshing always re-resolves from auth state, and login/signup are not linkable.

### Firebase setup

[firebase.js](frontend/src/firebase.js) initializes the app and exports `auth` (Firebase Auth), `db` (Firestore), and `analytics`. The config object with the API key being in source is **normal for Firebase web apps** — it identifies the project, it is not a secret. Actual access control is enforced by Firestore security rules (see Security below).

### Signup flow

[Signup.jsx](frontend/src/Signup.jsx) collects first name, last name, email, password (min 6 chars), then:

1. `createUserWithEmailAndPassword(auth, email, password)`
2. Writes a Firestore doc at `users/{uid}`:

```js
{ firstName, lastName, email, createdAt: ISOString, apiKeys: {} }
```

Step 1 signs the user in immediately, which fires `onAuthStateChanged` in App.jsx and swaps in the Dashboard — the routing is implicit, Signup never navigates anywhere itself.

### Login flow

[Login.jsx](frontend/src/Login.jsx) calls `signInWithEmailAndPassword`; success is again handled implicitly by the auth listener. Errors render the raw Firebase message above the form. The "Forgot Password?" link and the GitHub/Twitter social buttons are visual only — no handlers.

### Dashboard

[Dashboard.jsx](frontend/src/Dashboard.jsx):

- On mount, fetches `users/{uid}` to greet the user by first name and list stored keys.
- "Add New API Key" form writes to the doc with `updateDoc({ ['apiKeys.' + provider]: apiKey })`, then patches local state so the "Stored Keys" list updates without a re-fetch.
- Stored keys are listed by provider name with a "✓ Configured" badge — the key value itself is never displayed.
- Logout calls `signOut(auth)`; the auth listener swaps back to Login.

### Data model

One Firestore collection:

```
users/{uid}
  firstName: string
  lastName:  string
  email:     string
  createdAt: string (ISO)
  apiKeys:   { openai?: string, anthropic?: string, gemini?: string, deepseek?: string }
```

## Bugs

1. **Signup race: Dashboard can load before the user doc exists.** `createUserWithEmailAndPassword` fires `onAuthStateChanged` *before* the `setDoc` in Signup completes. App.jsx unmounts Signup and mounts Dashboard, whose fetch can win the race against the doc write — the header then shows "Welcome, ...!" until a refresh. Worse, if `setDoc` fails outright (e.g. rules deny it), the error is set on an already-unmounted component, so the user never sees it and the doc never exists.

2. **Content taller than the viewport is unreachable.** `body { overflow: hidden }` in [index.css](frontend/src/index.css) disables scrolling globally. The Dashboard grows as keys are added, and on short/mobile screens the signup form already clips — anything past the fold is simply cut off.

3. **Dashboard fetch failures are silent.** The `getDoc` catch only logs to console; the UI just shows "Welcome, ...!" forever with no error or retry.

4. **Wrong dependency: `firestore` in [package.json](frontend/package.json).** The `firestore` npm package (v1.1.6) is an unrelated third-party library — Firestore actually comes from the `firebase` package already in use. It should be removed.

5. **Dead UI that looks functional.** "Forgot Password?" and the four social-login buttons do nothing. The GitHub icon's SVG path is also mangled (`6.5-7.a4.6` in both Login and Signup), so it may not render correctly.

6. **Raw Firebase error messages shown to users.** Strings like `Firebase: Error (auth/invalid-credential).` leak implementation detail and read poorly. Error codes should map to friendly copy.

7. **Unused template leftovers.** `App.css`, `assets/hero.png`, `assets/react.svg`, and `assets/vite.svg` are referenced nowhere. The `analytics` export in firebase.js is also never used (and `getAnalytics` can throw in environments without cookie/storage support — `isSupported()` guards against this).

## Security

- **API keys are stored in plaintext in Firestore.** This is the big one. The dashboard is pitched as "manage your API keys securely," but anything a browser writes to Firestore is plaintext in the database and readable by anyone the rules allow (including any future client-side code and project admins). If these keys are meant to be *used* for anything, the right shape is: the browser sends the key once to the future FastAPI backend over HTTPS, the backend encrypts it (e.g. KMS or at least app-level encryption) and makes provider calls server-side. Keys should never round-trip back to the client.
- **Firestore security rules are the entire access-control story and they live outside this repo.** They cannot be verified from the code. If the project is still in test mode (open rules), every user's email, name, and API keys are readable and writable by anyone on the internet. Rules should restrict `users/{uid}` to `request.auth.uid == uid`, and it's worth committing a `firestore.rules` file to the repo so this is visible and versioned.
- **No email verification** — accounts are usable immediately with any email string.

## Areas for improvement

- **Move API-key handling to the planned FastAPI backend** (see Security) — this is the natural first backend feature.
- **Add real routing** (React Router or TanStack Router) so `/login`, `/signup`, and `/dashboard` are linkable and the back button works.
- **Fix the signup race** — either `await setDoc` before treating signup as complete (create the doc, *then* rely on auth state), or have the Dashboard fall back to creating/re-reading the doc when it's missing.
- **Key management UX**: no way to view, replace-with-confirmation, or delete a stored key; saving silently overwrites. A delete button (`deleteField()`) and an "added on" date would go a long way.
- **Use `serverTimestamp()`** instead of a client-generated ISO string for `createdAt`.
- **Implement or remove the dead UI** — password reset is nearly free (`sendPasswordResetEmail`); social login buttons should either get `signInWithPopup` providers or be deleted.
- **Friendly auth errors** — map `err.code` (`auth/invalid-credential`, `auth/email-already-in-use`, …) to human copy.
- **Loading/skeleton state for the Dashboard fetch**, plus visible error + retry.
- **Delete unused files** (`App.css`, unused assets) and the unused `analytics` export or gate it behind `isSupported()`.
- **Password policy** — 6 characters is Firebase's floor; consider a strength requirement at signup.
- **Tests and CI** — nothing is tested; component tests around the auth flows (Vitest + Testing Library) would catch regressions like the signup race.
- **Extract inline styles** — Dashboard and the error banners are styled inline; moving them into the CSS (or adopting Tailwind/CSS modules) keeps the theme in one place.
