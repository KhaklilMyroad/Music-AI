# 12 — Running, building and releasing this, step by step

Written for someone with no programming or engine experience, per brief §21.
Every step says exactly what to click. Where something needs a purchase or an
account, it says so instead of pretending.

Target platform: **PC**. Windows is primary; Linux and macOS notes are at the
end.

---

## Part A — Play the prototype right now (2 minutes, nothing to install)

This is the quickest way to see whether the game *feels* right.

1. Open the prototype link that came with this handoff, in Chrome or Edge.
2. Click **New campaign**.
3. You are on the strategic map in June 1944. Click the diamond icon on the
   Normandy coast — that is your resistance cell.
4. A panel slides up. Click **Sabotage** or **Reconnaissance**, then
   **Confirm order**. You just spent materiel; the number at the top right
   changed.
5. Click **End week**. A report lists exactly what happened and why.
6. Click **Operations** at the bottom left, then **A line in the hedges**, then
   **Begin operation**.
7. A dark overlay says **Click to capture the mouse** and lists the keys. Click
   it. The cursor disappears and you are standing in a lane in Normandy.
8. `W` `A` `S` `D` to move, the **mouse** to look, `Shift` to run, `Ctrl` to
   crouch, `Z` to go prone, `Q` and `X` to lean around a corner.
9. Walk to the telephone pole. A prompt appears naming the key — **hold `E`**
   to cut the line.
10. Hold **right mouse** to aim at the gun emplacement in the far field and keep
    it centred to observe it. Hold `Alt` to steady your breathing.
11. Walk into the barn to extract. The result screen lists each change.
12. Click **Return to the map**. Your intelligence went up and a new operation
    unlocked.

Press `Esc` at any time: it releases the mouse and pauses.

**The graphics are deliberately plain** — they are a blockout, not the finished
art. What you are judging is whether the loop works and whether the controls
feel right.

---

## Part B — Check that the rules are correct (5 minutes)

This runs the 182 automated tests. You do not need to understand the output;
you need the last line to say `182 passed`.

1. Install Node.js: open <https://nodejs.org>, click the green **LTS** button,
   run the installer, click **Next** until it finishes.
2. Open the **Start menu**, type `cmd`, press **Enter**.
3. Type this and press **Enter** (adjust the path to where this folder is):

   ```
   cd C:\Users\YourName\Downloads\Music-AI
   ```

4. Type this and press **Enter**:

   ```
   node web/tests/run-all.js
   ```

5. Scroll to the bottom. You want:

   ```
   182 passed
   ```

   Anything with `failed` is a real bug. Copy the whole window and send it.

There is also a check for control-key clashes, which needs Python:

```
python3 -I tools/check_input_bindings.py
```

It should say `no undeclared clashes`.

---

## Part C — Open the Godot project (15 minutes)

**This project has never been opened in Godot**, because the machine that wrote
it did not have Godot installed. Expect errors on the first open. That is
expected, not a surprise — see `docs/13-LIMITATIONS.md`.

1. Go to <https://godotengine.org/download/windows>.
2. Download **Godot Engine 4.3**, the **Standard** version, not .NET.
3. Right-click the ZIP → **Extract All** → **Extract**.
4. Double-click `Godot_v4.3-stable_win64.exe`. There is no installer.
5. In the Project Manager, click **Import**.
6. Click **Browse**, open the `godot` folder inside this project, select
   `project.godot`, click **Open**.
7. Click **Import & Edit**.
8. Look at the bottom panel. If a **Debugger** or **Errors** tab has a red
   number, click it. Those errors are what to send.
9. Press **F5** to run.

### Running the Godot tests

Open a `cmd` window and type this on one line, adjusting both paths:

```
"C:\Users\YourName\Downloads\Godot_v4.3-stable_win64.exe" --headless --path "C:\Users\YourName\Downloads\Music-AI\godot" --script res://tests/test_runner.gd
```

The last line says how many passed and how many failed.

---

## Part D — Make a Windows build (20 minutes)

Far simpler than the mobile path: no SDK, no signing key, no second computer.

1. In Godot, click **Editor** → **Manage Export Templates** → **Download and
   Install**. Wait for it to finish.
2. Click **Project** → **Export**.
3. Click **Add…** → **Windows Desktop**.
4. Leave the defaults. Under **Binary Format**, keep **64 Bits** ticked.
5. Click **Export Project**, choose an **empty** folder, name it
   `WarBeneathTheMap.exe`, and **untick** "Export With Debug".
6. That folder now holds the game. Zip the whole folder to send it — the `.exe`
   alone will not run without the files beside it.

### Optional: sign the executable

Windows will show a "unknown publisher" warning without a code-signing
certificate. One costs roughly USD 200–400 a year from a certificate authority.
It is not required to run the game and is not required for Steam. It is worth
having before distributing an `.exe` directly from a website.

---

## Part E — Release on Steam

This is the real distribution path and most of it is paperwork, not code.

### E1. Set up the account

1. Go to <https://partner.steamgames.com> and sign up as a Steamworks partner.
2. Pay the **Steam Direct** fee — **USD 100 per title** at the time of
   writing. It is recoupable against revenue. **Verify the current amount
   yourself; store fees change and I have not checked today's figure.**
3. Complete the tax and banking forms. This takes days, not minutes, and
   blocks everything else. Do it first.
4. **Keep the account in your own name.** Whoever holds it controls the store
   page, the builds and the money.

### E2. Build the depot

1. Download the **Steamworks SDK** from the partner site.
2. Extract it. Inside `tools/ContentBuilder` there are `app_build_*.vdf` and
   `depot_build_*.vdf` template files.
3. Copy the folder you exported in Part D into
   `tools/ContentBuilder/content/`.
4. Edit the two `.vdf` files: put your App ID and Depot ID in them (Steam gives
   you both when you create the app) and point `ContentRoot` at your folder.
5. Run, from inside `tools/ContentBuilder`:

   ```
   builder\steamcmd.exe +login YOUR_ACCOUNT +run_app_build ..\scripts\app_build_YOURAPPID.vdf +quit
   ```

6. The build appears on the partner site under **Builds**. Set it live on a
   branch to test it.

### E3. Before you can publish

- Store page: capsule art in several sizes, a trailer, screenshots,
  description, tags. The screenshots must be **actual gameplay** — the brief is
  explicit about this and so is Steam.
- Content rating questionnaires (ESRB and PEGI via the partner site, USK
  separately for Germany — see the open question in `docs/11`).
- A two-week minimum between the store page going live and release, which Steam
  enforces.
- Decide on a demo build and on Steam Cloud. Both are optional; both are
  separate work.

---

## Part F — Linux and macOS

**Linux:** export a Linux build from the same Export window (add a **Linux**
preset). Most Linux players will run the Windows build through Proton anyway,
so the useful work is testing that path on Steam Deck or a Proton install
rather than maintaining a native build.

**macOS:** Godot can export macOS from Windows, but the result is unsigned and
recent macOS will refuse to open it. Signing and notarising needs a Mac and an
Apple Developer membership (about USD 99 a year). Recommendation: defer macOS
until there is a reason to pay for it.

---

## If something goes wrong

Send all of:

- which Part you were on and which numbered step;
- the **entire** contents of the black window or the Godot **Errors** tab, not
  a summary;
- your Windows version, your Godot version, and your graphics card.

A screenshot of an error is enough. You do not need to interpret it.
