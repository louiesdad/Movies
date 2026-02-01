import Foundation

struct WorkoutConfig: Codable, Equatable {
    var warmupDuration: TimeInterval    // seconds
    var intervalCount: Int
    var workDuration: TimeInterval      // seconds
    var restDuration: TimeInterval      // seconds
    var cooldownDuration: TimeInterval  // seconds

    static let `default` = WorkoutConfig(
        warmupDuration: 300,   // 5 minutes
        intervalCount: 8,
        workDuration: 60,      // 1 minute
        restDuration: 60,      // 1 minute
        cooldownDuration: 300  // 5 minutes
    )

    /// Total workout duration in seconds.
    /// Must match the sum of durations produced by `phases`.
    var totalDuration: TimeInterval {
        guard intervalCount > 0 else {
            return warmupDuration + cooldownDuration
        }
        return warmupDuration
            + Double(intervalCount) * workDuration
            + Double(intervalCount - 1) * restDuration
            + cooldownDuration
    }

    /// Builds the ordered list of phases with their durations
    var phases: [(phase: WorkoutPhase, duration: TimeInterval)] {
        var result: [(WorkoutPhase, TimeInterval)] = []
        result.append((.warmup, warmupDuration))
        for i in 0..<intervalCount {
            result.append((.work, workDuration))
            if i < intervalCount - 1 {
                result.append((.rest, restDuration))
            }
        }
        result.append((.cooldown, cooldownDuration))
        return result
    }

    // MARK: - Persistence

    private static let storageKey = "RowCoach_WorkoutConfig"

    func save() {
        if let data = try? JSONEncoder().encode(self) {
            UserDefaults.standard.set(data, forKey: Self.storageKey)
        }
    }

    static func load() -> WorkoutConfig {
        guard let data = UserDefaults.standard.data(forKey: storageKey),
              let config = try? JSONDecoder().decode(WorkoutConfig.self, from: data)
        else {
            return .default
        }
        return config
    }
}
