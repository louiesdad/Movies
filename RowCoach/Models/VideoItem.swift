import Foundation

struct VideoItem: Identifiable, Codable, Equatable {
    let id: UUID
    var title: String
    var description: String
    var urlString: String
    var isCustom: Bool

    var url: URL? {
        URL(string: urlString)
    }

    init(id: UUID = UUID(), title: String, description: String, urlString: String, isCustom: Bool = false) {
        self.id = id
        self.title = title
        self.description = description
        self.urlString = urlString
        self.isCustom = isCustom
    }
}

// MARK: - Video Library

struct VideoLibrary {
    /// Curated sample videos — replace URLs with your own MP4 links
    static let sampleVideos: [VideoItem] = [
        VideoItem(
            title: "Calm River Row",
            description: "Peaceful POV rowing on a quiet river at dawn",
            urlString: "https://videos.pexels.com/video-files/5765290/5765290-hd_1920_1080_30fps.mp4"
        ),
        VideoItem(
            title: "Lake Morning",
            description: "Early morning row across a still mountain lake",
            urlString: "https://videos.pexels.com/video-files/6394054/6394054-uhd_2560_1440_25fps.mp4"
        ),
        VideoItem(
            title: "Ocean Coastal Row",
            description: "Rowing along a scenic ocean coastline",
            urlString: "https://videos.pexels.com/video-files/4925025/4925025-hd_1920_1080_30fps.mp4"
        ),
    ]

    // MARK: - Persistence for custom videos

    private static let storageKey = "RowCoach_CustomVideos"

    static func loadCustomVideos() -> [VideoItem] {
        guard let data = UserDefaults.standard.data(forKey: storageKey),
              let items = try? JSONDecoder().decode([VideoItem].self, from: data)
        else {
            return []
        }
        return items
    }

    static func saveCustomVideos(_ videos: [VideoItem]) {
        if let data = try? JSONEncoder().encode(videos) {
            UserDefaults.standard.set(data, forKey: storageKey)
        }
    }

    static func allVideos() -> [VideoItem] {
        sampleVideos + loadCustomVideos()
    }
}
