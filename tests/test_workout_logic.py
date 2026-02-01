#!/usr/bin/env python3
"""
End-to-end logic tests for RowCoach workout engine.

These tests reimplement the Swift model/viewmodel logic in Python to validate
correctness of all the bug fixes (C1-C3, H1-H4, M1-M8) without needing Xcode.

Run: python3 tests/test_workout_logic.py
"""

import unittest
import math


# ============================================================================
# Reimplemented Swift models in Python (mirrors the actual Swift code)
# ============================================================================

class WorkoutPhase:
    WARMUP = "warmup"
    WORK = "work"
    REST = "rest"
    COOLDOWN = "cooldown"
    FINISHED = "finished"

    TARGET_SPM = {
        "warmup": (18, 22),
        "work": (28, 32),
        "rest": (16, 20),
        "cooldown": (16, 20),
        "finished": (0, 0),
    }

    VIDEO_RATE = {
        "warmup": 0.8,
        "work": 1.2,
        "rest": 0.6,
        "cooldown": 0.7,
        "finished": 0.0,
    }

    DISPLAY_NAME = {
        "warmup": "WARM UP",
        "work": "WORK",
        "rest": "REST",
        "cooldown": "COOL DOWN",
        "finished": "FINISHED",
    }


class WorkoutConfig:
    def __init__(self, warmup=300, intervals=8, work=60, rest=60, cooldown=300):
        self.warmup_duration = warmup
        self.interval_count = intervals
        self.work_duration = work
        self.rest_duration = rest
        self.cooldown_duration = cooldown

    @property
    def total_duration(self):
        """Mirrors WorkoutConfig.totalDuration (FIXED version with H2 guard)"""
        if self.interval_count <= 0:
            return self.warmup_duration + self.cooldown_duration
        return (
            self.warmup_duration
            + self.interval_count * self.work_duration
            + (self.interval_count - 1) * self.rest_duration
            + self.cooldown_duration
        )

    @property
    def phases(self):
        """Mirrors WorkoutConfig.phases"""
        result = []
        result.append((WorkoutPhase.WARMUP, self.warmup_duration))
        for i in range(self.interval_count):
            result.append((WorkoutPhase.WORK, self.work_duration))
            if i < self.interval_count - 1:
                result.append((WorkoutPhase.REST, self.rest_duration))
        result.append((WorkoutPhase.COOLDOWN, self.cooldown_duration))
        return result


class WorkoutViewModel:
    """Mirrors WorkoutViewModel.swift with all fixes applied."""

    def __init__(self, config: WorkoutConfig):
        self.config = config
        self.phases = config.phases
        self.current_phase_index = 0
        self.current_phase = WorkoutPhase.WARMUP
        self.phase_time_remaining = 0.0
        self.total_elapsed_time = 0.0
        self.current_interval_number = 0
        self.is_running = False
        self.is_paused = False
        self.is_finished = False
        self._prepare_first_phase()

    def _prepare_first_phase(self):
        if self.phases:
            phase, duration = self.phases[0]
            self.current_phase = phase
            self.phase_time_remaining = duration
            self._update_interval_number()

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.is_paused = False
        self.is_finished = False

    def pause(self):
        self.is_paused = True
        self.is_running = False

    def resume(self):
        self.is_paused = False
        self.is_running = True

    def stop(self):
        self.is_running = False
        self.is_paused = False
        self.is_finished = True

    def tick(self, elapsed: float):
        """Simulate a timer tick with given elapsed time."""
        if not self.is_running or self.is_paused:
            return
        self.total_elapsed_time += elapsed
        self.phase_time_remaining -= elapsed
        if self.phase_time_remaining <= 0:
            self._advance_phase()

    def _advance_phase(self):
        # H4 fix: carry overflow forward
        overflow = -self.phase_time_remaining

        self.current_phase_index += 1
        if self.current_phase_index >= len(self.phases):
            self.current_phase = WorkoutPhase.FINISHED
            self.phase_time_remaining = 0
            self.stop()
            return

        phase, duration = self.phases[self.current_phase_index]
        self.current_phase = phase
        self.phase_time_remaining = duration - overflow
        self._update_interval_number()

    def _update_interval_number(self):
        # H1 fix: simple count, no dead ternary
        work_count = 0
        for i in range(self.current_phase_index + 1):
            if self.phases[i][0] == WorkoutPhase.WORK:
                work_count += 1
        self.current_interval_number = work_count

    @property
    def video_playback_rate(self):
        return WorkoutPhase.VIDEO_RATE[self.current_phase]

    @property
    def target_spm(self):
        return WorkoutPhase.TARGET_SPM[self.current_phase]

    @property
    def phase_progress(self):
        if self.current_phase_index >= len(self.phases):
            return 0
        _, duration = self.phases[self.current_phase_index]
        if duration <= 0:
            return 0
        return 1.0 - (self.phase_time_remaining / duration)

    @property
    def total_progress(self):
        td = self.config.total_duration
        if td <= 0:
            return 0
        return self.total_elapsed_time / td

    @property
    def interval_label(self):
        if self.current_phase not in (WorkoutPhase.WORK, WorkoutPhase.REST):
            return ""
        return f"{self.current_interval_number} of {self.config.interval_count}"


