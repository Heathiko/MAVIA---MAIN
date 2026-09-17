from django.conf import settings
from django.db import models
from django.utils import timezone

from lessons.models import CourseGroup, LearningObject, OutlineNode, Question
from question_generation.models import GeneratedQuestion


class Enrollment(models.Model):
    """A student's membership in a course. Teachers manage the roster from the
    web app; the per-student progress report is scoped to these rows."""

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="enrollments",
        limit_choices_to={"role": "STUDENT"},
    )
    course = models.ForeignKey(
        CourseGroup,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        unique_together = ("student", "course")
        ordering = ["-created_at", "id"]

    def __str__(self):
        return f"{self.student} in {self.course}"


class LearningState(models.Model):
    """One row per (student, course): where the learner currently is and how
    well they're doing. The web review player never writes this — only the
    student-facing adaptive endpoints do."""

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="learning_states",
    )
    course = models.ForeignKey(
        CourseGroup,
        on_delete=models.CASCADE,
        related_name="learning_states",
    )
    # Top-level outline node (module) and the child topic being worked on.
    current_module = models.ForeignKey(
        OutlineNode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    current_lesson_node = models.ForeignKey(
        OutlineNode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    current_question = models.ForeignKey(
        Question,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    # --- Learning-path mode -------------------------------------------------
    # Set together, in place of current_question, once current_lesson_node has
    # a published learning path (learning_path.services.get_published_path).
    # A topic without one still runs the plain PDF-order walk above; the two
    # never populate for the same state at once. See adaptive/PATH_MODE.md.
    current_step_position = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Position (1-based) of the learning-path step the learner is on.",
    )
    current_generated_question = models.ForeignKey(
        GeneratedQuestion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    # Stack of steps to resume, nearest (next to pop) last: pushed on every
    # detour into a prerequisite, popped once that prerequisite step is fully
    # answered. Bounded by adaptive.services.MAX_REMEDIATION_DEPTH — a learner
    # is never routed more than that many prerequisites deep before the engine
    # falls back to an alternate chunk or gives up rerouting. Each entry is
    # {"position": <step position>, "chunk_id": <LearningObject id or None>} --
    # "chunk_id" records which learning object (representative vs. an
    # alternate PDF's own telling of the concept) the resumed step was showing
    # at the moment it detoured, so resuming knows whether an unused alternate
    # is still available or whether it's already down to its last escalated
    # variant. See adaptive/PATH_MODE.md.
    remediation_stack = models.JSONField(default=list, blank=True)
    # Step positions that have already spent their one prerequisite detour in
    # the current topic. remediation_stack alone cannot carry this: it is
    # *popped* when a detour is resumed, so without a separate record a step
    # that fails again right after being resumed is free to detour into the
    # same prerequisite a second time, and a learner who keeps missing walks
    # that loop forever (position N -> prerequisite -> back to N -> ...).
    # MAX_REMEDIATION_DEPTH bounds how deep the stack goes at once; this
    # bounds how many times any one step may reach for the remedy at all.
    # Reset when the learner moves to another topic, since positions are
    # numbered per topic. See adaptive/PATH_MODE.md.
    remediated_positions = models.JSONField(default=list, blank=True)
    # Which learning object supplies the current step's content/questions.
    # None means the step's representative (the default, and the only option
    # before chunk-switching existed). Set to an alternate's id when the
    # representative's own ladder (normal/simplified/elaborated) has been
    # exhausted and another uploaded PDF's version of the same concept exists.
    current_chunk = models.ForeignKey(
        LearningObject,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    current_variant = models.CharField(
        max_length=10,
        choices=[("normal", "Normal"), ("simplified", "Simplified"), ("elaborated", "Elaborated")],
        default="normal",
    )
    # -------------------------------------------------------------------------
    # Attempts spent on current_question, so the engine can move a learner on
    # after repeated wrong answers rather than stranding them.
    current_question_attempts = models.PositiveIntegerField(default=0)
    # When the current run at the current topic began. StudentResponse rows
    # are kept forever (the teacher report reads them), but only those from
    # the current attempt count as "already cleared" -- otherwise a student
    # who finished a topic and opened it again would be advanced straight
    # back past every step they had ever answered, arriving at the end
    # without being taught anything. See services._step_answered_ids.
    attempt_started_at = models.DateTimeField(default=timezone.now)
    mastery = models.FloatField(default=0.30)
    attempts = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("student", "course")
        ordering = ["-updated_at", "id"]

    def __str__(self):
        return f"{self.student} · {self.course} · mastery {self.mastery:.2f}"


class StudentResponse(models.Model):
    learning_state = models.ForeignKey(
        LearningState,
        on_delete=models.CASCADE,
        related_name="responses",
    )
    # Exactly one of these is set: `question` for the plain PDF-order walk,
    # `generated_question` for a learning-path step (see LearningState above).
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="+", null=True, blank=True,
    )
    generated_question = models.ForeignKey(
        GeneratedQuestion, on_delete=models.CASCADE, related_name="+", null=True, blank=True,
    )
    selected_answer = models.CharField(max_length=255)
    is_correct = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(question__isnull=False, generated_question__isnull=True)
                    | models.Q(question__isnull=True, generated_question__isnull=False)
                ),
                name="student_response_exactly_one_question_type",
            ),
        ]

    def __str__(self):
        qid = self.question_id or self.generated_question_id
        return f"Q{qid} {'✓' if self.is_correct else '✗'}"
