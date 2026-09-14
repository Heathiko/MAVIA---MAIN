from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from lessons.models import OutlineNode

from .services import build_topic_path, get_published_path

# The review preview has no permission classes, deliberately: it is a
# teacher-authoring endpoint beside `lessons` and `question_generation`, which
# are also open, and gating only this app made the review screen unreachable.
# The published path is different -- students read it -- so it requires a
# signed-in user.

ANSWER_VIEWERS = {"TEACHER", "ADMIN"}


@api_view(["GET"])
def topic_learning_path(request, node_id):
    """The topic's learning path as the review screen previews it.

    ``paths`` stays a list so the client renders one path the way it rendered
    several, and a topic with no content is an empty list rather than a special
    case.
    """
    try:
        topic = OutlineNode.objects.get(pk=node_id)
    except OutlineNode.DoesNotExist:
        return Response({"detail": "Topic not found."}, status=status.HTTP_404_NOT_FOUND)

    path = build_topic_path(topic.id)
    return Response({
        "topic": {"id": topic.id, "title": topic.title},
        "paths": [path] if path["steps"] else [],
        "problems": [],
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def published_learning_path(request, node_id):
    """The path saved at the topic's last successful publish.

    Correct answers are included for teachers and admins only, so a student's
    device never receives the answer key. See ``learning_path/HANDOFF.md``.
    """
    try:
        topic = OutlineNode.objects.get(pk=node_id)
    except OutlineNode.DoesNotExist:
        return Response({"detail": "Topic not found."}, status=status.HTTP_404_NOT_FOUND)

    include_answers = getattr(request.user, "role", None) in ANSWER_VIEWERS
    path = get_published_path(topic, include_answers=include_answers)
    if path is None:
        return Response(
            {"detail": "This topic has no published learning path yet. Publish it first."},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response(path)