class PlayerUIView:
    """Mirrors PlayerUIView with C3 rate guard fix."""

    def __init__(self):
        self.current_rate = 0.0
        self.actual_rate = 0.0
        self.is_playing = False
        self.rate_set_count = 0  # Track how many times rate was actually set

    def play(self, rate: float):
        if not self.is_playing:
            self.is_playing = True
        # C3 fix: only set rate when it actually changes
        if abs(self.current_rate - rate) > 0.001:
            self.actual_rate = rate
            self.current_rate = rate
            self.rate_set_count += 1

    def pause(self):
        self.is_playing = False
        self.current_rate = 0


# ============================================================================
# Tests
# ============================================================================


class TestWorkoutPhase(unittest.TestCase):
    """Test WorkoutPhase enum properties."""

    def test_display_names(self):
        self.assertEqual(WorkoutPhase.DISPLAY_NAME["warmup"], "WARM UP")
        self.assertEqual(WorkoutPhase.DISPLAY_NAME["work"], "WORK")
        self.assertEqual(WorkoutPhase.DISPLAY_NAME["rest"], "REST")
        self.assertEqual(WorkoutPhase.DISPLAY_NAME["cooldown"], "COOL DOWN")
        self.assertEqual(WorkoutPhase.DISPLAY_NAME["finished"], "FINISHED")

    def test_target_spm_ranges(self):
        self.assertEqual(WorkoutPhase.TARGET_SPM["warmup"], (18, 22))
        self.assertEqual(WorkoutPhase.TARGET_SPM["work"], (28, 32))
        self.assertEqual(WorkoutPhase.TARGET_SPM["rest"], (16, 20))
        self.assertEqual(WorkoutPhase.TARGET_SPM["cooldown"], (16, 20))
        self.assertEqual(WorkoutPhase.TARGET_SPM["finished"], (0, 0))

    def test_video_playback_rates(self):
        self.assertAlmostEqual(WorkoutPhase.VIDEO_RATE["warmup"], 0.8)
        self.assertAlmostEqual(WorkoutPhase.VIDEO_RATE["work"], 1.2)
        self.assertAlmostEqual(WorkoutPhase.VIDEO_RATE["rest"], 0.6)
        self.assertAlmostEqual(WorkoutPhase.VIDEO_RATE["cooldown"], 0.7)
        self.assertAlmostEqual(WorkoutPhase.VIDEO_RATE["finished"], 0.0)

    def test_no_case_iterable(self):
        """M8: finished is a state, not a phase — ensure we don't treat it as iteratable."""
        active_phases = ["warmup", "work", "rest", "cooldown"]
        for phase in active_phases:
            self.assertIn(phase, WorkoutPhase.VIDEO_RATE)
            self.assertGreater(WorkoutPhase.VIDEO_RATE[phase], 0)
        # finished should have zero rate
        self.assertEqual(WorkoutPhase.VIDEO_RATE["finished"], 0.0)


