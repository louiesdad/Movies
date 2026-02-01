# RowCoach

An iOS app that plays POV rowing videos while guiding you through structured workouts on your magnetic rowing machine.

## Features

- **POV Video Playback** — Stream scenic rowing videos full-screen during your workout
- **Video Speed Sync** — Playback speed adjusts to match workout intensity (slower warmup, faster intervals)
- **Configurable Workouts** — Set warmup, interval count, work/rest duration, and cooldown
- **Live HUD Overlay** — Shows current phase, countdown timer, interval progress, target stroke rate, and total time
- **Video Library** — Browse included scenes or add your own MP4 video URLs
- **Settings Persistence** — Your workout config is saved between sessions

## Workout Structure

```
Warm Up → [Work → Rest] × N → Cool Down
```

Each phase has a target stroke rate (SPM) and video speed:

| Phase     | Target SPM | Video Speed |
|-----------|-----------|-------------|
| Warm Up   | 18-22     | 0.8x        |
| Work      | 28-32     | 1.2x        |
| Rest      | 16-20     | 0.6x        |
| Cool Down | 16-20     | 0.7x        |

## Setup

### Prerequisites

- A Mac with **Xcode 15+** (free from the Mac App Store)
- **XcodeGen** (generates the Xcode project from `project.yml`)

### Steps

1. **Install XcodeGen** (one time):
   ```bash
   brew install xcodegen
   ```

2. **Clone this repo**:
   ```bash
   git clone https://github.com/louiesdad/Movies.git
   cd Movies/RowCoach
   ```

3. **Generate the Xcode project**:
   ```bash
   xcodegen
   ```
   This creates `RowCoach.xcodeproj` from `project.yml`.

4. **Open in Xcode**:
   ```bash
   open RowCoach.xcodeproj
   ```

5. **Set your development team**:
   - Select the **RowCoach** target → **Signing & Capabilities**
   - Choose your Apple ID / development team
   - Xcode will handle provisioning automatically

6. **Run on your iPhone**:
   - Connect your iPhone via USB
   - Select your device in the Xcode toolbar
   - Press **Cmd+R** to build and run

### Free Apple Developer Account

With a free Apple ID you can sideload to your own device, but the app expires after 7 days and needs reinstalling. The $99/year Apple Developer Program removes this limitation.

## Adding Videos

The app ships with a few sample video URLs. To add your own:

1. Go to [Pexels Videos](https://www.pexels.com/search/videos/rowing/) or [Pixabay Videos](https://pixabay.com/videos/search/rowing/)
2. Find a POV rowing or water scene video
3. Right-click the download button → Copy Link Address to get the direct MP4 URL
4. In the app, tap **Choose a Scene → Add Video URL** and paste it

## Project Structure

```
RowCoach/
├── RowCoachApp.swift           # App entry point
├── Info.plist                  # App configuration
├── project.yml                 # XcodeGen project spec
├── Assets.xcassets/            # Colors, app icon
├── Models/
│   ├── WorkoutPhase.swift      # Phase enum (warmup/work/rest/cooldown)
│   ├── WorkoutConfig.swift     # Workout settings with persistence
│   └── VideoItem.swift         # Video model + library
├── ViewModels/
│   └── WorkoutViewModel.swift  # Timer engine + phase management
├── Views/
│   ├── HomeView.swift          # Main screen
│   ├── WorkoutConfigView.swift # Interval/duration controls
│   ├── WorkoutPlayerView.swift # Full-screen workout experience
│   ├── VideoLibraryView.swift  # Video picker
│   └── AddVideoView.swift      # Add custom video URL
└── Components/
    ├── VideoPlayerView.swift   # AVPlayer wrapper with speed control
    └── WorkoutHUDView.swift    # Translucent stats overlay
```
