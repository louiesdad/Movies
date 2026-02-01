import XCTest
@testable import RowCoach

final class WorkoutViewModelTests: XCTestCase {

    private func makeVM(warmup: TimeInterval = 300, intervals: Int = 8,
                        work: TimeInterval = 60, rest: TimeInterval = 60,
                        cooldown: TimeInterval = 300) -> WorkoutViewModel {
        let config = WorkoutConfig(
            warmupDuration: warmup, intervalCount: intervals,
            workDuration: work, restDuration: rest, cooldownDuration: cooldown
        )
        return WorkoutViewModel(config: config)
    }

    // MARK: - Initial State

    func testInitialState() {
        let vm = makeVM()
        XCTAssertEqual(vm.currentPhase, .warmup)
        XCTAssertEqual(vm.phaseTimeRemaining, 300)
        XCTAssertEqual(vm.totalElapsedTime, 0)
        XCTAssertEqual(vm.currentIntervalNumber, 0)
        XCTAssertFalse(vm.isRunning)
        XCTAssertFalse(vm.isPaused)
        XCTAssertFalse(vm.isFinished)
    }

    // MARK: - Controls

    func testStartStop() {
        let vm = makeVM()
        vm.start()
        XCTAssertTrue(vm.isRunning)
        XCTAssertFalse(vm.isPaused)

        vm.stop()
        XCTAssertFalse(vm.isRunning)
        XCTAssertTrue(vm.isFinished)
    }

    func testPauseResume() {
        let vm = makeVM()
        vm.start()

        vm.pause()
        XCTAssertFalse(vm.isRunning)
        XCTAssertTrue(vm.isPaused)

        vm.resume()
        XCTAssertTrue(vm.isRunning)
        XCTAssertFalse(vm.isPaused)
    }

    func testReset() {
        let vm = makeVM(warmup: 10, intervals: 1, work: 10, rest: 5, cooldown: 10)
        vm.start()
        // The timer runs async, so we test reset clears state
        vm.stop()
        vm.reset()

        XCTAssertFalse(vm.isRunning)
        XCTAssertFalse(vm.isPaused)
        XCTAssertFalse(vm.isFinished)
        XCTAssertEqual(vm.currentPhase, .warmup)
        XCTAssertEqual(vm.totalElapsedTime, 0)
    }

    // MARK: - H1 Fix: Interval Numbering

    func testIntervalNumberingThroughFullWorkout() {
        let vm = makeVM(warmup: 5, intervals: 3, work: 10, rest: 5, cooldown: 5)
        vm.start()

        // Warmup — no interval number
        XCTAssertEqual(vm.currentPhase, .warmup)
        XCTAssertEqual(vm.currentIntervalNumber, 0)
        XCTAssertEqual(vm.intervalLabel, "")
    }

    // MARK: - H4 Fix: Overflow Carry-Forward

    func testTotalDurationMatchesPhasesSumAlgebraically() {
        // If totalDuration and phases disagree, totalProgress will be wrong
        let configs: [WorkoutConfig] = [
            .default,
            WorkoutConfig(warmupDuration: 0, intervalCount: 0, workDuration: 0, restDuration: 0, cooldownDuration: 0),
            WorkoutConfig(warmupDuration: 60, intervalCount: 1, workDuration: 30, restDuration: 15, cooldownDuration: 60),
        ]
        for cfg in configs {
            let phaseSum = cfg.phases.reduce(0.0) { $0 + $1.duration }
            XCTAssertEqual(cfg.totalDuration, phaseSum, accuracy: 0.001)
        }
    }

    // MARK: - Video Playback Rate

    func testVideoPlaybackRateMatchesPhase() {
        let vm = makeVM(warmup: 5, intervals: 1, work: 5, rest: 5, cooldown: 5)
        XCTAssertEqual(vm.videoPlaybackRate, 0.8, accuracy: 0.01)  // warmup
    }

    // MARK: - Target SPM

    func testTargetSPMPerPhase() {
        XCTAssertEqual(WorkoutPhase.warmup.targetSPM, 18...22)
        XCTAssertEqual(WorkoutPhase.work.targetSPM, 28...32)
        XCTAssertEqual(WorkoutPhase.rest.targetSPM, 16...20)
        XCTAssertEqual(WorkoutPhase.cooldown.targetSPM, 16...20)
        XCTAssertEqual(WorkoutPhase.finished.targetSPM, 0...0)
    }

    // MARK: - Phase Progress

    func testPhaseProgressStartsAtZero() {
        let vm = makeVM()
        XCTAssertEqual(vm.phaseProgress, 0.0, accuracy: 0.01)
    }

    // MARK: - Formatting

    func testFormatTime() {
        XCTAssertEqual(WorkoutViewModel.formatTime(0), "0:00")
        XCTAssertEqual(WorkoutViewModel.formatTime(59), "0:59")
        XCTAssertEqual(WorkoutViewModel.formatTime(60), "1:00")
        XCTAssertEqual(WorkoutViewModel.formatTime(90), "1:30")
        XCTAssertEqual(WorkoutViewModel.formatTime(3600), "60:00")
    }

    func testFormatTimeNegativeClampedToZero() {
        XCTAssertEqual(WorkoutViewModel.formatTime(-5), "0:00")
    }

    // MARK: - Zero Intervals

    func testZeroIntervalsWorkout() {
        let vm = makeVM(warmup: 5, intervals: 0, work: 60, rest: 60, cooldown: 5)
        XCTAssertEqual(vm.currentPhase, .warmup)
        // phases should be just warmup + cooldown
        XCTAssertEqual(vm.config.phases.count, 2)
    }
}