class TestWorkoutConfig(unittest.TestCase):
    """Test WorkoutConfig including H2 fix."""

    def test_default_config(self):
        c = WorkoutConfig()
        self.assertEqual(c.warmup_duration, 300)
        self.assertEqual(c.interval_count, 8)
        self.assertEqual(c.work_duration, 60)
        self.assertEqual(c.rest_duration, 60)
        self.assertEqual(c.cooldown_duration, 300)

    def test_total_duration_default(self):
        """8 intervals: 300 + 8*60 + 7*60 + 300 = 1500"""
        c = WorkoutConfig()
        self.assertEqual(c.total_duration, 300 + 8 * 60 + 7 * 60 + 300)
        self.assertEqual(c.total_duration, 1500)

    def test_total_duration_matches_phases_sum(self):
        """totalDuration must always equal sum of all phase durations."""
        configs = [
            WorkoutConfig(),
            WorkoutConfig(warmup=60, intervals=1, work=30, rest=30, cooldown=60),
            WorkoutConfig(warmup=120, intervals=3, work=45, rest=30, cooldown=90),
            WorkoutConfig(warmup=0, intervals=5, work=120, rest=60, cooldown=0),
            WorkoutConfig(warmup=600, intervals=12, work=30, rest=15, cooldown=300),
        ]
        for cfg in configs:
            phase_sum = sum(d for _, d in cfg.phases)
            self.assertEqual(
                cfg.total_duration,
                phase_sum,
                f"Mismatch for config intervals={cfg.interval_count}: "
                f"totalDuration={cfg.total_duration} != phases_sum={phase_sum}",
            )

    def test_h2_zero_intervals(self):
        """H2 FIX: 0 intervals should be warmup + cooldown only, not negative."""
        c = WorkoutConfig(warmup=300, intervals=0, work=60, rest=60, cooldown=300)
        self.assertEqual(c.total_duration, 600)
        phases = c.phases
        # Should be just warmup + cooldown
        self.assertEqual(len(phases), 2)
        self.assertEqual(phases[0], (WorkoutPhase.WARMUP, 300))
        self.assertEqual(phases[1], (WorkoutPhase.COOLDOWN, 300))

    def test_h2_one_interval_no_rest(self):
        """With 1 interval, there should be no rest period."""
        c = WorkoutConfig(warmup=60, intervals=1, work=30, rest=30, cooldown=60)
        # 60 + 30 + 0 rest + 60 = 150
        self.assertEqual(c.total_duration, 150)
        phases = c.phases
        self.assertEqual(len(phases), 3)  # warmup, work, cooldown
        self.assertEqual(phases[0][0], WorkoutPhase.WARMUP)
        self.assertEqual(phases[1][0], WorkoutPhase.WORK)
        self.assertEqual(phases[2][0], WorkoutPhase.COOLDOWN)

    def test_phases_structure_default(self):
        """Default 8 intervals: warmup, [work, rest]*7, work, cooldown = 17 phases."""
        c = WorkoutConfig()
        phases = c.phases
        # warmup + 8 work + 7 rest + cooldown = 17
        self.assertEqual(len(phases), 17)
        self.assertEqual(phases[0][0], WorkoutPhase.WARMUP)
        self.assertEqual(phases[-1][0], WorkoutPhase.COOLDOWN)
        # Last work interval should NOT be followed by rest
        self.assertEqual(phases[-2][0], WorkoutPhase.WORK)

    def test_phases_alternating_pattern(self):
        """Work and rest should alternate correctly."""
        c = WorkoutConfig(warmup=60, intervals=4, work=30, rest=20, cooldown=60)
        phases = c.phases
        # warmup, work, rest, work, rest, work, rest, work, cooldown = 9
        expected = [
            WorkoutPhase.WARMUP,
            WorkoutPhase.WORK, WorkoutPhase.REST,
            WorkoutPhase.WORK, WorkoutPhase.REST,
            WorkoutPhase.WORK, WorkoutPhase.REST,
            WorkoutPhase.WORK,
            WorkoutPhase.COOLDOWN,
        ]
        actual = [p for p, _ in phases]
        self.assertEqual(actual, expected)


