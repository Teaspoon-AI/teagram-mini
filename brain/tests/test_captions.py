#
# Unit test: CaptionTap's utterance-scoped caption contract.
#
# The invariant (paid for three times over): every spoken utterance is charted in
# EXACTLY one bubble, in playout order — fillers included — and a barged utterance
# emits NO final (the client commits its in-progress bubble; a late final would
# render as a duplicate after the user's message). Utterances are segmented by
# TTSTextFrame.context_id (one audio context per LLM turn / per filler), NOT by
# LLM-response boundaries, which do not align with playout when tool-call fillers
# and chained turns play as one continuous audio segment.
#
# The USER-HOLD rules exist because the Talk UI commits the active assistant
# bubble at the user's FIRST interim — 1-3 words before the barge machinery
# decides anything. Partials emitted in that window reopen a second bubble with
# near-identical text (the "seen twice" bug, observed live 2026-07-05 with a
# tool card then rendering into the stray bubble).
#
# Run: python test_captions.py   (or via pytest)
#

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipecat.frames.frames import (  # noqa: E402
    BotStoppedSpeakingFrame,
    LLMFullResponseEndFrame,
    TTSTextFrame,
)
from pipecat.processors.frame_processor import FrameDirection  # noqa: E402
from pipecat.utils.text.base_text_aggregator import AggregationType  # noqa: E402

from teagram_brain.captions import CaptionTap, VoiceActivity  # noqa: E402


def W(s, ctx, pts=None):
    f = TTSTextFrame(s, aggregated_by=AggregationType.WORD)
    f.context_id = ctx
    if pts is not None:
        f.pts = pts
    return f


def END(pts):
    f = LLMFullResponseEndFrame()
    f.pts = pts
    return f


class Harness:
    def __init__(self):
        self.activity = VoiceActivity()
        self.tap = CaptionTap(self.activity)
        self.sent = []  # (text, final) transcript messages, in emit order
        sent = self.sent

        async def fake_push(frame, direction=FrameDirection.DOWNSTREAM):
            m = getattr(frame, "message", None)
            if m and m.get("type") == "transcript":
                sent.append((m["text"], m["final"]))
        self.tap.push_frame = fake_push

    async def words(self, text, ctx, pts=None):
        # pipecat 1.5.0 delivers each word as a BARE TTSTextFrame token (no spacing);
        # the caption reducer rejoins them. Feeding bare tokens here is what makes this
        # harness reproduce prod — a trailing space would hide the concatenation bug.
        for w in text.split():
            await self.tap.process_frame(W(w, ctx, pts), FrameDirection.DOWNSTREAM)

    async def feed(self, frame):
        await self.tap.process_frame(frame, FrameDirection.DOWNSTREAM)

    async def barge(self):
        # pipecat delivers interruptions out-of-band via _start_interruption; the
        # override is the real entry point, so drive it directly.
        await self.tap._start_interruption()

    def user_talks(self):
        self.activity.stamp()  # what UserTranscriptEmitter does per interim/final

    def user_quiet(self):
        self.activity.user_ts -= 60.0  # age the stamp past the hold window

    def finals(self):
        return [t for t, f in self.sent if f]

    def partials(self):
        return [t for t, f in self.sent if not f]


async def test_seamless_multi_utterance_segment():
    # Filler then reply playing as ONE audio segment (no BotStopped between):
    # each utterance gets its own final, in playout order — never a concatenated
    # bubble ("Opening that page. He won…") next to a reply-only final.
    h = Harness()
    await h.words("Opening that page.", "ctx-filler")
    await h.words("He won six titles.", "ctx-reply")
    await h.feed(BotStoppedSpeakingFrame())
    assert h.finals() == ["Opening that page.", "He won six titles."], h.sent
    assert not any("page. He" in p for p in h.partials()), h.partials()
    print("  PASS seamless filler→reply → two ordered finals, no concatenation")


async def test_barge_in_no_final_no_stragglers():
    # Barge mid-utterance: client commits the bubble — no final from us, and
    # straggler word frames already released by the transport clock are dropped.
    h = Harness()
    await h.words("Sure thing—just send", "ctx-a")
    await h.barge()
    await h.words("me the", "ctx-a")     # stragglers of the dead context
    await h.feed(BotStoppedSpeakingFrame())
    assert h.finals() == [], h.sent
    assert h.partials()[-1] == "Sure thing—just send", h.partials()
    h.user_quiet()
    await h.words("What specifically?", "ctx-b")
    await h.feed(BotStoppedSpeakingFrame())
    assert h.finals() == ["What specifically?"], h.sent
    print("  PASS barge → no final, stragglers dropped, next utterance clean")


async def test_user_hold_no_reopened_bubble():
    # The "seen twice" bug: the user starts talking (their interim commits the
    # active bubble client-side) 1-3 words BEFORE the barge fires. Words played
    # in that window must NOT emit partials (they'd reopen a second bubble that
    # a following tool card then renders into).
    h = Harness()
    await h.words("Top stories: NBC News", "ctx-news")
    h.user_talks()                        # first interim → client commits bubble
    await h.words("highlights breaking", "ctx-news")  # overlap window: held
    await h.barge()                       # turn machinery catches up
    await h.feed(BotStoppedSpeakingFrame())
    assert h.finals() == [], h.sent
    assert h.partials()[-1] == "Top stories: NBC News", h.partials()
    print("  PASS user-hold → no partials after the user's interim, no reopen")


