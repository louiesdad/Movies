import SwiftUI

struct WorkoutConfigView: View {
    @Binding var config: WorkoutConfig

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Workout")
                .font(.headline)

            VStack(spacing: 12) {
                durationRow(label: "Warm Up", value: $config.warmupDuration, range: 60...900, step: 30)
                Divider()
                intervalCountRow
                Divider()
                durationRow(label: "Work", value: $config.workDuration, range: 15...600, step: 15)
                Divider()
                durationRow(label: "Rest", value: $config.restDuration, range: 15...600, step: 15)
                Divider()
                durationRow(label: "Cool Down", value: $config.cooldownDuration, range: 60...900, step: 30)
                Divider()
                totalRow
            }
            .padding()
            .background(Color(.secondarySystemGroupedBackground))
            .cornerRadius(12)
        }
    }

    // MARK: - Rows

    private func durationRow(label: String, value: Binding<TimeInterval>, range: ClosedRange<TimeInterval>, step: TimeInterval) -> some View {
        HStack {
            Text(label)
                .foregroundColor(.primary)

            Spacer()

            HStack(spacing: 12) {
                Button {
                    let newVal = value.wrappedValue - step
                    if newVal >= range.lowerBound {
                        value.wrappedValue = newVal
                    }
                } label: {
                    Image(systemName: "minus.circle.fill")
                        .font(.title3)
                        .foregroundColor(.blue)
                }
                .buttonStyle(.plain)

                Text(formatDuration(value.wrappedValue))
                    .font(.system(.body, design: .monospaced))
                    .frame(minWidth: 50, alignment: .center)

                Button {
                    let newVal = value.wrappedValue + step
                    if newVal <= range.upperBound {
                        value.wrappedValue = newVal
                    }
                } label: {
                    Image(systemName: "plus.circle.fill")
                        .font(.title3)
                        .foregroundColor(.blue)
                }
                .buttonStyle(.plain)
            }
        }
    }

    private var intervalCountRow: some View {
        HStack {
            Text("Intervals")
                .foregroundColor(.primary)

            Spacer()

            HStack(spacing: 12) {
                Button {
                    if config.intervalCount > 1 {
                        config.intervalCount -= 1
                    }
                } label: {
                    Image(systemName: "minus.circle.fill")
                        .font(.title3)
                        .foregroundColor(.blue)
                }
                .buttonStyle(.plain)

                Text("\(config.intervalCount)")
                    .font(.system(.body, design: .monospaced))
                    .frame(minWidth: 50, alignment: .center)

                Button {
                    if config.intervalCount < 30 {
                        config.intervalCount += 1
                    }
                } label: {
                    Image(systemName: "plus.circle.fill")
                        .font(.title3)
                        .foregroundColor(.blue)
                }
                .buttonStyle(.plain)
            }
        }
    }

    private var totalRow: some View {
        HStack {
            Text("Total Duration")
                .fontWeight(.medium)
            Spacer()
            Text(formatDuration(config.totalDuration))
                .font(.system(.body, design: .monospaced))
                .fontWeight(.medium)
                .foregroundColor(.blue)
        }
    }

    // MARK: - Helpers

    private func formatDuration(_ seconds: TimeInterval) -> String {
        let totalSecs = Int(seconds)
        let mins = totalSecs / 60
        let secs = totalSecs % 60
        if secs == 0 {
            return "\(mins) min"
        }
        return "\(mins):\(String(format: "%02d", secs))"
    }
}