class TestWorkoutViewModel(unittest.TestCase):
    """Test WorkoutViewModel including H1 and H4 fixes."""

    def _make_vm(self, **kwargs):
        return WorkoutViewModel(WorkoutConfig(**kwargs))

    def test_initial_state(self):
        vm = self._make_vm()
        self.assertEqual(vm.current_phase, WorkoutPhase.WARMUP)
        self.assertEqual(vm.phase_time_remaining, 300)
        self.assertEqual(vm.total_elapsed_time, 0)
        self.assertEqual(vm.current_interval_number, 0)
        self.assertFalse(vm.is_running)
        self.assertFalse(vm.is_finished)

    def test_start_stop(self):
        vm = self._make_vm()
        vm.start()
        self.assertTrue(vm.is_running)
        self.assertFalse(vm.is_paused)
        vm.stop()
        self.assertFalse(vm.is_running)
        self.assertTrue(vm.is_finished)

    def test_pause_resume(self):
        vm = self._make_vm()
        vm.start()
        vm.pause()
        self.assertFalse(vm.is_running)
        self.assertTrue(vm.is_paused)
        vm.resume()
        self.assertTrue(vm.is_running)
        self.assertFalse(vm.is_paused)

    def test_tick_advances_time(self):
        vm = self._make_vm(warmup=10, intervals=1, work=10, rest=5, cooldown=10)
        vm.start()
        vm.tick(1.0)
        self.assertAlmostEqual(vm.total_elapsed_time, 1.0)
        self.assertAlmostEqual(vm.phase_time_remaining, 9.0)

    def test_tick_while_paused_does_nothing(self):
        vm = self._make_vm()
        vm.start()
        vm.pause()
        vm.tick(5.0)
        self.assertAlmostEqual(vm.total_elapsed_time, 0.0)

    def test_phase_transition_warmup_to_work(self):
        vm = self._make_vm(warmup=10, intervals=2, work=20, rest=10, cooldown=10)
        vm.start()
        # Tick past warmup
        vm.tick(10.0)
        self.assertEqual(vm.current_phase, WorkoutPhase.WORK)
        self.assertEqual(vm.current_interval_number, 1)

    def test_h1_interval_numbering_through_full_workout(self):
        """H1 FIX: Verify interval numbering is correct through work/rest phases."""
        vm = self._make_vm(warmup=5, intervals=3, work=10, rest=5, cooldown=5)
        vm.start()

        # Warmup
        self.assertEqual(vm.current_phase, WorkoutPhase.WARMUP)
        self.assertEqual(vm.current_interval_number, 0)
        self.assertEqual(vm.interval_label, "")

        # Advance past warmup
        vm.tick(5.0)
        self.assertEqual(vm.current_phase, WorkoutPhase.WORK)
        self.assertEqual(vm.current_interval_number, 1)
        self.assertEqual(vm.interval_label, "1 of 3")

        # Advance past work 1
        vm.tick(10.0)
        self.assertEqual(vm.current_phase, WorkoutPhase.REST)
        self.assertEqual(vm.current_interval_number, 1)
        self.assertEqual(vm.interval_label, "1 of 3")

        # Advance past rest 1
        vm.tick(5.0)
        self.assertEqual(vm.current_phase, WorkoutPhase.WORK)
        self.assertEqual(vm.current_interval_number, 2)
        self.assertEqual(vm.interval_label, "2 of 3")

        # Advance past work 2
        vm.tick(10.0)
        self.assertEqual(vm.current_phase, WorkoutPhase.REST)
        self.assertEqual(vm.current_interval_number, 2)
        self.assertEqual(vm.interval_label, "2 of 3")

        # Advance past rest 2
        vm.tick(5.0)
        self.assertEqual(vm.current_phase, WorkoutPhase.WORK)
        self.assertEqual(vm.current_interval_number, 3)
        self.assertEqual(vm.interval_label, "3 of 3")

        # Advance past work 3 (last — no rest after)
        vm.tick(10.0)
        self.assertEqual(vm.current_phase, WorkoutPhase.COOLDOWN)
        self.assertEqual(vm.interval_label, "")

        # Advance past cooldown
        vm.tick(5.0)
        self.assertEqual(vm.current_phase, WorkoutPhase.FINISHED)
        self.assertTrue(vm.is_finished)

    def test_h4_overflow_carried_forward(self):
        """H4 FIX: Timer overshoot should be carried to the next phase."""
        vm = self._make_vm(warmup=10, intervals=1, work=10, rest=5, cooldown=10)
        vm.start()

        # Tick 10.05s — overshoot warmup by 0.05s
        vm.tick(10.05)
        self.assertEqual(vm.current_phase, WorkoutPhase.WORK)
        # Work should start at 10.0 - 0.05 = 9.95
        self.assertAlmostEqual(vm.phase_time_remaining, 9.95, places=2)

    def test_h4_cumulative_drift_minimal(self):
        """H4 FIX: Over many phase transitions, total elapsed should match total duration."""
        vm = self._make_vm(warmup=5, intervals=8, work=10, rest=5, cooldown=5)
        vm.start()

        # Simulate with 0.1s ticks (like the real app timer)
        tick_count = 0
        max_ticks = 2000  # safety limit
        while not vm.is_finished and tick_count < max_ticks:
            vm.tick(0.1)
            tick_count += 1

        self.assertTrue(vm.is_finished)
        # Total elapsed should be very close to total duration
        expected = vm.config.total_duration
        drift = abs(vm.total_elapsed_time - expected)
        self.assertLess(drift, 0.2, f"Timer drift {drift:.4f}s exceeds 0.2s threshold")

    def test_video_playback_rate_per_phase(self):
        """Video speed should change with each phase."""
        vm = self._make_vm(warmup=5, intervals=1, work=5, rest=5, cooldown=5)
        vm.start()

        self.assertAlmostEqual(vm.video_playback_rate, 0.8)  # warmup

        vm.tick(5.0)
        self.assertAlmostEqual(vm.video_playback_rate, 1.2)  # work

        # Single interval: no rest after last work, goes to cooldown
        vm.tick(5.0)
        self.assertAlmostEqual(vm.video_playback_rate, 0.7)  # cooldown

    def test_phase_progress(self):
        vm = self._make_vm(warmup=10, intervals=1, work=10, rest=5, cooldown=10)
        vm.start()

        self.assertAlmostEqual(vm.phase_progress, 0.0)
        vm.tick(5.0)
        self.assertAlmostEqual(vm.phase_progress, 0.5)
        vm.tick(5.0)
        # Phase transition happened, progress resets for new phase
        self.assertAlmostEqual(vm.phase_progress, 0.0, places=1)

    def test_total_progress(self):
        vm = self._make_vm(warmup=10, intervals=1, work=10, rest=5, cooldown=10)
        vm.start()
        total = vm.config.total_duration  # 30
        vm.tick(15.0)
        self.assertAlmostEqual(vm.total_progress, 15.0 / total, places=2)

    def test_workout_completes(self):
        """Full workout should eventually reach FINISHED using realistic ticks."""
        vm = self._make_vm(warmup=2, intervals=2, work=3, rest=1, cooldown=2)
        vm.start()

        # Total: 2 + 3 + 1 + 3 + 2 = 11s, simulate with 0.1s ticks
        tick_count = 0
        while not vm.is_finished and tick_count < 200:
            vm.tick(0.1)
            tick_count += 1

        self.assertEqual(vm.current_phase, WorkoutPhase.FINISHED)
        self.assertTrue(vm.is_finished)
        self.assertFalse(vm.is_running)

    def test_zero_intervals_workout(self):
        """H2 edge case: 0 intervals should just be warmup + cooldown."""
        vm = self._make_vm(warmup=5, intervals=0, work=60, rest=60, cooldown=5)
        vm.start()

        self.assertEqual(vm.current_phase, WorkoutPhase.WARMUP)
        vm.tick(5.0)
        self.assertEqual(vm.current_phase, WorkoutPhase.COOLDOWN)
        vm.tick(5.0)
        self.assertEqual(vm.current_phase, WorkoutPhase.FINISHED)
        self.assertTrue(vm.is_finished)


