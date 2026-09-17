import React, { useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import { useNarration } from "@/hooks/useNarration";
import { useBrailleKeypad } from "@/input/useBrailleKeypad";
import { colors, radii, spacing } from "@/theme";

// Mirrors lessons.Question from the API.
export type Question = {
  id: number;
  order: number;
  prompt: string;
  question_type: "open_ended" | "true_false" | "multiple_choice" | string;
  choices: string[];
  correct_answer: string;
};

export type SubmitResult = { is_correct: boolean; mastery: number; completed: boolean };

type Option = { key: string; label: string };
const LETTERS = ["a", "b", "c", "d", "e", "f"];

// Every option is addressed by its letter, True/False included: the braille
// numpad has one physical key per letter, so the same finger position has to
// mean the same thing whatever kind of question is on screen. A = True,
// B = False. The backend accepts those letters for TF questions --
// see adaptive/services.py::path_answer_is_correct.
function optionsFor(question: Question): Option[] {
  if (question.question_type === "true_false") {
    return [
      { key: LETTERS[0], label: "True" },
      { key: LETTERS[1], label: "False" },
    ];
  }
  return (question.choices ?? []).map((label, index) => ({ key: LETTERS[index], label }));
}

type Props = {
  question: Question;
  index: number;
  total: number;
  onSubmit: (answer: string) => Promise<SubmitResult>;
  onNext: () => void;
  // Bumped by the screen when the learner asks to hear it again (the
  // "repeat the question" voice command). Re-reads the question in place -- unlike remounting the
  // card, an answer already given is kept.
  repeatSignal?: number;
};

export default function QuestionCard({ question, index, total, onSubmit, onNext, repeatSignal = 0 }: Props) {
  const options = useMemo(() => optionsFor(question), [question]);
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<SubmitResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const narration = useNarration();
  const advancedRef = useRef(false);
  // The verdict has to wait for the read-back of the chosen answer to finish.
  // speak() stops whatever is talking, so a fast reply from the server would
  // otherwise cut "Answered A. Solid." off mid-word. These two track which of
  // the pair happened first; whichever finishes last plays the verdict.
  const readBackDoneRef = useRef(false);
  // `advance` is false when the submit failed: the student stays on this
  // question to try again, so the verdict must not move them on.
  const verdictRef = useRef<{ text: string; advance: boolean } | null>(null);

  const answered = result !== null;
  const openEnded = options.length === 0;

  function advanceOnce() {
    if (advancedRef.current) return;
    advancedRef.current = true;
    onNext();
  }

  function speakVerdictWhenReady() {
    if (!readBackDoneRef.current || verdictRef.current === null) return;
    const { text, advance } = verdictRef.current;
    verdictRef.current = null;
    narration.speak(text, advance ? { onDone: advanceOnce } : undefined);
  }

  // "A. Solid. B. Liquid." -- the letter is the key they press, so it is
  // read with every option, not just implied by the order.
  function readQuestionAloud() {
    const choiceText = options.map((o) => `${o.key.toUpperCase()}. ${o.label}.`).join(" ");
    narration.speak(choiceText ? `${question.prompt} ${choiceText}` : question.prompt, {
      onDone: openEnded ? advanceOnce : undefined,
    });
  }

  // Read the new question (and its choices) aloud as soon as it appears.
  // Open-ended questions have nothing to grade -- move on as soon as the
  // prompt's been read instead of waiting on a tap that never comes from
  // choose() below.
  useEffect(() => {
    advancedRef.current = false;
    readQuestionAloud();
    return () => narration.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question.id]);

  // Asked to hear it again. Only while the question is still open: once an
  // answer is in, the read-back and verdict are already speaking and the card
  // is about to move on, so re-reading would talk over them.
  const lastRepeat = useRef(repeatSignal);
  useEffect(() => {
    if (repeatSignal === lastRepeat.current) return;
    lastRepeat.current = repeatSignal;
    if (answered || submitting) return;
    readQuestionAloud();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repeatSignal]);

  // Set synchronously, unlike `submitting`: a keypad can deliver two presses
  // before React re-renders, and the state flags would still read false for
  // the second one -- submitting the same question twice.
  const choosingRef = useRef(false);

  async function choose(key: string) {
    if (choosingRef.current || submitting || answered) return;
    choosingRef.current = true;
    setSelected(key);
    setSubmitting(true);
    setError(null);
    readBackDoneRef.current = false;
    verdictRef.current = null;

    // Read the choice back immediately, before the network round trip: the
    // student needs to know which key registered without waiting on a server.
    const option = options.find((o) => o.key === key);
    narration.speak(
      option ? `Answered ${option.key.toUpperCase()}. ${option.label}.` : `Answered ${key}.`,
      {
        onDone: () => {
          readBackDoneRef.current = true;
          speakVerdictWhenReady();
        },
      }
    );

    try {
      const res = await onSubmit(key);
      setResult(res);
      verdictRef.current = { text: res.is_correct ? "Correct." : "Not quite.", advance: true };
      speakVerdictWhenReady();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Couldn't submit your answer.";
      // Not answered after all -- let the learner try again.
      choosingRef.current = false;
      setSelected(null);
      setError(message);
      // Say it too -- a silent failure leaves a student who cannot read the
      // red text waiting on a question that will never move.
      verdictRef.current = { text: "That answer didn't send. Please try again.", advance: false };
      speakVerdictWhenReady();
    } finally {
      setSubmitting(false);
    }
  }

  // Braille keypad over Bluetooth: 7, 8, 9 and + answer A, B, C and D (the
  // mapping is src/input/brailleKeypad.ts). Answering goes through choose(),
  // exactly like a tap, so the read-back and verdict are identical.
  const numLockWarnedRef = useRef(false);
  useBrailleKeypad(
    (action) => {
      if (action.kind === "numLockOff") {
        // Once per question: a held or repeated arrow should not become a loop.
        if (numLockWarnedRef.current) return;
        numLockWarnedRef.current = true;
        narration.speak("Number lock is off. Press Num Lock, then answer with 7, 8, 9, or plus.");
        return;
      }
      if (choosingRef.current || answered || submitting) return;
      const option = options.find((o) => o.key === action.letter);
      if (!option) {
        // e.g. + (D) on a True/False question: say so rather than do nothing.
        narration.speak(`There is no option ${action.letter.toUpperCase()}.`);
        return;
      }
      choose(option.key);
    },
    { enabled: !openEnded }
  );

  return (
    <View style={styles.card}>
      <Text style={styles.counter}>
        Question {index + 1} of {total}
      </Text>
      <Text style={styles.prompt} accessibilityRole="header">
        {question.prompt}
      </Text>

      {openEnded ? (
        <Text style={styles.note}>
          This is an open-ended question — read it aloud with your teacher. It isn’t
          auto-graded here.
        </Text>
      ) : (
        <View style={styles.options}>
          {options.map((option) => {
            const isCorrect =
              answered && option.key.toLowerCase() === question.correct_answer.trim().toLowerCase();
            const isWrongPick = answered && option.key === selected && !isCorrect;
            return (
              <Pressable
                key={option.key}
                disabled={answered || submitting}
                onPress={() => choose(option.key)}
                accessibilityRole="button"
                style={[
                  styles.option,
                  option.key === selected && !answered && styles.optionSelected,
                  isCorrect && styles.optionCorrect,
                  isWrongPick && styles.optionWrong,
                ]}
              >
                <View style={styles.optionKey}>
                  <Text style={styles.optionKeyText}>{option.key.toUpperCase()}</Text>
                </View>
                <Text style={styles.optionLabel}>{option.label}</Text>
              </Pressable>
            );
          })}
        </View>
      )}

      {submitting && <ActivityIndicator color={colors.brand600} />}
      {error && <Text style={styles.error}>{error}</Text>}

      {answered && (
        <View style={styles.feedback}>
          <Text style={result?.is_correct ? styles.correct : styles.wrong}>
            {result?.is_correct ? "Correct" : "Not quite"}
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    gap: spacing.sm,
  },
  counter: {
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 1,
    textTransform: "uppercase",
    color: colors.faint,
  },
  prompt: { fontSize: 16, fontWeight: "700", color: colors.ink },
  note: { fontSize: 13, color: colors.muted, fontStyle: "italic" },
  options: { gap: spacing.sm },
  option: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.panel,
    borderRadius: radii.sm,
    borderWidth: 2,
    borderColor: colors.border,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  optionSelected: { borderColor: colors.brand400 },
  optionCorrect: { borderColor: colors.success, backgroundColor: colors.successBg },
  optionWrong: { borderColor: colors.danger, backgroundColor: colors.dangerBg },
  optionKey: {
    width: 24,
    height: 24,
    borderRadius: radii.pill,
    backgroundColor: colors.brand600,
    alignItems: "center",
    justifyContent: "center",
  },
  optionKeyText: { fontSize: 11, fontWeight: "800", color: colors.white },
  optionLabel: { flex: 1, fontSize: 14, fontWeight: "600", color: colors.ink },
  feedback: { gap: spacing.xs },
  correct: { fontSize: 14, fontWeight: "800", color: colors.success },
  wrong: { fontSize: 14, fontWeight: "800", color: colors.danger },
  error: { fontSize: 12, fontWeight: "600", color: colors.danger },
});
