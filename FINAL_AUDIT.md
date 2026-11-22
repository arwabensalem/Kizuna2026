# KIZUNA final audit

Audit date: 21 November 2026. Scope is the Django monolith in this repository. No new features were added. No application code was changed in this pass, because the checks below did not find a defect that breaks a page, a URL, a model, a test, or the shared simulation clock.

The live SQLite clock is hour **32**, scenario **NORMAL**, crisis state **none**. This audit did not advance it and did not reset it.

## Commands that were run

From `C:\Users\arwab\Desktop\kizuna`, with `KIZUNA_USE_SQLITE=1`:

| Command | Result |
| --- | --- |
| `python manage.py check` | System check identified no issues (0 silenced). |
| `python manage.py makemigrations --check --dry-run` | No changes detected. |
| `python manage.py showmigrations --plan` | No unapplied migrations. |
| `python manage.py test` | **154 tests OK** in 77.8s. |
| Signed-in page and API smoke (citizen `citizen.demo`, farmer `farmer.olive`, anonymous) | Status codes below. No 500 responses. |
| Browser, already signed in | Tunisia map, digital twin, dashboard, and Crisis Day render. Twin canvas is present and reads `Hour 32 · NORMAL`. Leaflet loaded 27 paths and map tiles. |

## Page and API smoke

Signed in as `citizen.demo` (role citizen), host `127.0.0.1`:

| Path | Status |
| --- | --- |
| `/`, `/dashboard/`, `/homes/`, `/twin/`, `/twin/business/1/`, `/ai/`, `/crisis/`, `/crisis/day/`, `/network/`, `/passport/`, `/league/`, `/tunisia/`, `/market/`, `/brain/`, `/simulation/`, `/autopilot/`, `/weather/`, `/accounts/profile/` | 200 |
| `/farms/`, `/businesses/` | 403 (role check; citizen cannot open farmer or business lists) |
| `GET /api/health/`, `/api/simulation/state/`, `/api/crisis/day/`, `/api/network/`, `/api/tunisia/`, `/api/brain/` | 200 |

Signed in as `farmer.olive`: `/farms/` and `/market/` return 200. `/homes/` and `/businesses/` return 403.

Anonymous:

| Request | Status |
| --- | --- |
| `POST /api/simulation/advance/` | 403 |
| `POST /api/simulation/reset/` | 403 |
| `POST /api/ai/water/` | 403 |
| `GET /api/crisis/day/` | 403 |
| `GET /api/twin/homes/1/` | 403 |
| `GET /api/brain/` | 403 |
| `GET /api/simulation/state/` | 200 |

The anonymous state response is the synthetic shared clock. It does not include another user's home or farm records. Advance and reset stay login-only.

Live database: 43 tables. Users present: `citizen.demo` (citizen), `Arwa` (citizen), `farmer.olive` (farmer). Passwords are hashed. This document does not record them.

## Inspection

### 1. Django configuration

`config/settings.py` loads `.env`, uses `accounts.User`, session auth, CSRF, clickjacking protection, `TIME_ZONE = Africa/Tunis`, and `LOGIN_URL = /accounts/login/`. `DEBUG` defaults to on (`DJANGO_DEBUG` defaults to `1`). `ALLOWED_HOSTS` defaults to `localhost` and `127.0.0.1`. `SECRET_KEY` comes from `DJANGO_SECRET_KEY`, with a `django-insecure-` fallback used only when that variable is absent. MySQL password is `os.environ.get('MYSQL_PASSWORD', '')`. SQLite is selected only when `KIZUNA_USE_SQLITE=1`, file `db.sqlite3`. Both `.env` and `db.sqlite3` are gitignored.

### 2. Database

SQLite is the database this audit ran against. Pages that read the clock, homes, the Tunisia atlas, the network, the brain, and Crisis Day all returned 200. MySQL is the configured path when `KIZUNA_USE_SQLITE` is unset. It was not started for this audit.