async def test_user_hold_survivor_resumes_full_text():
    # Same overlap but NO barge (1-word garble, bot keeps talking): partials
    # resume once the user is quiet and the next one carries the FULL text.
    h = Harness()
    await h.words("It was the best", "ctx-d")
    h.user_talks()
    await h.words("of times, it was", "ctx-d")  # held
    h.user_quiet()
    await h.words("the worst of times.", "ctx-d")
    await h.feed(BotStoppedSpeakingFrame())
    assert h.finals() == ["It was the best of times, it was the worst of times."], h.sent
    assert "It was the best of times, it was" in h.partials()[-1], h.partials()
    print("  PASS user-hold survivor → resumed partial carries full text, one final")


async def test_reply_end_finalizes_at_last_word():
    # The playout-paced LLMFullResponseEndFrame (pts = last word) finalizes
    # immediately — the final must beat the user's next interim, not wait ~0.4s
    # for BotStopped silence detection (the duplicated-greeting race).
    h = Harness()
    await h.words("Hey there.", "ctx-greet", pts=1_000)
    await h.feed(END(pts=1_000))
    assert h.finals() == ["Hey there."], h.sent
    h.user_talks()                        # user replies AFTER the final went out
    await h.feed(BotStoppedSpeakingFrame())  # later silence detection: no double
    assert h.finals() == ["Hey there."], h.sent
    print("  PASS reply-end pts → final at last word, BotStopped no-ops after")


async def test_stale_end_ignored():
    # A wordless (pure tool-call) turn's End carries a stale pts predating the
    # currently-playing utterance's words: it must not cut that utterance short.
    h = Harness()
    await h.words("Looking up Austin", "ctx-filler", pts=5_000)
    await h.feed(END(pts=1_000))          # stale: belongs to an earlier turn
    assert h.finals() == [], h.sent
    await h.words("weather now.", "ctx-filler", pts=6_000)
    await h.feed(BotStoppedSpeakingFrame())
    assert h.finals() == ["Looking up Austin weather now."], h.sent
    print("  PASS stale End (pts < first word) ignored")


async def test_final_skipped_when_client_committed():
    # Utterance fully shown, user interim commits the bubble, THEN the boundary
    # fires: an identical final would render after the user's message as a
    # duplicate bubble — skip it.
    h = Harness()
    await h.words("Hey there.", "ctx-greet", pts=1_000)
    h.user_talks()                        # interim beat the boundary this time
    await h.feed(END(pts=1_000))
    assert h.finals() == [], h.sent
    assert h.partials()[-1] == "Hey there.", h.partials()
    print("  PASS final skipped when the client already committed identical text")


async def test_bare_tokens_rejoined_with_spaces():
    # pipecat 1.5.0 delivers bare word tokens; the caption must rejoin them with
    # single spaces (regression: "Hello!Howcanihelpyoutoday?").
    h = Harness()
    for tok in ["Hello!", "How", "can", "I", "help", "you", "today?"]:
        await h.feed(W(tok, "ctx-g"))
    await h.feed(BotStoppedSpeakingFrame())
    assert h.finals() == ["Hello! How can I help you today?"], h.sent
    assert h.partials()[-1] == "Hello! How can I help you today?", h.partials()
    # Standalone trailing punctuation / a split contraction attaches left (no space).
    h2 = Harness()
    for tok in ["It", "'s", "here", "."]:
        await h2.feed(W(tok, "ctx-p"))
    await h2.feed(BotStoppedSpeakingFrame())
    assert h2.finals() == ["It's here."], h2.sent
    print("  PASS bare tokens rejoined with spaces; punctuation attaches left")


async def test_clean_single_utterance():
    h = Harness()
    await h.words("It is forty two degrees.", "ctx-1")
    await h.feed(BotStoppedSpeakingFrame())
    assert h.finals() == ["It is forty two degrees."], h.sent
    assert h.partials()[0] == "It", h.partials()
    print("  PASS clean reply → partials grow, one final")


async def test_no_empty_or_double_finals():
    h = Harness()
    await h.words("Hello.", "ctx-1")
    await h.feed(BotStoppedSpeakingFrame())
    await h.feed(BotStoppedSpeakingFrame())  # extra BotStopped (drain) no-ops
    await h.words("Again.", "ctx-2")
    await h.words("More.", "ctx-3")          # switch finalizes ctx-2 exactly once
    await h.feed(BotStoppedSpeakingFrame())
    assert h.finals() == ["Hello.", "Again.", "More."], h.sent
    print("  PASS boundary spam → exactly one final per utterance, none empty")


def test_captions():
    async def main():
        await test_seamless_multi_utterance_segment()
        await test_barge_in_no_final_no_stragglers()
        await test_user_hold_no_reopened_bubble()
        await test_user_hold_survivor_resumes_full_text()
        await test_reply_end_finalizes_at_last_word()
        await test_stale_end_ignored()
        await test_final_skipped_when_client_committed()
        await test_bare_tokens_rejoined_with_spaces()
        await test_clean_single_utterance()
        await test_no_empty_or_double_finals()
    asyncio.run(main())


if __name__ == "__main__":
    test_captions()
    print("ALL PASS")
