# 12 — Running and building this, step by step

Written for someone with no programming or engine experience, per brief §21.
Every step says exactly what to click. Where something cannot be done without a
purchase or a second computer, it says so plainly instead of pretending.

---

## Part A — Play the prototype right now (2 minutes, nothing to install)

This is the quickest way to see whether the game *feels* right.

1. Open the link for the playable prototype that came with this handoff.
2. On a phone, **turn the phone sideways**. The game is designed for landscape.
3. Tap **New campaign**.
4. You are on the strategic map in June 1944. Tap the diamond icon on the
   Normandy coast — that is your resistance cell.
5. A panel slides up from the bottom. Tap **Sabotage** or **Reconnaissance**,
   then tap **Confirm order**. You just spent materiel; the number at the top
   right changed.
6. Tap **End week**. A report appears listing exactly what happened and why.
7. Tap **Operations** at the bottom left, then **A line in the hedges**, then
   **Begin operation**.
8. You are now standing in a lane in Normandy. Your **left thumb** moves, your
   **right thumb** looks. The buttons on the right are fire, aim and reload.
9. Walk to the telephone pole. A button labelled **Interact** appears — **hold
   it** to cut the line.
10. Hold **Aim** and look at the gun emplacement in the east field from a
    distance to observe it.
11. Walk into the barn to extract. The result screen lists each change.
12. Tap **Return to the map**. Look at the top-right numbers: your intelligence
    went up, and a new operation unlocked.

That is the whole loop the brief describes. **The graphics are deliberately
plain** — they are a blockout, not the finished art. What you are judging here
is whether the loop works.

---

## Part B — Check that the rules are correct (5 minutes)

This runs the 162 automated tests. You do not need to understand the output;
you need the last line to say `162 passed`.

1. Install Node.js: open <https://nodejs.org>, click the big green **LTS**
   button, run the installer, click **Next** until it finishes.
2. Open the **Start menu**, type `cmd`, press **Enter**. A black window opens.
3. Type this and press **Enter** (replace the path with where this project
   folder actually is):

   ```
   cd C:\Users\YourName\Downloads\Music-AI
   ```

4. Type this and press **Enter**:

   ```
   node web/tests/run-all.js
   ```

5. Wait about one second. Scroll to the bottom. You want:

   ```
   162 passed
   ```

   If it says anything with `failed`, copy the whole window and send it to the
   developer. That is a real bug, and it is better found here than on a phone.

---

## Part C — Open the Godot project (15 minutes)

**Important:** this project has never been opened in Godot, because the machine
that wrote it did not have Godot installed. Expect errors on the first open.
That is normal and expected — see `docs/13-LIMITATIONS.md`.

1. Go to <https://godotengine.org/download/windows>.
2. Download **Godot Engine 4.3** — the **Standard** version, not .NET.
3. You get a ZIP file. Right-click it → **Extract All** → **Extract**.
4. Double-click `Godot_v4.3-stable_win64.exe`. No installer; it just runs.
5. In the Project Manager window, click **Import**.
6. Click **Browse**, navigate to this project folder, open the `godot` folder
   inside it, and select the file called `project.godot`. Click **Open**.
7. Click **Import & Edit**.
8. The editor opens. Look at the bottom panel. If there is a tab called
   **Debugger** or **Errors** with a red number on it, click it. Those are the
   errors to send to the developer.
9. Press **F5** to run. If it starts, you will see the launch screen listing
   what content is installed.

### Running the Godot tests

1. In the editor, click the **Output** tab at the bottom.
2. Open the Start menu, type `cmd`, press **Enter**.
3. Type this, all on one line, and press **Enter** (adjust both paths):

   ```
   "C:\Users\YourName\Downloads\Godot_v4.3-stable_win64.exe" --headless --path "C:\Users\YourName\Downloads\Music-AI\godot" --script res://tests/test_runner.gd
   ```

4. The last line tells you how many passed and how many failed.

---

## Part D — Make an Android file you can install (1–2 hours, first time only)

You need this to put the game on a real phone. There is no shortcut.

### D1. Install the Android build tools

1. Download **Android Studio** from
   <https://developer.android.com/studio>. Run the installer; accept the
   defaults.
2. Open Android Studio. On the welcome screen click **More Actions** →
   **SDK Manager**.
3. Click the **SDK Tools** tab. Tick **Android SDK Build-Tools**,
   **Android SDK Command-line Tools** and **Android SDK Platform-Tools**.
   Click **Apply**, then **OK**, and let it download.
4. Write down the path shown at the top as **Android SDK Location**. You will
   need it in a moment.

### D2. Make a signing key

A signing key is the file that proves a build came from you. **Keep it. If you
lose it you can never update your own app.**

1. Open the Start menu, type `cmd`, press **Enter**.
2. Type this all on one line and press **Enter** (adjust the SDK path):

   ```
   "C:\Program Files\Android\Android Studio\jbr\bin\keytool.exe" -genkeypair -v -keystore C:\Users\YourName\wbtm-release.keystore -alias wbtm -keyalg RSA -keysize 2048 -validity 10000
   ```

3. It asks for a password. Type one and **write it down somewhere safe**. You
   will not see the characters as you type — that is normal.
4. It asks for your name, organisation and country. Answer or press **Enter** to
   skip. At the end type `yes` and press **Enter**.
5. You now have `wbtm-release.keystore` in your user folder. Back it up.

### D3. Tell Godot where everything is

1. In Godot, click **Editor** (top menu) → **Editor Settings**.
2. In the search box type `android`.
3. Set **Android SDK Path** to the SDK Location you wrote down.
4. Set **Debug Keystore** to your `.keystore` file, **Debug Keystore User** to
   `wbtm`, and **Debug Keystore Pass** to your password.
5. Close Editor Settings.
6. Click **Project** → **Install Android Build Template**, then **Install**.

### D4. Export

1. Click **Project** → **Export**.
2. Click **Add…** → **Android**.
3. Under **Keystore**, set **Release** to your `.keystore` file, **Release User**
   to `wbtm`, and **Release Password** to your password.
4. Set **Architectures** → tick **arm64-v8a** only.
5. Click **Export Project**, choose where to save, name it `wbtm.apk`, and
   **untick** "Export With Debug".
6. Copy `wbtm.apk` to your phone, tap it, and allow installation from this
   source when the phone asks.

**If Godot refuses to export**, read the message at the bottom of the Export
window. It names exactly which of the steps above is incomplete.

---

## Part E — iOS

**This cannot be done on Windows.** Godot's iOS export requires macOS and
Xcode (brief T3). The options are:

1. Borrow or buy a Mac (a Mac mini is the cheapest), install Xcode free from
   the Mac App Store, and export from Godot on that machine.
2. Use a paid cloud Mac service.
3. Have the developer do the iOS builds and send you the TestFlight link.

You will also need an **Apple Developer Program** membership (about USD 99 a
year) to put the game on any iPhone other than your own.

**Keep the signing key and both store accounts in your own name.** The brief
asks for this specifically, and it matters: whoever holds them controls updates.

---

## If something goes wrong

Send the developer all of:

- which Part you were on and which numbered step;
- the **entire** contents of the black window or the Godot **Errors** tab, not a
  summary;
- your Windows version, your Godot version, and your phone model if a phone was
  involved.

A screenshot of an error message is enough. You do not need to interpret it.
