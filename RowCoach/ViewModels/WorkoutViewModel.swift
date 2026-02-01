import Foundation
import Combine

final class WorkoutViewModel: ObservableObject {

    // MARK: - Published State

    @Published var currentPhase: WorkoutPhase = .warmup
    @Published var phaseTimeRemaining: TimeInterval = 0
    @Published var totalElapsedTime: TimeInterval = 0
    @Published var currentIntervalNumber: Int = 0  // 1-based during work/rest
    @Published var isRunning: Bool = false
    @Published var isPaused: Bool = false
    @Published var isFinished: Bool = false

    // MARK: - Configuration

    let config: WorkoutConfig
    private(set) var phases: [(phase: WorkoutPhase, duration: TimeInterval)] = []
    private var currentPhaseIndex: Int = 0

    // MARK: - Timer

    private var timer: AnyCancellable?
    private var lastTick: Date?
    private let tickInterval: TimeInterval = 0.1  // 100ms updates for smooth countdown

    // MARK: - Computed

    var totalIntervals: Int { config.intervalCount }

    var targetSPM: ClosedRange<Int> { currentPhase.targetSPM }

    var videoPlaybackRate: Float { currentPhase.videoPlaybackRate }

    var phaseProgress: Double {
        guard let phaseDuration = currentPhaseDuration, phaseDuration > 0 else { return 0 }
        return 1.0 - (phaseTimeRemaining / phaseDuration)
    }

    var totalProgress: Double {
        guard config.totalDuration > 0 else { return 0 }
        return totalElapsedTime / config.totalDuration
    }

    var formattedPhaseTime: String { Self.formatTime(phaseTimeRemaining) }
    var formattedTotalTime: String { Self.formatTime(totalElapsedTime) }

    var formattedTotalDuration: String { Self.formatTime(config.totalDuration) }

    var intervalLabel: String {
        guard currentPhase == .work || currentPhase == .rest else { return "" }
        return "\(currentIntervalNumber) of \(totalIntervals)"
    }

    private var currentPhaseDuration: TimeInterval? {
        guard currentPhaseIndex < phases.count else { return nil }
        return phases[currentPhaseIndex].duration
    }

    // MARK: - Init

    init(config: WorkoutConfig) {
        self.config = config
        self.phases = config.phases
        prepareFirstPhase()
    }

    // MARK: - Controls

    func start() {
        guard !isRunning else { return }
        isRunning = true
        isPaused = false
        isFinished = false
        lastTick = Date()
        startTimer()
    }

    func pause() {
        isPaused = true
        isRunning = false
        stopTimer()
    }

    func resume() {
        isPaused = false
        isRunning = true
        lastTick = Date()
        startTimer()
    }

    func stop() {
        isRunning = false
        isPaused = false
        isFinished = true
        stopTimer()
    }

    func reset() {
        stopTimer()
        isRunning = false
        isPaused = false
        isFinished = false
        currentPhaseIndex = 0
        totalElapsedTime = 0
        currentIntervalNumber = 0
        prepareFirstPhase()
    }

    // MARK: - Timer Logic

    private func startTimer() {
        timer = Timer.publish(every: tickInterval, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                self?.tick()
            }
    }

    private func stopTimer() {
        timer?.cancel()
        timer = nil
    }

    private func tick() {
        guard isRunning, !isPaused else { return }

        let now = Date()
        let elapsed = now.timeIntervalSince(lastTick ?? now)
        lastTick = now

        totalElapsedTime += elapsed
        phaseTimeRemaining -= elapsed

        if phaseTimeRemaining <= 0 {
            advancePhase()
        }
    }

    private func advancePhase() {
        // Carry forward any time that overshot past zero to prevent drift (fixes H4)
        let overflow = -phaseTimeRemaining

        currentPhaseIndex += 1

        if currentPhaseIndex >= phases.count {
            // Workout complete
            currentPhase = .finished
            phaseTimeRemaining = 0
            stop()
            return
        }

        let next = phases[currentPhaseIndex]
        currentPhase = next.phase
        phaseTimeRemaining = next.duration - overflow
        updateIntervalNumber()
    }

    private func prepareFirstPhase() {
        guard !phases.isEmpty else { return }
        let first = phases[0]
        currentPhase = first.phase
        phaseTimeRemaining = first.duration
        updateIntervalNumber()
    }

    private func updateIntervalNumber() {
        // Count how many work phases we've reached so far (including current)
        var workCount = 0
        for i in 0...currentPhaseIndex where phases[i].phase == .work {
            workCount += 1
        }
        currentIntervalNumber = workCount
    }

    // MARK: - Formatting

    static func formatTime(_ seconds: TimeInterval) -> String {
        let totalSeconds = max(0, Int(ceil(seconds)))
        let mins = totalSeconds / 60
        let secs = totalSeconds % 60
        return String(format: "%d:%02d", mins, secs)
    }
}