### 3. Models

Homes, farms, businesses, sensors, actuators, weather timelines, simulation steps, anomalies, marketplace products and buyer requests, and the resource passport and league all have migrations and passing tests. Owner filters are on the querysets that back private pages. Another user's object returns 404. Relationships used by the dashboard, twin, passport, league, and market tests are intact (`makemigrations --check` is clean).

### 4. Migrations

33 migration modules under `apps/`. `showmigrations --plan` shows every migration applied on the SQLite file. `makemigrations --check --dry-run` reports no model drift.

Apps with no tables of their own, only `__init__.py` migrations, are dashboard, digital twin, and crisis. Their data lives in the apps they read (homes, simulation, weather, and so on).

### 5. Authentication

`AUTH_USER_MODEL` is `accounts.User`. Passwords go through Django's hasher. Login, logout, and profile pages respond. Anonymous posts that change the clock or call the AI and crisis APIs return 403 JSON `{"detail":"Authentication required."}`. Pages that require a login redirect to `/accounts/login/`.

### 6. Permissions

`role_required` keeps citizens out of `/farms/` and `/businesses/` (403) and keeps farmers out of `/homes/` and `/businesses/` (403). Admin passes every role check. The digital twin for a business (`/twin/business/<pk>/`) is login-required and owner-filtered. `citizen.demo` can open Harbour Gym (`/twin/business/1/`) because that row is owned by that account. The dashboard still links My Farm and Business for every role. Those links 403 for a citizen. That is the role check, left as specified.

### 7. API endpoints

Working, login-gated unless noted:

- `GET /api/health/` and `GET /api/v1/health/` — public, `{"status":"ok","project":"KIZUNA"}`.
- `GET /api/simulation/state/` — public synthetic clock, plus `series` and `reading`. Does not advance the clock.
- `POST /api/simulation/advance/` and `POST /api/simulation/reset/` — login required.
- `POST /api/ai/water/` — login required.
- `GET /api/crisis/day/` — login required. Does not move the shared clock.
- `GET /api/network/`, `GET /api/tunisia/`, `GET /api/brain/` — login required.
- `GET /api/twin/homes/<pk>/` — login required, owner filtered.

`config/api_urls.py` still includes `api/v1/crisis/` and `api/v1/exchange/` from empty `urlpatterns`. The live crisis API is `/api/crisis/`. The live market is the HTML under `/market/`. The live network is `/api/network/`. Those empty includes do not shadow a working route.

### 8. Simulation

One source of truth: `apps.simulation.services.current_state()` and `SimulationStep`. `GET /api/simulation/state/` reads it. The dashboard, twin, brain, network, and autopilot poll that URL once a second while the tab is visible (`static/js/live.js`). Hidden tabs stop the poll. "Run clock" posts `/api/simulation/advance/` about once a second and is the only control on those pages that writes the clock. Crisis Day, the passport, the league, and the Tunisia profile do not write the clock.

Current stored state: hour 32, NORMAL. Hours already stored stay stored. Reset, on the simulation page, deletes `SimulationStep` rows and returns to hour 0. This audit did not press it.

### 9. AI engine

`engine/agents/` holds four deterministic modules (water, energy, agriculture, climate) and `KizunaOrchestrator.coordinate`. They read a state dict and return findings, actions, and a trace. They do not call a language model and they do not write the clock or an actuator. Thresholds are the ones already used by the crisis lab and the simulation (tank bands, battery reserve, pump watts, crop-stress formula).

`engine/orchestrator.py` `Orchestrator.decide`, and the other engine stubs, still raise `NotImplementedError`. Tests assert that. The conceptual agents do not replace those stubs.

### 10. Anomaly detection

Open anomaly events are counted on the dashboard as "Active crisis" and the card says the shared clock can still be NORMAL. That matched the browser: 2 open alerts on the signed-in homes while the clock read NORMAL. Scores are not invented here. The detection app's tests are inside the 154 that passed.