class TestPlayerRateGuard(unittest.TestCase):
    """Test C3 fix: rate should only be set when it actually changes."""

    def test_c3_rate_not_set_repeatedly(self):
        """Calling play() with the same rate 100 times should only set rate once."""
        player = PlayerUIView()
        for _ in range(100):
            player.play(rate=1.2)
        self.assertEqual(player.rate_set_count, 1)
        self.assertAlmostEqual(player.actual_rate, 1.2)

    def test_c3_rate_set_on_change(self):
        """Rate should be set when it actually changes."""
        player = PlayerUIView()
        player.play(rate=0.8)
        self.assertEqual(player.rate_set_count, 1)

        player.play(rate=1.2)
        self.assertEqual(player.rate_set_count, 2)

        player.play(rate=0.6)
        self.assertEqual(player.rate_set_count, 3)

    def test_c3_rate_reset_after_pause(self):
        """After pause, rate should be re-applied on next play (currentRate reset to 0)."""
        player = PlayerUIView()
        player.play(rate=1.2)
        self.assertEqual(player.rate_set_count, 1)

        player.pause()
        player.play(rate=1.2)
        # Should set rate again because pause reset currentRate to 0
        self.assertEqual(player.rate_set_count, 2)

    def test_c3_tiny_rate_difference_ignored(self):
        """Differences below 0.001 threshold should not trigger a rate set."""
        player = PlayerUIView()
        player.play(rate=1.2)
        self.assertEqual(player.rate_set_count, 1)

        player.play(rate=1.2005)  # diff = 0.0005 < 0.001
        self.assertEqual(player.rate_set_count, 1)  # should NOT re-set


