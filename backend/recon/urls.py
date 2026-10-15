from django.urls import path

from . import views

urlpatterns = [
    path("orgs", views.orgs),
    path("disagreements", views.disagreements),
]
