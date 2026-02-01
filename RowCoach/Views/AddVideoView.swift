import SwiftUI

struct AddVideoView: View {
    var onAdd: (VideoItem) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var title = ""
    @State private var subtitle = ""
    @State private var urlString = ""
    @State private var showError = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Video Details") {
                    TextField("Title", text: $title)
                    TextField("Description (optional)", text: $subtitle)
                }

                Section("Video URL") {
                    TextField("https://example.com/video.mp4", text: $urlString)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                }

                Section {
                    Text("Paste a direct link to an MP4 video file. You can find free rowing POV videos on Pexels.com or Pixabay.com — look for the download link and copy the URL.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            .navigationTitle("Add Video")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Add") { addVideo() }
                        .fontWeight(.semibold)
                        .disabled(title.isEmpty || urlString.isEmpty)
                }
            }
            .alert("Invalid URL", isPresented: $showError) {
                Button("OK", role: .cancel) { }
            } message: {
                Text("Please enter a valid video URL starting with http:// or https://")
            }
        }
    }

    private func addVideo() {
        guard URL(string: urlString) != nil,
              urlString.hasPrefix("http://") || urlString.hasPrefix("https://")
        else {
            showError = true
            return
        }

        let video = VideoItem(
            title: title,
            subtitle: subtitle.isEmpty ? "Custom video" : subtitle,
            urlString: urlString,
            isCustom: true
        )
        onAdd(video)
        dismiss()
    }
}
