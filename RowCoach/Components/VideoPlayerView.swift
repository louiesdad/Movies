import SwiftUI
import AVFoundation
import AVKit

/// A looping video player that supports playback rate changes.
/// Wraps AVPlayerLayer in a UIViewRepresentable for SwiftUI.
struct VideoPlayerView: UIViewRepresentable {
    let url: URL
    let playbackRate: Float
    let isPlaying: Bool

    func makeUIView(context: Context) -> PlayerUIView {
        let view = PlayerUIView()
        view.configure(url: url)
        return view
    }

    func updateUIView(_ uiView: PlayerUIView, context: Context) {
        if isPlaying {
            uiView.play(rate: playbackRate)
        } else {
            uiView.pause()
        }
    }

    static func dismantleUIView(_ uiView: PlayerUIView, coordinator: ()) {
        uiView.cleanup()
    }
}

/// UIView subclass that hosts an AVPlayerLayer for video playback.
final class PlayerUIView: UIView {

    private var player: AVPlayer?
    private var playerLayer: AVPlayerLayer?
    private var loopObserver: Any?

    override class var layerClass: AnyClass {
        AVPlayerLayer.self
    }

    private var avPlayerLayer: AVPlayerLayer {
        layer as! AVPlayerLayer
    }

    func configure(url: URL) {
        let playerItem = AVPlayerItem(url: url)
        let player = AVPlayer(playerItem: playerItem)
        player.isMuted = true  // mute video audio — rowing machine is loud enough
        self.player = player

        avPlayerLayer.player = player
        avPlayerLayer.videoGravity = .resizeAspectFill

        // Loop: when video ends, seek back to start
        loopObserver = NotificationCenter.default.addObserver(
            forName: .AVPlayerItemDidPlayToEndTime,
            object: playerItem,
            queue: .main
        ) { [weak player] _ in
            player?.seek(to: .zero)
            player?.play()
        }
    }

    func play(rate: Float) {
        guard let player = player else { return }
        if player.timeControlStatus != .playing {
            player.play()
        }
        player.rate = rate
    }

    func pause() {
        player?.pause()
    }

    func cleanup() {
        player?.pause()
        player = nil
        if let observer = loopObserver {
            NotificationCenter.default.removeObserver(observer)
            loopObserver = nil
        }
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        avPlayerLayer.frame = bounds
    }
}
