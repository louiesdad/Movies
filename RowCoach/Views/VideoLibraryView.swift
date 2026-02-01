import SwiftUI

struct VideoLibraryView: View {
    @Binding var selectedVideo: VideoItem?
    @Environment(\.dismiss) private var dismiss
    @State private var allVideos: [VideoItem] = []
    @State private var showAddVideo = false

    var body: some View {
        NavigationStack {
            List {
                Section("Included Scenes") {
                    ForEach(allVideos.filter { !$0.isCustom }) { video in
                        videoRow(video)
                    }
                }

                let customVideos = allVideos.filter { $0.isCustom }
                if !customVideos.isEmpty {
                    Section("My Videos") {
                        ForEach(customVideos) { video in
                            videoRow(video)
                        }
                        .onDelete(perform: deleteCustomVideo)
                    }
                }

                Section {
                    Button {
                        showAddVideo = true
                    } label: {
                        HStack {
                            Image(systemName: "plus.circle.fill")
                                .foregroundColor(.blue)
                            Text("Add Video URL")
                        }
                    }
                }
            }
            .navigationTitle("Choose a Scene")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
            .sheet(isPresented: $showAddVideo) {
                AddVideoView { newVideo in
                    var custom = VideoLibrary.loadCustomVideos()
                    custom.append(newVideo)
                    VideoLibrary.saveCustomVideos(custom)
                    refreshVideos()
                }
            }
            .onAppear {
                refreshVideos()
            }
        }
    }

    private func videoRow(_ video: VideoItem) -> some View {
        Button {
            selectedVideo = video
            dismiss()
        } label: {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(video.title)
                        .font(.body.weight(.medium))
                        .foregroundColor(.primary)
                    Text(video.subtitle)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(2)
                }

                Spacer()

                if selectedVideo?.id == video.id {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.blue)
                }
            }
            .contentShape(Rectangle())
        }
    }

    private func deleteCustomVideo(at offsets: IndexSet) {
        var custom = VideoLibrary.loadCustomVideos()
        // Map offsets from filtered list to custom array
        let customVideos = allVideos.filter { $0.isCustom }
        for offset in offsets {
            let videoToDelete = customVideos[offset]
            custom.removeAll { $0.id == videoToDelete.id }
            if selectedVideo?.id == videoToDelete.id {
                selectedVideo = allVideos.first
            }
        }
        VideoLibrary.saveCustomVideos(custom)
        refreshVideos()
    }

    private func refreshVideos() {
        allVideos = VideoLibrary.allVideos()
    }
}
