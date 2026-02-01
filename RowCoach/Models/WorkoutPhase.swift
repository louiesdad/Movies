import Foundation

enum WorkoutPhase: String, Codable {
    case warmup
    case work
    case rest
    case cooldown
    case finished

    var displayName: String {
        switch self {
        case .warmup:   return "WARM UP"
        case .work:     return "WORK"
        case .rest:     return "REST"
        case .cooldown: return "COOL DOWN"
        case .finished: return "FINISHED"
        }
    }

    /// Target strokes per minute range for each phase
    var targetSPM: ClosedRange<Int> {
        switch self {
        case .warmup:   return 18...22
        case .work:     return 28...32
        case .rest:     return 16...20
        case .cooldown: return 16...20
        case .finished: return 0...0
        }
    }

    /// Video playback rate multiplier for each phase
    var videoPlaybackRate: Float {
        switch self {
        case .warmup:   return 0.8
        case .work:     return 1.2
        case .rest:     return 0.6
        case .cooldown: return 0.7
        case .finished: return 0.0
        }
    }

}
