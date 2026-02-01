import SwiftUI

struct HomeView: View {
    @State private var config = WorkoutConfig.load()
    @State private var selectedVideo: VideoItem?
    @State private var showVideoLibrary = false
    @State private var showWorkout = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    headerSection
                    videoSection
                    WorkoutConfigView(config: $config)
                    startButton
                }
                .padding()
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("RowCoach")
            .sheet(isPresented: $showVideoLibrary) {
                VideoLibraryView(selectedVideo: $selectedVideo)
            }
            .fullScreenCover(isPresented: $showWorkout) {
                if let video = selectedVideo {
                    WorkoutPlayerView(config: config, video: video)
                }
            }
            .onChange(of: config) { _, newConfig in
                newConfig.save()
            }
            .onAppear {
                if selectedVideo == nil {
                    selectedVideo = VideoLibrary.allVideos().first
                }
            }
        }
    }

    // MARK: - Sections

    private var headerSection: some View {
        VStack(spacing: 4) {
            Image(systemName: "figure.rowing")
                .font(.system(size: 48))
                .foregroundStyle(.blue)
            Text("Row with a view")
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
        .padding(.top, 8)
    }

    private var videoSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Scene")
                .font(.headline)

            Button {
                showVideoLibrary = true
            } label: {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(selectedVideo?.title ?? "Choose a video")
                            .font(.body.weight(.medium))
                            .foregroundColor(.primary)
                        if let desc = selectedVideo?.description {
                            Text(desc)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    Spacer()
                    Image(systemName: "chevron.right")
                        .foregroundColor(.secondary)
                }
                .padding()
                .background(Color(.secondarySystemGroupedBackground))
                .cornerRadius(12)
            }
        }
    }

    private var startButton: some View {
        Button {
            config.save()
            showWorkout = true
        } label: {
            HStack {
                Image(systemName: "play.fill")
                Text("Start Workout")
                    .fontWeight(.semibold)
            }
            .frame(maxWidth: .infinity)
            .padding()
            .background(selectedVideo != nil ? Color.blue : Color.gray)
            .foregroundColor(.white)
            .cornerRadius(14)
        }
        .disabled(selectedVideo == nil)
        .padding(.top, 8)
    }
}

#Preview {
    HomeView()
}