class TestZStackLayerOrder(unittest.TestCase):
    """
    C1 FIX: Verify the conceptual layer ordering in WorkoutPlayerView.
    In SwiftUI ZStack, last child is on top. Controls must be above tap-catcher.
    We verify by parsing the actual Swift source file.
    """

    def test_c1_controls_above_tap_catcher(self):
        """Parse WorkoutPlayerView.swift and verify layer ordering."""
        import os
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "RowCoach", "Views", "WorkoutPlayerView.swift"
        )
        with open(filepath) as f:
            content = f.read()

        # Find positions of key layer markers
        tap_catcher_pos = content.find("// Layer 5: Tap-to-toggle")
        controls_pos = content.find("// Layer 6: Controls overlay")
        finished_pos = content.find("// Layer 7: Finished overlay")

        self.assertGreater(tap_catcher_pos, 0, "Tap-catcher layer comment not found")
        self.assertGreater(controls_pos, 0, "Controls layer comment not found")
        self.assertGreater(finished_pos, 0, "Finished layer comment not found")

        # Controls must appear AFTER tap-catcher (higher in ZStack = on top)
        self.assertGreater(
            controls_pos, tap_catcher_pos,
            "Controls must be above tap-catcher in ZStack"
        )
        # Finished must be topmost
        self.assertGreater(
            finished_pos, controls_pos,
            "Finished overlay must be above controls"
        )

    def test_c1_video_not_hit_testable(self):
        """VideoPlayerView should have allowsHitTesting(false)."""
        import os
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "RowCoach", "Views", "WorkoutPlayerView.swift"
        )
        with open(filepath) as f:
            content = f.read()

        # Video player should not intercept taps
        video_section = content[content.find("VideoPlayerView("):content.find("// Layer 3")]
        self.assertIn(".allowsHitTesting(false)", video_section)