### 11. Autonomous control

The autopilot board shows the shared clock (farm pump, home valve, farm valve) as a read-only strip. Rule-based actuators move only when the user runs the rules, and that run is logged. The poll does not move them. Crisis Day's action list is its own local timeline.

### 12. Three.js digital twin

`/twin/` renders one WebGL canvas. The readout followed the shared clock (`Hour 32 · NORMAL`) without rebuilding the house. Geometry still comes from the home's own `simulate_home` records. Clock tanks, battery, solar, pump, and valves are overlaid in the browser. Business twin for Harbour Gym returns 200 for its owner. Three.js is loaded from the import map in `templates/base.html` (`three@0.170.0`).

### 13. Leaflet Tunisia map

`/tunisia/` draws the governorate GeoJSON (`static/data/tunisia-governorates.geojson`) with Leaflet. The browser showed the map, zoom controls, a simulated national index, and an explicit note that governorate colours are a fixed profile for the scenario, not a national dataset. House 1 and Harbour Gym have no coordinates, so the page lists them as unplaced. That is accurate.

### 14. Charts

Dashboard "Stored hours" is Chart.js on `#dash-chart` (home tank percent and home battery percent, last stored hours). Crisis Lab uses Chart.js canvases. Crisis Day uses its own SVG. `static/js/charts.js` still throws `"renderCharts is phase 3."` and is not referenced by any template. Nothing on the demo path calls it.

### 15. Crisis Lab

`/crisis/` returns 200 for a signed-in user. Crop stress and the lab formulas are the same ones the agents and Crisis Day reuse. The lab does not write the shared clock.

### 16. What If?

`/ai/` returns 200. Scenario posts go through the login-gated AI API. The page is the existing scenario explorer. It is separate from `engine/agents/`, which is a Python decision layer and has no LLM client.

### 17. Resource Network

`/network/` and `GET /api/network/` return 200 when signed in. The dashboard's top flows at hour 32 were Solar C → Business C, Solar B → Battery B, Solar A → Battery A, Solar A → Home A, and Farm B → Home D. Those labels are the simulated network graph for that stored hour. The page header on the dashboard marks the hour as simulated. The network view refreshes when the polled hour changes. It does not keep its own clock.

### 18. Resource Passport

`/passport/` returns 200. The citizen dashboard still shows the section "Resource passport" and the sentence `Current resilience score for House 1: 82. Appliance load 0 W.` Scores come from stored hours and the existing formulas. The audit did not add a score.

### 19. Resilience League

`/league/` returns 200. Ranking stays improvement against each row's own baseline. Tests covering ties are in the 154 that passed.

### 20. Marketplace

`/market/` returns 200 for a citizen and for a farmer. Product and buyer-request pages are independent of the crisis clock. The live SQLite catalog still has the demo product and the demo buyer requests created in earlier sessions. They are application data, not a claim about a real market.

### 21. Business module

`/businesses/` is role-gated (403 for citizen and farmer). A business the user owns is available through the twin (`/twin/business/1/` for Harbour Gym). The form still accepts a name-only create and fills the numeric twin fields from model defaults, which is what the accounts test requires. Supplementary energy on a business is calculated and labeled. It is not described as powering the whole building.

### 22. KIZUNA Brain

`/brain/` and `GET /api/brain/` return 200 when signed in. Anonymous `GET /api/brain/` returns 403. The dashboard brain card at hour 32 read NORMAL, temperature 25.63°C, water HIGH, solar MEDIUM, grid AVAILABLE. The brain panel refreshes when the polled hour, scenario, or status changes. It does not write the clock.

### 23. Crisis Day

`/crisis/day/` loads at 10:00 NORMAL with START, PAUSE, and RESET for that local timeline. The page states that the series is deterministic, does not call a weather service, and does not change the shared simulation clock. `GET /api/crisis/day/` is 403 when anonymous and 200 when signed in. The dashboard START CRISIS DAY control is a link to this page, not a form, so it cannot submit the logout form.

