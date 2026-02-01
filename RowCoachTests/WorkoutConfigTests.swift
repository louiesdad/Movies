import XCTest
@testable import RowCoach

final class WorkoutConfigTests: XCTestCase {

    func testDefaultConfig() {
        let c = WorkoutConfig.default
        XCTAssertEqual(c.warmupDuration, 300)
        XCTAssertEqual(c.intervalCount, 8)
        XCTAssertEqual(c.workDuration, 60)
        XCTAssertEqual(c.restDuration, 60)
        XCTAssertEqual(c.cooldownDuration, 300)
    }

    func testTotalDurationDefault() {
        // 300 + 8*60 + 7*60 + 300 = 1500
        let c = WorkoutConfig.default
        XCTAssertEqual(c.totalDuration, 1500)
    }

    func testTotalDurationMatchesPhasesSum() {
        let configs: [WorkoutConfig] = [
            .default,
            WorkoutConfig(warmupDuration: 60, intervalCount: 1, workDuration: 30, restDuration: 30, cooldownDuration: 60),
            WorkoutConfig(warmupDuration: 120, intervalCount: 3, workDuration: 45, restDuration: 30, cooldownDuration: 90),
            WorkoutConfig(warmupDuration: 0, intervalCount: 5, workDuration: 120, restDuration: 60, cooldownDuration: 0),
            WorkoutConfig(warmupDuration: 600, intervalCount: 12, workDuration: 30, restDuration: 15, cooldownDuration: 300),
        ]
        for cfg in configs {
            let phaseSum = cfg.phases.reduce(0.0) { $0 + $1.duration }
            XCTAssertEqual(cfg.totalDuration, phaseSum, accuracy: 0.001,
                "Mismatch for intervals=\(cfg.intervalCount)")
        }
    }

    // MARK: - H2 Fix

    func testZeroIntervals() {
        let c = WorkoutConfig(warmupDuration: 300, intervalCount: 0, workDuration: 60, restDuration: 60, cooldownDuration: 300)
        XCTAssertEqual(c.totalDuration, 600, "0 intervals should be warmup + cooldown only")

        let phases = c.phases
        XCTAssertEqual(phases.count, 2)
        XCTAssertEqual(phases[0].phase, .warmup)
        XCTAssertEqual(phases[1].phase, .cooldown)
    }

    func testOneIntervalNoRest() {
        let c = WorkoutConfig(warmupDuration: 60, intervalCount: 1, workDuration: 30, restDuration: 30, cooldownDuration: 60)
        XCTAssertEqual(c.totalDuration, 150)  // 60 + 30 + 0 + 60

        let phases = c.phases
        XCTAssertEqual(phases.count, 3)
        XCTAssertEqual(phases[0].phase, .warmup)
        XCTAssertEqual(phases[1].phase, .work)
        XCTAssertEqual(phases[2].phase, .cooldown)
    }

    func testPhasesAlternateCorrectly() {
        let c = WorkoutConfig(warmupDuration: 60, intervalCount: 4, workDuration: 30, restDuration: 20, cooldownDuration: 60)
        let phaseTypes = c.phases.map(\.phase)
        let expected: [WorkoutPhase] = [
            .warmup,
            .work, .rest, .work, .rest, .work, .rest, .work,
            .cooldown
        ]
        XCTAssertEqual(phaseTypes, expected)
    }

    func testLastWorkNotFollowedByRest() {
        let c = WorkoutConfig.default
        let phases = c.phases
        // Second to last should be .work (the 8th work interval)
        XCTAssertEqual(phases[phases.count - 2].phase, .work)
        XCTAssertEqual(phases.last?.phase, .cooldown)
    }
}