class TestVideoPlayerSourceFixes(unittest.TestCase):
    """Verify C2/C3/H3/M1/M2 fixes by parsing VideoPlayerView.swift source."""

    def setUp(self):
        import os
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "RowCoach", "Components", "VideoPlayerView.swift"
        )
        with open(filepath) as f:
            self.content = f.read()

    def test_c2_uses_avplayerlooper(self):
        """Should use AVPlayerLooper, not NotificationCenter-based looping."""
        self.assertIn("AVPlayerLooper", self.content)
        self.assertNotIn("AVPlayerItemDidPlayToEndTime", self.content)
        self.assertNotIn("NotificationCenter", self.content)

    def test_c2_uses_avqueueplayer(self):
        """Should use AVQueuePlayer (required by AVPlayerLooper)."""
        self.assertIn("AVQueuePlayer", self.content)

    def test_c3_rate_guard_exists(self):
        """Should compare currentRate before setting player.rate."""
        self.assertIn("abs(currentRate - rate)", self.content)

    def test_h3_status_binding(self):
        """Should have a status binding for loading/error states."""
        self.assertIn("@Binding var status: VideoPlayerStatus", self.content)
        self.assertIn("enum VideoPlayerStatus", self.content)
        self.assertIn(".loading", self.content)
        self.assertIn(".ready", self.content)
        self.assertIn(".error", self.content)

    def test_h3_kvo_observation(self):
        """Should observe AVPlayerItem.status via KVO."""
        self.assertIn("observe(playerItem:", self.content)
        self.assertIn(".status", self.content)
        self.assertIn("NSKeyValueObservation", self.content)

    def test_m1_no_unused_player_layer(self):
        """M1: Should not have an unused stored playerLayer property."""
        # The class has avPlayerLayer (computed) but should NOT have a stored playerLayer
        lines = self.content.split("\n")
        stored_player_layer = [
            l for l in lines
            if "private var playerLayer: AVPlayerLayer?" in l
        ]
        self.assertEqual(
            len(stored_player_layer), 0,
            "Dead playerLayer property should be removed"
        )

    def test_m2_no_redundant_layout_subviews(self):
        """M2: Should not have redundant layoutSubviews override."""
        self.assertNotIn("layoutSubviews", self.content)

    def test_cleanup_disables_looping(self):
        """Cleanup should disable looping and release resources."""
        self.assertIn("disableLooping()", self.content)
        self.assertIn("removeAllItems()", self.content)


class TestWorkoutPhaseSourceFixes(unittest.TestCase):
    """Verify M3/M8 fixes by parsing WorkoutPhase.swift source."""

    def setUp(self):
        import os
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "RowCoach", "Models", "WorkoutPhase.swift"
        )
        with open(filepath) as f:
            self.content = f.read()

    def test_m3_no_phase_color_name(self):
        """M3: phaseColorName should be removed."""
        self.assertNotIn("phaseColorName", self.content)

    def test_m8_no_case_iterable(self):
        """M8: Should not conform to CaseIterable."""
        self.assertNotIn("CaseIterable", self.content)


class TestInfoPlistFixes(unittest.TestCase):
    """Verify M4 ATS fix."""

    def test_m4_media_specific_ats(self):
        """Should use NSAllowsArbitraryLoadsForMedia, not NSAllowsArbitraryLoads."""
        import os
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "RowCoach", "Info.plist"
        )
        with open(filepath) as f:
            content = f.read()

        self.assertIn("NSAllowsArbitraryLoadsForMedia", content)
        # Should NOT have the overly broad one (unless it's part of the media key name)
        lines = [l.strip() for l in content.split("\n")]
        broad_ats = [l for l in lines if l == "<key>NSAllowsArbitraryLoads</key>"]
        self.assertEqual(len(broad_ats), 0, "Should not use broad NSAllowsArbitraryLoads")