### 24. Frontend responsiveness

Dashboard layout is the sidebar board. At the project breakpoint (760px and below) the sidebar becomes a horizontal scrolling row and the cards stack. Tunisia, the twin, and Crisis Day use the top navigation from `base.html` and rendered without a missing-asset error in the browser. Static files referenced by templates (`kizuna.css`, `live.js`, `twin.js`, `brain.js`, `network.js`, `simulation.js`, `crisis-day.js`, `crisis.js`, `tunisia.js`, `ai.js`, `home.js`, `farm.js`, `main.js`, `api.js`, the GeoJSON) are on disk.

`static/js/map.js` throws `"renderMap is phase 4."` if called. No template loads it. The Tunisia map is `static/js/tunisia.js`.

### 25. Security

- No MySQL password is hardcoded. Empty string is the default so a missing env var fails the connection instead of shipping a password.
- No plaintext user passwords. Test passwords exist only inside tests.
- `.env` and `db.sqlite3` are gitignored.
- CSRF middleware is on. Clock advance and reset require a logged-in session.
- Owner scoping returns 404 for another user's object.
- `GET /api/simulation/state/` is readable without a login. The payload is the synthetic clock and the clock-level reading, not a user's private home. Tightening that was not done in this pass: the view is intentional, the tests allow it, and the mutating endpoints stay closed.
- `SECRET_KEY` fallback and `DEBUG` default are local-demo settings. Set `DJANGO_SECRET_KEY` and `DJANGO_DEBUG=0` before any host that is not this laptop.
- `ALLOWED_HOSTS` does not include `testserver`. Django's own test runner adds it. A hand-rolled `Client()` must pass `HTTP_HOST=127.0.0.1` or it receives 400 DisallowedHost. That is Django's host check, not a broken route.

### 26. Error handling

Anonymous access to private APIs returns 403 JSON, not a traceback. Missing homes and missing coordinates are written on the page (Tunisia lists unplaced sites). AI and simulation client scripts throw only after a failed response, with the server `detail` when present. The unused `charts.js` and `map.js` throws are unreachable from the templates.

Simulated data is labeled on the surfaces that show it: dashboard "Simulated", Tunisia "Simulated demo", Crisis Day "Deterministic demo" and "does not call a weather service". No accuracy percentage is claimed in the project code.

## What works

- Django check, migrations, and the full test suite (154 tests).
- Login, role checks, owner filtering, and hashed passwords.
- The shared simulation clock as the single source of truth, polled once a second on the live pages, advanced only by Run clock.
- Dashboard, My Home, digital twin (Three.js), business twin, What If?, Crisis Lab, Crisis Day, resource network, resource passport, resilience league, Tunisia map (Leaflet), marketplace, brain, simulation, autopilot, and weather.
- Deterministic water, energy, agriculture, and climate modules with a coordinating trace. They do not move the clock.
- Charts on the dashboard and in the crisis views. The Tunisia map and the twin canvas render in the browser.

## What was fixed

Nothing in application code. This pass did not find a broken URL, a missing template, a missing static file on a live page, a migration drift, a 500, a JavaScript error on the pages opened in the browser, or a clock that disagreed with the stored hour.

Earlier sessions already corrected the items those sessions introduced (dashboard flow unpacking, the business form rejecting a name-only create, league ties, marketplace message scoping, battery decimal handling, Crisis Day markup, the rain chip wording). Those fixes are already in the tree and are covered by the 154 passing tests. They were not re-opened.

## Remaining limitations

