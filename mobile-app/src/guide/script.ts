// The spoken guide: what a learner is told the first time they open the app,
// and every time they press the minus key afterwards.
//
// It is a list of parts rather than one long string for two reasons. A learner
// who already knows the first half should be able to interrupt without losing
// the rest, so each part is spoken separately and the player can stop between
// them (see useGuide). And the words a part describes -- which key, which
// gesture -- are built from the same constants the app actually binds, so the
// guide cannot drift out of step with the keypad map the way written docs do.
//
// Keep each part to one idea and a few sentences. This is heard, not read:
// there is no skimming back, so a part that runs long is a part that gets lost.

export type GuidePart = {
  // Named so a screen can play one part on its own -- e.g. the answering part
  // when a learner reaches their first question.
  id: string;
  text: string;
};

// Spoken as digits, not words, because that is how they are printed on the
// keypad the learner is feeling for.
export const ANSWER_KEYS = { a: "7", b: "8", c: "4", d: "5" } as const;
export const COMMAND_KEYS = {
  repeat: "multiply",
  back: "divide",
  guide: "minus",
  next: "plus",
} as const;

export const GUIDE_PARTS: GuidePart[] = [
  {
    id: "welcome",
    text:
      "Welcome to MAVIA. I will explain how to move around, and how to answer. " +
      "You can stop me at any time by pressing any key. " +
      `To hear this guide again later, press the ${COMMAND_KEYS.guide} key on your keypad.`,
  },
  {
    id: "navigate",
    text:
      "To find a lesson, swipe right anywhere on the screen. " +
      "I will ask which course you want, and read out your courses four at a time.",
  },
  {
    id: "choosing",
    text:
      "Each one gets a letter: A, B, C and D. " +
      "Say the letter you want, or press its key: " +
      `${ANSWER_KEYS.a} for A, ${ANSWER_KEYS.b} for B, ${ANSWER_KEYS.c} for C, and ${ANSWER_KEYS.d} for D. ` +
      "If the one you want is not among those four, say next four, " +
      `or press the ${COMMAND_KEYS.next} key, and I will read the next four. ` +
      "Once you pick a course, I will ask which lesson you want the same way.",
  },
  {
    id: "listening",
    text:
      "When your lesson starts, it is read to you. " +
      "If it goes too quickly, say, can you repeat the lesson, and I will read it again. " +
      "While a question is open, say, can you repeat that question, to hear the question again. " +
      `You can also press the ${COMMAND_KEYS.repeat} key at any time to hear whatever is playing from the start.`,
  },
  {
    id: "answering",
    text:
      "To answer a question, you have two ways. " +
      `Press the key for your letter: ${ANSWER_KEYS.a} for A, ${ANSWER_KEYS.b} for B, ` +
      `${ANSWER_KEYS.c} for C, and ${ANSWER_KEYS.d} for D. ` +
      "Or tap anywhere on the screen: once for A, twice for B, three times for C, four times for D. " +
      "I will say each letter as you tap, and your answer is taken a moment after you stop.",
  },
  {
    id: "leaving",
    text:
      `To leave a lesson and go back, press the ${COMMAND_KEYS.back} key, or say, go back. ` +
      "That is everything. Swipe right to begin.",
  },
];

/** The whole guide as one string, for a screen that would rather read it. */
export const GUIDE_TEXT = GUIDE_PARTS.map((part) => part.text).join(" ");

export function guidePart(id: string): GuidePart | undefined {
  return GUIDE_PARTS.find((part) => part.id === id);
}
