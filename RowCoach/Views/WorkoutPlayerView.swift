import SwiftUI

struct WorkoutPlayerView: View {
    let config: WorkoutConfig
    let video: VideoItem

    @StateObject private var viewModel: WorkoutViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var showControls = true
    @State private var showStopConfirmation = false

    init(config: WorkoutConfig, video: VideoItem) {
        self.config = config
        self.video = video
        _viewModel = StateObject(wrappedValue: WorkoutViewModel(config: config))
    }

    var body: some View {
        ZStack {
            // Background: black
            Color.black.ignoresSafeArea()

            // Video layer (full screen)
            if let url = video.url {
                VideoPlayerView(
                    url: url,
                    playbackRate: viewModel.videoPlaybackRate,
                    isPlaying: viewModel.isRunning
                )
                .ignoresSafeArea()
            }

            // HUD overlay
            if !viewModel.isFinished {
                WorkoutHUDView(viewModel: viewModel)
                    .transition(.opacity)
            }

            // Controls overlay (top bar)
            if showControls {
                controlsOverlay
                    .transition(.opacity)
            }

            // Finished overlay
            if viewModel.isFinished {
                finishedOverlay
            }

            // Tap to show/hide controls
            Color.clear
                .contentShape(Rectangle())
                .onTapGesture {
                    withAnimation(.easeInOut(duration: 0.2)) {
                        showControls.toggle()
                    }
                }
                .allowsHitTesting(!viewModel.isFinished)
        }
        .statusBarHidden(true)
        .onAppear {
            viewModel.start()
            // Auto-hide controls after 3 seconds
            DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                withAnimation { showControls = false }
            }
        }
        .onDisappear {
            viewModel.stop()
        }
        .confirmationDialog("End Workout?", isPresented: $showStopConfirmation) {
            Button("End Workout", role: .destructive) {
                viewModel.stop()
                dismiss()
            }
            Button("Cancel", role: .cancel) { }
        } message: {
            Text("Are you sure you want to end this workout?")
        }
    }

    // MARK: - Controls Overlay

    private var controlsOverlay: some View {
        VStack {
            HStack {
                // Close / Stop button
                Button {
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
