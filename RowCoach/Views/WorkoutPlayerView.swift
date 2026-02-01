import SwiftUI

struct WorkoutPlayerView: View {
    let config: WorkoutConfig
    let video: VideoItem

    @StateObject private var viewModel: WorkoutViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var showControls = true
    @State private var showStopConfirmation = false
    @State private var videoStatus: VideoPlayerStatus = .loading
    @State private var autoHideTask: Task<Void, Never>?
    /// Track whether workout was running before the stop dialog paused it
    @State private var wasRunningBeforeStopDialog = false

    init(config: WorkoutConfig, video: VideoItem) {
        self.config = config
        self.video = video
        _viewModel = StateObject(wrappedValue: WorkoutViewModel(config: config))
    }

    var body: some View {
        ZStack {
            // Layer 1: Background
            Color.black.ignoresSafeArea()

            // Layer 2: Video
            if let url = video.url {
                VideoPlayerView(
                    url: url,
                    playbackRate: viewModel.videoPlaybackRate,
                    isPlaying: viewModel.isRunning,
                    status: $videoStatus
                )
                .ignoresSafeArea()
                .allowsHitTesting(false)
            }

            // Layer 3: Video status overlays (loading / error)
            videoStatusOverlay

            // Layer 4: HUD overlay
            if !viewModel.isFinished {
                WorkoutHUDView(viewModel: viewModel)
                    .allowsHitTesting(false)
                    .transition(.opacity)
            }

            // Layer 5: Tap-to-toggle (BELOW controls, ABOVE HUD)
            Color.clear
                .contentShape(Rectangle())
                .onTapGesture {
                    withAnimation(.easeInOut(duration: 0.2)) {
                        showControls.toggle()
                    }
                    if showControls {
                        scheduleAutoHide()
                    }
                }
                .allowsHitTesting(!viewModel.isFinished)

            // Layer 6: Controls overlay (ON TOP — receives taps over tap-catcher)
            if showControls && !viewModel.isFinished {
                controlsOverlay
                    .transition(.opacity)
            }

            // Layer 7: Finished overlay (topmost)
            if viewModel.isFinished {
                finishedOverlay
            }
        }
        .statusBarHidden(true)
        .onAppear {
            viewModel.start()
            scheduleAutoHide()
        }
        .onDisappear {
            autoHideTask?.cancel()
            viewModel.stop()
        }
        .confirmationDialog("End Workout?", isPresented: $showStopConfirmation, titleVisibility: .visible) {
            Button("End Workout", role: .destructive) {
                viewModel.stop()
                dismiss()
            }
            Button("Cancel", role: .cancel) {
                // Auto-resume if workout was running before we paused for the dialog
                if wasRunningBeforeStopDialog {
                    viewModel.resume()
                }
            }
        } message: {
            Text("Are you sure you want to end this workout?")
        }
    }

    // MARK: - Auto-hide Controls

    private func scheduleAutoHide() {
        autoHideTask?.cancel()
        autoHideTask = Task { @MainActor in
            try? await Task.sleep(for: .seconds(3))
            guard !Task.isCancelled else { return }
            withAnimation { showControls = false }
        }
    }

    // MARK: - Video Status Overlay

    @ViewBuilder
    private var videoStatusOverlay: some View {
        switch videoStatus {
        case .loading:
            VStack(spacing: 12) {
                ProgressView()
                    .scaleEffect(1.5)
                    .tint(.white)
                Text("Loading video...")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.7))
            }
        case .error(let message):
            VStack(spacing: 12) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.system(size: 36))
                    .foregroundColor(.yellow)
                Text("Video failed to load")
                    .font(.headline)
                    .foregroundColor(.white)
                Text(message)
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.6))
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 40)
                Text("The workout timer is still running.")
                    .font(.caption2)
                    .foregroundColor(.white.opacity(0.5))
            }
        case .ready:
            EmptyView()
        }
    }

    // MARK: - Controls Overlay

    private var controlsOverlay: some View {
        VStack {
            HStack {
                // Close / Stop button
                Button {
                    wasRunningBeforeStopDialog = viewModel.isRunning
                    if viewModel.isRunning || viewModel.isPaused {
                        viewModel.pause()
                        showStopConfirmation = true
                    } else {
                        dismiss()
                    }
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.title)
                        .foregroundStyle(.white.opacity(0.8))
                }

                Spacer()

                // Pause / Resume
                if viewModel.isRunning {
                    Button {
                        viewModel.pause()
                    } label: {
                        Image(systemName: "pause.circle.fill")
                            .font(.title)
                            .foregroundStyle(.white.opacity(0.8))
                    }
                } else if viewModel.isPaused {
                    Button {
                        viewModel.resume()
                    } label: {
                        Image(systemName: "play.circle.fill")
                            .font(.title)
                            .foregroundStyle(.white.opacity(0.8))
                    }
                }
            }
            .padding(.horizontal, 20)
            .padding(.top, 60)

            Spacer()
        }
    }

    // MARK: - Finished Overlay

    private var finishedOverlay: some View {
        VStack(spacing: 20) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 64))
                .foregroundColor(.green)

            Text("Workout Complete!")
                .font(.title.bold())
                .foregroundColor(.white)

            Text("Total time: \(viewModel.formattedTotalTime)")
                .font(.title3)
                .foregroundColor(.white.opacity(0.8))

            Button {
                dismiss()
            } label: {
                Text("Done")
                    .fontWeight(.semibold)
                    .frame(width: 200)
                    .padding()
                    .background(Color.blue)
                    .foregroundColor(.white)
                    .cornerRadius(14)
            }
            .padding(.top, 12)
        }
        .padding(32)
        .background(
            RoundedRectangle(cornerRadius: 24)
                .fill(.ultraThinMaterial)
                .environment(\.colorScheme, .dark)
        )
    }
}
