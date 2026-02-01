import SwiftUI

/// Translucent heads-up display overlaid on the video during a workout.
struct WorkoutHUDView: View {
    @ObservedObject var viewModel: WorkoutViewModel

    var body: some View {
        VStack(spacing: 0) {
            Spacer()

            VStack(spacing: 12) {
                // Phase badge
                phaseBadge

                // Phase timer (large)
                Text(viewModel.formattedPhaseTime)
                    .font(.system(size: 72, weight: .bold, design: .monospaced))
                    .foregroundColor(.white)

                // Phase progress bar
                phaseProgressBar

                // Stats grid
                statsGrid

                // Total time
                HStack {
                    Text("Total")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.7))
                    Text(viewModel.formattedTotalTime)
                        .font(.system(size: 18, weight: .medium, design: .monospaced))
                        .foregroundColor(.white)
                    Text("/ \(viewModel.formattedTotalDuration)")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.5))
                }
            }
            .padding(20)
            .background(
                RoundedRectangle(cornerRadius: 20)
                    .fill(.ultraThinMaterial)
                    .environment(\.colorScheme, .dark)
            )
            .padding(.horizontal, 16)
            .padding(.bottom, 20)
        }
    }

    // MARK: - Subviews

    private var phaseBadge: some View {
        HStack(spacing: 8) {
            Circle()
                .fill(phaseColor)
                .frame(width: 10, height: 10)

            Text(viewModel.currentPhase.displayName)
                .font(.system(size: 16, weight: .bold))
                .foregroundColor(.white)

            if !viewModel.intervalLabel.isEmpty {
                Text("(\(viewModel.intervalLabel))")
                    .font(.system(size: 14, weight: .medium))
                    .foregroundColor(.white.opacity(0.8))
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(
            Capsule()
                .fill(phaseColor.opacity(0.3))
        )
    }

    private var phaseProgressBar: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: 4)
                    .fill(Color.white.opacity(0.2))
                    .frame(height: 6)

                RoundedRectangle(cornerRadius: 4)
                    .fill(phaseColor)
                    .frame(width: geo.size.width * viewModel.phaseProgress, height: 6)
                    .animation(.linear(duration: 0.1), value: viewModel.phaseProgress)
            }
        }
        .frame(height: 6)
    }

    private var statsGrid: some View {
        HStack(spacing: 20) {
            statItem(
                label: "Target SPM",
                value: "\(viewModel.targetSPM.lowerBound)-\(viewModel.targetSPM.upperBound)"
            )

            if !viewModel.intervalLabel.isEmpty {
                statItem(
                    label: "Interval",
                    value: viewModel.intervalLabel
                )
            }

            statItem(
                label: "Speed",
                value: String(format: "%.1fx", viewModel.videoPlaybackRate)
            )
        }
    }

    private func statItem(label: String, value: String) -> some View {
        VStack(spacing: 2) {
            Text(label)
                .font(.system(size: 10, weight: .medium))
                .foregroundColor(.white.opacity(0.6))
            Text(value)
                .font(.system(size: 16, weight: .semibold, design: .monospaced))
                .foregroundColor(.white)
        }
    }

    private var phaseColor: Color {
        switch viewModel.currentPhase {
        case .warmup:   return .orange
        case .work:     return .red
        case .rest:     return .green
        case .cooldown: return .blue
        case .finished: return .gray
        }
    }
}