class TestAppIconExists(unittest.TestCase):
    """M5: AppIcon asset catalog should exist."""

    def test_m5_appicon_exists(self):
        import os
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "RowCoach", "Assets.xcassets", "AppIcon.appiconset", "Contents.json"
        )
        self.assertTrue(os.path.exists(filepath), "AppIcon.appiconset/Contents.json missing")

        import json
        with open(filepath) as f:
            data = json.load(f)
        self.assertIn("images", data)
        self.assertIn("info", data)


class TestHomeViewFixes(unittest.TestCase):
    """Verify M7/L6 fixes by parsing HomeView.swift source."""

    def setUp(self):
        import os
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "RowCoach", "Views", "HomeView.swift"
        )
        with open(filepath) as f:
            self.content = f.read()

    def test_m7_fullscreen_cover_item(self):
        """M7: Should use .fullScreenCover(item:) not .fullScreenCover(isPresented:)."""
        self.assertIn(".fullScreenCover(item:", self.content)
        self.assertNotIn("fullScreenCover(isPresented: $showWorkout)", self.content)

    def test_m7_workout_video_state(self):
        """M7: Should have workoutVideo state variable."""
        self.assertIn("@State private var workoutVideo: VideoItem?", self.content)

    def test_l6_uses_subtitle(self):
        """L6: Should use .subtitle not .description on VideoItem."""
        self.assertIn("selectedVideo?.subtitle", self.content)
        self.assertNotIn("selectedVideo?.description", self.content)


class TestVideoItemSubtitle(unittest.TestCase):
    """L6: VideoItem should use subtitle, not description."""

    def setUp(self):
        import os
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "RowCoach", "Models", "VideoItem.swift"
        )
        with open(filepath) as f:
            self.content = f.read()

    def test_l6_no_description_property(self):
        """Should not have a 'description' stored property."""
        lines = self.content.split("\n")
        desc_lines = [l.strip() for l in lines if l.strip().startswith("var description:")]
        self.assertEqual(len(desc_lines), 0, "Should not have 'var description' property")

    def test_l6_has_subtitle_property(self):
        """Should have a 'subtitle' stored property."""
        self.assertIn("var subtitle: String", self.content)


class TestStopConfirmationResume(unittest.TestCase):
    """L4: Stop confirmation cancel should auto-resume if workout was running."""

    def setUp(self):
        import os
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "RowCoach", "Views", "WorkoutPlayerView.swift"
        )
        with open(filepath) as f:
            self.content = f.read()

    def test_l4_tracks_was_running(self):
        """Should track wasRunningBeforeStopDialog state."""
        self.assertIn("wasRunningBeforeStopDialog", self.content)

    def test_l4_resumes_on_cancel(self):
        """Cancel button should resume if workout was running."""
        self.assertIn("wasRunningBeforeStopDialog", self.content)
        self.assertIn("viewModel.resume()", self.content)


class TestAutoHideCancellable(unittest.TestCase):
    """M6: Auto-hide should use cancellable Task, not fire-and-forget dispatch."""

    def setUp(self):
        import os
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "RowCoach", "Views", "WorkoutPlayerView.swift"
        )
        with open(filepath) as f:
            self.content = f.read()

    def test_m6_no_dispatch_async_after(self):
        """Should not use DispatchQueue.main.asyncAfter."""
        self.assertNotIn("DispatchQueue.main.asyncAfter", self.content)

    def test_m6_uses_task(self):
        """Should use Task with cancellation."""
        self.assertIn("autoHideTask", self.content)
        self.assertIn("Task.isCancelled", self.content)
        self.assertIn("autoHideTask?.cancel()", self.content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
