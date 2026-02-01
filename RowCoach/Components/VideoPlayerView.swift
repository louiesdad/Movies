import SwiftUI
import AVFoundation

// MARK: - Status enum (shared with WorkoutPlayerView)

enum VideoPlayerStatus: Equatable {
    case loading
    case ready
    case error(String)
}

// MARK: - SwiftUI wrapper

/// A looping video player that supports playback rate changes.
/// Uses AVQueuePlayer + AVPlayerLooper for gapless looping and
/// reports loading/error status via a binding.
struct VideoPlayerView: UIViewRepresentable {
    let url: URL
    let playbackRate: Float
    let isPlaying: Bool
    @Binding var status: VideoPlayerStatus

    func makeCoordinator() -> Coordinator {
        Coordinator(status: $status)
    }

    func makeUIView(context: Context) -> PlayerUIView {
        let view = PlayerUIView()
        view.configure(url: url, coordinator: context.coordinator)
        return view
    }

    func updateUIView(_ uiView: PlayerUIView, context: Context) {
        if isPlaying {
            uiView.play(rate: playbackRate)
        } else {
            uiView.pause()
        }
    }

    static func dismantleUIView(_ uiView: PlayerUIView, coordinator: Coordinator) {
        coordinator.invalidate()
        uiView.cleanup()
    }

    // MARK: - Coordinator (observes player item status)

    final class Coordinator: NSObject {
        private var statusBinding: Binding<VideoPlayerStatus>
        private var statusObservation: NSKeyValueObservation?

        init(status: Binding<VideoPlayerStatus>) {
            self.statusBinding = status
        }

        func observe(playerItem: AVPlayerItem) {
            statusObservation = playerItem.observe(\.status, options: [.new, .initial]) { [weak self] item, _ in
                DispatchQueue.main.async {
                    switch item.status {
                    case .readyToPlay:
                        self?.statusBinding.wrappedValue = .ready
                    case .failed:
                        let message = item.error?.localizedDescription ?? "Unknown error"
                        self?.statusBinding.wrappedValue = .error(message)
                    case .unknown:
                        self?.statusBinding.wrappedValue = .loading
                    @unknown default:
                        break
                    }
                }
            }
        }

        func invalidate() {
            statusObservation?.invalidate()
            statusObservation = nil
        }
    }
}

// MARK: - UIView hosting AVPlayerLayer

final class PlayerUIView: UIView {

    private var player: AVQueuePlayer?
    private var playerLooper: AVPlayerLooper?
    /// Tracks the last rate we applied to avoid redundant sets (fixes C3)
    private var currentRate: Float = 0

    override class var layerClass: AnyClass {
        AVPlayerLayer.self
    }

    private var avPlayerLayer: AVPlayerLayer {
        layer as! AVPlayerLayer
    }

    func configure(url: URL, coordinator: VideoPlayerView.Coordinator) {
        let asset = AVURLAsset(url: url)
        let playerItem = AVPlayerItem(asset: asset)
        let player = AVQueuePlayer(items: [playerItem])
        player.isMuted = true  // mute video audio — rowing machine is loud enough
        self.player = player

        // Gapless looping via AVPlayerLooper (fixes C2 — no more play() on loop)
        playerLooper = AVPlayerLooper(player: player, templateItem: playerItem)

        avPlayerLayer.player = player
        avPlayerLayer.videoGravity = .resizeAspectFill

        // Observe item status for loading/error feedback (fixes H3)
        coordinator.observe(playerItem: playerItem)
    }

    func play(rate: Float) {
        guard let player = player else { return }
        if player.timeControlStatus != .playing {
            player.play()
        }
        // Only update rate when it actually changes (fixes C3 — no micro-stutter)
        if abs(currentRate - rate) > 0.001 {
            player.rate = rate
            currentRate = rate
        }
    }

    func pause() {
        player?.pause()
        currentRate = 0
    }

    func cleanup() {
        playerLooper?.disableLooping()
        playerLooper = nil
        player?.pause()
        player?.removeAllItems()
        player = nil
    }
}