- Local defaults: `DEBUG` on, and a `django-insecure-` secret if `DJANGO_SECRET_KEY` is unset. Fine on this laptop. Set both before any other host.
- MySQL was not exercised in this audit. The password is env-only. SQLite is the demo database (`KIZUNA_USE_SQLITE=1`).
- The shared clock is at hour 32 NORMAL because earlier demos ran it. Reset is a user action on `/simulation/` and it deletes stored hours.
- A citizen who opens My Farm or Business from the dashboard gets 403. Farmers get 403 on Homes and Business. The links stay, because the role check stays.
- House 1 and Harbour Gym have no latitude or longitude, so they are listed and not drawn on the Tunisia map.
- `GET /api/simulation/state/` is anonymous-readable. It exposes the synthetic clock only.
- `api/v1/crisis/` and `api/v1/exchange/` are empty includes. Use `/api/crisis/`, `/market/`, and `/api/network/`.
- `static/js/charts.js` and `static/js/map.js` are unused stubs that throw if imported. Live charts and the map are other files.
- `engine/orchestrator.py` and the other engine stubs still raise `NotImplementedError` on purpose. The working decision layer is `engine/agents/`.
- Governorate colours are a fixed simulated profile. The page says so. They are not a national measurement.
- There is no project README. The commands and the demo order are in the two sections below.

## Exact commands to run the project

PowerShell, from the project directory. The virtualenv is `.venv`.

```powershell
cd C:\Users\arwab\Desktop\kizuna
.\.venv\Scripts\Activate.ps1
$env:KIZUNA_USE_SQLITE = '1'
python manage.py check
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Open `http://127.0.0.1:8000/` and sign in with an account that already exists in `db.sqlite3` (`citizen.demo`, `Arwa`, or `farmer.olive`). This document does not contain the password. A new account can be registered from the login page, or created with `python manage.py createsuperuser`.

To use MySQL instead, unset `KIZUNA_USE_SQLITE` and set `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, and `MYSQL_PORT` in the environment or in `.env`. Do not put the password in source.

Optional checks:

```powershell
$env:KIZUNA_USE_SQLITE = '1'
python manage.py makemigrations --check --dry-run
python manage.py test
```

## Exact steps to launch the final hackathon demo

Stay on SQLite unless MySQL is already running. Do not reset the clock unless you want hour 0 and are willing to drop the stored hours.

1. Run the commands above. Leave the server on `http://127.0.0.1:8000/`.
2. Sign in as the citizen account (`citizen.demo` is the account the dashboard was built around). You land on `/dashboard/`.
3. Read the board. Hour, tanks, batteries, solar, resilience, flows, and the brain all come from the stored clock. The header says Simulated.
4. If you want the clock to move, press **Run clock**, wait a few seconds, then press it again to pause. Leaving the tab hides the poll and stops the stepper. Do not press Reset on the simulation page unless you mean to wipe stored hours.
5. Open **Digital Twin**. The house canvas should show the same hour as the dashboard. Open **Harbour Gym** from the twin page for the business twin (`/twin/business/1/`).
6. Back on the dashboard, press **START CRISIS DAY**. Press **START** on that page. The 10:00–20:00 series plays locally. Pause and Reset on that page affect only that series. The shared clock stays where you left it. The page says it does not call a weather service.
7. Open **Tunisia**. The map is Leaflet with 24 governorates. Say out loud that the colour is a simulated index. Registered sites without coordinates are listed as unplaced.
8. Walk the remaining jury pages from the dashboard sidebar, in this order if time is short: **Resource Network**, **Resource Passport**, **Resilience League**, **KIZUNA Exchange** (`/market/`), **What If?** (`/ai/`), **Crisis Lab**, then **KIZUNA Brain** from the dashboard card.
9. For the farmer half of the demo, sign out and sign in as `farmer.olive`. Open **My Farm** (that account can) and **KIZUNA Exchange**. Homes and Business stay closed for that role.
10. Stop the server with Ctrl+C in the same terminal.

Do not describe governorate scores, network node names (Home A, Solar C, Business C), or Crisis Day totals as measurements. They are simulated, and the pages say so.
