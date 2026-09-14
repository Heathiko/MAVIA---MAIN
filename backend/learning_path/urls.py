from django.urls import path

from . import views

urlpatterns = [
    path("topics/<int:node_id>/", views.topic_learning_path, name="topic-learning-path"),
    path("topics/<int:node_id>/published/", views.published_learning_path, name="published-learning-path"),
]
